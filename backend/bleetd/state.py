"""Small SQLite state store; only high-entropy credential hashes reach disk."""
import hashlib
import json
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .config import SCOPES


def utcnow():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def validate_scopes(scopes):
    if not scopes or not set(scopes) <= SCOPES:
        raise ValueError("invalid scopes")
    return sorted(set(scopes))


class State:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        # Opening with restrictive permissions avoids a plaintext-readable creation window.
        descriptor = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        os.close(descriptor)
        os.chmod(self.path, 0o600)
        with self.connection() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS tokens (hash TEXT PRIMARY KEY, name TEXT NOT NULL, scopes TEXT NOT NULL, created TEXT NOT NULL, revoked INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS enrollments (hash TEXT PRIMARY KEY, scopes TEXT NOT NULL, expires REAL NOT NULL, used INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, time TEXT NOT NULL, host_id TEXT, kind TEXT NOT NULL, message TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS samples (id INTEGER PRIMARY KEY AUTOINCREMENT, host_id TEXT NOT NULL, time TEXT NOT NULL, metrics TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS samples_host ON samples(host_id, id);
            CREATE TABLE IF NOT EXISTS hosts (id TEXT PRIMARY KEY, snapshot TEXT NOT NULL);
            """)

    @contextmanager
    def connection(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def issue_token(self, name, scopes):
        scopes = validate_scopes(scopes)
        token = secrets.token_urlsafe(32)
        with self.connection() as db:
            db.execute("INSERT INTO tokens(hash,name,scopes,created) VALUES(?,?,?,?)", (digest(token), name[:128], json.dumps(scopes), utcnow()))
        return token

    def authenticate(self, token):
        if not token or len(token) > 512:
            return None
        with self.connection() as db:
            row = db.execute("SELECT name,scopes,created FROM tokens WHERE hash=? AND revoked=0", (digest(token),)).fetchone()
        return {**dict(row), "scopes": json.loads(row["scopes"])} if row else None

    def revoke_token(self, token):
        with self.connection() as db:
            db.execute("UPDATE tokens SET revoked=1 WHERE hash=?", (digest(token),))

    def issue_enrollment(self, scopes, ttl=600, now=None):
        scopes = validate_scopes(scopes)
        if not 1 <= ttl <= 86400:
            raise ValueError("enrollment TTL must be 1–86400 seconds")
        code = secrets.token_urlsafe(24)
        now = time.time() if now is None else now
        with self.connection() as db:
            db.execute("DELETE FROM enrollments WHERE expires < ? OR used=1", (time.time(),))
            db.execute("INSERT INTO enrollments(hash,scopes,expires) VALUES(?,?,?)", (digest(code), json.dumps(scopes), now + ttl))
        return code

    def redeem(self, code, name):
        if len(code) > 512:
            return None
        token = secrets.token_urlsafe(32)
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT scopes FROM enrollments WHERE hash=? AND used=0 AND expires>?", (digest(code), time.time())).fetchone()
            if not row:
                return None
            db.execute("UPDATE enrollments SET used=1 WHERE hash=?", (digest(code),))
            db.execute("INSERT INTO tokens(hash,name,scopes,created) VALUES(?,?,?,?)", (digest(token), name[:128], row["scopes"], utcnow()))
        return {"token": token, "scopes": json.loads(row["scopes"])}

    def add_event(self, host_id, kind, message):
        with self.connection() as db:
            db.execute("INSERT INTO events(time,host_id,kind,message) VALUES(?,?,?,?)", (utcnow(), host_id, kind, message))
            db.execute("DELETE FROM events WHERE id NOT IN (SELECT id FROM events ORDER BY id DESC LIMIT 1000)")

    def events(self, limit=100):
        with self.connection() as db:
            rows = db.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (max(1, min(limit, 1000)),)).fetchall()
        return [{**dict(row), "id": str(row["id"])} for row in rows]

    def save_host(self, host, keep=720):
        with self.connection() as db:
            db.execute("INSERT OR REPLACE INTO hosts(id,snapshot) VALUES(?,?)", (host["id"], json.dumps(host)))
            metrics = host.get("metrics")
            if metrics and not metrics.get("stale"):
                db.execute("INSERT INTO samples(host_id,time,metrics) VALUES(?,?,?)", (host["id"], metrics["collected_at"], json.dumps(metrics)))
                db.execute("DELETE FROM samples WHERE host_id=? AND id NOT IN (SELECT id FROM samples WHERE host_id=? ORDER BY id DESC LIMIT ?)", (host["id"], host["id"], keep))

    def cached_hosts(self):
        with self.connection() as db:
            return {row["id"]: json.loads(row["snapshot"]) for row in db.execute("SELECT * FROM hosts")}

    def history(self, host_id, limit=120):
        with self.connection() as db:
            rows = db.execute("SELECT metrics FROM samples WHERE host_id=? ORDER BY id DESC LIMIT ?", (host_id, max(1, min(limit, 1000)))).fetchall()
        return list(reversed([json.loads(row["metrics"]) for row in rows]))
