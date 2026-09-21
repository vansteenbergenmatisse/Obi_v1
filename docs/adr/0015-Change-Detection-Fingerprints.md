# 0015 — Change-Detection Fingerprints

Status: Accepted
Date: 2026-09-18
Governs: apps/automation (ingestion, confluence_sync, shared/hashing, platform/db)

> **Retroactive ADR.** This records a decision already shipped and covered by tests; it
> documents existing behavior, it does not change it. Written to close a documentation
> gap (cm-docs). No dedicated ADR previously described the fingerprints or the change
> classes they drive.

## Context

On every sync of a Confluence page, ingestion must decide whether to **rebuild** the page
(re-chunk and re-embed — expensive, and it embeds the whole page per ADR-0002 §6 and the
never-bend rule "a rebuild embeds the whole page") or apply a cheap **metadata-only**
update. Only a change to the retrieved content or the pipeline config should cost a
re-embed. Label edits, permission changes and attachment swaps must not.

To decide this deterministically — tolerating duplicated, delayed and out-of-order webhook
events (ADR-0002 §1) — the sync needs a stable, comparable fingerprint of each independent
facet of a page, persisted from the last successful sync.

## Decision

1. **Deterministic SHA-256 fingerprints**, 32 bytes, stored as BYTEA. Helpers live in one
   place, `apps/automation/app/shared/hashing.py`, with explicit canonicalization: NFC
   normalize + whitespace-collapse for text, sorted-key compact JSON for structures, a
   `\x1f` unit separator between parts. Change-detection state is always a hash, never raw
   content.

2. **Three metadata fingerprints**, computed together in
   `apps/automation/app/features/ingestion/domain/change_detection.py::classify()`
   (lines 122-124), alongside the body `content_hash` / `structure_hash` from
   normalization:
   - `hash_labels(labels)` — the deduped, normalized, sorted label set (`labels_hash`).
   - `hash_access_scope(read_account_ids, space_key)` — the **permission fingerprint**:
     sorted read-restriction principals plus the space key.
   - `hash_attachment_manifest(attachments)` — an order-independent hash of each
     attachment's `(id, version, fileSize, mediaType)`.

3. **Fingerprint comparison yields change classes.** `_classify_metadata`
   (change_detection.py:183-206) compares each freshly computed hash to the persisted
   `LocalState`: a differing `labels_hash` → `labels_changed`, `access_scope_hash` →
   `permissions_changed`, `attachment_manifest_hash` → `attachment_changed`.

4. **Only content/structure changes trigger a re-embed.** `_REBUILD_CLASSES`
   (`apps/automation/app/features/confluence_sync/application/sync_service.py:36-43`) is
   exactly `{body_changed, section_added, section_updated, section_removed, section_moved,
   index_config_change}`. `labels_changed`, `permissions_changed` and `attachment_changed`
   are deliberately excluded: they take the metadata-only path, which updates the tags,
   hashes and `access_scope` on `page_source` and propagates to chunks **without
   re-embedding**. A change to `access_scope_hash` independently drives restriction
   replacement onto every chunk (sync_service.py:143, 295-296).

5. **Re-embed reuse is gated separately** by pipeline-config match
   (`versioning.reusable_active_children`, versioning.py:258-272), never by these metadata
   hashes. A pipeline/embedding-model change forces a full re-embed regardless of them.

## Reason / Consequences

- Cheap changes stay cheap: a label-only edit leaves embeddings byte-identical and creates
  no new `document_version` (test_scope_tagging_retag.py).
- `attachment_changed` is excluded from rebuild specifically to avoid colliding with the
  `uq_document_version_idem` constraint at the same `cf_version` (sync_service.py:44-55).
- Fingerprints are the single source of the change decision, so idempotency and
  out-of-order tolerance are structural, not incidental.

Cross-references: ADR-0002 (retrieval and versioning model; re-embed triggers).

Tests: `test_scope_tagging_retag.py`, `test_worker_sync.py` (metadata-only resync keyed on
`access_scope_hash`), `test_document_constraints.py`, `test_versioning_failed.py`.
