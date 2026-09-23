# Security scope

Webhook Lab v0.1 is a local, single-user development tool. Bind to loopback. Do not expose this build as a public service.

- The inbox URL is a capture capability. Anyone who knows it can submit events.
- An independent admin token protects event inspection and replay. Keep `data/admin.token` private. File permissions are best-effort on Windows; directory access control remains the user's responsibility.
- Bodies are stored unchanged, unencrypted. **Header redaction does not redact payloads.** Do not use real customer or payment data in demos.
- Only a small diagnostic header allowlist keeps values. All other values are replaced before persistence. Query strings are not stored.
- Raw bodies download as attachments; previews use text nodes; the workbench has a restrictive CSP and no third-party assets. The optional `/docs` page uses FastAPI's standard external Swagger assets.
- Replay destinations are trusted server configuration. Private addresses are intentionally allowed for local testing. This is not sufficient SSRF isolation for a public multi-user deployment; configure egress controls before changing that scope.
- Redirects, captured credentials, and captured signatures are not forwarded. Outgoing attempts have bounded timeouts; response bodies are not stored.
- Token auth and a 256 KiB body limit do not replace public rate limits, tenant isolation or total-storage quotas. There is an event-count cap, but no attempt-count cap or automatic retention yet.
- The example receiver listens on loopback and keeps idempotency data in memory. It is instructional, not production infrastructure.

For a suspected vulnerability, avoid putting credentials or private payloads in a public issue. Use the maintainer's contact link from their GitHub profile to arrange a private report.
