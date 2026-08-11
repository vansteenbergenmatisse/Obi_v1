"""Persistence for the event ledger (dedup + status transitions)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.features.confluence_sync.schemas.events import EventEnvelope
from app.platform.db.enums import EventProcStatus, PageStatus
from app.platform.db.models import EventLedger
from app.shared.hashing import hash_json


def _status_enum(status: str | None) -> PageStatus | None:
    if not status:
        return None
    try:
        return PageStatus(status)
    except ValueError:
        return None


def record_event(
    session: Session, envelope: EventEnvelope, *, origin: int, self_generated: bool
) -> int | None:
    """Insert an event idempotently. Returns the new id, or None if a duplicate.

    Two independent unique constraints can both mean "duplicate": `uq_event_ledger_payload_hash`
    (same canonical content) and `ux_event_ledger_delivery_id` (same delivery, even if a field
    Confluence resends non-deterministically makes the hash differ). A target-less
    `ON CONFLICT DO NOTHING` — no `index_elements` — absorbs a violation on *either* constraint in
    one round trip, instead of only the one named; a redelivery with the same `delivery_id` but a
    different `payload_hash` no longer raises an uncaught `IntegrityError` (PLAN 4.6.11).
    """
    payload_hash = hash_json(envelope.canonical_dedup_payload())
    stmt = (
        pg_insert(EventLedger)
        .values(
            event_type=envelope.event_type,
            event_timestamp=envelope.event_timestamp,
            page_id=envelope.page_id,
            cf_version=envelope.cf_version,
            space_id=envelope.space_id,
            source_status=_status_enum(envelope.status),
            payload_hash=payload_hash,
            delivery_id=envelope.delivery_id,
            origin=origin,
            self_generated=self_generated,
            proc_status=EventProcStatus.received,
            payload=envelope.raw or envelope.canonical_dedup_payload(),
        )
        .on_conflict_do_nothing()
        .returning(EventLedger.id)
    )
    return session.execute(stmt).scalar_one_or_none()


def mark_status(
    session: Session, event_id: int, status: EventProcStatus, *, reason: str | None = None
) -> None:
    ev = session.get(EventLedger, event_id)
    if ev is None:
        return
    ev.proc_status = status
    if status in (EventProcStatus.done, EventProcStatus.dead_letter):
        ev.processed_at = datetime.now(UTC)
    if reason:
        ev.dead_letter_reason = reason
    session.flush()
