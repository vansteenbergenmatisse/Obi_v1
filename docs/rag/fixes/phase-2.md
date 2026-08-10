# Phase 2 — Ingestion — Audit Findings

**Audited:** 2026-08-10
**Scope:** apps/automation/app/features/ingestion, platform/clients/embeddings_client.py
**Verification run:**
- `cd apps/automation && uv run pytest app/features/ingestion/tests/ -q` → **36 passed**, 0 failed.
- `uv run ruff check app/features/ingestion app/platform/clients/embeddings_client.py` → **All checks passed!**
- `uv run pyright` (whole repo, then filtered) → **34 errors, 1 warning** repo-wide, matching the
  stated baseline (2 ruff errors / 17 unformatted files / 34 pyright errors) exactly. Within scope:
  4 errors are pre-existing in `app/features/ingestion/tests/test_pipeline_reuse.py` (2×
  `list[float] | None` not assignable to `list[float]` on `Chunk(embedding=...)`, 2× invariant-list
  `list[OldChild]` vs `list[Chunk]` on `_resolve_children`); 1 warning is a missing `openpyxl` stub in
  `attachment_extraction.py:110`. `uv run pyright app/platform/clients/embeddings_client.py` in
  isolation → **0 errors, 0 warnings** — this file is currently pyright-clean (see Confirmed
  correct).
- `uv run ruff format --check app/features/ingestion app/platform/clients/embeddings_client.py` →
  5 files would be reformatted (`domain/tokenization.py`, `infrastructure/page_source_repo.py`,
  `tests/test_contextualizer.py`, `tests/test_pipeline_reuse.py`,
  `platform/clients/embeddings_client.py`) — none of these appear in the current `git status` diff,
  so this is pre-existing baseline debt, not a regression from unreviewed work.
- Repo-wide `uv run ruff check .` → 2 errors (both outside my scope, an import-order fix in an
  alembic migration file) and `uv run ruff format --check .` → 17 files unformatted — confirms the
  task's stated baseline (2/17/34) is current and accurate. Note: the *project* `CLAUDE.md` still
  states "Ruff 2 errors / 25 unformatted, Pyright 31/1" — that figure is now stale (actual is 17
  unformatted / 34 pyright errors); worth a doc refresh outside this audit's scope.

## Security

- **[low]** `apps/automation/app/platform/clients/embeddings_client.py:85` — `_HttpEmbeddingProvider.__init__`
  builds its own `httpx.Client(timeout=self._timeout)` when none is injected, and it is never closed
  (no `close()`/context-manager use, no `atexit`/lifespan hook). Not a security control gap (C4
  timeout/retry/backoff/breaker and C10 abuse cap are all present and correct — see Confirmed
  correct), just a minor resource-lifecycle nit; a long-lived worker process holding one of these
  around per-embedder-instance leaks a connection pool. Low severity because in practice one
  `EmbeddingProvider` is built once per process via `build_ingestion_services`.
- **[low]** The circuit breaker in `_HttpEmbeddingProvider.embed()` (`embeddings_client.py:95-117`)
  only tracks `consecutive_failures` as a **local variable inside one `embed()` call** — it does not
  persist "open" state across separate calls to `embed()`. A provider outage will re-attempt the
  full retry budget on every subsequent `stage_and_activate` call rather than short-circuiting
  quickly, until the local batch-failure count within that single call reaches
  `embedding_breaker_threshold`. Acceptable for a background-worker (non-request-path) surface, but
  worth naming since the docstring/FEATURES.md call it a "circuit breaker" without qualifying that
  it doesn't have cross-call memory.
- No secrets logged: `OpenAIEmbeddingProvider`/`VoyageEmbeddingProvider` never log the `Authorization`
  header or API key; `log.warning(...)` calls in the contextualizer/embeddings paths pass only
  structured non-secret fields. Confirmed clean.

## Dead code / unused

