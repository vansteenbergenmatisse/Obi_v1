# ingestion

## Purpose (two lines)
Owns ingestion stages 3-4: turns normalized page blocks into parent/child chunks, contextualizes and embeds children with incremental reuse, then stages, validates and atomically activates a new `document_version` (with GC and rollback). It also holds the stage-2 change-classification domain logic (`change_detection.py`), even though CLAUDE.md assigns stage 2 to `confluence_sync`.

## Entry points
| symbol | file:line | called by |
|---|---|---|
| `build_ingestion_services` | `apps/automation/app/features/ingestion/application/services.py:41` | `confluence_sync/application/sync_service.py:93`; `confluence_sync/tests/test_ingestion_pipeline.py:76,84`; `confluence_sync/tests/test_versioning_rollback.py:137` |
| `stage_and_activate` | `apps/automation/app/features/ingestion/application/versioning.py:187` | `confluence_sync/application/sync_service.py:172` |
| `deactivate_page` | `apps/automation/app/features/ingestion/application/versioning.py:402` | `confluence_sync/application/sync_service.py:90,135,264` |
| `rollback_to` | `apps/automation/app/features/ingestion/application/versioning.py:419` | none found in `apps/automation/app` or `apps/automation/scripts` outside tests — only `confluence_sync/tests/test_versioning_rollback.py` calls it |
| `reusable_active_children` | `apps/automation/app/features/ingestion/application/versioning.py:258` | internally by `stage_and_activate` (`versioning.py:204`); also imported directly in `confluence_sync/tests/test_ingestion_pipeline.py:8` |
| `classify` | `apps/automation/app/features/ingestion/domain/change_detection.py:104` | `confluence_sync/application/sync_service.py:123` |
| `decide_body_fetch` | `apps/automation/app/features/ingestion/domain/change_detection.py:90` | `confluence_sync/application/sync_service.py:117` |
| `get_local_state` | `apps/automation/app/features/ingestion/infrastructure/page_source_repo.py:16` | `confluence_sync/application/sync_service.py:95` |
| `extract_attachment` | `apps/automation/app/features/ingestion/domain/attachment_extraction.py:34` | `confluence_sync/application/sync_service.py:246` |
| `attachment_to_blocks` | `apps/automation/app/features/ingestion/domain/attachment_extraction.py:128` | `confluence_sync/application/sync_service.py:247` |
| `ensure_document` | `apps/automation/app/features/ingestion/infrastructure/page_source_repo.py:38` | `versioning.py:200` (internal, not re-exported at the feature root) |

## Reads and writes
| tables, files, queues touched | read or write | file:line |
|---|---|---|
| `page_source` (via `PageSource` ORM model) | read | `versioning.py:267-270` (`reusable_active_children`), `326-327` (`_activate`), `421` (`rollback_to`) |
| `page_source` | write | `versioning.py:348-374` (`_activate` sets pointer, tags, hashes, stamps); `versioning.py:442-458` (`rollback_to`); `versioning.py:404-408` (`deactivate_page`) |
| `document` (via `Document` model) | read/write (get-or-create) | `page_source_repo.py:38-46` (`ensure_document`) |
| `document_version` (via `DocumentVersion` model) | write (insert staging) | `versioning.py:206-221` |
| `document_version` | write (state transitions: staging→active/failed, active→superseded) | `versioning.py:240` (gate→failed), `versioning.py:330-345` (`_activate`), `versioning.py:392-398` (`_gc_superseded`, superseded→failed→deleted), `versioning.py:428-438` (`rollback_to`) |
| `chunk` (via `Chunk` model) | write (insert, `is_active=False`) | `versioning.py:59-146` (`build_chunks`) |
| `chunk` | write (activate/deactivate `is_active`, link parent/prev/next) | `versioning.py:294-311` (`_link_chunks`), `versioning.py:336-344` (`_activate`), `versioning.py:411-414` (`deactivate_page`), `versioning.py:439-441` (`rollback_to`) |

