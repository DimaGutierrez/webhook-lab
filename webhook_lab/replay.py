import asyncio
from time import perf_counter

import httpx

from webhook_lab.store import Store


async def deliver(store: Store, event: dict, target: str, url: str, client: httpx.AsyncClient):
    """One explicit attempt. Never retry a side effect automatically."""
    attempt_id = store.begin_attempt(event["id"], target)
    started = perf_counter()
    status_code = None
    error = None
    status = "failed"
    # Do not replay captured credentials, cookies, host or provider signatures.
    headers = {
        "content-type": event["headers"].get("content-type", "application/octet-stream"),
        "x-webhook-lab-event-id": event["id"],
        "idempotency-key": event["id"],
    }
    try:
        async with asyncio.timeout(12):
            # Read only response headers: a destination cannot exhaust memory with its body.
            async with client.stream(
                "POST", url, content=event["body"], headers=headers
            ) as response:
                status_code = response.status_code
                status = "delivered" if 200 <= status_code < 300 else "failed"
                if status != "delivered":
                    error = f"Destination returned HTTP {status_code}"
    except (TimeoutError, httpx.TimeoutException):
        error = "Destination timed out"
    except httpx.HTTPError:
        error = "Destination connection failed"
    except asyncio.CancelledError:
        store.finish_attempt(
            attempt_id,
            round((perf_counter() - started) * 1000),
            "interrupted",
            None,
            "Request cancelled before completion",
        )
        raise
    return store.finish_attempt(
        attempt_id, round((perf_counter() - started) * 1000), status, status_code, error
    )
