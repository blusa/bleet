"""Exercise public API, actual SDK transport, real Git reads and a local PTY."""
import base64
import json
import os
import subprocess
import sys
import time

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from bleetd.app import create_app
from bleetd.config import Config, Host


def headers(token):
    return {"Authorization": "Bearer " + token, "Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


def rpc(client, token, method, params=None, request_id=1):
    return client.post("/mcp", headers=headers(token), json={"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}})


def test_mcp_transport_real_reads_scopes_and_tool_hints(tmp_path):
    code = tmp_path / "code"
    code.mkdir()
    (code / "hello.py").write_text("hello from real repository\n")
    app = create_app(Config(state_dir=tmp_path / "state", repositories={"code": str(code)}))
    read_token = app.state.state.issue_token("read", ["read"])
    pair_token = app.state.state.issue_token("pair", ["t3:pair"])
    with TestClient(app) as client:
        initialized = rpc(client, read_token, "initialize", {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "tests", "version": "1"}})
        assert initialized.status_code == 200
        assert initialized.json()["result"]["serverInfo"]["name"] == "bleetd"
        tools = rpc(client, read_token, "tools/list").json()["result"]["tools"]
        pairing = next(tool for tool in tools if tool["name"] == "create_t3_pairing")
        assert pairing["annotations"]["readOnlyHint"] is False
        assert pairing["annotations"]["idempotentHint"] is False
        response = rpc(client, read_token, "tools/call", {"name": "read_file", "arguments": {"repository": "code", "path": "hello.py"}})
        assert response.status_code == 200
        result = response.json()["result"]
        assert not result.get("isError")
        payload = json.loads(result["content"][0]["text"])
        assert payload["lines"] == [{"line": 1, "text": "hello from real repository"}]
        denied = rpc(client, pair_token, "tools/call", {"name": "read_file", "arguments": {"repository": "code", "path": "hello.py"}})
        assert denied.json()["result"]["isError"] is True
        denied_pair = rpc(client, read_token, "tools/call", {"name": "create_t3_pairing", "arguments": {"host_id": "anything"}})
        assert denied_pair.json()["result"]["isError"] is True
        assert "hello from" not in denied.text
        assert response.headers["cache-control"] == "no-store"


def test_t3_api_link_png_and_sdk_png_are_same_credential(tmp_path):
    class SSH:
        async def run(self, host, command, **kwargs):
            return "Pairing URL: http://127.0.0.1:3773/pair#token=test-fixture-only\n"
    config = Config(state_dir=tmp_path, hosts=[Host(id="ts:host", name="host", address="host.example", ssh_target="host", magic_dns="host.example")])
    app = create_app(config)
    gateway = app.state.gateway
    gateway.ssh = SSH()
    token = app.state.state.issue_token("pair", ["t3:pair"])
    with TestClient(app) as client:
        response = client.post("/v1/t3/pair", headers=headers(token), json={"host_id": "ts:host", "output": "both"})
        assert response.status_code == 200
        assert response.json()["pairing_url"] == "https://host.example/pair#token=test-fixture-only"
        assert base64.b64decode(response.json()["qr_png_base64"]).startswith(b"\x89PNG\r\n\x1a\n")
        assert response.headers["cache-control"] == "no-store"
        gateway._pair_last.clear()
        result = rpc(client, token, "tools/call", {"name": "create_t3_pairing", "arguments": {"host_id": "ts:host", "output": "qr"}}).json()["result"]
        assert result.get("isError") is not True
        image = next(block for block in result["content"] if block["type"] == "image")
        assert image["mimeType"] == "image/png"
        assert base64.b64decode(image["data"]).startswith(b"\x89PNG")
        text = json.loads(next(block for block in result["content"] if block["type"] == "text")["text"])
        assert text["pairing_url"] is None
        assert text["host_id"] == "ts:host"


def test_websocket_requires_header_scope_and_allowlist(tmp_path):
    app = create_app(Config(state_dir=tmp_path))
    token = app.state.state.issue_token("reader", ["read"])
    terminal_token = app.state.state.issue_token("terminal", ["terminal:connect"])
    with TestClient(app) as client:
        for url, auth in [("/v1/terminal?host_id=x&token=" + terminal_token, {}), ("/v1/terminal?host_id=x", headers(token)), ("/v1/terminal?host_id=x", headers(terminal_token))]:
            with pytest.raises(WebSocketDisconnect):
                with client.websocket_connect(url, headers=auth):
                    pass


def test_real_pty_input_resize_output_exit_and_disconnect_cleanup(tmp_path):
    # Replace only external SSH with a real local child; exercise actual PTY/ioctl,
    # WebSocket framing, process exit and disconnect cleanup in the production code.
    pidfile = tmp_path / "child.pid"
    script = '''import os, sys, signal, fcntl, termios, struct
open(sys.argv[1], 'w').write(str(os.getpid()))
def resized(*args):
 rows, cols, _, _ = struct.unpack('HHHH', fcntl.ioctl(0, termios.TIOCGWINSZ, bytes(8)))
 print('SIZE:%s:%s' % (cols, rows), flush=True)
signal.signal(signal.SIGWINCH, resized)
print('READY', flush=True)
for line in sys.stdin:
 if line.strip() == 'quit': sys.exit(0)
 print('GOT:' + line.strip(), flush=True)
'''
    child = tmp_path / "child.py"
    child.write_text(script)
    app = create_app(Config(state_dir=tmp_path / "state", hosts=[Host(id="x", name="x", address="x", ssh_target="x")]))
    class LocalSSH:
        async def run(self, *args, **kwargs):
            raise ValueError("no metrics in local PTY test")
        def argv(self, host, tty=False):
            return [sys.executable, "-u", str(child), str(pidfile)]
    app.state.gateway.ssh = LocalSSH()
    token = app.state.state.issue_token("terminal", ["terminal:connect"])
    def receive_until(socket, expected):
        combined = ""
        for _ in range(20):
            message = socket.receive_json()
            combined += message.get("data", "")
            if expected in combined:
                return combined
        pytest.fail("expected terminal output absent: " + expected)
    with TestClient(app) as client:
        with client.websocket_connect("/v1/terminal?host_id=x&mode=shell", headers=headers(token)) as socket:
            receive_until(socket, "READY")
            socket.send_json({"type": "resize", "cols": 88, "rows": 24})
            receive_until(socket, "SIZE:88:24")
            socket.send_json({"type": "input", "data": "hello\n"})
            receive_until(socket, "GOT:hello")
            socket.send_json({"type": "input", "data": "quit\n"})
            for _ in range(10):
                message = socket.receive_json()
                if message["type"] == "exit":
                    assert message["status"] == 0
                    break
            else:
                pytest.fail("missing exit frame")
        with client.websocket_connect("/v1/terminal?host_id=x&mode=shell", headers=headers(token)) as socket:
            receive_until(socket, "READY")
            pid = int(pidfile.read_text())
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
            time.sleep(.02)
        else:
            pytest.fail("PTY child survived WebSocket disconnect")


def test_git_diff_and_search_do_not_return_protected_files(tmp_path):
    from bleetd.repositories import Repositories
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "Tests"], check=True)
    (root / "code.py").write_text("old\n")
    (root / ".env").write_text("DO_NOT_EXPOSE=old\n")
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)
    (root / "code.py").write_text("new\n")
    (root / ".env").write_text("DO_NOT_EXPOSE=secret\n")
    repositories = Repositories({"repo": str(root)})
    diff = repositories.get_diff("repo")
    assert "+new" in diff["diff"]
    assert "DO_NOT_EXPOSE" not in diff["diff"]
    assert repositories.get_repository_status("repo")["entries"] == [{"status": " M", "path": "code.py"}]
    assert repositories.search_code("repo", "DO_NOT_EXPOSE")["matches"] == []
    assert len(diff["revision"]) == 40


