# 02 — Ingestion (the write path)

The write path turns a Confluence page into searchable rows in Postgres. It runs as the **writer**
DB role (table owner; bypasses RLS), so ingestion is never blocked by the read-path isolation policy.
Two features own it: `app/features/confluence_sync` (get data in, classify the change) and
`app/features/ingestion` (turn a page into chunks + embeddings + a new immutable version).

End-to-end order:

```
Confluence webhook (or reconciliation sweep)
  → event_ledger (dedup) → job queue (idempotent enqueue)
  → worker (3-transaction discipline) → sync_service.handle_sync_page (classify change)
  → [rebuild?] chunking (parent/child) → contextualize → embed (children) → tsv (children)
  → stage_and_activate: immutable document_version (staging) → atomic pointer-swap → GC
```

## 1. Webhook receipt

`POST /confluence/events`, handler `receive_confluence_event` (webhook.py:88-93). Declared
STATE-MUTATING, no LLM (webhook.py:3, security baseline webhook.py:7-24). Order inside the handler:

1. **Rate limit** per client IP — `SlidingWindowRateLimiter(webhook_rate_limit_per_minute=300)`,
   lazily on `app.state` (webhook.py:80-85, 94-97).
2. **Body-size cap** — `webhook_max_body_bytes` (512 KiB) → 413 (webhook.py:99-101).
3. **HMAC signature** — `_verify_signature` (webhook.py:67-77): header `X-Hub-Signature-256`;
   **fail-closed 503** if `confluence_webhook_secret` unset; 401 if header missing; strips an optional
   `sha256=` prefix; `expected = hmac.new(secret, raw_body, sha256).hexdigest()`; constant-time
   `hmac.compare_digest`, 401 on mismatch.
4. **Parse** JSON (400 on decode / non-dict), then `parse_webhook_payload` → `EventEnvelope`
   (webhook.py:105-112). The parser tolerates both nested (`page`/`content` + `version`/`space`/
   `actor`) and flattened webhook shapes and retains the full body in `raw` (events.py:68-111).
5. **`ingest_event(session, envelope, settings, origin=0)`** (webhook.py:113).
6. A structured `webhook_event` log line (event_type, page_id, actor, delivery_id,
   accepted/duplicate/ignored/self_generated, job_id) — webhook.py:115-126.

The handler does **no** page fetch or indexing — that is all deferred to the worker. Each request is
one short transaction via the `get_db` / `session_scope()` dependency.

### Event ledger dedup

`ingest_event` (event_service.py:41-64):

- **Unsubscribed types dropped** — `envelope.event_type not in ALL_EVENTS` ⇒ ignored
  (event_service.py:44-45). Subscription sets: `DELETE_EVENTS` (page trashed/archived/removed/deleted),
  `SYNC_EVENTS` (created/updated/moved/restored/unarchived, attachment created/updated/removed, label
  added/deleted, page permissions updated), `SPACE_EVENTS` (space updated / permissions updated),
  `ALL_EVENTS = union` (events.py:10-30).
- **Self-event guard** — if the actor is `confluence_service_account_id`, mark the ledger row
  `done`/`self_generated` and enqueue **no** job (event_service.py:47-60) — prevents our own writes
  from looping back.
- **Dedup** — `event_repo.record_event` (event_repo.py:25-57) computes `payload_hash =
  hash_json(envelope.canonical_dedup_payload())` and inserts with a **target-less**
  `on_conflict_do_nothing()`, so a violation on **either** unique constraint —
  `uq_event_ledger_payload_hash` (canonical content) or `ux_event_ledger_delivery_id` (partial-unique
  delivery id) — is absorbed in one round trip. Returns the new id, or `None` for a duplicate. The
  dedup key is `(event_type, page_id, cf_version, space_id, status, event_timestamp, delivery_id)` and
  **excludes receive time** (events.py:46-56), so a redelivery of the same event is a graceful no-op.

## 2. The job queue (`platform/jobs/queue.py`)

A generic, crash-safe Postgres-backed queue. Reconciliation feeds the **same** queue as the webhook —
there is never a blind re-embed path.

