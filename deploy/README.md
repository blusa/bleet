# Private ZORAK deployment

Bleet runs behind the existing Caddy wildcard at `https://bleet.zorak.blusa.cloud`.
`compose.yaml` publishes only `127.0.0.1:8791`; Caddy rejects sources outside the
tailnet and loopback. Bearer authentication still applies to snapshot, MCP and
terminal endpoints. No Tailscale Serve or Funnel is used.

Persistent data lives at `/mnt/user/appdata/bleet`:

- `state/`: token hashes, enrollment and metrics/history; owned by UID/GID 10001.
- `config/config.json`: administrative allowlist, using `config.zorak.example.json`.
- `ssh/id_ed25519`: dedicated identity generated on ZORAK, mode 600, UID 10001.
- `ssh/known_hosts`: host keys obtained through trusted management connections.
- `releases/<id>/source/`: source snapshot, mounted read-only at `/code/blussh`.

The container runs as UID 10001 with a read-only filesystem, a temporary `/tmp`,
all capabilities dropped, and read-only SSH/config/code mounts. Four fixed host
Linux counter mounts provide ZORAK CPU/memory/topology without installing Python
on Unraid; the collector labels this `host_proc_sys_mount` and leaves GPU and
network/SSH reachability unknown when not measured. It uses
`100.100.100.100` for MagicDNS; ZORAK's system resolver does not resolve these
names. Private keys and tokens must never enter a source snapshot or git.

For a prepared release source, run on ZORAK (use the real release ID):

```sh
cd /mnt/user/appdata/bleet/releases/<id>/source/deploy
export BLEET_CODE_ROOT=/mnt/user/appdata/bleet/releases/<id>/source
export BLEET_IMAGE_TAG=<id>
docker compose config --quiet
docker compose build --pull
docker compose up -d --wait
curl --fail http://127.0.0.1:8791/health
```

Set source/config/SSH directories traversable by UID 10001 and keep the state and
identity owned by that UID. Do not copy personal private keys into the service.
The dedicated public identity has forwarding disabled on each authorized host;
PTY sessions remain permitted. ZORAK's key is persisted in
`/boot/config/ssh/root/authorized_keys` as well as the live root authorized keys.

Caddy source and its deployment procedure live in `dotfiles-macos/zorak/caddy`;
the Bleet operational runbook lives in `dotfiles-macos/zorak/bleet`. Validate a
candidate inside the running Caddy container and reload only after backend health
passes. Keep an in-place backup of the previous Caddyfile; its existing file bind
mount means replacing the inode can leave Caddy reading the old file.

Enrollment issuance is local administration. Redirect a short-lived code to a
protected file using `bleetd enroll --output`; never print codes/tokens to logs.
Use `docker exec --user 10001:10001 bleetd bleetd ...` and the mounted config.
The parent release operator handles credential delivery.

A rollback uses the previous release's compose file, its `BLEET_CODE_ROOT`, and
its image tag. Persistent state and SSH identity are shared across releases;
never remove them as part of a rollback. Back up the state database before schema
changes. The initial working-tree snapshot deliberately excludes all `.git` history and
reports Git metadata unavailable. `python3 deploy/stage-source.py /tmp/bleet-source.tar.gz`
creates this explicit source archive plus a SHA-256 manifest.
Only files already tracked or staged in Git under the public source roots are
eligible; add intended new source files to the index first. Private deployment
directories, identity filenames, Git metadata and symlinks are excluded even if
tracked. Untracked local files are never copied. Tracked file contents include
their current working-tree edits.
After the release commit is public, replace it with a fresh public HTTPS clone checked out at the
exact release SHA from `https://github.com/blusa/bleet`. Never copy local Git objects, config, hooks or credentials.
