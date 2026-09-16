"""Webhook security + ingest: HMAC auth, size cap, rate limit, dedup, self-event suppression."""

from __future__ import annotations

import hmac
import json
from hashlib import sha256

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.features.confluence_sync.server.webhook import get_settings_dep
from app.main import create_app
from app.platform.config import Settings
from app.platform.db.engine import session_scope
from app.platform.db.models import Job

pytestmark = (
    pytest.mark.db
)  # substep 0.5.1: real local Postgres via this dir's session-scoped conftest

_SECRET = "test-webhook-secret"


def make_client(settings: Settings) -> TestClient:
    app = create_app(settings=settings, start_scheduler=False)
    app.dependency_overrides[get_settings_dep] = lambda: settings
    return TestClient(app)


def sign(raw: bytes, secret: str = _SECRET) -> dict[str, str]:
    return {"X-Hub-Signature-256": "sha256=" + hmac.new(secret.encode(), raw, sha256).hexdigest()}


def event_body(**overrides) -> dict:
    body = {
        "eventType": "page_updated",
        "page": {"id": "1001", "spaceId": "100", "status": "current", "version": {"number": 3}},
        "actor": {"accountId": "acct-alice"},
        "timestamp": "2026-06-01T00:00:00Z",
    }
    body.update(overrides)
    return body


def _job_count() -> int:
    with session_scope() as s:
        return s.execute(select(func.count(Job.id))).scalar_one()


def test_valid_signed_event_is_accepted_and_enqueued(webhook_settings):
    client = make_client(webhook_settings)
    raw = json.dumps(event_body()).encode()
    resp = client.post("/confluence/events", content=raw, headers=sign(raw))
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["accepted"] is True
    assert payload["job_id"] is not None
    assert _job_count() == 1


def test_missing_signature_is_rejected(webhook_settings):
    client = make_client(webhook_settings)
    raw = json.dumps(event_body()).encode()
    resp = client.post("/confluence/events", content=raw)
    assert resp.status_code == 401
    assert _job_count() == 0


def test_bad_signature_is_rejected(webhook_settings):
    client = make_client(webhook_settings)
    raw = json.dumps(event_body()).encode()
    resp = client.post("/confluence/events", content=raw, headers=sign(raw, "wrong-secret"))
    assert resp.status_code == 401
    assert _job_count() == 0


def test_duplicate_delivery_is_deduped(webhook_settings):
    client = make_client(webhook_settings)
    raw = json.dumps(event_body()).encode()
    first = client.post("/confluence/events", content=raw, headers=sign(raw))
    second = client.post("/confluence/events", content=raw, headers=sign(raw))
    assert first.json()["job_id"] is not None
    assert second.json()["duplicate"] is True
    assert _job_count() == 1


def test_self_generated_event_enqueues_no_job(webhook_settings):
    client = make_client(webhook_settings)
    raw = json.dumps(
        event_body(actor={"accountId": webhook_settings.confluence_service_account_id})
    ).encode()
    resp = client.post("/confluence/events", content=raw, headers=sign(raw))
    body = resp.json()
    assert body["self_generated"] is True
    assert body["job_id"] is None
    assert _job_count() == 0


def test_oversized_body_is_rejected(webhook_settings):
    client = make_client(webhook_settings.model_copy(update={"webhook_max_body_bytes": 256}))
    raw = json.dumps(event_body(padding="x" * 1024)).encode()
    resp = client.post("/confluence/events", content=raw, headers=sign(raw))
    assert resp.status_code == 413


def test_unset_secret_fails_closed(settings):
    # `settings` fixture has no webhook secret configured
    client = make_client(settings)
    raw = json.dumps(event_body()).encode()
    resp = client.post("/confluence/events", content=raw, headers=sign(raw))
    assert resp.status_code == 503


def test_rate_limit_returns_429(webhook_settings):
    client = make_client(webhook_settings.model_copy(update={"webhook_rate_limit_per_minute": 2}))
    raw = json.dumps(event_body()).encode()
    codes = [
        client.post("/confluence/events", content=raw, headers=sign(raw)).status_code
        for _ in range(3)
    ]
    assert codes[-1] == 429
