"""Change detection & classification (pure domain).

Given the active local state and freshly fetched Confluence metadata (and optionally the body
blocks), decide what changed and whether re-embedding is required. No I/O here — the application
service fetches inputs and applies the resulting actions.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.features.ingestion.domain import normalization as norm
from app.platform.clients.confluence_client import ConfluencePageMeta
from app.platform.db.enums import ChangeClass, PageStatus
from app.platform.hashing import (
    hash_access_scope,
    hash_attachment_manifest,
    hash_labels,
    sha256_text,
)

# Confluence statuses that mean "remove from the live index".
_GONE_STATUSES = {"trashed", "deleted", "archived"}


@dataclass(frozen=True)
class LocalState:
    """Active indexed state of a page (subset of PageSource needed for detection)."""

    current_cf_version: int
    page_status: PageStatus
    title: str
    parent_id: int | None
    content_hash: bytes
    structure_hash: bytes
    attachment_manifest_hash: bytes
    access_scope_hash: bytes
    labels_hash: bytes
    parser_version: int
    chunker_version: int
    contextualization_version: int
    contextualization_and_schema: int  # retrieval_schema_version
    embedding_model: str


@dataclass(frozen=True)
class TargetVersions:
    parser_version: int
    chunker_version: int
    contextualization_version: int
    retrieval_schema_version: int
    embedding_model: str


@dataclass
class ChangeDecision:
    classes: set[ChangeClass] = field(default_factory=set)
    needs_body_fetch: bool = False
    needs_reembed: bool = False
    is_delete: bool = False
    # freshly computed hashes (present only when the body/metadata were available)
    content_hash: bytes | None = None
    structure_hash: bytes | None = None
    labels_hash: bytes | None = None
    access_scope_hash: bytes | None = None
    attachment_manifest_hash: bytes | None = None

    @property
    def meaningful(self) -> bool:
        return self.classes != {ChangeClass.no_change} and bool(self.classes)


def map_page_status(status: str) -> PageStatus:
    try:
        return PageStatus(status)
    except ValueError:
        return PageStatus.current


def index_config_changed(local: LocalState, target: TargetVersions) -> bool:
    return (
        local.parser_version != target.parser_version
        or local.chunker_version != target.chunker_version
        or local.contextualization_version != target.contextualization_version
        or local.contextualization_and_schema != target.retrieval_schema_version
        or local.embedding_model != target.embedding_model
    )


def decide_body_fetch(
    local: LocalState | None, meta: ConfluencePageMeta, target: TargetVersions
) -> bool:
    """Fetch the full body only when content may have changed or must be re-derived."""
    if local is None:
        return meta.status not in _GONE_STATUSES  # first index of a live page
    if meta.status in _GONE_STATUSES:
        return False  # delete/deactivate needs no body
    if meta.version_number > local.current_cf_version:
        return True  # a new source revision exists
    # re-derive under new parser/chunker/model/schema
    return index_config_changed(local, target)


def classify(
    *,
    local: LocalState | None,
    meta: ConfluencePageMeta,
    target: TargetVersions,
    labels: list[str] | None = None,
    restrictions: list[str] | None = None,
    space_key: str | None = None,
    attachments: list[dict] | None = None,
    blocks: list[norm.Block] | None = None,
) -> ChangeDecision:
    """Classify a page change. ``blocks`` is provided iff the body was fetched."""
    decision = ChangeDecision()
    labels = labels or []
    restrictions = restrictions or []
    attachments = attachments or []

    # compute available metadata hashes
    decision.labels_hash = hash_labels(labels)
    decision.access_scope_hash = hash_access_scope(restrictions, space_key)
    decision.attachment_manifest_hash = hash_attachment_manifest(attachments)
    if blocks is not None:
        decision.content_hash = norm.content_hash(blocks)
        decision.structure_hash = norm.structure_hash(blocks)

    status = map_page_status(meta.status)

    # 1. deletion / deactivation short-circuit (bypasses version guard)
    if meta.status in _GONE_STATUSES:
        decision.classes.add(ChangeClass.status_changed)
        decision.is_delete = True
        decision.needs_body_fetch = False
        decision.needs_reembed = False
        return decision

    # 2. first-ever index
    if local is None:
        decision.classes.add(ChangeClass.body_changed)
        decision.needs_body_fetch = True
        decision.needs_reembed = True
        return decision

    cfg_changed = index_config_changed(local, target)

    # 3. version guard: nothing newer and no config change -> no meaningful change
    if meta.version_number <= local.current_cf_version and not cfg_changed:
        # still detect cheap metadata-only drift that does not bump the version
        _classify_metadata(decision, local, meta, status)
        if not decision.classes:
            decision.classes.add(ChangeClass.no_change)
        return decision

    # 4. index-config change forces a rebuild under the new pipeline
    if cfg_changed:
        decision.classes.add(ChangeClass.index_config_change)
        decision.needs_body_fetch = True
        decision.needs_reembed = True

    # 5. metadata comparisons
    _classify_metadata(decision, local, meta, status)

    # 6. body comparisons (only when body was fetched)
    if blocks is not None:
        if decision.content_hash != local.content_hash:
            if decision.structure_hash != local.structure_hash:
                # structure changed -> section-level diff drives the concrete classes
                decision.classes.add(ChangeClass.section_updated)
            else:
                decision.classes.add(ChangeClass.body_changed)
            decision.needs_reembed = True
    elif meta.version_number > local.current_cf_version:
        # a newer revision exists but we have not fetched the body yet
        decision.needs_body_fetch = True

    if not decision.classes:
        decision.classes.add(ChangeClass.no_change)
    return decision


def _classify_metadata(
    decision: ChangeDecision,
    local: LocalState,
    meta: ConfluencePageMeta,
    status: PageStatus,
) -> None:
    if meta.title != local.title:
        decision.classes.add(ChangeClass.title_changed)
    if meta.parent_id != local.parent_id:
        decision.classes.add(ChangeClass.parent_changed)
    if decision.labels_hash is not None and decision.labels_hash != local.labels_hash:
        decision.classes.add(ChangeClass.labels_changed)
    if (
        decision.access_scope_hash is not None
        and decision.access_scope_hash != local.access_scope_hash
    ):
        decision.classes.add(ChangeClass.permissions_changed)
    if (
        decision.attachment_manifest_hash is not None
        and decision.attachment_manifest_hash != local.attachment_manifest_hash
    ):
        decision.classes.add(ChangeClass.attachment_changed)
    if status != local.page_status:
        decision.classes.add(ChangeClass.status_changed)


def section_stable_key(page_id: int, section: norm.Section) -> bytes:
    """Stable section identity: independent of body text and of edits to other sections."""
    return sha256_text(
        str(page_id),
        ">".join(section.heading_path),
        str(section.level),
        str(section.sibling_ordinal),
    )
