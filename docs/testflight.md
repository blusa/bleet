# Bleet 0.1.0 beta handoff

The native app and widget extension use bundle IDs `cloud.blusa.bleet` and `cloud.blusa.bleet.widgets`, with App Group `group.cloud.blusa.bleet`, team `VMGQ6AAMB5`, version 0.1.0 and initial build 1. TestFlight distribution and the invitation to the requested tester are authorized; no public App Store release is intended.

## What to test

Connect your phone to the tailnet, open Connection and enroll with a short-lived code from the gateway administrator. The default editable URL is `https://bleet.zorak.blusa.cloud`. Check host switching, CPU core heatmap, GPU selection, RAM/VRAM bars and hardware details. Open Monitor to use the remote btop/htop/top fallback, or Terminal for the configured remote shell. Pair T3 Code only when you intend to authorize a T3 client; the link and QR are temporary credentials.

On iPhone Duo, compare the compact dashboard and the open split layout. Machine, GPU and core selection should survive resizing. Desk is an explicit toggle in this first beta. Add CPU, GPU and memory widgets, select a machine and check their timestamps; iOS controls widget refresh timing. Offline widgets show a saved snapshot, not a live connection. Demo exploration is always labeled and has no terminal or pairing authority.

## Release prerequisites

Register and assign the App Group to both bundle IDs, create the Bleet App Store Connect record, and use valid distribution signing profiles. These portal operations require a current Apple web session; the existing ASC API key handles subsequent API/upload operations. Build on BUSTER using the checked-in Xcode project and scheme, with Xcode 27.1 and its Metal Toolchain. Increment the build number before repeating an uploaded build. Never embed a gateway token or enrollment code in the app, metadata, test notes or screenshots.

Upload a signed App Store Connect archive/IPA, wait for processing, set the encryption declaration and test notes, attach the processed build to a beta group, and verify the tester invitation. A simulator build or unsigned archive is not a TestFlight deployment. Record the actual app ID/build ID and invitation state in release evidence after these steps succeed.

The gateway requires VPN access. External beta/App Store review would require a separately approved reachable review setup; the bundled demo exposes the visual interface but does not grant a shell or private data access. Start with internal testing where the tester’s App Store Connect role permits it. Privacy policy: `https://github.com/blusa/bleet/blob/main/docs/privacy.md`; support: `https://github.com/blusa/bleet/issues`.
