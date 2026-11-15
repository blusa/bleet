# Bleet privacy

Effective November 15, 2026. Bleet is a native client for your own private fleet gateway. It includes no advertising, analytics, tracking or third-party AI integration.

Bleet connects to the HTTPS gateway you configure. That gateway processes enrollment requests, device authorization, hardware readings, terminal sessions and explicit T3 pairing requests. Its administrator controls host access, configured code roots and data retention. The supplied single-gateway backend stores token hashes, up to 720 metric samples per host and up to 1,000 status events. It does not store terminal transcripts or T3 pairing credentials.

The iOS app stores its device token in this device’s Keychain. It shares only the last hardware snapshot, original measurement time and demo label with its widgets. Widgets have no device token and make no network requests. Removing the device credential clears local access and the shared snapshot; the gateway administrator can revoke server authorization. Existing terminal sessions must also be closed separately.

Enrollment codes are temporary and single use. T3 pairing links and QR codes grant pairing authority until expiry; Bleet shows them temporarily without saving or copying them. Opening a link passes it to the selected browser and T3 service, which can retain it. Do not share pairing credentials with unintended recipients.

Demo readings are bundled examples and clearly labeled. Shell sessions run with the configured gateway SSH user’s permissions. No camera, location, contacts, health or microphone permission is requested.

For questions, contact the developer through [the Bleet repository](https://github.com/blusa/bleet/issues). For private gateway data, contact the administrator of that gateway. Do not include credentials in support requests.
