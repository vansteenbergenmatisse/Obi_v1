"""Webhook ingest path: validate -> self-event check -> dedup+persist -> enqueue idempotent job.

The full page fetch/parse/index NEVER happens here — that is deferred to a background job so the
webhook can acknowledge in a few milliseconds. Idempotency + the worker's version guard make
duplicated / delayed / out-of-order deliveries safe.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.features.confluence_sync.infrastructure import event_repo
from app.features.confluence_sync.schemas.events import (
    ALL_EVENTS,
    DELETE_EVENTS,
    SPACE_EVENTS,
    EventEnvelope,
)
from app.platform.config import Settings
from app.platform.jobs import enqueue_job
from schema.enums import EventProcStatus

JOB_SYNC_PAGE = "sync_page"
JOB_DELETE_PAGE = "delete_page"
JOB_RECONCILE_SPACE = "reconcile_space"


@dataclass
class IngestResult:
    accepted: bool
    duplicate: bool = False
    self_generated: bool = False
    ignored: bool = False
    event_id: int | None = None
    job_id: int | None = None
    reason: str = ""


def ingest_event(
    session: Session, envelope: EventEnvelope, settings: Settings, *, origin: int = 0
) -> IngestResult:
    if envelope.event_type not in ALL_EVENTS:
        return IngestResult(accepted=False, ignored=True, reason="unsubscribed_event_type")

    self_generated = bool(
        settings.confluence_service_account_id
        and envelope.actor_account_id == settings.confluence_service_account_id
    )

    event_id = event_repo.record_event(
        session, envelope, origin=origin, self_generated=self_generated
    )
    if event_id is None:
        return IngestResult(accepted=True, duplicate=True, reason="duplicate_event")

    if self_generated:
        event_repo.mark_status(session, event_id, EventProcStatus.done, reason="self_generated")
        return IngestResult(accepted=True, self_generated=True, event_id=event_id)

    job_id = _enqueue_for_event(session, envelope, settings, event_id)
    event_repo.mark_status(session, event_id, EventProcStatus.queued)
    return IngestResult(accepted=True, event_id=event_id, job_id=job_id)


def _enqueue_for_event(
    session: Session, envelope: EventEnvelope, settings: Settings, event_id: int
) -> int | None:
    schema = settings.retrieval_schema_version
    if envelope.event_type in SPACE_EVENTS:
        key = f"{JOB_RECONCILE_SPACE}:{envelope.space_id}:{event_id}"
        return enqueue_job(
            session,
            job_type=JOB_RECONCILE_SPACE,
            idempotency_key=key,
            payload={"space_id": envelope.space_id},
            source_event_id=event_id,
        )
    if envelope.event_type in DELETE_EVENTS:
        key = f"{JOB_DELETE_PAGE}:{envelope.page_id}:{envelope.event_type}"
        return enqueue_job(
            session,
            job_type=JOB_DELETE_PAGE,
            idempotency_key=key,
            payload={"status": envelope.status or "trashed"},
            page_id=envelope.page_id,
            cf_version=envelope.cf_version,
            priority=50,  # deletions are higher priority
            source_event_id=event_id,
        )
    # everything else -> sync_page (re-fetch, classify, version-guard on the worker)
    ver = envelope.cf_version if envelope.cf_version is not None else "na"
    key = f"{JOB_SYNC_PAGE}:{envelope.page_id}:{envelope.event_type}:{ver}:{schema}"
    return enqueue_job(
        session,
        job_type=JOB_SYNC_PAGE,
        idempotency_key=key,
        payload={"event_type": envelope.event_type},
        page_id=envelope.page_id,
        cf_version=envelope.cf_version,
        source_event_id=event_id,
    )