- **`apps/automation/app/features/ingestion/domain/attachment_extraction.py`** (the entire module —
  `extract_attachment`, `ExtractionResult`, and all `_pdf_native`/`_docx_native`/`_xlsx_native`
  helpers) has **zero call sites** anywhere in the production pipeline. It is not exported from
  `ingestion/__init__.py`, not imported by `versioning.py`, `services.py`,
  `confluence_sync/application/sync_service.py`, or the worker — the only place it is referenced at
  all is its own test file (`tests/test_attachment_extraction.py`). This is a fully-built capability
  (native PDF/DOCX/XLSX/CSV/HTML/text extraction with OCR-gating) that is never wired into chunking
  or embedding. `PageHashes.attachment_manifest_hash` (used for change detection) only hashes the
  attachment *manifest* (filenames/sizes/etc. — see `hash_attachment_manifest`), never the extracted
  text, so attachment content is currently **not searchable** despite the extraction code existing.
  This does not contradict any doc claim (PLAN.md/DESIGN.md/how_this_works.md only ever describe
  fetching an attachment *manifest* for hashing, never content extraction into the index), so it is
  not a plan deviation — just orphaned code that should either be wired in or explicitly flagged as
  deferred/parked in PLAN.md so a future reader doesn't assume attachments are searchable.
- No TODO/FIXME/XXX markers and no commented-out code blocks found anywhere in
  `app/features/ingestion/**` or `embeddings_client.py`.
- All `Settings` fields relevant to this feature (`embedding_*`, `contextualization_*`,
  `chunker_version`, etc.) are read somewhere in `services.py`/`contextualizer.py`/
  `embeddings_client.py` — none declared-but-unread.
- `_gc_superseded` (`versioning.py:378-399`) sets `state=DocState.failed` on a version immediately
  before `session.delete(obj)`-ing it in the same function. The intermediate `UPDATE` is redundant
  (the row is deleted a few lines later in the same transaction) — harmless, but dead work. Not worth
  a fix on its own; note only.

## Plan / design deviations (docs vs. code disagree, or an acceptance criterion isn't actually met)

- **[medium-high] `rollback_to` does not restore `PageSource`'s cached change-detection state — only
  the retrieval-visible pointer.** `versioning.py:419-446`. how_this_works.md §6 states rollback "is
  the same pointer swap in reverse: point at a retained superseded version, flip `is_active`.
  Instant, no re-embedding," and PLAN.md's "already modern" table credits versioning.py with
  "Immutable versioning + atomic activation + rollback + GC" wholesale. That claim is **true for the
  read path** (chunks' `is_active` flips correctly, exactly one active version, retrieval sees a
  consistent corpus — verified by `confluence_sync/tests/test_versioning_rollback.py`), but **false
  for the write-path registry state**: `rollback_to` only writes `ps.active_doc_version_id`,
  `ps.current_cf_version`, and `ps.updated_at` on `PageSource`. It never restores
  `ps.content_hash`/`ps.structure_hash`/`ps.parser_version`/`ps.chunker_version`/
  `ps.contextualization_version`/`ps.embedding_model`/`ps.embedding_dim`/
  `ps.retrieval_schema_version` to the *target* `DocumentVersion`'s values (these ARE available on
  `DocumentVersion` and could be copied back), and it never restores
  `ps.title`/`ps.labels_hash`/`ps.access_scope_hash`/`ps.attachment_manifest_hash`/`ps.source_url`/
  `ps.source_modified_at`/`ps.page_status` at all (these live **only** on `PageSource`, not on
  `DocumentVersion`, so there is nothing to roll back to for them — they are simply left however they
  were before the rollback call).
  **Concrete failure mode:** after a rollback, `get_local_state` (`page_source_repo.py:16-35`) —
  which `change_detection.classify` uses as ground truth for the *next* incremental sync — returns
  stale hashes/version-stamps that describe the version being rolled back **away from**, not the
  restored version. If the real Confluence page hasn't changed since, the next sync's freshly
  computed `content_hash`/`structure_hash` will match those stale values (both reflect the same,
  unchanged real content) even though the *active* `document_version`/chunks now correspond to an
  **older** `cf_version`. `classify()`'s version guard (`meta.version_number > local.current_cf_version`)
  does fire and force `needs_body_fetch=True`, but the body-hash comparison in step 6 will then
  spuriously report "no body change" (comparing today's real content-hash against the stale,
  matching hash) and the metadata comparisons in `_classify_metadata` will similarly see no drift —
  so the decision can collapse to `no_change` and skip re-indexing, silently leaving the corpus
  pinned to the rolled-back-to version even though a newer real revision exists and was never
  re-applied. This is a genuine correctness gap in the "rollback restores prior state correctly"
  claim, not merely a docs wording issue.
  **Test coverage confirms the gap is real and unguarded:** `test_rollback_restores_prior_version`
  (`confluence_sync/tests/test_versioning_rollback.py:21-41`) only asserts
  `active_version(1001).cf_version == 2`, `active_versions_count(1001) == 1`, and the active chunk
  set — i.e., only the pointer swap. It never inspects `PageSource.content_hash` /
  `parser_version` / etc. after rollback, so nothing catches this today.
