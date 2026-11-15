"""Bounded read-only access to administrator-mounted repository roots."""
import fnmatch
import os
import re
import stat
import subprocess
import time
from pathlib import Path

from .state import utcnow

# Exclude metadata, identity material and common secret/config directories, including
# variants such as .env.production, service-account.json and SSH id_ed25519.pub.
SECRET_PATTERNS = (".git", ".env*", ".ssh", ".aws", ".azure", ".gnupg", ".kube", ".t3", ".codex", ".asc", "secrets", "secret", "secrets.*", "*credentials*", "*token*", "*.pem", "*.key", "*.p12", "*.pfx", "*.keystore", "id_rsa*", "id_ed25519*", "id_ecdsa*", "*service-account*", "*.sqlite*", "*.db", "known_hosts", ".netrc", ".npmrc", ".pypirc", "config.local.*")
SKIP_DIRS = {"node_modules", ".venv", "__pycache__", ".build", "build", "dist"}
MAX_FILE_BYTES = 1_000_000
MAX_OUTPUT = 64_000


def excluded(name):
    return any(fnmatch.fnmatch(name.lower(), pattern) for pattern in SECRET_PATTERNS)


class Repositories:
    def __init__(self, roots):
        self.roots = {key: Path(value).expanduser().resolve(strict=True) for key, value in roots.items()}
        if any(not root.is_dir() for root in self.roots.values()):
            raise ValueError("repository root must be a directory")

    def resolve(self, repository, path=".", *, allow_missing=False):
        root = self.roots.get(repository)
        if root is None:
            raise ValueError("repository is not allowlisted")
        relative = Path(path)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("path is not permitted")
        current = root
        for part in relative.parts:
            if excluded(part):
                raise ValueError("secret or metadata path is excluded")
            current = current / part
            if current.is_symlink():
                raise ValueError("symlink access is excluded")
        try:
            resolved = current.resolve(strict=not allow_missing)
            resolved.relative_to(root)
        except (OSError, ValueError):
            raise ValueError("path is unavailable or outside repository") from None
        return resolved

    def _git(self, root, arguments, limit=MAX_OUTPUT):
        env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_OPTIONAL_LOCKS": "0", "GIT_NO_LAZY_FETCH": "1", "GIT_TERMINAL_PROMPT": "0"})
        # The root is explicitly allowlisted, including a read-only mount owned by
        # another UID. Pin worktree scope, disable executable helpers, then inspect
        # config without executing it to neutralize all named clean/process filters.
        base = ["git", "--no-optional-locks", "--literal-pathspecs", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null", "-c", "diff.external=", "-c", f"safe.directory={root}", "--work-tree=" + str(root), "-C", str(root)]
        config = self._run_git(base + ["config", "--includes", "--null", "--list"], env, MAX_OUTPUT)
        if config is None:
            return None
        overrides = []
        for entry in config.split("\0"):
            key = entry.split("\n", 1)[0]
            if re.fullmatch(r"filter\..+\.(?:process|clean|smudge|required)", key):
                overrides += ["-c", key + ("=false" if key.endswith(".required") else "=")]
        return self._run_git(base + overrides + arguments, env, limit)

    def _run_git(self, argv, env, limit):
        try:
            process = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env)
            # Bounded read rather than capture_output, which can exhaust memory.
            import threading
            timer = threading.Timer(5, process.kill)
            timer.start()
            try:
                data = process.stdout.read(limit + 1)
                if len(data) > limit:
                    process.kill()
                    raise ValueError("repository output exceeds limit; request a narrower path")
                process.wait(timeout=1)
                if process.returncode:
                    return None
                return data.decode("utf-8", "replace")
            finally:
                timer.cancel()
                if process.poll() is None:
                    process.kill()
                    process.wait()
                process.stdout.close()
        except (OSError, subprocess.TimeoutExpired):
            return None

    def metadata(self, repository):
        root = self.resolve(repository)
        revision = self._git(root, ["rev-parse", "--verify", "HEAD"], limit=128)
        return {"repository": repository, "host_id": "bleetd", "observed_at": utcnow(), "revision": revision.strip() if revision else None}

    def list_repositories(self):
        return {"repositories": [self.metadata(key) for key in self.roots], "observed_at": utcnow()}

    def list_directory(self, repository, path=".", offset=0, limit=100):
        directory = self.resolve(repository, path)
        if not directory.is_dir():
            raise ValueError("path is not a directory")
        offset, limit = max(0, min(offset, 10000)), max(1, min(limit, 200))
        entries = []
        # Bound inspection independently of the returned page size.
        for index, child in enumerate(directory.iterdir()):
            if index >= 10000:
                break
            if child.is_symlink() or excluded(child.name):
                continue
            if child.is_file() or child.is_dir():
                entries.append({"name": child.name, "kind": "directory" if child.is_dir() else "file"})
        entries.sort(key=lambda item: item["name"])
        return {**self.metadata(repository), "path": path, "entries": entries[offset:offset + limit], "next_offset": offset + limit if len(entries) > offset + limit else None}

    def _read_text(self, repository, path):
        file = self.resolve(repository, path)
        root = self.roots[repository]
        parts = file.relative_to(root).parts
        if not parts:
            raise ValueError("path is not a regular file")
        descriptors = []
        try:
            directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
            descriptors.append(os.open(root, directory_flags))
            for part in parts[:-1]:
                descriptors.append(os.open(part, directory_flags, dir_fd=descriptors[-1]))
            fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=descriptors[-1])
        except OSError:
            raise ValueError("file is unavailable or a symlink was encountered") from None
        finally:
            for directory_fd in reversed(descriptors):
                os.close(directory_fd)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode) or os.fstat(fd).st_size > MAX_FILE_BYTES:
                raise ValueError("only bounded regular files can be read")
            with os.fdopen(fd, "rb", closefd=False) as stream:
                raw = stream.read(MAX_FILE_BYTES + 1)
            if len(raw) > MAX_FILE_BYTES or b"\0" in raw:
                raise ValueError("binary or oversized file is excluded")
            try:
                text = raw.decode("utf-8")
            except UnicodeError:
                raise ValueError("only UTF-8 text is supported") from None
        finally:
            os.close(fd)
        return text

    def read_file(self, repository, path, start_line=1, max_lines=200):
        text = self._read_text(repository, path)
        start = max(1, min(start_line, 100000))
        count = max(1, min(max_lines, 500))
        result, size = [], 0
        lines = text.splitlines()
        for index in range(start - 1, min(len(lines), start - 1 + count)):
            size += len(lines[index].encode())
            if size > MAX_OUTPUT:
                break
            result.append({"line": index + 1, "text": lines[index]})
        return {**self.metadata(repository), "path": path, "lines": result, "total_lines": len(lines), "truncated": bool(lines) and (not result or result[-1]["line"] < len(lines))}

    def search_code(self, repository, query, path=".", limit=100):
        if not query or len(query) > 256:
            raise ValueError("query must contain 1–256 characters")
        root = self.resolve(repository, path)
        if not root.is_dir():
            raise ValueError("search path must be a directory")
        limit = max(1, min(limit, 200))
        matches, examined, budget, truncated = [], 0, 0, False
        output_bytes = 0
        deadline = time.monotonic() + 5
        base = self.roots[repository]
        for directory, dirs, files in os.walk(root, followlinks=False):
            dirs[:] = sorted(name for name in dirs if not excluded(name) and name not in SKIP_DIRS and not (Path(directory) / name).is_symlink())
            for name in sorted(files):
                examined += 1
                if examined > 2000 or budget > 10_000_000 or time.monotonic() > deadline:
                    truncated = True
                    break
                if excluded(name):
                    continue
                relative = str((Path(directory) / name).relative_to(base))
                try:
                    file = self.resolve(repository, relative)
                    if not file.is_file() or file.stat().st_size > MAX_FILE_BYTES:
                        continue
                    budget += file.stat().st_size
                    text = self._read_text(repository, relative)
                except (OSError, ValueError):
                    continue
                for line_number, line in enumerate(text.splitlines()[:500], 1):
                    if query in line:
                        output_bytes += len(line.encode()) + len(relative.encode()) + 64
                        if output_bytes > MAX_OUTPUT:
                            truncated = True
                            break
                        matches.append({"path": relative, "line": line_number, "text": line})
                        if len(matches) >= limit:
                            truncated = True
                            break
                if truncated or len(matches) >= limit:
                    break
            if truncated:
                break
        return {**self.metadata(repository), "query": query, "matches": matches, "truncated": truncated, "searched_lines_per_file": 500, "examined_files": examined}

    def get_repository_status(self, repository):
        root = self.resolve(repository)
        text = self._git(root, ["status", "--porcelain=v1", "-z", "--untracked-files=normal", "--no-renames"])
        if text is None:
            raise ValueError("Git status unavailable")
        entries = []
        for item in text.split("\0"):
            if len(item) < 4:
                continue
            try:
                self.resolve(repository, item[3:], allow_missing=True)
            except ValueError:
                continue
            entries.append({"status": item[:2], "path": item[3:]})
        return {**self.metadata(repository), "entries": entries}

    def get_diff(self, repository, path=".", staged=False):
        root = self.resolve(repository)
        requested = self.resolve(repository, path, allow_missing=True)
        prefix = str(requested.relative_to(root))
        args = ["diff", "--no-ext-diff", "--no-textconv", "--no-renames"] + (["--cached"] if staged else [])
        names = self._git(root, args + ["--name-only", "-z", "--", prefix])
        if names is None:
            raise ValueError("Git diff unavailable")
        permitted = []
        for name in names.split("\0"):
            if not name:
                continue
            try:
                self.resolve(repository, name, allow_missing=True)
            except ValueError:
                continue
            permitted.append(name)
        text = self._git(root, args + ["--unified=3", "--"] + permitted) if permitted else ""
        if text is None:
            raise ValueError("Git diff unavailable")
        return {**self.metadata(repository), "path": path, "staged": staged, "diff": text}
