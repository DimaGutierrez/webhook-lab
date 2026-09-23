# Webhook Lab

[![Checks](https://github.com/DimaGutierrez/webhook-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/DimaGutierrez/webhook-lab/actions/workflows/ci.yml)

**Follow the event. Understand the failure.**

A local webhook workbench built with Python and FastAPI. Capture an event, inspect its payload, and follow every replay attempt from failure to recovery.

**Status:** working v0.1 local prototype. Single user, one inbox, manual replay. No hosted service or background retry queue yet.

[Español](README.es.md) · [Wiki](https://github.com/DimaGutierrez/webhook-lab/wiki) · [Discussions](https://github.com/DimaGutierrez/webhook-lab/discussions) · [Architecture](docs/architecture.md) · [Roadmap](docs/roadmap.md) · [Security](SECURITY.md)

## Try the story in 60 seconds

1. Start the app and unlock the workbench with your local token.
2. Click **Send sample event**. The browser sends a real POST into your inbox.
3. Replay to **Demo · unavailable (503)**. See the failed attempt appear.
4. Replay to **Demo · accepts (200)**. See the recovery without losing the first attempt.
5. Inspect the original bytes, sanitized headers, timestamps, and replay history.

The two demo destinations are explicitly simulated, in-process HTTP handlers. Configure a named destination to test an actual HTTP connection.

## Quick start · Python 3.12+

Run these commands from this repository's root:

```bash
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows PowerShell instead:
# .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.lock
python -m webhook_lab
```

Open **http://127.0.0.1:8000**. Paste the token stored in `data/admin.token` into the workbench. The token stays in browser memory and is cleared when you lock or reload the page.

If PowerShell blocks activation, use `.\.venv\Scripts\python.exe` directly instead of changing your execution policy.

### Docker alternative

```bash
docker compose up --build
docker compose exec lab cat /app/data/admin.token
```

The Compose service binds to **127.0.0.1**, and stores data in the `lab-data` volume. Container configuration is supplied; Docker execution has not been verified in the initial development environment.

## Capture a webhook

Copy the private URL displayed in the workbench:

```bash
curl -X POST 'http://127.0.0.1:8000/in/YOUR_INBOX_TOKEN' \
  -H 'Content-Type: application/json' \
  -H 'X-Event-Type: order.created' \
  --data '{"order_id":"ORD-1042","amount":4900,"currency":"USD"}'
```

In Windows PowerShell, use `curl.exe` or `Invoke-RestMethod`. Your inbox accepts POST only and returns `201` after persistence. There is a 256 KiB body limit and a 5,000-event capacity; exceeding either returns `413` or `507`, respectively. An inbox at capacity does not silently delete older events.

## Replay to your own service

Destinations are configured by the server operator, not supplied as arbitrary URLs in API requests. Only configure services you own or are authorized to test.

Start the included example receiver in a separate terminal:

```bash
python examples/receiver.py --port 9001 --fail-first 1
```

Then configure the lab and restart it:

```bash
# macOS / Linux
export WLAB_TARGETS='{"local-api":"http://127.0.0.1:9001/webhook"}'
python -m webhook_lab
```

```powershell
# Windows PowerShell
$env:WLAB_TARGETS = '{"local-api":"http://127.0.0.1:9001/webhook"}'
python -m webhook_lab
```

Replay an event to `local-api` three times. The example returns `503`, then `200`, then a deduplicated `200`. Its console shows whether it processed or deduplicated the event. **Deduplication belongs to this example receiver**, uses memory, and resets on restart. Webhook Lab deliberately records all three delivery attempts.

In Docker, `127.0.0.1` identifies the container. Configure the reachable hostname of your receiver; on Docker Desktop, `host.docker.internal` can address a host service.

Replay preserves the body bytes and content type. It adds a stable `Idempotency-Key` equal to the captured event ID and `X-Webhook-Lab-Event-Id`. Captured authorization, cookies, provider signatures, and other headers are **not** forwarded. This is a diagnostic replay, not a byte-for-byte HTTP request clone. Receivers requiring provider signatures need a future signing adapter.

## API

Interactive documentation: `/docs`. Authenticated endpoints require `Authorization: Bearer <admin token>`.

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Database connectivity and app version |
| POST | `/in/{inbox_token}` | Capture body and sanitized headers |
| GET | `/api/config` | Inbox path and named destinations |
| GET | `/api/events?limit=20&offset=0` | Paginated events and aggregate counts |
| GET | `/api/events/{id}` | Payload preview, exact base64 body, attempt history |
| GET | `/api/events/{id}/body` | Download original bytes as an attachment |
| POST | `/api/events/{id}/replay` | One attempt; JSON: `{"target":"demo-success"}` |

A `200` response from the replay API means the attempt was recorded. Check its `status` and `status_code` to determine whether the destination accepted delivery. A destination's `2xx` is not proof that its business logic succeeded.

## Development

```bash
python -m pip install -r requirements-dev.lock
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
```

Tests cover byte preservation, redaction, admin access, size and capacity limits, concurrent capture, persisted history, timeouts, connection failures, redirect blocking, and stable replay keys. The [Checks workflow](https://github.com/DimaGutierrez/webhook-lab/actions/workflows/ci.yml) runs on Windows and Linux; the badge above shows its current status.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `WLAB_HOST` | `127.0.0.1` | Bind address; keep local for this prototype |
| `WLAB_PORT` | `8000` | Listening port |
| `WLAB_DATA_DIR` | `data` | SQLite database and generated token location |
| `WLAB_ADMIN_TOKEN` | Generated locally | At least 24 characters; supply a random token |
| `WLAB_TARGETS` | `{}` | JSON object mapping target names to fixed HTTP(S) URLs |

Targets cannot contain URL credentials, query strings, or fragments. Redirects and environment proxy settings are disabled for replay. The operator controls DNS and destination configuration; this is not a hardened public egress gateway.

## Scope and limits

- Refresh is explicit; there is no live push feed yet.
- One process and one administrator. Do not run multiple workers against this prototype.
- SQLite provides local persistence. PostgreSQL, migrations and a durable worker are on the roadmap.
- Replay is manual, in the request lifecycle. Interrupted attempts are marked at the next startup and are not automatically resent.
- Payloads remain unredacted in a local, unencrypted database. Use synthetic data for demos.
- The app does not deduplicate incoming events or guarantee exactly-once delivery.
- No automatic retention, accounts, billing, telemetry, public tunnel, or public hosting is included.

## Contributing

Start with the [Wiki](https://github.com/DimaGutierrez/webhook-lab/wiki) for installation, replay examples, API configuration and troubleshooting. Then help shape the project:

- [Try the 503 → 200 challenge](https://github.com/DimaGutierrez/webhook-lab/discussions/1) and share the first confusing step.
- [Discuss duplicate webhooks](https://github.com/DimaGutierrez/webhook-lab/discussions/2): how does your receiver handle retries?
- [Choose the next feature](https://github.com/DimaGutierrez/webhook-lab/discussions/3) with a concrete debugging problem it would solve.

English and Spanish comments are welcome. If this tool helps you, a star makes it easy to find again and sharing a reproducible use case helps others try it.

Try the failure-to-recovery flow with a synthetic event and report where the experience becomes confusing. Small reproducible bugs are especially useful. See [CONTRIBUTING.md](CONTRIBUTING.md).

Created by [Diego Gutierrez](https://github.com/DimaGutierrez). MIT license.