- **Enqueue** — `enqueue_job` (queue.py:25-53): idempotent via
  `on_conflict_do_nothing(index_elements=["idempotency_key"])`; returns the id or `None` if the key
  already exists. Idempotency keys are built per event type (event_service.py:67-103):
  `sync_page:{page_id}:{event_type}:{ver}:{schema}`, `delete_page:{page_id}:{event_type}` (priority 50,
  higher), or `reconcile_space:{space_id}:{event_id}`.
- **Claim** — `claim_job` (queue.py:56-87): selects one `pending`/`failed` row with `available_at <=
  now`, `ORDER BY priority ASC, available_at ASC LIMIT 1` **`FOR UPDATE SKIP LOCKED`** (so two workers
  never grab the same job); sets `status=running`, `lease_owner`, `lease_expires_at = now +
  worker_lease_seconds` (120s), and increments `attempts`.
- **Complete** — `complete_job` sets `succeeded`, clears the lease (queue.py:90-95).
- **Fail / retry / dead-letter** — `fail_job` (queue.py:98-117): truncates the error to 4000 chars; if
  `attempts >= max_attempts` (default 5) → `dead_letter`, else `failed` with exponential backoff
  `base_backoff_seconds(5) · 2^(attempts-1)`, capped at 3600s, on `available_at`.
- **Reaper** — `reap_expired` (queue.py:120-131): any `leased`/`running` job whose lease expired is
  reset to `pending` — recovers work abandoned by a crashed worker.

## 3. The worker's 3-transaction discipline (`application/worker.py`)

`run_once` (worker.py:85-128) runs each job in **three separate transactions** so bookkeeping and work
never share a rollback (worker.py:1-15):

- **Txn 1 — Claim.** Own `session_scope()`; `claim_job`; if none, return. Committed on exit so the
  lease + `attempts` increment are durable **before** work starts (worker.py:95-100).
- **Txn 2 — Handle + complete atomically.** Re-`get(Job, job_id)`; run the handler; `complete_job` —
  the index mutation and the `succeeded` transition commit **together** (worker.py:112-120). If the
  handler raises, this txn rolls back entirely.
- **Txn 3 — Fail independently.** On any exception, a third `session_scope()` re-fetches the job and
  calls `fail_job(error=repr(exc))`, so the attempt count + error survive the rollback that undid the
  work (worker.py:121-128).

Handlers (worker.py:56-75): `_handle_sync_page` → `handle_sync_page` (reads `tags` from the payload);
`_handle_delete_page` → `handle_delete_page`; `_handle_reconcile_space` → `reconcile_space` (lazily
imported to avoid a module cycle — the one legal cycle-breaker, ADR-0003). Every handler is
**idempotent and version-guarded**, so re-running a reclaimed/retried job is safe. `drain` processes up
to `max_jobs=100` (worker.py:131-146).

## 4. Change classification (`application/sync_service.py` + `domain/change_detection.py`)

`handle_sync_page` (sync_service.py:77-199) fetches the page meta, labels, restrictions, and
attachments, decides whether to fetch the body (`decide_body_fetch`), then calls `classify(...)` to
produce a `ChangeDecision`, and branches:

| Outcome | When | `action` |
|---|---|---|
| gone / deactivated | meta missing, or a trashed/deleted/archived status | `"gone"` / `"deactivated"` |
| **rebuild** | first-ever index, or any class in `_REBUILD_CLASSES` | `"indexed"` |
| metadata-only | a meaningful but non-body change (labels, permissions, title, parent) | `"metadata_only"` |
| no change | nothing meaningful drifted | `"no_change"` |

`_REBUILD_CLASSES` (sync_service.py:36-43): `body_changed, section_added/updated/removed/moved,
index_config_change`. It **excludes `attachment_changed`** deliberately — a rebuild at the same
`cf_version` would violate `uq_document_version_idem` (sync_service.py:44-55).

`classify` (change_detection.py:104-180) is driven by **status + version + hashes**, not the raw
webhook `event_type` (the event type only routes the job type). It always recomputes metadata hashes
(`labels_hash`, `access_scope_hash`, `attachment_manifest_hash`) and, when the body was fetched,
content/structure hashes. Order: gone-statuses short-circuit (bypassing the version guard); first-ever
index ⇒ `body_changed` + needs re-embed; a version guard skips work when `meta.version <=
local.current_cf_version` and config is unchanged; a pipeline-config change forces
`index_config_change`; then metadata comparisons (`_classify_metadata`) and body comparisons
(content-hash differs ⇒ `body_changed`, and if structure also differs ⇒ `section_updated`).

