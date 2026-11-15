# Bleet v0.1 verification

Observed on BUSTER, November 14–15, 2026. The initial implementation checks and the subsequent signed TestFlight release are recorded separately below.

| Area | Evidence |
| --- | --- |
| Python | 66 tests passed: backend authentication, enrollment/scopes, official MCP transport, bounded code access, metric parsing, terminal lifecycle and existing desktop engine regressions. One upstream Starlette/httpx deprecation warning. |
| Swift models | 7 tests passed, including unknown versus zero, stable GPU selection, unified memory, measurement dates and terminal frames. |
| Native tests | 14 tests passed on a dedicated Bleet State Tests simulator running iOS 27.0. Signed simulator tests require the generated test-target Info.plist, now included in project.yml. |
| Native builds | Universal signed simulator build passed with Xcode 27.1. ARM64 Release archive passed with signing disabled; this archive is not distributable until signed/exported with the registered App Group and profiles. |
| Enrollment | Actual iPhone simulator redeemed a single-use code over the Caddy HTTPS URL, saved its token in Keychain and loaded real metrics for all four configured hosts. Relaunch restored authorization. An unsigned simulator build initially could not save a credential; signed builds provide the simulated entitlements. |
| Instruments | Actual CPU/core, GPU selection, memory, core inspection and manual Desk views exercised. Models/capacities appear in the interface. Demo readings remain labeled with their original timestamp. |
| Terminal | Actual native SwiftTerm connected to BRAK and rendered btop. Initial 13-point type produced btop's minimum-size error; fitting 80 columns resolves it. Text size and keyboard dismissal are exposed. Backend HTTPS WebSocket proof separately verified shell input, actual 120×40 PTY resize and exit 0. |
| T3 | Actual native pairing sheet displayed the returned PNG, temporary HTTPS link and expiry, then dismissed them. Credentials were not captured in screenshots/logs. Backend proof verified PNG signature, fixed expiry under one hour and no-store headers. |
| Widgets | Three widget kinds compile. An actual Home Screen CPU widget read the App Group snapshot and displayed its original measurement time. A light Home Screen exposed dark text on the graphite widget; the full-color widget now uses a dark color scheme, and a new screenshot verified readable labels. Accessory and tinted variants still need broader device acceptance. |
| Duo | Dedicated iOS 27.1 Duo displayed the open sidebar/detail layout and closed compact dashboard, including the new matrix + lowercase wordmark. Device screenshots confirmed the lit panels. Pose requests reported `first hinge-angle read returned no sample`; automatic hinge verification is unavailable. Desk is a manual toggle. |
| Private service | Valid TLS at `https://bleet.zorak.blusa.cloud`, resolving to tailnet address 100.78.112.90. Health 200; unauthenticated snapshot/MCP 401. Actual LAN-origin request remains 403 even with a spoofed forwarded address. Caddy config validates. |
| Docker and collectors | Nonroot UID 10001, read-only rootfs, only 127.0.0.1:8791 published. BRAK: 32 logical CPUs/2 NVIDIA GPUs; DEXTER: 32/1; BUSTER: 14/Apple unified GPU metadata, unsupported utilization null; ZORAK: 16 via explicitly labeled read-only host counters. |
| MCP | Official Streamable HTTP endpoint exposes 14 authenticated tools; live initialization, tool listing and bounded README reading passed. Code roots are explicit read-only mounts. No shell execution MCP tool. T3 issuance has a separate permission. |
| Restart | Backend-only restart and final image replacement retained all four collectors and passed metrics/MCP/PTY probes. SSH control sockets now live in a private ephemeral process directory. |

The repository is now `blusa/bleet`; existing macOS and Omarchy release identities remain blussh. The branch incorporates the latest main-branch desktop fixes. Source and Caddy deployment are reproducible in `deploy/` and `dotfiles-macos/zorak/bleet/`.

Implementation merged in PR #6 at `532d256866327365d66e2f8b50a6891dc38a8c09`, with CI passing. ZORAK now mounts a clean anonymous public clone at that exact commit; all 126 tracked blobs matched the public source. The signed TestFlight release and requested tester invitation subsequently completed as recorded below and in [the beta handoff](testflight.md).

