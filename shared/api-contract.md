# Bleet API v1 — implementation contract

Implementation is authorized by the user's full-send request. App and backend owners use this file verbatim; coordinate changes with the parent before altering the wire format.

Public origin: `https://bleet.zorak.blusa.cloud`. Backend is Docker on ZORAK, bound to host loopback, routed by the existing Caddy wildcard handler with tailnet/loopback source restrictions. Do not use Tailscale Serve or Funnel. Release builds run on BUSTER (the current machine), Apple team `VMGQ6AAMB5`.

## Authentication

App stores its per-device opaque bearer token in Keychain. No token is embedded in the app, repo, logs, URL query, widgets or release notes. `Authorization: Bearer <token>` applies to HTTP, WebSocket handshake and MCP. Server stores token hashes and explicit scopes: `read`, `terminal:connect`, `t3:pair`. Enrollment codes are short-lived and single-use, issued by a local administrative CLI, then redeemed by the app. Widget extension uses an App Group snapshot only, not an app credential.

`GET /health` is unauthenticated and returns `{ "status": "ok", "version": "0.1.0" }`.

`POST /v1/enroll` body: `{ "code": "...", "device_name": "Pablo's iPhone" }`. Response: `{ "token": "...", "scopes": ["read", "terminal:connect", "t3:pair"] }`. Never persist/log the plaintext response on the server. CLI issuance must support redirecting the code to a protected file without printing it in tool logs.

All times are ISO 8601 UTC strings (fractional seconds permitted); stable IDs are strings. Memory is bytes, utilization is 0–100, temperatures °C, power W. `null` means unknown, not zero. Clients must tolerate optional fields and future additions.

## Snapshot

`GET /v1/snapshot`, scope `read`. Shape is illustrated by `snapshot.example.json` (demo fixture, not live infrastructure). Host `status`: `online`, `degraded`, `offline`, `unknown`. CPU cores are physical cores with grouped logical IDs when topology is known; otherwise explicitly label topology as logical. Each GPU has stable UUID/id and index. Unified memory is counted once, not as separate dedicated VRAM. Snapshot includes latest events and source errors. Provider failure must preserve prior hosts and mark stale/unknown rather than claiming every host went offline.

An unreachable/unsupported collector returns `metrics: null` or optional/null fields and a concise `metrics_error`. A current timestamp cannot be assigned to cached metrics. Polling every 5–10 seconds in the visible app, with backend coalescing/caching, is sufficient for v0.1.

## T3 pairing

`POST /v1/t3/pair`, scope `t3:pair`. Body `{ "host_id": "ts:brak", "output": "both" }`; output enum `link`, `qr`, `both`. Response `{ "host_id": "ts:brak", "pairing_url": "https://.../pair#token=...", "expires_at": "...", "qr_png_base64": "..." }`; fields unused by the requested format may be null. Execute only the fixed T3 pairing script on the resolved allowlisted host. Reuse current `omarchy/blussh.py` behavior/redaction. No shell command, URL or SSH target supplied by the client. Response `Cache-Control: no-store`; no credential in history/logs. Default TTL remains the verified `1h`. Client MCP can retain its response, so do not promise client-side non-retention or single use.

## Terminal

`WS /v1/terminal?host_id=<stable-id>&mode=monitor`, scope `terminal:connect`; `mode` is `monitor` or `shell`. Token only in the Authorization header. `monitor` runs btop → htop → top via a fixed script. `shell` opens the authenticated SSH session to the allowlisted host. Both use a PTY and checked SSH host keys; never disable host checking.

Client JSON messages: `{ "type": "input", "data": "..." }`, `{ "type": "resize", "cols": 100, "rows": 30 }`. Server JSON messages: `{ "type": "output", "data": "..." }`, `{ "type": "exit", "status": 0 }`, `{ "type": "error", "message": "redacted error" }`. ANSI sequences remain in the output string for SwiftTerm. Resize the PTY when geometry changes. Closing the WebSocket cleans up its SSH subprocess/session.

## MCP

Streamable HTTP mounted at `/mcp`, same authentication/scopes. Data/code tools are read-only and bounded: list/get hosts, hardware, metrics/history/events/source state; list repositories/directories, read files with lines, search code, git status/diff. Explicit repository roots, symlink/traversal checks, secret path exclusions and bounded outputs. Include dates/revisions so stale data is visible.

`create_t3_pairing(host_id, output)` additionally requires `t3:pair`; hints `readOnlyHint: false`, `idempotentHint: false`. Returns link and/or PNG MCP content plus host/expiry metadata. Never expose arbitrary command execution through MCP. Terminal is an app-only capability. No T3 side effect from a data read.

## iOS presentation

Use the approved graphite/mint mockups as direction: CPU heatmap, GPU gauge, RAM/VRAM bars; exact values secondary. Preserve selected host/GPU/core through width changes. SwiftUI split navigation for wide Duo and compact navigation for small width. Manual desk layout is acceptable until a public posture API is verified. Widget snapshots always carry their measurement time. A clearly labeled demo is allowed for offline exploration and beta review, never silently masquerading as a live connection.
