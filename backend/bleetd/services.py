"""Shared inventory, metric, and T3 operations used by both API and MCP."""
import asyncio
import base64
import copy
import io
import json
import re
import shlex
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit, urlunsplit

import qrcode

from .collector import collect_mounted_linux, collector_command, parse_linux, parse_macos
from .ssh import SSH
from .state import utcnow

# Reuses the fixed discovery/fallback behavior from omarchy/blussh.py:t3_pair_script.
# No clipboard integration, supplied label, or user-provided remote command.
T3_SCRIPT = '''label='Bleet private gateway'
ttl=1h
t3=
if command -v t3 >/dev/null 2>&1; then
  t3=t3
elif [ -x "$HOME/.local/bin/t3" ]; then
  t3="$HOME/.local/bin/t3"
else
  v=$(grep -o '"activeVersion"[^,}]*' "$HOME/.t3/runtime/service-state.json" 2>/dev/null | cut -d'"' -f4)
  if [ -n "$v" ] && [ -x "$HOME/.t3/runtime/versions/$v/t3" ]; then
    t3="$HOME/.t3/runtime/versions/$v/t3"
  fi
fi
pair() {
  if [ -n "$t3" ]; then
    "$t3" pair "$@" </dev/null
  elif command -v npx >/dev/null 2>&1; then
    npx -y t3 pair "$@" </dev/null
  else
    echo 't3 unavailable' >&2
    return 127
  fi
}
pair --tailscale --ttl "$ttl" --label "$label"
rc=$?
if [ $rc -ne 0 ] && [ $rc -ne 127 ]; then
  pair --ttl "$ttl" --label "$label"
  rc=$?
fi
exit $rc
'''
ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
PAIRING = re.compile(r"Pairing URL:\s*(https?://\S+)")


class Gateway:
    def __init__(self, config, state, ssh=None):
        self.config, self.state = config, state
        self.ssh = ssh or SSH(config)
        self.hosts = {host.id: host for host in config.hosts}
        self.last = state.cached_hosts()
        for host in self.last.values():
            if host.get("metrics"):
                host["metrics"]["stale"] = True
            host["status"] = "unknown"
        self._snapshot = None
        self._last_poll = 0
        self._lock = asyncio.Lock()
        self._slots = asyncio.Semaphore(config.max_parallel_collectors)
        self._pair_locks = {host.id: asyncio.Lock() for host in config.hosts}
        self._pair_last = {}

    def resolve(self, host_id):
        host = self.hosts.get(host_id)
        if host is None or not host.enabled:
            raise ValueError("host is not allowlisted or enabled")
        return host

    async def _collect(self, host):
        prior = self.last.get(host.id, {})
        current = {"id": host.id, "name": host.name, "address": host.address, "source": host.source, "status": "unknown", "ssh_online": None, "network_online": None, "is_t3": host.is_t3, "enabled": host.enabled, "last_seen": prior.get("last_seen"), "metrics": copy.deepcopy(prior.get("metrics")), "metrics_error": None, "capabilities": ["ssh"] + (["t3"] if host.is_t3 else [])}
        if not host.enabled:
            current["metrics_error"] = "host disabled"
            if current["metrics"]:
                current["metrics"]["stale"] = True
            return current
        try:
            async with self._slots:
                if host.collector == "mounted_linux":
                    raw = await asyncio.to_thread(collect_mounted_linux)
                else:
                    output = await self.ssh.run(host, collector_command())
                    raw = json.loads(output)
            if raw.get("platform") not in ("linux", "darwin"):
                raise ValueError("unsupported collector platform")
            metrics = parse_linux(raw) if raw["platform"] == "linux" else parse_macos(raw)
            metrics["metrics_source"] = raw.get("metrics_source", "ssh_helper")
            current.update(metrics=metrics, status="online", ssh_online=True if host.collector == "ssh" else None, last_seen=utcnow())
        except asyncio.CancelledError:
            raise
        except Exception:
            # No remote output, URLs, tokens or infrastructure stderr is persisted.
            current["metrics_error"] = "host proc/sys mounts unavailable" if host.collector == "mounted_linux" else "hardware collection unavailable; check SSH, Python 3 and host-key configuration"
            current["status"] = "degraded" if current["metrics"] else "unknown"
            current["ssh_online"] = None  # A failed helper does not prove SSH or network is down.
            if current["metrics"]:
                current["metrics"]["stale"] = True
        if prior.get("status") != current["status"]:
            self.state.add_event(host.id, "host_status", f"Host status: {current['status']}")
        self.last[host.id] = current
        self.state.save_host(current, self.config.history_samples_per_host)
        return current

    async def snapshot(self):
        async with self._lock:
            if self._snapshot is not None and time.monotonic() - self._last_poll < self.config.cache_seconds:
                return copy.deepcopy(self._snapshot)
            hosts = await asyncio.gather(*(self._collect(host) for host in self.config.hosts))
            self._snapshot = {"schema_version": 1, "collected_at": utcnow(), "gateway": {"id": "bleetd", "name": self.config.gateway_name, "version": "0.1.0"}, "hosts": hosts, "events": self.state.events(50), "errors": [{"source": "ssh_collector", "host_id": host["id"], "message": host["metrics_error"]} for host in hosts if host.get("metrics_error")]}
            self._last_poll = time.monotonic()
            return copy.deepcopy(self._snapshot)

    async def pair(self, host_id, output):
        if output not in ("link", "qr", "both"):
            raise ValueError("output must be link, qr or both")
        host = self.resolve(host_id)
        if not host.is_t3:
            raise ValueError("T3 pairing is unavailable for this host")
        async with self._pair_locks[host.id]:
            if time.monotonic() - self._pair_last.get(host.id, -1000) < 5:
                raise ValueError("pairing temporarily rate limited")
            self._pair_last[host.id] = time.monotonic()
            # Start TTL before execution, to avoid overstating expiration after slow SSH.
            expires = datetime.now(timezone.utc) + timedelta(hours=1)
            try:
                text = await self.ssh.run(host, "bash -lc " + shlex.quote(T3_SCRIPT), timeout=self.config.pairing_timeout)
                match = PAIRING.search(ANSI.sub("", text))
                if not match:
                    raise ValueError("no pairing URL")
                url = urlsplit(match.group(1))
                if url.username or url.password or not url.hostname:
                    raise ValueError("invalid pairing URL")
                if host.magic_dns:
                    url = url._replace(scheme="https", netloc=host.magic_dns)
                if url.scheme != "https" or not url.fragment or "token=" not in url.fragment:
                    raise ValueError("invalid pairing URL")
                link = urlunsplit(url)
                png = None
                if output in ("qr", "both"):
                    buffer = io.BytesIO()
                    qrcode.make(link).save(buffer, format="PNG")
                    png = base64.b64encode(buffer.getvalue()).decode()
                return {"host_id": host.id, "pairing_url": link if output in ("link", "both") else None, "expires_at": expires.isoformat().replace("+00:00", "Z"), "qr_png_base64": png}
            except asyncio.CancelledError:
                raise
            except Exception:
                raise ValueError("T3 pairing failed; verify T3 availability and SSH configuration") from None
