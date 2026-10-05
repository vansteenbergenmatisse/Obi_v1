"""panel i1-ledger · substep 4.2 (coverage-audit gap G3)

f8098d0 proved *behaviorally* that every delivery surviving ledger dedup enqueues its own job;
these tests pin the literal idempotency-key strings `_enqueue_for_event` builds —
``sync_page:{page_id}:{event_id}``, ``delete_page:{page_id}:{event_id}``,
``reconcile_space:{space_id}:{event_id}`` — so a key that drops the event-ledger id (which would
collide forever: completed jobs are never pruned) or reorders its parts cannot slip back in behind
a still-green behavioral suite. Unit level, no database: ``enqueue_job`` is spied; the session is
only threaded through to it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

import pytest
from sqlalchemy.orm import Session

from app.features.confluence_sync.application import event_service
from app.features.confluence_sync.application.event_service import _enqueue_for_event
from app.features.confluence_sync.schemas.events import EventEnvelope

EVENT_ID = 77


def _envelope(event_type: str) -> EventEnvelope:
    return EventEnvelope(
        event_type=event_type,
        page_id=1001,
        cf_version=3,
        space_id=100,
        delivery_id="delivery-1",
        event_timestamp=datetime(2026, 6, 1, tzinfo=UTC),
    )


def _spy_enqueue(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    captured: dict[str, object] = {}

    def _enqueue(session: object, **kwargs: object) -> int:
        captured.update(kwargs)
        return 1

    monkeypatch.setattr(event_service, "enqueue_job", _enqueue)
    return captured


def test_i1_sync_event_idempotency_key_is_jobtype_page_and_event_id(monkeypatch, settings):
    """panel i1-ledger · substep 4.2 (gap G3)
    A sync-family event's job carries the literal key `sync_page:{page_id}:{event_id}` — the
    event-ledger id included, so a second distinct delivery for the same page still enqueues."""
    captured = _spy_enqueue(monkeypatch)

    _enqueue_for_event(cast(Session, object()), _envelope("page_updated"), settings, EVENT_ID)

    assert captured["job_type"] == "sync_page"
    assert captured["idempotency_key"] == "sync_page:1001:77"


def test_i1_delete_event_idempotency_key_is_jobtype_page_and_event_id(monkeypatch, settings):
    """panel i1-ledger · substep 4.2 (gap G3)
    A delete-family event's job carries the literal key `delete_page:{page_id}:{event_id}` — the
    event-ledger id included, so a second trash after a restore still enqueues."""
    captured = _spy_enqueue(monkeypatch)

    _enqueue_for_event(cast(Session, object()), _envelope("page_trashed"), settings, EVENT_ID)

    assert captured["job_type"] == "delete_page"
    assert captured["idempotency_key"] == "delete_page:1001:77"


def test_i1_space_event_idempotency_key_is_jobtype_space_and_event_id(monkeypatch, settings):
    """panel i1-ledger · substep 4.2 (gap G3)
    A space event's job carries the literal key `reconcile_space:{space_id}:{event_id}` — keyed by
    space (not page) plus the event-ledger id, so repeated space updates each reconcile."""
    captured = _spy_enqueue(monkeypatch)

    _enqueue_for_event(cast(Session, object()), _envelope("space_updated"), settings, EVENT_ID)

    assert captured["job_type"] == "reconcile_space"
    assert captured["idempotency_key"] == "reconcile_space:100:77"
