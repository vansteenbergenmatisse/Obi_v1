"""Table-shape tests for event_ledger — panel d-event_ledger, substep 0.5.3.

`test_event_dedup.py` already proves the *behavior* end-to-end through `ingest_event` (a
duplicate delivery dedupes, no second job). These tests prove the table's own shape at the
Postgres level instead: the two UNIQUE constraints firing directly on a raw ORM insert, and the
`event_proc_status` enum accepting exactly its six real values and rejecting anything else.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import DataError, IntegrityError

from schema.enums import EventProcStatus
from schema.models import EventLedger

pytestmark = (
    pytest.mark.db
)  # substep 0.5.3: real local Postgres via this dir's session-scoped conftest


def _row(*, payload_hash: bytes, delivery_id: str | None, **overrides) -> EventLedger:
    fields = dict(
        event_type="page_updated",
        event_timestamp=datetime(2026, 6, 1, tzinfo=UTC),
        page_id=1001,
        cf_version=3,
        space_id=100,
        payload_hash=payload_hash,
        delivery_id=delivery_id,
        origin=0,
        proc_status=EventProcStatus.received,
        self_generated=False,
        payload={},
    )
    fields.update(overrides)
    return EventLedger(**fields)


def test_d_event_ledger_payload_hash_is_unique(session):
    """panel d-event_ledger · substep 0.5.3
    uq_event_ledger_payload_hash: two rows sharing payload_hash (different delivery_id) cannot
    both commit — the second raises IntegrityError on flush."""
    session.add(_row(payload_hash=b"same-hash", delivery_id="delivery-1"))
    session.flush()

    session.add(_row(payload_hash=b"same-hash", delivery_id="delivery-2"))
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_d_event_ledger_delivery_id_partial_unique(session):
    """panel d-event_ledger · substep 0.5.3
    ux_event_ledger_delivery_id is a PARTIAL unique index (WHERE delivery_id IS NOT NULL): two
    rows sharing a non-null delivery_id collide, but two rows both with delivery_id NULL — the
    case explicitly outside the WHERE clause — do not."""
    session.add(_row(payload_hash=b"hash-1", delivery_id="dup-delivery"))
    session.flush()

    session.add(_row(payload_hash=b"hash-2", delivery_id="dup-delivery"))
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()

    # Outside the WHERE clause: two NULL delivery_ids never collide.
    session.add(_row(payload_hash=b"hash-3", delivery_id=None))
    session.add(_row(payload_hash=b"hash-4", delivery_id=None))
    session.flush()  # must not raise


def test_d_event_ledger_proc_status_enum_values(session):
    """panel d-event_ledger · substep 0.5.3
    event_proc_status accepts exactly received/deduped/queued/processing/done/dead_letter and
    rejects a value outside that set."""
    for i, status in enumerate(EventProcStatus):
        session.add(
            _row(
                payload_hash=f"hash-status-{i}".encode(),
                delivery_id=f"delivery-status-{i}",
                proc_status=status,
            )
        )
    session.flush()  # all six real values accepted
    session.rollback()

    session.add(
        _row(payload_hash=b"hash-bad", delivery_id="delivery-bad", proc_status="not_a_real_status")
    )
    with pytest.raises((DataError, LookupError)):
        session.flush()
    session.rollback()