## 5. Chunking — parent/child (`domain/chunking.py`)

Two tiers (`ChunkConfig`, chunking.py:31-39):

- **Parents** (`kind=0`): group a section's blocks into ~`parent_target` (1200) token spans, hard cap
  `parent_max` (2000). The **context unit** — not embedded, expanded at retrieval.
- **Children** (`kind=1`): ~`child_target` (400) token windows within a single parent
  (`child_min`=150, `child_max`=750), with `child_overlap_ratio` (0.12) overlap. The **embedding /
  match unit**.

Split priority: page → heading section → block (tables/code kept whole) → paragraph → sentence/word →
token (chunking.py:11). `plan_chunks` (chunking.py:62-117) packs parents (`_pack_parents`,
token-splitting an oversize unit at `parent_target`) and splits children (`_split_children`, merging a
trailing sub-`child_min` window back). Each chunk carries **stable identity keys** (ADR-0002):
`section_key`, `positional_key`, `content_key` (`sha256_text`), and `stable_key`
(position + content), so editing one section reuses unchanged embeddings. The parent↔child relation is
persisted in `_link_chunks` (versioning.py:294-311): parents flushed first, each child mapped to its
parent via `(section, parent_ordinal)` → `parent_chunk_id`, and children linked
`prev_chunk_id`/`next_chunk_id` in reading order.

## 6. Contextualization (`application/contextualizer.py`)

Each child's embedded **`retrieval_content`** is distinct from the verbatim **`display_content`** used
in citations. The contextualizer always prepends a factual metadata prefix (page title + heading path
joined by ` > `) and, when enabled, an LLM-written 1–2 sentence situating context, composed as
`prefix\n\n<llm ctx>\n\ntext` (contextualizer.py:79-91). The LLM path fires only when
`contextualization_enabled` and an Anthropic key are present (contextualizer.py:45-54); it uses the
**whole page as a prompt-cached system block** (billed once per page, capped at
`contextualization_max_doc_chars`) and the `routing_model` (`claude-haiku-4-5-20251001`),
`max_tokens=128`, with the instruction to add context "using only information present in the document."
It is **fail-soft**: on `AnthropicError` it logs and returns `""` (metadata-only) — contextualization
never fails ingestion.

## 7. Embedding (`platform/clients/embeddings_client.py`)

Only **children** are embedded, and only the indexes that actually need re-embedding
(`versioning._resolve_children`, versioning.py:149-184 — diff-matched children reuse the old
embedding + retrieval_content). The provider is chosen by `build_embedding_provider`:
`OpenAIEmbeddingProvider` (`POST /v1/embeddings` with `dimensions`), `VoyageEmbeddingProvider`
(`output_dimension`), `FakeEmbeddingProvider` (deterministic, offline), or a local provider. Batching
+ resilience (`_HttpEmbeddingProvider.embed`, embeddings_client.py:94-131): a per-call abuse cap
(`embedding_max_texts_per_call`, 20k), splitting into `embedding_max_batch` (128) batches, a circuit
breaker after `embedding_breaker_threshold` (5) consecutive failures, and bounded retry with
`min(0.3·2^n, 4)` backoff. `services.embedding_model` reflects the **actual** producer, so switching
providers later reads as a config change that the version-stamp gate turns into a full re-embed.

> **Embedding provider — code default vs deployed `.env`** (see also `01-system-overview.md`): the
> `settings.py` *default* is Voyage `voyage-3-large` @ 1024 dims (settings.py:61-63), but the deployed
> root `.env` (gitignored, verified 2026-09-07) overrides to `EMBEDDING_PROVIDER=openai`,
> `EMBEDDING_MODEL=text-embedding-3-large`, `EMBEDDING_DIM=3072`. So the **actual running config is
> OpenAI 3072-dim → the `halfvec(3072)` HNSW cast** (matching the ADRs/DESIGN); the Voyage/1024 default
> is only the no-override fallback and `VOYAGE_API_KEY` is currently empty. Both code paths exist; the
> live one is OpenAI-3072/halfvec.

