import base64
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from fastapi.testclient import TestClient

from webhook_lab.app import create_app
from webhook_lab.config import Settings
from webhook_lab.store import CapacityError, Store

TOKEN = "test-token-that-is-long-enough-for-local-tests"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def test_empty_targets_environment_uses_default(tmp_path, monkeypatch):
    monkeypatch.setenv("WLAB_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("WLAB_ADMIN_TOKEN", TOKEN)
    monkeypatch.setenv("WLAB_TARGETS", "")
    assert Settings.from_env().targets == {}


@pytest.fixture
def settings(tmp_path):
    return Settings(database=tmp_path / "test.sqlite3", admin_token=TOKEN)


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as session:
        yield session


def inbox(client):
    return client.get("/api/config", headers=AUTH).json()["inbox_path"]


def capture(client, body=b'{"type":"test.event"}', headers=None):
    response = client.post(inbox(client), content=body, headers=headers or {})
    assert response.status_code == 201
    return response.json()["id"]


def replay(client, event_id, target):
    return client.post(
        f"/api/events/{event_id}/replay",
        json={"target": target},
        headers=AUTH,
    )


def test_admin_routes_require_token_but_capture_uses_its_own_secret(client):
    for path in ["/api/config", "/api/events", "/api/events/nope", "/api/events/nope/body"]:
        assert client.get(path).status_code == 401
        assert client.get(path, headers={"Authorization": "Bearer incorrect"}).status_code == 401
    assert (
        client.post("/api/events/nope/replay", json={"target": "demo-success"}).status_code == 401
    )
    assert client.post("/in/wrong", content=b"test").status_code == 404
    assert client.post("/in/%C3%B1", content=b"test").status_code == 404
    assert client.get(inbox(client)).status_code == 405
    assert client.get("/health").json()["status"] == "ok"


def test_exact_binary_body_persisted_and_credentials_redacted(client, settings):
    body = b'\xff\x00{"spaces":  true}\r\n'
    event_id = capture(
        client,
        body,
        {
            "Content-Type": "application/octet-stream",
            "Authorization": "Bearer secret",
            "Cookie": "session=secret",
            "X-Api-Key": "secret",
            "X-Github-Event": "push",
            "X-Hub-Signature-256": "secret",
        },
    )
    result = client.get(f"/api/events/{event_id}", headers=AUTH).json()
    assert base64.b64decode(result["body_base64"]) == body
    assert result["size"] == len(body)
    assert result["headers"]["x-github-event"] == "push"
    for header in ["authorization", "cookie", "x-api-key", "x-hub-signature-256"]:
        assert result["headers"][header] == "[redacted]"
    raw = client.get(f"/api/events/{event_id}/body", headers=AUTH)
    assert raw.content == body
    assert raw.headers["content-type"] == "application/octet-stream"
    assert "attachment" in raw.headers["content-disposition"]
    assert Store(settings.database).event(event_id)["body"] == body


def test_size_limit_rejects_without_persisting(client, settings):
    path = inbox(client)
    assert client.post(path, content=b"x" * settings.max_body_bytes).status_code == 201
    assert client.post(path, content=b"x" * (settings.max_body_bytes + 1)).status_code == 413
    assert client.get("/api/events", headers=AUTH).json()["stats"]["events"] == 1


def test_demo_failure_then_success_has_two_distinct_attempts(client):
    event_id = capture(client)
    failed = replay(client, event_id, "demo-failure").json()
    delivered = replay(client, event_id, "demo-success").json()
    assert (failed["status"], failed["status_code"]) == ("failed", 503)
    assert (delivered["status"], delivered["status_code"]) == ("delivered", 200)
    assert failed["id"] != delivered["id"]
    result = client.get("/api/events", headers=AUTH).json()
    assert result["stats"] == {
        "events": 1,
        "attempts": 2,
        "outcomes": {"delivered": 1, "failed": 1},
    }
    assert result["items"][0]["last_status"] == "delivered"
    detail = client.get(f"/api/events/{event_id}", headers=AUTH).json()
    assert len(detail["attempts"]) == 2


def test_target_url_cannot_be_supplied_by_request(client):
    event_id = capture(client)
    assert replay(client, event_id, "http://169.254.169.254/latest/meta-data").status_code == 422
    response = client.post(
        f"/api/events/{event_id}/replay",
        headers=AUTH,
        json={
            "target": "demo-success",
            "url": "http://unconfigured.example",
        },
    )
    assert response.status_code == 422
    assert client.get("/api/events", headers=AUTH).json()["stats"]["attempts"] == 0


def test_external_replay_preserves_bytes_and_stable_key_without_credentials(tmp_path):
    requests = []

    def receive(request):
        requests.append(request)
        return httpx.Response(204)

    settings = Settings(tmp_path / "lab.db", TOKEN, {"receiver": "http://receiver.test/hook"})
    body = b'{  "original": true }\n'
    with TestClient(create_app(settings, httpx.MockTransport(receive))) as client:
        event_id = capture(
            client, body, {"Content-Type": "application/json", "Authorization": "secret"}
        )
        assert replay(client, event_id, "receiver").json()["status"] == "delivered"
        assert replay(client, event_id, "receiver").json()["status"] == "delivered"
    assert len(requests) == 2
    for request in requests:
        assert request.content == body
        assert request.headers["idempotency-key"] == event_id
        assert request.headers["x-webhook-lab-event-id"] == event_id
        assert request.headers["content-type"] == "application/json"
        assert "authorization" not in request.headers
        assert "cookie" not in request.headers


@pytest.mark.parametrize("failure", ["timeout", "connection", "redirect"])
def test_failures_recorded_and_redirects_not_followed(tmp_path, failure):
    calls = []

    def receive(request):
        calls.append(request)
        if failure == "timeout":
            raise httpx.ReadTimeout("contains-sensitive-url", request=request)
        if failure == "connection":
            raise httpx.ConnectError("contains-sensitive-url", request=request)
        return httpx.Response(302, headers={"Location": "http://forbidden.test"})

    settings = Settings(tmp_path / "lab.db", TOKEN, {"receiver": "http://receiver.test/hook"})
    with TestClient(create_app(settings, httpx.MockTransport(receive))) as client:
        result = replay(client, capture(client), "receiver").json()
        assert result["status"] == "failed"
        assert "contains-sensitive-url" not in result["error"]
        assert len(calls) == 1
        assert result["status_code"] == (302 if failure == "redirect" else None)


def test_restart_preserves_events_inbox_and_marks_unfinished_attempts(settings):
    with TestClient(create_app(settings)) as client:
        path = inbox(client)
        event_id = capture(client)
        client.app.state.store.begin_attempt(event_id, "demo-success")
    with TestClient(create_app(settings)) as client:
        assert inbox(client) == path
        result = client.get(f"/api/events/{event_id}", headers=AUTH).json()
        assert result["attempts"][0]["status"] == "interrupted"


def test_pagination_validation_and_missing_events(client):
    ids = [capture(client) for _ in range(3)]
    result = client.get("/api/events?limit=1&offset=1", headers=AUTH).json()
    assert len(result["items"]) == 1
    assert result["items"][0]["id"] == ids[1]
    assert result["stats"]["events"] == 3
    assert client.get("/api/events?limit=101", headers=AUTH).status_code == 422
    assert client.get("/api/events?offset=-1", headers=AUTH).status_code == 422
    assert client.get("/api/events/nope", headers=AUTH).status_code == 404
    assert replay(client, "nope", "demo-success").status_code == 404


def test_capacity_is_atomic_under_concurrent_capture(tmp_path):
    store = Store(tmp_path / "lab.db")
    store.initialize()

    def insert(_):
        try:
            store.capture(b"event", {}, 5)
            return True
        except CapacityError:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(insert, range(20))) == 5
    assert store.stats()["events"] == 5


def test_full_capacity_returns_507(tmp_path):
    settings = Settings(tmp_path / "lab.db", TOKEN, max_events=1)
    with TestClient(create_app(settings)) as client:
        capture(client)
        assert client.post(inbox(client), content=b"another").status_code == 507


@pytest.mark.parametrize(
    "url", ["file:///etc/passwd", "http://user:pass@host", "https://host/?token=x"]
)
def test_invalid_target_configuration_rejected(tmp_path, url):
    with pytest.raises(ValueError):
        Settings(tmp_path / "lab.db", TOKEN, {"receiver": url})


def test_static_app_has_no_external_assets_and_security_headers(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Follow the event" in response.text
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert response.headers["cache-control"] == "no-store"
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/openapi.json").status_code == 200
