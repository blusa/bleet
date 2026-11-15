# bleetd

Private Bleet API and official Python MCP SDK Streamable HTTP gateway. Production origin is `https://bleet.zorak.blusa.cloud`; Docker publishes only `127.0.0.1:8791`. Route through the existing Caddy wildcard handler with its tailnet/loopback source restrictions. Do not configure Tailscale Serve or Funnel.

## Local development

```sh
cd backend
uv sync --extra test
uv run pytest
uv run bleetd serve --config /absolute/path/config.json --host 127.0.0.1 --port 8791
```

Copy `config.example.json` to an external/private `config.json`, replace placeholder addresses/users, and create the state directory. `repositories` maps names to existing directories on the gateway/container, preferably read-only mounts. An absent repository root is a startup error. There are no implicit home-directory roots. Remote code access uses administrator-mounted read-only snapshots/filesystems; v1 does not execute client-supplied remote code commands. Revisions and observation dates identify the mounted worktree, not an independently refreshed remote index.

Each host has an immutable API `id`, human `name`, client-resolvable `address`, validated administrative `ssh_target`, optional `port` and `magic_dns`, `enabled`, and `is_t3`. Clients pass only `id`; they cannot override a target, port, command, label or TTL. `is_t3` is configured inventory/capability, not a fabricated live T3 health probe. Network status remains `null` when it is not independently measured. A helper failure yields null metrics or stale cached metrics and a concise source error; it does not imply a VPN outage. Configured hosts remain visible during failures.

## Docker deployment

```sh
cd backend
# Create these private deployment files outside the tracked checkout in production.
install -d -m 700 state ssh
# Populate config.json, known_hosts and a dedicated SSH identity securely.
# Run as root only while preparing bind-mount ownership:
chown -R 10001:10001 state ssh
chmod 600 ssh/id_ed25519
# Review compose.yaml paths before starting:
docker compose up -d --build
curl --fail http://127.0.0.1:8791/health
```

Container UID/GID is `10001:10001`. State `/var/lib/bleetd` is writable and persistent; config, known_hosts, identity and repositories are read-only. Root filesystem is read-only with `/tmp` tmpfs. The example sets container DNS `100.100.100.100`; prove MagicDNS resolution from inside the running container. A reachable host VPN does not guarantee Docker has tailnet DNS. Mount only the dedicated service identity, never an entire personal home directory. No app/device credentials belong in image layers or configuration examples.

Obtain and verify SSH host-key fingerprints using a trusted administrative channel before populating `known_hosts`; collecting with `ssh-keyscan` alone is not verification. Host-key checking is always `yes`; changed/missing keys fail closed. The container ignores ambient SSH config unless `ssh_config` explicitly names a read-only administrative file. SSH multiplex control sockets live in a unique private `/tmp/bleetd-ssh-*` directory per process with a 60-second idle lifetime; shutdown stops its masters and removes that directory. They never live in persistent state. The remote user must have intended read permissions and `python3`; Linux additionally uses `/proc`, sysfs and optionally `nvidia-smi`. macOS uses unprivileged `sysctl`, `vm_stat` and `top`. Unsupported GPU readings are null. macOS memory is active+wired+compressed pages; Apple Silicon RAM is counted once as unified memory. No elevated `powermetrics` operation is attempted. A host without Python 3 remains inventory with explicit missing metrics. For ZORAK/Unraid, set only that host to `"collector": "mounted_linux"` and bind `/proc/stat`, `/proc/meminfo`, `/proc/cpuinfo` to the matching files under `/host/proc`, plus `/sys/devices/system/cpu` to `/host/sys/devices/system/cpu`, all read-only. This source explicitly labels `metrics_source: "host_proc_sys_mount"`; it never falls back to container `/proc`. SSH/network remain independently unknown, and no host NVIDIA utilization is claimed from inside the container. At most one configured host may use these local host mounts. No Docker CPU/memory limits are used in the supplied configuration.

Caddy should reverse proxy to `127.0.0.1:8791` only after VPN/source restrictions, support WebSocket upgrades, and suppress access/request-body logs for enrollment, pairing and MCP. bleetd disables Uvicorn access logs. Do not add body tracing/debug logging. API/MCP responses use `Cache-Control: no-store`; T3 link and PNG generation stays in memory. A client can retain a sensitive MCP response, so issuance permission must be deliberate.

## Enrollment and tokens

Run administrative commands inside the service/container against the same config/state. Output is sensitive. Prefer `--output`, which exclusively creates a new file with mode `0600`, emits nothing to stdout and refuses overwrite/symlinks. Treat the file like a password and delete it after its intended transfer.

