"""Confluence webhook receiver.

Security tier: **STATE-MUTATING** (persists an event ledger row and enqueues a job). No LLM.
The receiver only validates, authenticates, and records the event, then returns in a few
milliseconds; the page fetch/parse/index runs later on the worker.

security_baseline (surface: POST /confluence/events, tier STATE-MUTATING):
  C1_auth:        covered   - HMAC-SHA256(raw body) vs X-Hub-Signature-256, constant-time;
                              fail-closed when the secret is unset.
  C2_rate_limit:  covered   - per-client-IP sliding window (webhook_rate_limit_per_minute).
  C3_input:       covered   - body-size cap + json parse + Pydantic EventEnvelope;
                              unsubscribed event_types dropped by ingest_event.
  C4_timeout:     covered   - one short DB transaction, no request-path fan-out; the page
                              fetch is deferred to the worker (tenacity retry/backoff).
  C5_output_rate: opted_out - response is a small fixed-size JSON ack, non-streaming.
  C6_redaction:   opted_out - no LLM call on this surface.
  C7_idempotency: covered   - event dedup on payload_hash + partial-unique delivery_id;
                              job enqueue idempotent on idempotency_key (ON CONFLICT).
  C8_concurrency: opted_out - all writes are single-statement idempotent upserts; no
                              shared-row read-modify-write, so no lock is needed.
  C9_audit:       covered   - immutable event_ledger row per delivery + structured
                              webhook_event log line (actor, event_type, page_id, outcome).
  C10_abuse:      covered   - rate limit + body-size cap; unset secret disables the endpoint.
                              Multi-instance scale would move the limiter to Redis (deferred).
"""

from __future__ import annotations

import hmac
import json
from collections.abc import Iterator
from hashlib import sha256

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.features.confluence_sync.application.event_service import ingest_event
from app.features.confluence_sync.schemas.events import parse_webhook_payload
from app.platform.config import Settings, get_settings
from app.platform.logging import get_logger
from app.shared.rate_limiter import SlidingWindowRateLimiter
from schema.engine import session_scope

log = get_logger("webhook")

router = APIRouter(tags=["confluence"])

_SIG_HEADER = "X-Hub-Signature-256"


# -- dependencies (overridable in tests via app.dependency_overrides) ------------------


def get_settings_dep() -> Settings:
    return get_settings()


def get_db() -> Iterator[Session]:
    """One short transaction per request: commit on success, rollback on error."""
    with session_scope() as session:
        yield session


# -- signature verification ------------------------------------------------------------


def _verify_signature(raw_body: bytes, header: str | None, settings: Settings) -> None:
    secret = settings.confluence_webhook_secret
    if not secret:
        # fail closed: an unconfigured secret means the endpoint is not safe to accept
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "webhook secret not configured")
    if not header:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing signature")
    provided = header.split("=", 1)[1] if header.startswith("sha256=") else header
    expected = hmac.new(secret.encode("utf-8"), raw_body, sha256).hexdigest()
    if not hmac.compare_digest(provided, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid signature")


def _rate_limiter(request: Request, settings: Settings) -> SlidingWindowRateLimiter:
    limiter = getattr(request.app.state, "rate_limiter", None)
    if limiter is None:
        limiter = SlidingWindowRateLimiter(settings.webhook_rate_limit_per_minute)
        request.app.state.rate_limiter = limiter
    return limiter


@router.post("/confluence/events")
async def receive_confluence_event(
    request: Request,
    settings: Settings = Depends(get_settings_dep),  # noqa: B008 — FastAPI dependency idiom
    session: Session = Depends(get_db),  # noqa: B008 — FastAPI dependency idiom
) -> dict:
    client_ip = request.client.host if request.client else "unknown"

    if not _rate_limiter(request, settings).allow(client_ip):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "rate limited")

    raw = await request.body()
    if len(raw) > settings.webhook_max_body_bytes:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "payload too large")

    _verify_signature(raw, request.headers.get(_SIG_HEADER), settings)

    try:
        payload = json.loads(raw or b"{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid json") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "expected a json object")

    envelope = parse_webhook_payload(payload)
    result = ingest_event(session, envelope, settings, origin=0)

    log.info(
        "webhook_event",
        event_type=envelope.event_type,
        page_id=envelope.page_id,
        actor=envelope.actor_account_id,
        delivery_id=envelope.delivery_id,
        accepted=result.accepted,
        duplicate=result.duplicate,
        ignored=result.ignored,
        self_generated=result.self_generated,
        job_id=result.job_id,
    )
    return {
        "accepted": result.accepted,
        "duplicate": result.duplicate,
        "ignored": result.ignored,
        "self_generated": result.self_generated,
        "event_id": result.event_id,
        "job_id": result.job_id,
    }