- Everything else claimed in PLAN.md §2's "already modern" table for this feature checked out as
  accurate on direct code inspection (see Confirmed correct below) — parent/child chunking, the
  3-pass reuse gate, and prompt-cached contextual retrieval are all implemented exactly as described.
- Minor wording nit, not a functional bug: FEATURES.md/contextualizer.py describe the Anthropic
  document context as "billed once per page" (prompt-cached). In reality each child that needs
  re-embedding still issues its own `create_message` call; the `cache_control: ephemeral` block
  means the **document tokens** are billed at Anthropic's discounted cache-read rate on repeat calls
  within the page, not literally billed once. Functionally correct and a real cost win, just not
  literally "billed once" — and note Anthropic's minimum-cacheable-length threshold (~1024–2048
  tokens depending on model) means very short pages may not actually get a cache hit at all; this
  isn't handled or observability-checked anywhere.

## Test coverage gaps

- No test asserts that `rollback_to` restores `PageSource`'s hash/version-stamp fields (see above) —
  add a test that rolls back, then calls `get_local_state`/inspects `PageSource` directly and
  asserts the mirrored fields match the target version, not the version rolled back from.
- No test exercises the scenario in the finding above end-to-end (rollback, then a subsequent sync
  of an unchanged Confluence page) to prove whether the system correctly detects it needs to
  re-index vs. incorrectly concludes "no change."
- `attachment_extraction.py`'s test file (`test_attachment_extraction.py`) is a good unit-level
  contract test for the module in isolation, but since the module has no caller, there is (by
  definition) no integration test proving attachment content ever reaches a chunk — consistent with
  it being dead code today, not a coverage gap in the strict sense.
- `_gc_superseded`'s "beyond retain window" boundary (exactly `retain` versions kept, the
  `superseded_at DESC` ordering when multiple pages/documents are superseded around the same
  timestamp) is exercised only indirectly via `test_ingestion_pipeline.py`/multi-version indexing in
  the confluence_sync suite, not by a focused ingestion-level unit test targeting GC edge cases
  (e.g., `retain=0`, ties in `superseded_at`).

## Deferred / future ideas

- Wire `attachment_extraction.extract_attachment` into the pipeline (or explicitly record in
  PLAN.md that attachment *content* indexing is parked/out of scope) so the dead-code finding above
  doesn't recur as a surprise later.
- Consider giving the embeddings/contextualization circuit breakers cross-call memory (e.g. an
  open-until timestamp) if ingestion volume grows enough that a sustained provider outage across
  many `stage_and_activate` calls in a scheduler run becomes a real cost/latency concern — not
  needed at current scale.
- Consider closing/reusing the `httpx.Client` created by `_HttpEmbeddingProvider` via a context
  manager or process-lifetime singleton, to avoid an unbounded number of open connection pools if
  `build_embedding_provider` is ever called more than once per process.

## Confirmed correct

