import importlib.util
import time
from concurrent.futures import ThreadPoolExecutor

import pytest


def test_backend_implementation_exists():
    assert importlib.util.find_spec("bleetd.app"), "API implementation is missing"


def test_tokens_are_hashed_and_revocable(tmp_path):
    from bleetd.state import State
    state = State(tmp_path / "state.db")
    token = state.issue_token("phone", ["read"])
    assert state.authenticate(token)["scopes"] == ["read"]
    assert state.authenticate("wrong") is None
    assert token.encode() not in (tmp_path / "state.db").read_bytes()
    state.revoke_token(token)
    assert state.authenticate(token) is None


def test_enrollment_single_use_atomic_and_expired(tmp_path):
    from bleetd.state import State
    state = State(tmp_path / "state.db")
    code = state.issue_enrollment(["read"], ttl=60)
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda _: state.redeem(code, "phone"), range(4)))
    assert sum(result is not None for result in results) == 1
    expired = state.issue_enrollment(["read"], ttl=1, now=time.time() - 10)
    assert state.redeem(expired, "phone") is None
    with pytest.raises(ValueError):
        state.issue_enrollment(["read"], ttl=86401)


def test_http_auth_enrollment_and_scope(tmp_path):
    from fastapi.testclient import TestClient
    from bleetd.app import create_app
    from bleetd.config import Config
    app = create_app(Config(state_dir=tmp_path, hosts=[]))
    state = app.state.state
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok", "version": "0.1.0"}
        assert client.get("/v1/snapshot").status_code == 401
        only_pair = state.issue_token("phone", ["t3:pair"])
        assert client.get("/v1/snapshot", headers={"Authorization": "Bearer " + only_pair}).status_code == 403
        code = state.issue_enrollment(["read"], 60)
        response = client.post("/v1/enroll", json={"code": code, "device_name": "phone"})
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        token = response.json()["token"]
        assert client.post("/v1/enroll", json={"code": code, "device_name": "phone"}).status_code == 401
        headers = {"Authorization": "Bearer " + token}
        assert client.get("/v1/snapshot", headers=headers).json()["hosts"] == []
        assert client.post("/v1/t3/pair", headers=headers, json={"host_id": "ts:brak", "output": "both"}).status_code == 403
        assert client.post("/mcp", json={}).status_code == 401


@pytest.mark.parametrize("target", ["-oProxyCommand=touch /tmp/pwn", "host; echo bad", "host\nother", "x$(id)", "user@host --bad"])
def test_ssh_target_rejects_injection(target):
    from bleetd.config import Host
    with pytest.raises(ValueError):
        Host(id="ts:x", name="x", address="x", ssh_target=target)


def test_repository_traversal_symlink_secret_and_bounded_read(tmp_path):
    from bleetd.repositories import Repositories
    root = tmp_path / "repo"
    root.mkdir()
    (root / "normal.py").write_text("one\ntwo\nthree\n")
    (tmp_path / "outside").write_text("outside secret")
    (root / "escape").symlink_to(tmp_path / "outside")
    (root / ".env").write_text("SECRET=hidden")
    (root / "credentials.json").write_text("hidden")
    repos = Repositories({"example": str(root)})
    assert repos.read_file("example", "normal.py", 2, 1)["lines"] == [{"line": 2, "text": "two"}]
    for path in ["../outside", "escape", ".env", "credentials.json", "/etc/passwd", ".git/config"]:
        with pytest.raises(ValueError):
            repos.read_file("example", path)
    assert [x["name"] for x in repos.list_directory("example")["entries"]] == ["normal.py"]
    assert repos.search_code("example", "hidden")["matches"] == []


def test_t3_errors_do_not_leak_secrets(tmp_path):
    from bleetd.config import Config, Host
    from bleetd.services import Gateway
    from bleetd.state import State
    class FailingSSH:
        async def run(self, host, command, **kwargs):
            raise RuntimeError("https://secret/pair#token=LEAK token=ALSO_LEAK bearer abc")
    gateway = Gateway(Config(state_dir=tmp_path, hosts=[Host(id="ts:x", name="x", address="x", ssh_target="x")]), State(tmp_path / "s.db"), ssh=FailingSSH())
    import asyncio
    with pytest.raises(ValueError) as error:
        asyncio.run(gateway.pair("ts:x", "both"))
    assert "LEAK" not in str(error.value)
    with pytest.raises(ValueError):
        asyncio.run(gateway.pair("ts:x;id", "link"))
    with pytest.raises(ValueError):
        asyncio.run(gateway.pair("ts:x", "shell"))


def test_directory_swap_cannot_escape_read_root(tmp_path, monkeypatch):
    from bleetd.repositories import Repositories
    root, outside = tmp_path / "repo", tmp_path / "outside"
    directory = root / "safe"
    directory.mkdir(parents=True)
    outside.mkdir()
    (directory / "data.py").write_text("permitted")
    (outside / "data.py").write_text("outside secret")
    repositories = Repositories({"repo": str(root)})
    original = repositories.resolve
    def swapped(repository, path="."):
        resolved = original(repository, path)
        if path == "safe/data.py":
            directory.rename(root / "backup")
            directory.symlink_to(outside, target_is_directory=True)
        return resolved
    monkeypatch.setattr(repositories, "resolve", swapped)
    with pytest.raises(ValueError):
        repositories.read_file("repo", "safe/data.py")


def test_ssh_transports_never_reuse_persistent_control_sockets(tmp_path):
    from bleetd.config import Config
    from bleetd.ssh import SSH
    import asyncio
    first, second = SSH(Config(state_dir=tmp_path)), SSH(Config(state_dir=tmp_path))
    try:
        assert first.control_dir != second.control_dir
        assert tmp_path not in first.control_dir.parents
        assert first.control_dir.stat().st_mode & 0o777 == 0o700
    finally:
        if hasattr(first, "close"):
            asyncio.run(first.close())
            asyncio.run(second.close())