## Review regressions

The first independent Sol review identified six bugs. Synthetic Git fixtures reproduced pathspec expansion into an excluded .env and missing deleted files, staged and unstaged; CLI archive fixtures reproduced local SSH identity inclusion. All five new Python cases failed before their fixes and now pass. Git uses literal pathspecs throughout and validates deleted paths without allowing secret or symlink ancestors. Source staging uses tracked public roots and excludes deployment directories/identities even if tracked.

Five asynchronous native tests reproduced late pairing after background/disconnect, live refresh overwriting demo or repopulating a disconnected widget cache, and enrollment reconnecting after disconnect. Session invalidation and pairing cancellation now reject those late responses; credential storage occurs only after current-session validation. Tests exercise real decoding, Keychain and shared cache with a delayed synthetic HTTPS transport. They pass, and a normal real enrollment again loaded the four hosts after the fix.

GPU suggestions now depend on the widget machine. Persisted GPU identifiers still resolve as entities, while rendering rejects an explicit GPU from another host or a removed host/GPU instead of substituting a first result. A shared-model regression passes; an isolated copy with the previous fallback behavior fails three assertions. Production source was not mutated during that check.

The patched backend is deployed as bleetd:0.1.0-20261115-reviewfix (image sha256:6f9adcda2a3ec0e31f6f4078a6a3e41b5269ada937bcead067a3aeb88426c39f). All 112 staged file hashes matched, no Git/identity/private config/state entered the archive, and literal/deleted-path regressions passed inside the running image. Four live collectors, HTTPS MCP and actual PTY resize/exit passed again. Both original simulator credentials and all deployment-probe credentials were revoked. Caddy was unchanged.

The iOS system offered to save the enrollment code as a password during normal enrollment acceptance; that offer was declined. The input now declares oneTimeCode semantics rather than relying on the default secure-field password classification.

Final manual acceptance on the dedicated state-test simulator successfully repeated normal live enrollment after the session guards changed. With oneTimeCode semantics, enrollment returned directly to real host readings without the Save Password sheet. Home Screen widget configuration was changed to DEXTER; its GPU menu offered only DEXTER · GPU 0. Both acceptance bearer credentials were then revoked (zero active server tokens), and the local device credential was removed. Apple web authentication remains unavailable; the third secure password request timed out without receiving a secret.

Independent review approved the current behavior after two sol-loop rounds with gpt-6.1-sol on xhigh. All six findings are resolved; no blocker or should findings remain. Usage was not exposed.

## Signed TestFlight release

After Apple web authentication and the authorized account-agreement update, App Store Connect registered **Bleet Private Fleet**, app `6835056287`. App Group `group.cloud.blusa.bleet` was created and assigned to both app and widget. The unchanged release source at `532d256866327365d66e2f8b50a6891dc38a8c09` was archived and exported on BUSTER with Xcode 27.1 and automatic API-key provisioning.

The IPA passed deep, strict signature verification. Both targets have the expected team and App Group, `get-task-allow=false`, and valid App Store provisioning profiles without device restrictions. The source icon is 1024×1024 with no alpha; Apple exposes the processed build's icon asset. IPA SHA-256: `940fef16d5b1fa501c4883a1654137d79ab166d170517c72edd13bc73f0f0002`.

Apple processed **0.1.0 (1)** as build `40808a35-4d98-44d8-aafd-ff6f71dce0a6`: `VALID`, non-exempt encryption false, and internal state `READY_FOR_BETA_TESTING`, advancing to `IN_BETA_TESTING` after inviting the tester. Both build-to-group and group-to-build reads confirm `Bleet Internal` membership. A separate group-tester read confirms the requested tester as `INVITED` after the invitation operation returned its receipt. Beta notes, description and privacy link were read back successfully. Email receipt, invitation acceptance and installation on the tester's own phone are not yet observed.

No external beta review or public App Store release was submitted. Private runtime credentials remain separate from TestFlight distribution; release preparation issued no new gateway bearer.
