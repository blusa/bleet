# Bleet wordmark

The mark keeps the nine mint squares, with a lowercase rounded `bleet` wordmark beside them. No mascot, badge or extra tagline.

- `bleet-wordmark-on-dark.svg` / `.png`: pale lettering for graphite/dark backgrounds.
- `bleet-wordmark-on-light.svg` / `.png`: graphite lettering for light backgrounds.
- Both SVGs contain outlined glyphs, so recipients need no font installed. Both PNGs have transparent backgrounds and are rendered at 3× (1173 × 432).
- `generate.swift` is the editable macOS source: nine rounded squares and semibold system rounded text, with deliberate optical spacing. Regenerate with `swift assets/branding/generate.swift` from the repository root.

The native `BleetWordmark` in `ios/Bleet/BleetApp.swift` uses the same proportions and system rounded type, scales with Dynamic Type, and exposes one accessible “Bleet” label. The launcher's existing opaque 1024 × 1024 AppIcon remains separate and unchanged.