@pytest.mark.parametrize("staged", [False, True])
def test_git_diff_treats_permitted_filenames_as_literal_paths(tmp_path, staged):
    from bleetd.repositories import Repositories
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    for name in ["[.]env", ".env"]:
        (tmp_path / name).write_text("old\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=Tests", "-c", "user.email=tests@example.invalid", "commit", "-qm", "fixture"], check=True)
    (tmp_path / "[.]env").write_text("public change\n")
    (tmp_path / ".env").write_text("EXCLUDED_FIXTURE_VALUE\n")
    if staged:
        subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    repositories = Repositories({"repo": str(tmp_path)})
    for path in [".", "[.]env"]:
        diff = repositories.get_diff("repo", path, staged=staged)["diff"]
        assert "+public change" in diff
        assert "EXCLUDED_FIXTURE_VALUE" not in diff
        assert "diff --git a/.env" not in diff


@pytest.mark.parametrize("staged", [False, True])
def test_git_status_and_diff_include_deleted_source_but_exclude_deleted_secrets(tmp_path, staged):
    from bleetd.repositories import Repositories
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "source.py").write_text("public source\n")
    (tmp_path / ".env").write_text("EXCLUDED_DELETED_FIXTURE\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=Tests", "-c", "user.email=tests@example.invalid", "commit", "-qm", "fixture"], check=True)
    (tmp_path / "source.py").unlink()
    (tmp_path / ".env").unlink()
    if staged:
        subprocess.run(["git", "-C", str(tmp_path), "add", "-u"], check=True)
    repositories = Repositories({"repo": str(tmp_path)})
    assert repositories.get_repository_status("repo")["entries"] == [{"status": "D " if staged else " D", "path": "source.py"}]
    for path in [".", "source.py"]:
        diff = repositories.get_diff("repo", path, staged=staged)["diff"]
        assert "-public source" in diff
        assert "EXCLUDED_DELETED_FIXTURE" not in diff


