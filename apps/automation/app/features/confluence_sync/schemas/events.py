"""Confluence webhook event envelope (validated boundary type)."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

# event types we subscribe to, grouped by the job they trigger
DELETE_EVENTS = {
    "page_trashed",
    "page_archived",
    "page_removed",
    "page_deleted",
}
SYNC_EVENTS = {
    "page_created",
    "page_updated",
    "page_moved",
    "page_restored",
    "page_unarchived",
    "attachment_created",
    "attachment_updated",
    "attachment_removed",
    "label_added",
    "label_deleted",
    "page_permissions_updated",
}
SPACE_EVENTS = {"space_updated", "space_permissions_updated"}
ALL_EVENTS = DELETE_EVENTS | SYNC_EVENTS | SPACE_EVENTS


class EventEnvelope(BaseModel):
    """Minimal, validated view of an inbound webhook payload."""

    event_type: str
    page_id: int | None = None
    cf_version: int | None = None
    space_id: int | None = None
    status: str | None = None
    event_timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    delivery_id: str | None = None
    actor_account_id: str | None = None
    raw: dict = Field(default_factory=dict)

    def canonical_dedup_payload(self) -> dict:
        """The fields that define event identity for dedup (excludes receive time)."""
        return {
            "event_type": self.event_type,
            "page_id": self.page_id,
            "cf_version": self.cf_version,
            "space_id": self.space_id,
            "status": self.status,
            "event_timestamp": self.event_timestamp.isoformat(),
            "delivery_id": self.delivery_id,
        }


def _as_int(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def parse_webhook_payload(payload: dict) -> EventEnvelope:
    """Map a raw Confluence webhook body to the validated :class:`EventEnvelope`.

    Tolerant of the two shapes seen in practice: a nested Confluence event
    (``{"eventType", "page": {...}}`` / ``"content"``) and a flattened shape whose keys already
    match the envelope. Unknown fields are ignored; the full body is retained in ``raw`` for the
    audit ledger. The subscription filter and version guard downstream make a permissive parse
    safe — an unrecognized event_type is simply dropped by ``ingest_event``.
    """
    content = payload.get("page") or payload.get("content") or {}
    version = content.get("version") or {}
    space = payload.get("space") or {}
    actor = payload.get("actor") or {}

    event_type = (
        payload.get("eventType") or payload.get("event") or payload.get("event_type") or ""
    )
    page_id = _as_int(payload.get("page_id") or content.get("id"))
    cf_version = _as_int(payload.get("cf_version") or version.get("number"))
    space_id = _as_int(
        payload.get("space_id") or content.get("spaceId") or space.get("id")
    )
    status = payload.get("status") or content.get("status")
    actor_account_id = (
        payload.get("actor_account_id")
        or payload.get("userAccountId")
        or actor.get("accountId")
    )
    delivery_id = payload.get("delivery_id") or payload.get("deliveryId")

    fields: dict = {
        "event_type": str(event_type),
        "page_id": page_id,
        "cf_version": cf_version,
        "space_id": space_id,
        "status": status,
        "actor_account_id": actor_account_id,
        "delivery_id": delivery_id,
        "raw": payload,
    }
    ts = payload.get("event_timestamp") or payload.get("timestamp")
    if ts:
        fields["event_timestamp"] = ts
    return EventEnvelope(**fields)
