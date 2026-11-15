# Bleet for iPhone and iPad

Native SwiftUI fleet instruments and WidgetKit snapshots. The layout follows available width: native split navigation above 700 points, compact machine picker below. Host/GPU/core selection belongs to the session store and survives layout changes. The Desk toggle is manual; no posture or fold-angle API is assumed.

## Build

Requires Xcode 27.1, its Metal Toolchain component (`xcodebuild -downloadComponent MetalToolchain`) and XcodeGen 2.46.0. From `ios/`:

```sh
xcodegen generate
xcodebuild -project Bleet.xcodeproj -scheme Bleet -sdk iphonesimulator -derivedDataPath build CODE_SIGN_IDENTITY=- build
swift test
```

The Bleet scheme also includes the iOS `BleetTests` target for Xcode Test. Team `VMGQ6AAMB5`, app `cloud.blusa.bleet`, extension `cloud.blusa.bleet.widgets`, App Group `group.cloud.blusa.bleet`, version 0.1.0 (1). Automatic signing and ASC registration belong to the release operator. A generic iOS archive can be produced with the Bleet scheme after capabilities/profiles are ready, including with `asc xcode archive`/`asc xcode export` using their installed CLI help.

SwiftTerm 1.18.0 (`7691f85b222a67a66b58499e1b2647443cf0dda7`) is pinned by revision in project.yml and Package.resolved. Its MIT license is in the fetched package. It renders the live ANSI stream; the app uses authenticated URLSession WebSockets, JSON input/output/resize frames, PTY resize callbacks and explicit connection teardown. The server implements the btop → htop → top fallback. Monitor starts with an 80-column fit so btop can render on a compact phone; Text size can fit the width or increase/decrease type, and Hide keyboard restores terminal height. No terminal text dump is substituted.

## Connect

Default gateway: `https://bleet.zorak.blusa.cloud`, editable in Connection. Connect the appropriate VPN first, obtain a short-lived enrollment code from the gateway administrator, then enroll. HTTPS certificate verification uses the system defaults. Enrollment tokens are stored in this device's Keychain, scoped by server origin, with WhenUnlockedThisDeviceOnly protection. Requests and errors never log credentials or return raw server errors.

An administrator may provide an enrollment deep link `bleet://enroll?server=<percent-encoded-https-origin>#code=<percent-encoded-code>`. The link fills the enrollment screen; the user submits explicitly. Codes are transient and cleared on submission/dismissal. A camera scanner is not included in v0.1; system QR scanners can open this URL scheme.

Explore Demo uses the bundled copy of `shared/snapshot.example.json` and always labels the sample. Terminal and T3 pairing are disabled in demo mode. The demo timestamp is intentionally not rewritten to the current date. Enrollment switches to real gateway mode.

T3 pairing responses appear only in a temporary view, with a QR image, explicit HTTPS link and expiry. They are not copied, logged or saved. The view is cleared when Bleet loses visibility. An existing T3 HTTPS origin opens only if the host supplies `t3_url`; the host address is never guessed to be a T3 origin.

## Widgets and freshness

Three configurable widgets show CPU cores, a chosen GPU and memory. Small/medium and appropriate accessory families are supported. Machine/GPU App Intents list entities from the last snapshot. Per-core CPU links and resource links restore app selection. No extension networking or credential access occurs. Only the JSON snapshot and a demo label flag are shared via the App Group. Widgets carry the original measurement time; old snapshots show Saved. Timeline entries advance freshness without claiming to collect metrics. Widget reload scheduling is controlled by iOS.

Foreground refresh is every eight seconds, with one coalesced AppStore/client. Requests stop while inactive; losing gateway access retains the prior measurement and its timestamp. Unknown metrics show dashes; zero remains zero. Unified memory is shown once. Exact byte counts, device models and GPU UUIDs are available under Hardware & exact values.

The UI uses native text styles, scrollable content and adaptive grids for Dynamic Type; no continuous metric animation is used. SwiftUI semantic rendering supports system widget tint. The terminal uses the device keyboard and SwiftTerm's accessory keys. Real terminal, VPN, pairing, widget tint, VoiceOver and resize interaction still need device acceptance checks.

## Wordmark

`BleetWordmark` combines the original mint matrix with lowercase rounded `bleet` text in the welcome screen and compact/sidebar titles. It scales with Dynamic Type and exposes one accessible Bleet label. Shared outlined SVG and transparent PNG variants are in [assets/branding](../assets/branding/README.md). The existing opaque 1024px AppIcon is unchanged.