def test_cli_enrollment_output_is_private_silent_and_usable(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"state_dir": str(tmp_path / "state"), "hosts": []}))
    secret_path = tmp_path / "enrollment"
    completed = subprocess.run([sys.executable, "-m", "bleetd.cli", "enroll", "--config", str(config_path), "--ttl", "60", "--device-scopes", "read", "--output", str(secret_path)], text=True, capture_output=True, check=True)
    assert completed.stdout == ""
    assert secret_path.stat().st_mode & 0o777 == 0o600
    code = secret_path.read_text().strip()
    assert len(code) >= 32
    app = create_app(Config.load(config_path))
    with TestClient(app) as client:
        enrolled = client.post("/v1/enroll", json={"code": code, "device_name": "CLI smoke"})
        assert enrolled.status_code == 200
        assert enrolled.json()["scopes"] == ["read"]
    refused = subprocess.run([sys.executable, "-m", "bleetd.cli", "enroll", "--config", str(config_path), "--output", str(secret_path)], text=True, capture_output=True)
    assert refused.returncode != 0
    assert refused.stdout == ""
    assert secret_path.read_text().strip() == code


def test_git_reads_never_run_repository_clean_filters(tmp_path):
    from bleetd.repositories import Repositories
    import shlex
    root = tmp_path / "repo"
    root.mkdir()
    def git(*arguments):
        subprocess.run(["git", "-C", str(root), *arguments], check=True, capture_output=True)
    git("init", "-q")
    git("config", "user.email", "test@example.invalid")
    git("config", "user.name", "Tests")
    (root / "code.py").write_text("original\n")
    (root / ".gitattributes").write_text("code.py filter=sideeffect\n")
    git("add", ".")
    git("commit", "-qm", "fixture")
    marker = tmp_path / "must-not-exist"
    git("config", "filter.sideeffect.clean", "touch " + shlex.quote(str(marker)) + "; cat")
    (root / "code.py").write_text("changed\n")
    repositories = Repositories({"repo": str(root)})
    result = repositories.get_diff("repo")
    assert "+changed" in result["diff"]
    repositories.get_repository_status("repo")
    assert not marker.exists(), "Git read invoked an arbitrary configured clean filter"