## External calls
| client | endpoint | timeout, retry, breaker present? | file:line |
|---|---|---|---|
| `AnthropicMessagesClient.create_message` (contextualization LLM call) | Anthropic Messages API (client built in `platform/clients`) | timeout/retries configured at construction (`services.py:45-49`, `settings.contextualization_timeout_seconds`/`max_retries`); no retry/timeout logic visible inside `contextualizer.py` itself — it only catches `AnthropicError` and degrades | `apps/automation/app/features/ingestion/application/contextualizer.py:113-124` |
| `services.embedder.embed` (embedding call) | provider implementation lives in `platform/clients/embeddings_client.py` (outside this folder) | not evidenced inside this folder — call site only | `apps/automation/app/features/ingestion/application/versioning.py:180` |
| optional libs `pypdf`, `python-docx`, `openpyxl` (not network calls, local parsing) | n/a | wrapped in `try/except Exception: return ""` — silently degrades to empty text, no timeout/retry concept applies | `apps/automation/app/features/ingestion/domain/attachment_extraction.py:86-125` |

## Tests present
| test file | behaviors asserted | panel ids |
|---|---|---|
| `apps/automation/app/features/ingestion/tests/test_chunking.py` | parent/child packing, stable-key determinism, section-key stability across edits, heading-path propagation, empty-blocks edge case | i3-parents, i3-children |
| `apps/automation/app/features/ingestion/tests/test_chunk_diff.py` | exact/moved/edited-in-slot/insert/delete reuse classification | ov-build (embedding reuse), i3-embed (today: reuse) |
| `apps/automation/app/features/ingestion/tests/test_tokenization.py` | token counting, window splitting bounds, overlap rejection | i3-children (split mechanics; no panel names tokenization directly) |
| `apps/automation/app/features/ingestion/tests/test_attachment_extraction.py` | per-format extraction, `needs_ocr` gating, unsupported/missing-lib skip, attachment-to-block wrapping | i3-attach, i3-blocks |
| `apps/automation/app/features/ingestion/tests/test_contextualizer.py` | fallback prefix, disabled path, LLM path with cached doc, LLM failure fallback, meta-refusal discard, doc-char truncation | i3-context |
| `apps/automation/app/features/ingestion/tests/test_pipeline_reuse.py` | first index embeds all children, identical re-index reuses all embeddings, single-section edit re-embeds only changed children | i3-embed, ov-build |
| **Not in this folder:** `confluence_sync/tests/test_versioning_rollback.py`, `confluence_sync/tests/test_ingestion_pipeline.py` | exercise `rollback_to`, `stage_and_activate`, `build_ingestion_services`, `reusable_active_children` (functions defined in this folder) from the other feature's test directory | i4-rollback, i4-staging |

## Known gaps
- `rollback_to` (`versioning.py:419-460`) has no production caller anywhere under `apps/automation/app` or `apps/automation/scripts` — only a test (`confluence_sync/tests/test_versioning_rollback.py`) invokes it, despite the design panel calling it an "Operator action" (`i4-rollback`).
- `_gc_superseded` (`versioning.py:378-399`) only ever queries `DocumentVersion.state == DocState.superseded` (`versioning.py:385`); a version marked `failed` directly by the validation gate (`versioning.py:240`) never transitions through `superseded` and is therefore never selected by this query — it is never garbage-collected by this function, contradicting the design's "GC deletes failed versions later" (`i4-failed`).
- No `scope_state` field or write appears anywhere in this folder (`grep scope_state` empty) — consistent with the design's own "target adds scope_state" framing for `i4-stamp` and `d-chunk`, but confirms it is fully unbuilt here.
- No `classified` state or deletion logic appears anywhere in this folder (`grep classified` empty) — the "classified chunks are deleted outright" behavior described in `r3-classified`/`s-classified` is not implemented in `features/ingestion`.
- `contextualizer.py:41-74` (the meta-refusal signal list) and the discard path at `contextualizer.py:125-129` are real, tested behavior (`test_contextualizer.py:89`) that no design panel in this assignment's list describes.
- Attachment upload/parse caps ("200 per page, 20 MB each", `i3-attach`) are not implemented in `domain/attachment_extraction.py` — `extract_attachment` takes already-fetched `bytes` and has no size/count guard.

