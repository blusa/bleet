import json
from pathlib import Path
import subprocess
import sys
import tarfile


def test_source_archive_excludes_local_deployment_identities_even_if_tracked(tmp_path):
    repo = tmp_path / "fixture"
    (repo / "deploy").mkdir(parents=True)
    stage = repo / "deploy/stage-source.py"
    stage.write_bytes((Path(__file__).resolve().parents[2] / "deploy/stage-source.py").read_bytes())
    public = {"README.md": "public readme\n", "backend/app.py": "print('public')\n"}
    private = ["backend/ssh/id_ed25519", "backend/id_rsa", "deploy/state/identity", "backend/config.json", "deploy/secrets/access", "backend/.ssh/id_ecdsa"]
    for path, value in {**public, **{name: "SYNTHETIC_PRIVATE_IDENTITY" for name in private}}.items():
        target = repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(value)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=Tests", "-c", "user.email=tests@example.invalid", "commit", "-qm", "fixture"], check=True)
    (repo / "backend/untracked-private-file").write_text("UNTRACKED_SYNTHETIC_IDENTITY")
    (repo / "README.md").write_text("public working-tree edit\n")
    archive = tmp_path / "source.tar.gz"
    subprocess.run([sys.executable, str(stage), str(archive)], check=True, capture_output=True)
    with tarfile.open(archive) as source:
        names = set(source.getnames())
        assert names == {"README.md", "backend/app.py", "deploy/stage-source.py", "SOURCE-MANIFEST.json"}
        assert source.extractfile("README.md").read() == b"public working-tree edit\n"
        manifest = json.load(source.extractfile("SOURCE-MANIFEST.json"))
        assert set(manifest["files"]) == names - {"SOURCE-MANIFEST.json"}
