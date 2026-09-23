import base64
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from webhook_lab.config import Settings
from webhook_lab.replay import deliver
from webhook_lab.store import CapacityError, Store

SAFE_HEADERS = {
    "content-type",
    "user-agent",
    "x-github-event",
    "x-github-delivery",
    "x-event-type",
    "idempotency-key",
    "traceparent",
}
STATIC = Path(__file__).parent / "static"


class ReplayRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target: str = Field(min_length=1, max_length=80)


def create_app(settings: Settings | None = None, transport: httpx.AsyncBaseTransport | None = None):
    settings = settings or Settings.from_env()
    store = Store(settings.database)
    demo = FastAPI()

    @demo.post("/{outcome}")
    async def demo_receiver(outcome: str):
        return JSONResponse({"demo": True}, status_code=200 if outcome == "success" else 503)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        store.initialize()
        async with (
            httpx.AsyncClient(
                timeout=10,
                follow_redirects=False,
                trust_env=False,
                transport=transport,
            ) as external,
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=demo),
                base_url="http://demo",
                follow_redirects=False,
            ) as demo_client,
        ):
            app.state.external = external
            app.state.demo_client = demo_client
            yield

    app = FastAPI(title="Webhook Lab", version="0.1.0", lifespan=lifespan)
    app.state.store = store

    async def authorize(authorization: Annotated[str | None, Header()] = None):
        expected = f"Bearer {settings.admin_token}"
        if not authorization or not secrets.compare_digest(
            authorization.encode(), expected.encode()
        ):
            raise HTTPException(401, "Admin token required", headers={"WWW-Authenticate": "Bearer"})

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Frame-Options"] = "DENY"
        if request.url.path == "/" or request.url.path.startswith("/static/"):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; style-src 'self'; "
                "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
            )
        return response

    @app.get("/", include_in_schema=False)
    async def index():
        return FileResponse(STATIC / "index.html")

    @app.get("/health")
    def health():
        store.stats()
        return {"status": "ok", "version": "0.1.0"}

    @app.post("/in/{token}", status_code=201, tags=["capture"])
    async def capture(token: str, request: Request):
        if not secrets.compare_digest(token.encode(), store.inbox_token().encode()):
            raise HTTPException(404, "Inbox not found")
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > settings.max_body_bytes:
                raise HTTPException(413, "Payload exceeds 256 KiB limit")
            body.extend(chunk)
        headers = {
            name: value if name in SAFE_HEADERS else "[redacted]"
            for name, value in request.headers.items()
        }
        try:
            event_id = store.capture(bytes(body), headers, settings.max_events)
        except CapacityError:
            raise HTTPException(507, "Local event capacity reached") from None
        return {"id": event_id, "status": "captured"}

    admin = [Depends(authorize)]

    @app.get("/api/config", dependencies=admin)
    def config():
        return {
            "inbox_path": f"/in/{store.inbox_token()}",
            "targets": [
                {"id": "demo-success", "name": "Demo · accepts (200)", "demo": True},
                {"id": "demo-failure", "name": "Demo · unavailable (503)", "demo": True},
                *[{"id": name, "name": name, "demo": False} for name in settings.targets],
            ],
            "max_body_bytes": settings.max_body_bytes,
        }

    @app.get("/api/events", dependencies=admin)
    def events(
        limit: Annotated[int, Query(ge=1, le=100)] = 100,
        offset: Annotated[int, Query(ge=0)] = 0,
    ):
        return {"items": store.events(limit, offset), "stats": store.stats()}

    def find_event(event_id):
        event = store.event(event_id)
        if not event:
            raise HTTPException(404, "Event not found")
        return event

    @app.get("/api/events/{event_id}", dependencies=admin)
    def detail(event_id: str):
        event = find_event(event_id)
        raw = event.pop("body")
        return event | {
            "body_text": raw.decode("utf-8", errors="replace"),
            "body_base64": base64.b64encode(raw).decode("ascii"),
            "attempts": store.attempts(event_id),
        }

    @app.get("/api/events/{event_id}/body", dependencies=admin)
    def download(event_id: str):
        event = find_event(event_id)
        return Response(
            event["body"],
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{event["id"]}.bin"'},
        )

    @app.post("/api/events/{event_id}/replay", dependencies=admin)
    async def replay(event_id: str, payload: ReplayRequest):
        event = find_event(event_id)
        if payload.target in {"demo-success", "demo-failure"}:
            url = "http://demo/" + payload.target.removeprefix("demo-")
            client = app.state.demo_client
        elif payload.target in settings.targets:
            url = settings.targets[payload.target]
            client = app.state.external
        else:
            raise HTTPException(422, "Choose a target configured by the server administrator")
        return await deliver(store, event, payload.target, url, client)

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app
