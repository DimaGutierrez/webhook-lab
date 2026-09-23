# Verification · 2026-09-22

Local environment: Windows, Python 3.12.14. Dependencies are pinned in the lock files.

## Completed

- `python -m pytest -q`: **18 passed**.
- `python -m ruff check .`: passed.
- `python -m ruff format --check .`: passed.
- `node --check webhook_lab/static/app.js`: passed.
- Browser: login, sample capture, 503 demo replay, 200 demo replay, payload inspection, attempt history.
- Browser: desktop and mobile layout checks; no horizontal document overflow at 1366 px or 390 px; no console warnings/errors observed during the tested flow.
- Real local HTTP: app on port 8765 and example receiver on port 8766. The same event produced 503, then 200, then 200. Receiver output confirmed `simulated_failure`, `processed`, `deduplicated`, with exactly one processed event in that in-memory example.
- Database persisted across a server restart.

## Not yet verified

- Docker build and Compose startup: Docker is not installed in this environment.
- GitHub Actions on Linux/Windows: configuration supplied; consult the repository's Actions tab for current remote results. This document records local verification before the first CI run.
- Load, sustained concurrency, production deployment and public security isolation.
- Installation by an independent developer.

## Dependency notices

The passing test run reports two upstream deprecation warnings: Starlette's HTTPX test-client integration and its AnyIO BlockingPortal alias. They do not fail the current tests; revisit the test-client dependency choices when updating the lock files. No warnings were suppressed.