**Model choice is a managed tradeoff, not an oversight.** OpenAI `text-embedding-3-large` @3072 is a
**deliberate, swappable config** (`build_embedding_provider` + the version-stamp gate make the provider
a config value, not a hard-coded assumption). As of 2026 it is no longer the MTEB leader —
voyage-3-large, Qwen3-Embedding, and Gemini embeddings now outrank it — but it stays chosen because it
is battle-tested at production scale and already wired end to end. The intended mechanism for staying
current is the **version-stamped eval bake-off (Phase 5.4)**: a candidate embedder is scored against
the gold set, and only a measured win flips the config (which the pipeline-version gate then turns into
a full re-embed, §9). **Matryoshka/MRL dimension truncation and int8 quantization** are available
storage/latency optimizations to consider *only* if that same eval shows the accuracy loss is within
tolerance — never applied blind.

## 8. Keyword `tsv`

Populated on **child** chunks only, in `build_chunks`: `tsv = to_tsvector('english', title + heading
path + text)` — the config is a SQL literal, the text a bound parameter (`_tsv`, versioning.py:40-43,
140). Parents get no `tsv`. Indexed by the GIN `ix_chunk_tsv_gin`.

## 9. Versioning, activation, rollback, GC (`application/versioning.py`)

An index update is **immutable and atomic** (ADR-0002). `stage_and_activate` runs in the caller's
single transaction (versioning.py:187-255):

1. **Ensure the `document`**; compute reusable children (returns `[]` when pipeline config changed — a
   full re-embed release gate, `_pipeline_config_matches` compares embedding_model/dim,
   contextualization_version, retrieval_schema_version).
2. **Create the new `document_version` in `staging`**, recording content/structure hashes and every
   pipeline version stamp (versioning.py:206-221).
3. **Build chunks** with `is_active=False`, link parents↔children.
4. **Validation gate:** if there are no child chunks, mark the version `failed` and raise — a bad build
   never activates (versioning.py:238-242).
5. **`_activate`** (the pointer swap, versioning.py:314-375): supersede the old active version
   (`superseded`, its chunks `is_active=False`); set the new version `active`, its chunks
   `is_active=True`; upsert `page_source` with `active_doc_version_id = new_version.id` plus title/url/
   hashes/pipeline stamps/`tags`/`current_cf_version`. Because `page_source.active_doc_version_id` is a
   `UNIQUE` deferrable FK and `document_version` has a partial-unique "one active per document" index,
   the swap is all-or-nothing — the live corpus is never half-rebuilt.
6. **`_gc_superseded`** (versioning.py:378-399): keep `DEFAULT_RETAIN_SUPERSEDED = 2` superseded
   versions for rollback; older ones are set `failed` then deleted (chunks cascade via FK).

**Rollback** — `rollback_to` (versioning.py:419-460): supersede the current, reactivate the target
version's chunks, repoint `active_doc_version_id`/`current_cf_version`, and **restore the target's
change-detection hashes + pipeline stamps** so the next sync does not falsely report `no_change`
(a real Phase 4.6 fix). Fields with no `document_version` counterpart self-heal on the next
reconciliation.

**Source-tag activation seam (ADR-0004):** the single activation point stamps `source_type =
"confluence"`, `source_id = "confluence:default"` (constants today, a parameter when a second source
lands) onto both chunks and `page_source` (versioning.py:34-37, 88-92, 352-353).

## 10. Reconciliation sweeps (`application/reconciliation.py`)

A safety-net that catches anything the webhook missed; both kinds route through the **same job queue**:

- **Lightweight** (daily, `lightweight_recon_cron = "0 3 * * *"`): cheap drift signals only —
  `_needs_sync` (reconciliation.py:58-65) enqueues a `sync_page` when version, status, parent, or title
  drift.
- **Complete** (every `complete_recon_interval_days = 14`): enqueues a `sync_page` for **every** live
  scoped page (re-checks labels/permissions/attachments even without a version bump) and deactivates
  orphans directly.

`_sweep_space` (reconciliation.py:145-221) lists live pages, applies the `source_scope` resolution to
restrict to scoped pages, enqueues via `_enqueue_sync` (which threads `source_scope` tags into the job
payload so the worker stamps them at activation), and purges registry rows no active root covers. Each
run is recorded as a `reconciliation_run` with per-bucket counts. **Space discovery** unions registry
spaces with spaces implied by any `source_scope` row (active or not) — this is what lets a brand-new
space get its first sweep (reconciliation.py:312-345).

## 11. `source_scope` + knowledge-scope label→tag resolution