```sh
# Enrollment expires after 10 minutes and can be redeemed exactly once.
bleetd enroll --config /etc/bleetd/config.json --ttl 600 \
  --device-scopes read,terminal:connect,t3:pair --output /tmp/bleet-enrollment
# Direct MCP credential: read only by default in this example.
bleetd token --config /etc/bleetd/config.json --name "MCP reader" \
  --device-scopes read --output /tmp/bleet-reader
# Revoke via a hidden local prompt; never put credentials in argv.
bleetd revoke --config /etc/bleetd/config.json
```

Without `--output`, issuance prints only the secret to stdout to support `umask 077; bleetd ... > protected-file`. Do not run it bare in a recorded console/tool session. When running via Docker, use a writable private file/container mount and securely retrieve it without echoing it into logs. Enrollment TTL is bounded to 1–86400 seconds; codes have 192 bits of entropy, token credentials 256 bits. The SQLite database stores hashes, device names, explicit scopes, expiry and revocation state, never plaintext credentials. Enrollment redemption and token creation share one atomic transaction. Enrollment attempts are limited per proxy source to 10/minute; Caddy is the source when proxying. A dedicated client can use only `read`, only `t3:pair`, or both; terminal permission independently gates the WebSocket.

The app redeems with `POST /v1/enroll` and stores the returned opaque token in Keychain. API, WebSocket handshake, and MCP use `Authorization: Bearer …`; tokens in URL query parameters are not accepted. `/health` returns status/version without a token. `/v1/snapshot` requires `read`; `/v1/t3/pair` requires `t3:pair`. Exact wire formats are in `../shared/api-contract.md`.

## MCP and terminal

MCP endpoint is exactly `/mcp`, implements Streamable HTTP with the official SDK, authenticates every request and checks scopes at each tool. Stateless transport avoids durable server sessions. Available tools: `list_hosts`, `get_host`, `get_hardware`, `get_metrics`, `get_metrics_history`, `get_events`, `get_sources`, `list_repositories`, `list_directory`, `read_file`, `search_code`, `get_repository_status`, `get_diff`, `create_t3_pairing`. T3 issuance is explicitly non-read-only and non-idempotent; it accepts only `link`, `qr`, or `both` and uses the fixed 1h script matching existing Omarchy behavior. A configured `magic_dns` rewrites the T3 host to its intended HTTPS origin. Pairing fails with a generic redacted error and has a 5-second per-host issuance interval. Clients may keep links until expiry; single use is not promised.

Repository reads reject absolute paths, `..`, symlink components, binary files, common secret paths and Git metadata. Files are capped at 1 MB, reads at 500 lines/64 KB, search at 2000 files/10 MB/5 seconds and 500 lines/file, results at 200 matches/64 KB. Directory inspection caps at 10000 entries and returns pages of 200 or fewer. Search limits are explicit in the result; split searches or use paged reads for larger files. Git output is bounded to 64 KB with a 5-second deadline, excludes protected paths, and disables external diff/textconv/fsmonitor helpers plus all configured clean/smudge/process filters, and pins the worktree to the allowlisted root. Repositories must be trusted read-only mounts: root configuration grants source access; names/contents are not an execution authorization. Keep credentials out of source files even when their paths are otherwise allowed.

The app-only `/v1/terminal?host_id=…&mode=monitor|shell` uses a PTY, bounded JSON frames, resize ioctls and session cleanup on disconnect/cancellation. Monitor mode runs the fixed `btop → htop → top` fallback; shell mode opens the explicitly authorized remote login shell. There is no terminal/execution MCP tool. Concurrent terminal sessions default to 8. Shell scope intentionally grants the service SSH user's shell authority, so issue it only to intended devices.

## Verification and operations

`uv run pytest` exercises hash/revocation state, concurrent single-use/expired enrollments, HTTP and MCP auth/scopes, actual MCP initialize/list/call transport, traversal/symlink/secrets, Git secret exclusion, CPU topology/counters/RAM/NVIDIA/macOS parsing, stale-time preservation, concurrent poll coalescing, T3 redaction/PNG, and a real local PTY input/resize/exit/disconnect cycle. External SSH and T3 are replaced only at their external operation boundary in unit integration tests; test fixture tokens never grant access to a real service.

Health means the process responds, not that every host is reachable. Inspect authenticated snapshot `errors`, per-host `metrics_error`, `metrics.stale`, and measurement dates for collector readiness. Polls coalesce at 5 seconds by default and also run in the background. Samples persist up to 720 per host, events up to 1000; old samples retain their original measurement timestamp. Query history via MCP. SQLite is a single-gateway design; run one Uvicorn worker/container per state directory. Back up the state database privately, since its token hashes and device inventory remain sensitive. Revocation takes effect on the next HTTP/MCP/handshake; close an already established terminal session separately when revoking its device.

Live fleet SSH, real T3 issuance, Docker builds, public Caddy routing and iOS integration require separate deployment verification; unit tests do not establish them.
