#!/usr/bin/env python3
"""Archive public working-tree source without Git history or machine credentials."""
import argparse
import fnmatch
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile

ROOTS = ("backend", "deploy", "shared", "ios", "macos", "omarchy", "docs", "README.md")
SKIP = {".git", ".claude", ".codex", ".superpowers", ".venv", "venv", "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache", ".build", "DerivedData", "build", "dist", "node_modules", "xcuserdata", ".swiftpm", ".DS_Store"}
PRIVATE = {"ssh", ".ssh", "state", "secrets", "fleet-secrets", ".aws", ".azure", ".gnupg", ".kube", ".t3", ".asc", "config.json", "known_hosts"}
IDENTITIES = ("id_rsa*", "id_ed25519*", "id_ecdsa*", "id_dsa*", "*credentials*", "*service-account*")
EXTENSIONS = (".pyc", ".ipa", ".p12", ".p8", ".mobileprovision", ".sqlite", ".sqlite3", ".db", ".key", ".pem")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parent.parent
    archive = args.archive.resolve()
    selected = []
    # Git's index is the public-file allowlist; local untracked deployment files
    # never enter an archive. Contents still come from the working tree.
    tracked = subprocess.check_output(["git", "-c", "core.fsmonitor=false", "ls-files", "-z", "--", *ROOTS], cwd=repo).decode()
    for name in tracked.split("\0"):
        if not name:
            continue
        relative = Path(name)
        path = repo / relative
        if any(p in SKIP or p.lower() in PRIVATE or any(fnmatch.fnmatch(p.lower(), pattern) for pattern in IDENTITIES) or p.startswith((".env", "build-", "DerivedData")) or p.endswith((".xcarchive", ".dSYM")) for p in relative.parts):
            continue
        if path.is_symlink() or not path.is_file() or path.name.endswith(EXTENSIONS) or path.resolve() != path:
            continue
        if path == archive:
            continue
        selected.append(path)
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    manifest = {"source": "working-tree", "base_revision": revision, "git_metadata": False, "files": {str(p.relative_to(repo)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(selected)}}
    with tarfile.open(archive, "w:gz") as tar:
        for path in sorted(selected):
            tar.add(path, arcname=str(path.relative_to(repo)), recursive=False)
        data = (json.dumps(manifest, indent=2) + "\n").encode()
        import io
        entry = tarfile.TarInfo("SOURCE-MANIFEST.json")
        entry.size = len(data)
        entry.mode = 0o644
        tar.addfile(entry, io.BytesIO(data))
    print(f"{archive}: {len(selected)} public source files; working-tree, Git metadata unavailable")


if __name__ == "__main__":
    main()