Two distinct tag systems, **unioned** (never one replacing the other):

**(a) Confluence label → knowledge-scope tag** (`domain/knowledge_scope.py`, ADR-0011). A page's
native Confluence labels (already fetched every sync for `labels_hash`) are intersected with the
recognized set (`Settings.knowledge_scope_set`, loaded from repo-root `config/knowledge_scopes.json`:
`obi-general-test, obi-mews-test, obi-operacloud-test, obi-toast-test`). `resolve_knowledge_scope_tags`
(knowledge_scope.py:24-31): provider tags = matched labels minus `obi-general-test`; **more than one
provider label ⇒ a quarantined conflict** — zero label-derived tags contributed, `knowledge_scope_conflict`
logged, self-heals on the next sync (never "first wins," never "available everywhere"). `handle_sync_page`
computes `final_tags =
sorted(source_scope_tags ∪ label_tags)` and threads it into the same `stage_and_activate` /
metadata-only seam (sync_service.py:103-115, 180-189).

**(b) `source_scope` roots → tags-by-page** (`domain/scope_resolver.py`, PLAN 3.5.6). A `space` root
covers all live pages; a `page` root covers itself + descendants via a `parent_id` walk over the live
page list. `resolve_space_scope` (scope_resolver.py:66-100) distinguishes "no rows ever"
(unrestricted) from "rows exist, all inactive" (restrict to the empty set — deactivating a space's
last root purges its coverage). These `source_scope` tags encode *sync inclusion*, a different axis
from knowledge scope.

Tags are stamped on `chunk.tags` and `page_source.tags` at activation, and updated in place on the
metadata-only path. The **readiness gate** `verify_knowledge_scope_coverage` (knowledge_scope_backfill.py,
PLAN 10.7) counts active chunks whose tags overlap none of the recognized scopes (using the same bound
array-overlap predicate as retrieval) and reports `is_ready` only when that count is zero — the machine
gate that must pass before `enable_knowledge_scope_filtering` is flipped on.

## 12. Attachment ingestion

Confluence **page attachments** (PDF/DOCX/XLSX/CSV/HTML) flow through the *same* chunk/embed pipeline
as body text (a Phase 4.6 wiring). `extract_attachment` (attachment_extraction.py:34-69) is native-first
and **never raises**: images → empty text + `needs_ocr` flag (OCR is only flagged, never run eagerly);
CSV/HTML/Markdown/text via stdlib; PDF via `pypdf` (flags `needs_ocr` when native text < 20 chars);
DOCX via `python-docx`; XLSX via `openpyxl`; a missing library ⇒ `method="skipped"`, no crash.
`attachment_to_blocks` wraps extracted text as normalized blocks under a synthetic heading path
`["Attachments", title]`, so it chunks, contextualizes, and embeds identically to body text.

Orchestration (`sync_service._attachment_blocks`, sync_service.py:202-248): only on a rebuild;
attachments sorted by id; capped at `confluence_attachment_max_per_page` (200); per-attachment
fail-soft (skip missing/oversized-by-metadata/unfetchable, oversized enforced again at download via
`confluence_attachment_max_bytes` = 20 MB). Blocks are appended to the body blocks before staging.

**Known limitation:** attachment content is **not** folded into `content_hash`/`structure_hash`
(body-only), and `attachment_changed` alone does **not** trigger a rebuild (it would collide with
`uq_document_version_idem` at the same `cf_version`). So an attachment-only change waits for the next
body edit or a pipeline-version bump; an attachment change alongside any body change is indexed
immediately (sync_service.py:44-55, 150-165).

**Visual content is intentionally text-only today.** Images produce empty text + a `needs_ocr` flag
that is never acted on (OCR/VLM never runs), and PDFs go through `pypdf`, which flattens layout — so
scanned pages, diagrams, and image-only content contribute nothing to the index. This matches the 2026
"ship text-first" sequencing: quantify how much of the corpus is actually visual via a **corpus audit**,
then add multimodal (VLM captioning, Docling, TableFormer) only where an eval justifies the cost. Note
the gap is narrower than it looks: Confluence **body** tables are already preserved — they arrive as
structured HTML and the chunker keeps them whole (§5, tables/code kept whole) — so the deficit is
concentrated in PDF/scanned attachments and images, not in native page tables.
