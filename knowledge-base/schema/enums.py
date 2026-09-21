"""Domain enums, mapped 1:1 to Postgres ENUM types (see migration 0001)."""

from __future__ import annotations

from enum import StrEnum


class PageStatus(StrEnum):
    current = "current"
    draft = "draft"
    trashed = "trashed"
    archived = "archived"
    deleted = "deleted"


class DocState(StrEnum):
    staging = "staging"
    active = "active"
    superseded = "superseded"
    failed = "failed"


class EventProcStatus(StrEnum):
    received = "received"
    deduped = "deduped"
    queued = "queued"
    processing = "processing"
    done = "done"
    dead_letter = "dead_letter"


class JobStatus(StrEnum):
    pending = "pending"
    # `claim_job` transitions straight to `running`; `leased` is never assigned, only read
    # defensively in `reap_expired`'s recoverable-states filter. `cancelled` has no producer or
    # consumer at all. Both are accepted no-ops (PLAN 4.6.13) — dropping them buys nothing since
    # this is a native Postgres ENUM type, not a plain column check.
    leased = "leased"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    dead_letter = "dead_letter"
    cancelled = "cancelled"


class ReconStatus(StrEnum):
    running = "running"
    completed = "completed"
    failed = "failed"


class ChangeClass(StrEnum):
    no_change = "no_change"
    body_changed = "body_changed"
    section_added = "section_added"
    section_updated = "section_updated"
    section_removed = "section_removed"
    section_moved = "section_moved"
    title_changed = "title_changed"
    parent_changed = "parent_changed"
    labels_changed = "labels_changed"
    attachment_changed = "attachment_changed"
    permissions_changed = "permissions_changed"
    status_changed = "status_changed"
    parser_only = "parser_only"
    index_config_change = "index_config_change"
    full_rebuild = "full_rebuild"


# Postgres ENUM type names (referenced by models + migration)
PG_ENUMS: dict[str, type[StrEnum]] = {
    "page_status": PageStatus,
    "doc_state": DocState,
    "event_proc_status": EventProcStatus,
    "job_status": JobStatus,
    "recon_status": ReconStatus,
    "change_class": ChangeClass,
}
