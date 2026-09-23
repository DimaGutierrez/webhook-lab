# Roadmap

This is a plan, not a list of shipped features.

## v0.1 · local workbench (implemented)

- Capture, inspect, download raw body, manually replay.
- Persisted attempt history; local token; named destinations.
- In-process failure/success demo and an external example receiver.
- Automated API tests and an English/Spanish README.

## Launch follow-up

- Verify Docker Compose on a machine with Docker installed.
- Windows and Linux GitHub Actions checks passed after publication; see [current checks](https://github.com/DimaGutierrez/webhook-lab/actions/workflows/ci.yml).
- Record a real 45-second demo with synthetic data.
- Test installation with at least two external developers.
- Collect feedback through the [Wiki](https://github.com/DimaGutierrez/webhook-lab/wiki) and [Discussions](https://github.com/DimaGutierrez/webhook-lab/discussions/3).

## v0.2 · explain the failure

- Live event updates and server-side search.
- Configurable data retention and explicit deletion.
- Compare attempts; make interrupted/pending states prominent.
- Durable receiver example with a unique idempotency constraint.
- Publish a reproducible benchmark with hardware and limitations.

## v0.3 · background delivery

- PostgreSQL migrations and a persistent job queue.
- Worker leases, bounded exponential backoff with jitter, dead-letter inspection.
- Crash recovery tests and per-destination concurrency limits.
- Metrics for queue age, delivery latency and retry outcomes.

## Public hosting gate

Tenant isolation, quotas, ingress rate limits, storage retention, TLS, hardened outbound access, authentication review, and payload handling need their own design before offering a public service. The local prototype is not that service.