- **Parent/child chunking** (`domain/chunking.py`): parent tier `kind=0`, ~1200 target/2000 max
  tokens, not embedded (`embedding=None`); child tier `kind=1`, ~400 target (150–750 bounds), 12%
  overlap, embedded + `tsv`. `_link_chunks` (`versioning.py:294-311`) wires `parent_chunk_id` by
  matching `(section, parent_ordinal)` and sets `prev_chunk_id`/`next_chunk_id` in reading order —
  exactly as how_this_works.md §5.1/§6 describes; "parent expansion is a join away" (PLAN.md §2) is
  accurate.
- **Contextual retrieval is genuinely prompt-cached**: `contextualizer.py:54`
  (`system_blocks = [cached_system_block(doc_ctx)]`) and `anthropic_client.py:127-129`
  (`cache_control: {"type": "ephemeral"}`) confirm the whole-page system block carries Anthropic's
  cache-control directive, built once per page and reused across all of that page's per-child calls.
  Degrades cleanly to the metadata-only prefix on `AnthropicError` or when disabled/no key — verified
  by `tests/test_contextualizer.py`.
- **3-pass re-embed reuse gate genuinely avoids needless re-embeds**: `domain/chunk_diff.py`'s
  exact→moved→edited-in-slot passes correctly consume from a shared `remaining` pool so no old chunk
  is double-matched; unmatched news are inserts, unmatched olds are deletes. `_resolve_children`
  (`versioning.py:149-184`) only calls `contextualizer.contextualize` + `embedder.embed` for
  `diff.reembed_indexes`, copying `retrieval_content`/`embedding` straight from the matched old chunk
  for every reuse — confirmed by `tests/test_chunk_diff.py` and `tests/test_pipeline_reuse.py`
  (spy-embedder call counts).
- **Reuse is correctly disabled wholesale on a pipeline-config change**: `reusable_active_children`
  (`versioning.py:258-280`) returns `[]` whenever `_pipeline_config_matches` is false (embedding
  model/dim, contextualization version, or retrieval schema version differs from the active version's
  stamps), forcing every child through the full re-embed path — matches the "full re-embed release
  gate" description in both PLAN.md and how_this_works.md §5.5, and is exercised by
  `confluence_sync/tests/test_ingestion_pipeline.py`.
- **Activation is atomic and consistent for the read path**: `stage_and_activate` builds the whole
  new version + chunks with `is_active=False`, validates (raises + marks `failed` if zero child
  chunks were produced, leaving the live index untouched), then `_activate` supersedes the old
  version/chunks and flips the new ones to active inside the same session/transaction — a partial
  unique index (`ux_document_version_one_active`) guarantees at most one active version per document.
  Readers filtering on `is_active` never see a half-built page. GC (`_gc_superseded`) deletes
  versions beyond the retain window (default 2) with chunks cascading via FK `ondelete="CASCADE"`.
- **`embeddings_client.py` is currently pyright-clean** — the task brief's note about "a known
  pyright error per earlier investigation" does not reproduce today (isolated pyright run: 0 errors,
  0 warnings; it also does not appear anywhere in the whole-repo pyright output). Either it was fixed
  since that investigation or the note was stale; either way, no outstanding pyright issue exists in
  this file today.
- **`embeddings_client.py` security controls are all present and correctly wired**: per-call abuse
  cap (`embedding_max_texts_per_call`, C10), fixed batch sizing (`embedding_max_batch`), bounded
  retry with exponential backoff capped at 4s (`_post_with_retry`, C4), a consecutive-failure breaker
  (`embedding_breaker_threshold`), and a configurable timeout on every `httpx` call. No secrets are
  logged. Matches FEATURES.md's documented `security_baseline` for
  `openai.embeddings.create` exactly.
- **Ruff is clean** for the whole ingestion feature + `embeddings_client.py` (`ruff check`: 0
  errors); the 5 unformatted files under `ruff format --check` are pre-existing baseline debt (not
  touched by any file in the current `git status` diff), consistent with ADR-0003 D1's
  no-regression policy.
