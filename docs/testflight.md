# Bleet 0.1.0 beta handoff

The native app and widget extension use bundle IDs `cloud.blusa.bleet` and `cloud.blusa.bleet.widgets`, with App Group `group.cloud.blusa.bleet`, team `VMGQ6AAMB5`, version 0.1.0 and initial build 1. TestFlight distribution and the invitation to the requested tester are authorized; no public App Store release is intended.

## Published internal beta — November 15, 2026

**Bleet Private Fleet 0.1.0 (1)** is available for internal TestFlight testing. App Store Connect app ID: `6835056287`; build ID: `40808a35-4d98-44d8-aafd-ff6f71dce0a6`. The build was archived and uploaded from BUSTER at source commit `532d256866327365d66e2f8b50a6891dc38a8c09`.

Apple reports `VALID` processing; internal distribution advanced from `READY_FOR_BETA_TESTING` to `IN_BETA_TESTING` after inviting the tester. The `Bleet Internal` group has the build, and the requested tester's email invitation was created and independently confirmed as `INVITED`. Acceptance and installation are the tester's next steps. What to Test notes, the beta description and the privacy-policy URL are configured in `es-MX`.

The App Group is registered and assigned to both targets. The exported IPA's app and widget signatures and store profiles were verified, with the expected team/App Group and debugging disabled. IPA SHA-256: `940fef16d5b1fa501c4883a1654137d79ab166d170517c72edd13bc73f0f0002`. The matrix icon is included in the processed build. The on-device display name remains Bleet.

This is an internal beta with email invitations; there is no public TestFlight join link. The gateway still requires private-network access and separate single-use enrollment. No gateway credential is embedded in the IPA or beta notes.

## What to test

Connect your phone to the tailnet, open Connection and enroll with a short-lived code from the gateway administrator. The default editable URL is `https://bleet.zorak.blusa.cloud`. Check host switching, CPU core heatmap, GPU selection, RAM/VRAM bars and hardware details. Open Monitor to use the remote btop/htop/top fallback, or Terminal for the configured remote shell. Pair T3 Code only when you intend to authorize a T3 client; the link and QR are temporary credentials.

On iPhone Duo, compare the compact dashboard and the open split layout. Machine, GPU and core selection should survive resizing. Desk is an explicit toggle in this first beta. Add CPU, GPU and memory widgets, select a machine and check their timestamps; iOS controls widget refresh timing. Offline widgets show a saved snapshot, not a live connection. Demo exploration is always labeled and has no terminal or pairing authority.

## Reproducing a release

In a fresh environment, register and assign the App Group to both bundle IDs, create the App Store Connect record, and use valid distribution signing profiles. These portal operations require a current Apple web session; the existing ASC API key handles subsequent API/upload operations. The initial release above completed those steps. Build on BUSTER using the checked-in Xcode project and scheme, with Xcode 27.1 and its Metal Toolchain. Increment the build number before repeating an uploaded build. Never embed a gateway token or enrollment code in the app, metadata, test notes or screenshots.

Upload a signed App Store Connect archive/IPA, wait for processing, set the encryption declaration and test notes, attach the processed build to a beta group, and verify the tester invitation. A simulator build or unsigned archive is not a TestFlight deployment. Record the actual app ID/build ID and invitation state in release evidence after these steps succeed.

The gateway requires VPN access. External beta/App Store review would require a separately approved reachable review setup; the bundled demo exposes the visual interface but does not grant a shell or private data access. Start with internal testing where the tester’s App Store Connect role permits it. Privacy policy: `https://github.com/blusa/bleet/blob/main/docs/privacy.md`; support: `https://github.com/blusa/bleet/issues`.
