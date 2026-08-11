"""Event ingest dedup: a duplicate delivery is idempotent and enqueues no second job."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select

from app.features.confluence_sync.application.event_service import ingest_event
from app.features.confluence_sync.schemas.events import EventEnvelope
from app.platform.db.engine import session_scope
from app.platform.db.models import EventLedger, Job


def _envelope() -> EventEnvelope:
    return EventEnvelope(
        event_type="page_updated",
        page_id=1001,
        cf_version=3,
        space_id=100,
        delivery_id="delivery-1",
        event_timestamp=datetime(2026, 6, 1, tzinfo=UTC),
    )


def test_duplicate_delivery_is_idempotent(session, settings):
    with session_scope() as s:
        first = ingest_event(s, _envelope(), settings)
        second = ingest_event(s, _envelope(), settings)

    assert first.accepted and first.job_id is not None
    assert second.accepted and second.duplicate is True

    with session_scope() as s:
        assert s.execute(select(func.count(EventLedger.id))).scalar_one() == 1
        assert s.execute(select(func.count(Job.id))).scalar_one() == 1


def test_same_delivery_id_different_payload_dedupes_gracefully_not_500(session, settings):
    """PLAN 4.6.11: a redelivery sharing `delivery_id` but not `payload_hash` (e.g. Confluence
    resent the same webhook with a bumped `cf_version`) must dedupe as gracefully as an exact
    repeat — not raise an uncaught IntegrityError on `ux_event_ledger_delivery_id`, which
    `on_conflict_do_nothing(index_elements=["payload_hash"])` alone never guarded against."""
    first_envelope = _envelope()
    second_envelope = EventEnvelope(
        event_type=first_envelope.event_type,
        page_id=first_envelope.page_id,
        cf_version=4,  # differs from _envelope()'s 3 -> changes payload_hash
        space_id=first_envelope.space_id,
        delivery_id=first_envelope.delivery_id,  # same delivery_id
        event_timestamp=first_envelope.event_timestamp,
    )

    with session_scope() as s:
        first = ingest_event(s, first_envelope, settings)
        second = ingest_event(s, second_envelope, settings)  # must not raise

    assert first.accepted and first.job_id is not None
    assert second.accepted and second.duplicate is True

    with session_scope() as s:
        assert s.execute(select(func.count(EventLedger.id))).scalar_one() == 1
        assert s.execute(select(func.count(Job.id))).scalar_one() == 1