## Claims from the design
| panel | claim | file:line | verdict | note |
|---|---|---|---|---|
| ov-decide | "Classification by hashes works" | `domain/change_detection.py:104-180` | confirmed | `classify()` compares content/structure/labels/access-scope/attachment-manifest hashes |
| ov-decide | "attachment-only changes never rebuild" (today gap) | `domain/change_detection.py:200-204` | confirmed | `attachment_changed` class is added but `needs_reembed`/`needs_body_fetch` are left untouched in `_classify_metadata` |
| ov-decide | "the version guard can skip a label change" (today gap) | `domain/change_detection.py:148-154` | drifted | Within this file the version-guard branch still calls `_classify_metadata` (line 151), which compares `labels_hash` (line 122, 193-194) whenever labels are supplied — this file does not skip a label change by itself. Whether labels are actually re-fetched in that branch is decided by the caller (`confluence_sync`, outside this folder) — needs live/cross-feature check to confirm the gap's true location |
| ov-build | "Parent and child chunking, contextual notes, embeddings, keyword index and attachments all run" | `domain/chunking.py:62-159`; `application/contextualizer.py:98-111`; `application/versioning.py:40-43,140,180`; `domain/attachment_extraction.py:34-150` | confirmed | all five sub-behaviors evidenced |
| ov-build | "Embedding reuse checks body text only" | `domain/chunk_diff.py:74-92` | confirmed | pass 1/2 key off `stable_key`/`content_key`, both derived purely from chunk text (`chunking.py:79-115`) |
| ov-activate | "Staging version, validation gate, atomic pointer swap, GC and rollback all run" | `application/versioning.py:206-221,238-242,314-375,378-399,419-460` | confirmed | all five steps present |
| cm-ingest | code locations: `domain/chunking.py`, `application/contextualizer.py`, `domain/chunk_diff.py`, `domain/attachment_extraction.py`, `application/versioning.py` | folder listing (see Entry points) | drifted | list is accurate but incomplete — omits `domain/change_detection.py`, `domain/normalization.py`, `domain/tokenization.py`, `application/services.py`, `infrastructure/page_source_repo.py`, all of which exist and are exported from `__init__.py:18-53` |
| cm-ingest | "Writes document, document_version, chunk" | `application/versioning.py:200,206-221,59-146` | drifted | also writes `page_source` (the pointer, tags, hashes, stamps) at `versioning.py:348-374`, not mentioned in the claim |
| i1-handle | code at `confluence_sync/application/worker.py:56-75,112-120` | n/a | missing | owned by confluence_sync, not present in this folder |
| i2-rebuild | code at `confluence_sync/application/sync_service.py:150-165` | n/a | missing | owned by confluence_sync |
| i2-rebuild | code at `ingestion/application/versioning.py:187-255 — stage_and_activate` | `application/versioning.py:187-255` | confirmed | function boundaries match exactly |
| i2-tobuild | "body blocks and attachment blocks passed to the chunker" (hand-off) | none given | missing | no "Where in the code" section on this panel; conceptual hand-off, not independently verifiable inside this folder |
| i3-blocks | code at `ingestion/domain/normalize.py — block model` | `domain/normalization.py:24-35` (Block dataclass) | drifted | file is named `normalization.py`, not `normalize.py` |
| i3-blocks | code at `ingestion/domain/attachment_extraction.py:attachment_to_blocks` | `domain/attachment_extraction.py:128-150` | confirmed | matches exactly, including heading path `["Attachments", title]` |
| i3-parents | code at `ingestion/domain/chunking.py:31-39,62-117` | `domain/chunking.py:31-38` (`ChunkConfig`), `62-117` (`plan_chunks`) | confirmed | `ChunkConfig` dataclass actually ends at line 38 not 39 (one blank line off); `plan_chunks` range matches exactly |
| i3-parents | "Size target 1200, hard cap 2000; boundary never crosses heading section" | `domain/chunking.py:33-38` (`parent_target=1200, parent_max=2000`); `71-90` (`plan_chunks` iterates per `section`) | confirmed | |
| i3-children | code at `domain/chunking.py — _split_children` | `domain/chunking.py:150-159` | confirmed | |
| i3-children | code at `application/versioning.py:294-311 — _link_chunks` | `application/versioning.py:294-311` | confirmed | exact match |
| i3-children | "Overlap 12 percent" | `domain/chunking.py:36` (`child_overlap_ratio: float = 0.12`) | confirmed | |
| i3-children | "Identity: section_key, positional_key, content_key, stable_key" | `domain/chunking.py:48-51` | confirmed | |
| i3-children | "kind = 1" | not evidenced in this folder | needs live | `KIND_CHILD` is imported from `app.platform.db.models` (`versioning.py:30`); its numeric value is defined in `platform/db/models.py`, outside this folder |
| i3-context | code at `application/contextualizer.py:45-91 — the composition` | `application/contextualizer.py:45-91` contains the meta-refusal signal tuple, `_is_meta_refusal`, `ContextItem`, and the start of `Contextualizer.contextualize` | drifted | the actual composition logic (`_metadata_prefix`, `_compose`) is at lines 133-146, not 45-91 — the line range is stale relative to the file's current content (meta-refusal detection was added later, commit `2435127`) |
| i3-context | code sample `retrieval_content = f"{title} > {heading_path}\n\n{llm_note}\n\n{child_text}"` | `application/contextualizer.py:133-146` | drifted | actual code builds the prefix via `_metadata_prefix` (title and heading-trail joined with `" — "`, not `>`; heading segments within the trail are joined with `" > "`) then `_compose` joins with newlines — not a literal match to the panel's snippet |
| i3-context | "Cost: whole page is a prompt-cached system block, billed once per page" | `application/contextualizer.py:100-109` | confirmed | one `cached_system_block(doc_ctx)` built per `contextualize()` call and reused for every item |
| i3-context | "Stored as retrieval_content (embedded); display_content stays verbatim" | `application/versioning.py:136-139` | confirmed | |
| i3-context | "Fail-soft: an LLM error gives the prefix only" | `application/contextualizer.py:113-124` | confirmed | `except AnthropicError` returns `""`, degrading to metadata-only prefix |
| i3-embed | code at `platform/clients/embeddings_client.py:94-131`, `platform/config/settings.py:61-63` | n/a | missing | owned by `platform/clients` and `platform/config`, not this folder |
| i3-embed | "Today only changed children are embedded (stable_key reuse)" | `application/versioning.py:149-184` (`_resolve_children`); `domain/chunk_diff.py:56-113` | confirmed | evidenced in this folder even though the panel's own code pointers are platform-side |
| i3-attach | code at `domain/attachment_extraction.py:34-69 — extract_attachment` | `domain/attachment_extraction.py:34-69` | confirmed | exact match |
| i3-attach | "Types: PDF, DOCX, XLSX, CSV, HTML, Markdown, text" | `domain/attachment_extraction.py:48-67` | confirmed | |
| i3-attach | "Images: empty text plus needs_ocr flag; never run" | `domain/attachment_extraction.py:45-46` | confirmed | |
| i3-attach | "Caps: 200 per page, 20 MB each" | none in this folder | missing | not implemented in `domain/attachment_extraction.py`; likely owned by `confluence_sync/application/sync_service.py` (cited by the panel itself for its second location) |
| i3-attach | "Failure: today, per attachment, skipped" | `domain/attachment_extraction.py:69` | confirmed | `extract_attachment` never raises, returns `method="skipped"` |
| i3-tsv | code at `application/versioning.py:40-43,140 — _tsv` | `application/versioning.py:40-43,140` | confirmed | exact match, `to_tsvector('english', title + heading path + text)` |
| i3-tsv | code at `platform/db/models.py:315-320 — GIN index` | n/a | missing | owned by platform |
| i4-document | "One row per page… stage_and_activate, step 1" | `application/versioning.py:200` (`ensure_document(session, meta.page_id)`) | confirmed | |
| i4-staging | code at `application/versioning.py:206-221 — the insert` | `application/versioning.py:206-221` | confirmed | exact match |
| i4-staging | "Today: uniqueness (document_id, cf_version, retrieval_schema_version, embedding_model); a second build at one page version collides" | `application/versioning.py:206-221` (no collision handling / no try-except around the insert) | confirmed | the constraint itself lives in `platform/db/models.py:225-231` (not this folder); this folder's code does not guard against or catch the collision, consistent with "collides" |
| i4-staging | tests "Replace an attachment only…", "Run the same job twice…" | not in this folder | missing | tests live in `confluence_sync/tests/test_attachment_wiring.py` and `confluence_sync/tests/test_worker_sync.py` |
| i4-chunks | code at `application/versioning.py — build_chunks, _link_chunks` | `application/versioning.py:59-146,294-311` | confirmed | |
| i4-chunks | "Order: parents flushed first, then children mapped" | `application/versioning.py:294-307` | confirmed | |
| i4-chunks | "Flags: is_active = false" | `application/versioning.py:99` (`common` dict) | confirmed | |
| i4-chunks | "Uniqueness (doc_version_id, stable_key)" | not evidenced in this folder | missing | DB constraint, owned by `platform/db/models.py` |
| i4-gate | code at `application/versioning.py:238-242 — the gate` | `application/versioning.py:238-242` | confirmed | exact match, including `state=failed`, raise, and the docstring-referenced empty-page case |
| i4-swap | code at `application/versioning.py:314-375 — _activate` | `application/versioning.py:314-375` | confirmed | exact match |
| i4-swap | code at `platform/db/models.py:235-240 — ux_document_version_one_active` | n/a | missing | owned by platform |
| i4-stamp | code at `application/versioning.py:34-37,88-92,352-353 — the seam` | `application/versioning.py:34-37,88-92,352-353` | confirmed | exact match; `_SOURCE_TYPE="confluence"`, `_SOURCE_ID="confluence:default"` |
| i4-stamp | "tags from source_scope union labels" | `application/versioning.py:93,354` (`tags=list(tags) if tags is not None else []`) | drifted | `versioning.py` only stamps whatever `tags` list it is handed as a parameter; the union-of-labels computation itself is not present in this folder (comment at line 90 says it is "threaded from the covering source_scope root(s)") |
| i4-failed | "State failed; cleanup: GC deletes failed versions later" | `application/versioning.py:240,378-399` | drifted | `_gc_superseded` (378-399) queries only `state == DocState.superseded` (line 385); a version set to `failed` directly by the gate (line 240) never becomes `superseded` and is never touched by this function — see Known gaps |
| i4-gc | code at `application/versioning.py:378-399 — _gc_superseded` | `application/versioning.py:378-399` | confirmed | exact match; keeps `DEFAULT_RETAIN_SUPERSEDED = 2` (line 32) most recent |
| i4-rollback | code at `application/versioning.py:419-460 — rollback_to` | `application/versioning.py:419-460` | confirmed | exact match |
| i4-rollback | tests "Roll back, then sync same content: no_change", "…newer edit arrives: detected, not masked" | not in this folder | missing | tests live in `confluence_sync/tests/test_versioning_rollback.py` |
| tg-add | steps referencing stage 1/2 label handling and stage 3/4 first-index build | none given | missing | no "Where in the code" section on this panel; owned primarily by `confluence_sync` (labels/scope-state), ingestion's contribution (full build via `stage_and_activate`) has no direct panel-cited pointer |
| r3-classified | "Classified chunks are deleted outright" | none found (`grep classified` empty in this folder) | missing | no "classified" handling anywhere under `apps/automation/app/features/ingestion`; likely owned by `confluence_sync` |
| s-writer | code at `platform/db/schema.py:52-68 — apply_chunk_rls` | n/a | missing | owned by platform |
| s-classified | "label sets state = classified…deactivated and chunk rows deleted" | none found in this folder | missing | same as r3-classified |
| ks-index | "queued job runs ingestion stages 2 to 4…tags on chunks are recognized labels" | `application/versioning.py:93,354` (tags stamped on chunks and page_source) | confirmed | tags-on-chunks part evidenced here; the "queued job runs stages 2-4" orchestration itself is `confluence_sync`, outside this folder |
| d-page_source | code at `platform/db/models.py:95-158 — PageSource` | n/a | missing | owned by platform; this folder reads/writes the table via the ORM model (see Reads and writes) but does not define it |
| d-document | code at `platform/db/models.py:180-194 — Document` | n/a | missing | owned by platform |
| d-document_version | code at `platform/db/models.py:197-241 — DocumentVersion` | n/a | missing | owned by platform |
| d-chunk | code at `platform/db/models.py:244-342 — Chunk` | n/a | missing | owned by platform |
| sc-kb | code at `platform/db/models.py, schema.py`; `alembic/versions/`; `config/knowledge_scopes.json`; `scripts/seed_curated_knowledge.py` | n/a | missing | all owned by platform / knowledge-base infra, none in this folder |

## Not on the design page
- `apps/automation/app/features/ingestion/domain/tokenization.py` (`TokenCounter`, tiktoken/heuristic backend) — no panel in this assignment's list names it directly, though `i3-children`'s "Split order" note describes its effect.
- `apps/automation/app/features/ingestion/application/services.py` (`IngestionServices`, `build_ingestion_services`) — the dependency-wiring bundle (counter, config, contextualizer, embedder) has no panel of its own.
- `apps/automation/app/features/ingestion/domain/change_detection.py:80-101` (`index_config_changed`) — the pipeline-config-change detector that forces a full re-embed; not named by any panel in this list, though its effect is described in `ov-build`'s "Note".
- Meta-refusal detection in `application/contextualizer.py:34-80,125-129` (discarding LLM replies that talk about "not having access to the document") — real, tested behavior with no corresponding design panel.
- `apps/automation/app/features/ingestion/domain/normalization.py:149-170` (`build_sections`) and `173-181` (`content_hash`/`structure_hash` functions) — used by both stage-2 classification and stage-3 chunking; not individually named by any panel.
