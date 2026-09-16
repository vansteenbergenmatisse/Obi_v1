# Design-vs-code delta — one row per panel (192/192)

Sorted by the phase of the action plan that first names the panel (Phase 0 regression items
first, ascending, unscheduled last). `found` cites `synopsis-file.md:line` from
`docs/Final_docs/0.3-code-vs-design-audit-2026-09-14/`. `today`/`target` are paraphrased from
`docs/Final_docs/obi-system-brief.md` (verbatim where short enough to quote directly).

Change-column rule (from the assignment): `none` = confirmed and target equals today. `small`
= target is under a day of work, or the row is a documentation/citation fix only. `large` = a
stage or a table changes. `blocked` = the panel's own status/text names a genuinely open,
unresolved owner call (not inferred from `docs/plan/decisions.md`, which is unpopulated).

## Phase 0 — regression items (91)

| panel | today | found | target | change |
|---|---|---|---|---|
| ov-confluence | Live on one Confluence Cloud site; 4 labeled test pages indexed; Basic Auth API token in root .env | confirmed via platform ownership — HttpConfluenceClient/FixtureConfluenceGateway exist as described (confluence_sync.md:121, cites platform/clients) | restrictions endpoint fails closed (page treated as restricted to nobody) | none |
| ov-corpus | Supabase Cloud pgvector 0.8.2; "Alembic head 0009 live; 0010 coded, not yet applied" | drifted — chain already runs through 0012; commit 2435127 says "0012 applied to Supabase," contradicting "0009 live" (alembic-and-scripts.md:70) | never disable RLS on Supabase; never run the 0009 downgrade there | small |
| ov-widget | Built in apps/web; launcher/teaser/panel/composer/images/screenshot/6 locales; "shared invite token for the pilot" | drifted — pilot invite token already deleted (ADR/PLAN 11.1c), replaced by per-user JWT (widget.md:77) | (page is stale, not code) | small |
| cm-root | Builds the app, retriever, answer service, scheduler; mounts the two routers | confirmed — all five steps present (entrypoint.md:59); one step's own description is imprecise (entrypoint.md:63, drifted) | (no substantive target beyond today) | none |
| cm-docs | ADR list 0001–0013(9 named) | confirmed titles match (packages-config-infra-docs.md:64); "needs at least one new ADR: fingerprint, scope_state, label-gated ingestion, edge token" is needs-live/unverified from static code (packages-config-infra-docs.md:65) | write the missing ADR(s) | small |
| cm-contracts | Types + "planned: token-claims.json and iframe-messages.ts" | drifted — both files already exist and are wired (packages-config-infra-docs.md:55) | (already done, page stale) | small |
| cm-tokens | Light theme, indigo accent, Inter | confirmed (packages-config-infra-docs.md:57) | (none) | none |
| cm-infra | docker-compose pins pgvector 0.8.x; local dev + test DB; "production is Supabase" | confirmed for local; needs live for the production claim (packages-config-infra-docs.md:63) | (none beyond live confirmation) | small |
| i1-checks | Rate 300/min, body cap 512 KiB, HMAC, no-secret 503, bad JSON 400 | confirmed (confluence_sync.md:88; shared.md:57) | (none) | none |
| i1-ledger | Dedup key = event_type+page_id+cf_version+space_id+status+event_timestamp+delivery_id | confirmed (confluence_sync.md:89) | (none) | none |
| i1-self | actor == service account → marked, no job | confirmed (confluence_sync.md:90) | (none) | none |
| i1-claim | FOR UPDATE SKIP LOCKED, 120s lease | confirmed (confluence_sync.md:93; platform.md:81) | (none) | none |
| i1-reaper | Finds expired leases, resets to pending | confirmed (platform.md:83) | (none) | none |
| i1-fail | 5 attempts, backoff 5×2^(n-1) capped 1h, error cut 4000 chars | confirmed (platform.md:84) | (none) | none |
| i1-handle | sync_page/delete_page/reconcile_space; commit together; drain 100/tick | confirmed (confluence_sync.md:98) | (none) | none |
| i2-fetch | Always fetch meta/labels/restrictions/attachments; body only when moved | confirmed (confluence_sync.md:99; platform.md:85) | (none) | none |
| i2-meta | Labels/permissions-only change → update in place | confirmed behavior; panel's own line-range citation is stale (confluence_sync.md:106, drifted) | (doc fix) | small |
| i2-nochange | Fingerprint equals stored → update last_reconciled_at, stop | confirmed (confluence_sync.md:103) | (none) | none |
| i2-tobuild | Body/attachment blocks handed to chunker | missing — panel gives no code location to check, conceptual hand-off only (ingestion.md:72) | (none) | none |
| i2-inplace | Writes page_source + active chunks; replaces page_restriction rows | confirmed (confluence_sync.md:107) | (none) | none |
| i3-blocks | Normalize HTML → blocks; tables/code kept whole | drifted — file is `normalization.py` not `normalize.py` (ingestion.md:73); attachment part confirmed (ingestion.md:74) | (rename the panel's citation) | small |
| i3-parents | ~1200 tokens, cap 2000, never crosses heading | confirmed (ingestion.md:75-76) | (none) | none |
| i3-children | ~400 tokens, 12% overlap, identity keys, links | confirmed (ingestion.md:77-80); "kind=1" needs live — value defined in platform (ingestion.md:81) | (none) | small |
| i3-context | Title + heading path + Haiku note + child text; fail-soft | drifted — line refs stale, code sample no longer literal (`_metadata_prefix`/`_compose` replaced the shown snippet) (ingestion.md:82-83); cost/storage/fail-soft confirmed (ingestion.md:84-86) | (doc fix) | small |
| i3-tsv | to_tsvector('english', title+path+text), GIN indexed | confirmed (ingestion.md:94); GIN index citation off ~13 lines (platform.md:91, drifted) | (doc fix) | small |
| i4-document | One document row per page | confirmed (ingestion.md:96) | (none) | none |
| i4-chunks | Parents first, then children; is_active=false | confirmed (ingestion.md:100-102) | (none) | none |
| i4-gate | Zero children → failed, live version untouched | confirmed (ingestion.md:104) | (none) | none |
| i4-swap | One transaction: supersede old, activate new, repoint | confirmed (ingestion.md:105); index citation off ~5 lines (platform.md:94, drifted) | (doc fix) | small |
| i4-failed | State failed; "cleanup: GC deletes failed versions later" | drifted — real gap: `_gc_superseded` only ever selects `state==superseded`; a version set `failed` by the gate never transitions and is never GC'd (ingestion.md:109) | GC logic must also collect `failed`-state versions | large |
| i4-gc | Keeps 2 most recent superseded versions, deletes older | confirmed for its own defined scope (ingestion.md:110) | (none) | none |
| i4-rollback | Repoint + restore hashes so next sync isn't masked | confirmed (ingestion.md:111); named tests live in confluence_sync, not this folder (ingestion.md:112, missing) | (none) | none |
| tg-add | Label event → stage 1/2 handling, first-index build | missing — panel gives no code location, behavior distributed and already confirmed via i1/i2/i4 rows | (none) | none |
| tg-change | label_deleted then label_added; worker reads current set | confirmed — worker re-fetches labels fresh each sync (confluence_sync.md:120) | coalescing itself is not built (tracked under i1-enqueue, Phase 2) | none |
| tg-first | Build creates document/version/chunks with tags | not audited in any 0.3 synopsis (no row names `tg-first` specifically) | (none named) | small |
| tg-retag | Touches page_source.tags/chunk.tags/scope_state/labels_hash only | drifted — citation stale (confluence_sync.md:307-320 → actual `_apply_metadata_only` is elsewhere); `scope_state` field does not exist yet anywhere (confluence_sync.md:113) | scope_state column (tracked under tg-state, Phase 2) | small |
| r1-proxy | POST /api/chat, Bearer CHAT_API_KEY, SSE unbuffered, 30 MB cap; "its own auth: x-widget-access-token today" | confirmed the proxy mechanics (widget.md:108); drifted — `x-widget-access-token` no longer exists, the target (X-Obi-Token forwarding) is already built (widget.md:109) | (page stale, code ahead) | small |
| r1-limits | Rate 20/min, history 1-20×4000, images 4×5MB, LLM 30s/2/5, output 8000 chars, PII redaction | confirmed values; cited line ranges stale (docstring grew) (rag_agent.md:78) | (doc fix) | small |
| r1-small | Closed-set exact match, Haiku 150 tokens, static fallback, images dropped | confirmed behavior; `is_small_talk` line moved (rag_agent.md:80) | (doc fix) | small |
| r1-clarify | Flag off by default, 12-word heuristic, fails open | confirmed `decide_clarification`; `parse_clarification_reply` cited at wrong location (rag_agent.md:81) | (doc fix) | small |
| r1-idem | Header Idempotency-Key; key binds principal today, "target: token subject" | drifted — ahead of design: already binds `token_subject`, not body principal, contradicting the stated open target (rag_agent.md:82) | (page stale, code ahead) | small |
| r1-short | Small talk / clarification write no query_trace row | confirmed, with a named test (rag_agent.md:84) | (none) | none |
| r2-embed | Same embedding model as pages; empty text skipped | drifted — panel's own cited line is off by one (retrieval.md:81) | (doc fix) | small |
| r2-gucs | set_config for sources/scopes; hnsw.ef_search=100 | confirmed content; cited range 21-49 misses `apply_knowledge_scope` at 58-76 (retrieval.md:82-83) | (doc fix) | small |
| r2-dense | Cosine `<=>`, HNSW index, candidate_k=75 | confirmed content; cited range off ~27 lines (retrieval.md:84); index DDL citation owned by platform (retrieval.md:85, missing here) | (doc fix) | small |
| r2-keyword | plainto_tsquery AND→OR, ts_rank, limit 75 | confirmed content; cited range off ~30 lines (retrieval.md:86) | (doc fix) | small |
| r2-indexes | HNSW + GIN index definitions | confirmed content; GIN citation off ~13 lines, same shift as i3-tsv (platform.md:96) | (doc fix) | small |
| r3-reader | rag_reader: LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS | confirmed; `ensure_reader_role` cited ~162 lines off (platform.md:97-98) | (doc fix) | small |
| r3-source | chunk_source_read policy, ENABLE/NO FORCE | confirmed; citation cuts off before the actual CREATE POLICY statement (retrieval.md:97; platform.md:99, same gap) | (doc fix) | small |
| r3-acl | page_restriction rows, fresh per request, before rerank | confirmed content; `fetch_page_scopes` citation off ~27 lines (retrieval.md:100) | (doc fix) | small |
| r3-torerank | Up to rerank_depth candidates fetched in same transaction | confirmed (retrieval.md:102) | (none) | none |
| r3-deny | Forgotten set_config → zero rows (fail closed) | not a Claims-table row in any synopsis — only mentioned in `retrieval.md`'s Known gaps (retrieval.md:55), not its Claims table | (audit gap flagged) | small |
| r3-groups | Groups expanded to members at sync time; sentinel on failure | confirmed (retrieval.md:101, missing-here/owned-elsewhere; platform.md:102, confirmed) | (none) | none |
| r4-rerank | Cohere rerank-v3.5, /v2/rerank | confirmed call + size; panel's own cited call-site line is wrong (retrieval.md:107; platform.md:103-104) | (doc fix) | small |
| r4-weak | Compare top score to refusal_min_rerank_score=0.10 | drifted — threshold already recalibrated to 0.05 as of 2026-09-12, not 0.10; function line moved (rag_agent.md:86) | update the design page's threshold number | small |
| r4-proceed | Top-k passages + scores + coverage verdict move to stage 5 | confirmed partial — top-k+scores built exactly as described; "coverage verdict" doesn't exist yet (tracked under r5-coverage) (retrieval.md:112) | (none for this panel's own scope) | none |
| r5-evidence | [n] Page title + parent text, 1-based numbering | not audited in any 0.3 synopsis (no dedicated Claims row in rag_agent.md) | (none named) | small |
| r5-generate | claude-sonnet-5, 800 tokens, cached system prompt | not audited in any 0.3 synopsis (no dedicated Claims row in rag_agent.md; only referenced inside the ov-answer row) | (none named) | small |
| r5-enforce | Split into sentences; keep only cited; strip invented markers | confirmed `enforce_citations` exactly; degrade path cited at wrong lines (rag_agent.md:91) | (doc fix) | small |
| r5-stream | start/token(40/15ms)/citations/done events; one query_trace row | confirmed behavior; `_stream_answer` cited at stale lines (rag_agent.md:92; widget.md:113, confirmed) | (doc fix) | small |
| r5-nocite | Refuse no_citations when nothing survives | drifted — the `unsupported` half of this panel's own reason list doesn't exist yet (no support-check module); `no_citations` half fully confirmed (rag_agent.md:95) | (tracked under r5-ground, Phase 3) | small |
| r5-image | Second Claude call, 500 tokens, anti-injection, never cited | confirmed behavior; cited lines stale (rag_agent.md:93) | (doc fix) | small |
| r5-feedback | PATCH /chat/{trace_id}/feedback, ±1, writes query_trace.feedback | confirmed; cited lines stale (rag_agent.md:96) | (doc fix) | small |
| w-launcher | Teaser 3s/20s; opens from launcher or teaser | confirmed (widget.md:92) | (none) | none |
| w-panel | Fixed overlay, clamp(360px,29%,440px); one ChatSessionProvider | confirmed (widget.md:93) | (none) | none |
| w-composer | Images: base64 newest turn, 4/turn, "5 MB each" | drifted — 4-per-turn confirmed; 5 MB cap is not enforced anywhere client-side (widget.md:94) | add a client-side size check | small |
| w-scope | "Set once, by the embedding page, as the knowledgeScope prop" | drifted — real `/embed` frame never sets this prop; scope comes from the verified token instead (widget.md:96); dev-switcher part confirmed (widget.md:97-98) | (page describes a path the real embed doesn't use) | small |
| w-proxy | /api/chat + feedback route; adds server key; byte passthrough | confirmed (widget.md:103) | (none) | none |
| w-i18n | Six locales; greeting/chips/placeholder/footer/teaser/menus | confirmed (widget.md:104) | (none) | none |
| w-screenshot | html-to-image; hides widget root; lands in attachment strip | confirmed (widget.md:107) | (none) | none |
| w-render | Streamed tokens, citation chips, refusal banner, clarifying chips | confirmed for today's scope; "partial" amber note not built yet (widget.md:105-106, tracked under r5-partial) | (none for today's own scope) | none |
| d-event_ledger | One row per delivery; dedup keys; status enum | confirmed (confluence_sync.md:124); model citation off by 11 lines (platform.md:105, drifted) | (doc fix) | small |
| d-document | One row per page, stable id | confirmed (platform.md:108; ingestion.md:119, missing-here) | (none) | none |
| d-reconciliation_run | One row per sweep with counts | confirmed (confluence_sync.md:126); model citation off by 11 lines (platform.md:111, drifted) | (doc fix) | small |
| d-page_restriction | One row per (page, principal); zero rows = open | confirmed (confluence_sync.md:123; platform.md:113) | (none) | none |
| s-source | Lock 1, ADR-0004/0013, fails closed | confirmed for the in-folder half (retrieval.md:119) | (none) | none |
| s-acl | Lock 3, ADR-0005, fails closed, runs before rerank | confirmed (retrieval.md:120) | (none) | none |
| s-permitted | Only rows passing all locks reach reranker/generator | confirmed (retrieval.md:121) | (none) | none |
| s-writer | Owner exempt via NO FORCE RLS | drifted — same citation gap as r3-source (platform.md:116); confirmed for local role, needs live for Supabase owner role (packages-config-infra-docs.md:76) | (doc fix + a live check) | small |
| s-reader | rag_reader used by HybridRetriever's transactions etc. | confirmed partial (retrieval.md:123; alembic-and-scripts.md:92) | (none) | none |
| s-anon | anon/authenticated hold GRANT SELECT, blocked by RLS only | confirmed (platform.md:117) | never disable RLS on Supabase | none |
| s-audit | Per-query/per-refusal/per-sync audit fields | drifted — `subject_hash` already shipped (half the target); `decision` field still absent; per-refusal/per-sync log lines owned by other features (platform.md:118) | add `decision` column (tracked under d-query_trace, Phase 3) | small |
| ks-index | Queued job runs stages 2-4; tags on chunks = recognized labels | confirmed for the tags-on-chunks part (ingestion.md:117) | (none) | none |
| vd-text | Title + heading path + note + child text, ~400 tokens | confirmed (platform.md:123) | (none) | none |
| vd-column | chunk.embedding vector(3072), nullable, children only | needs live — code default is 1024 dims (Voyage), deployed dim depends on `.env` (platform.md:119); structural claim confirmed (alembic-and-scripts.md:98) | pick one default (tracked as vd-model, unscheduled/blocked) | small |
| vd-hnsw | ix_chunk_embedding_hnsw, halfvec, m=16/ef_construction=200 | confirmed (platform.md:120; alembic-and-scripts.md:97) | (none) | none |
| vd-nearest | Top 75 nearest by cosine distance | confirmed (platform.md:126) | (none) | none |
| vd-rls | RLS on chunk covers the embedding column | confirmed (platform.md:121; alembic-and-scripts.md:99) | (none) | none |
| vd-question | Question embedded with same model; compared by cosine | needs live — same dimension-parameterization open question as vd-column/vd-model (platform.md:127) | (tracked as vd-model, unscheduled/blocked) | small |
| vd-keyword | tsv = to_tsvector('english', ...), GIN | confirmed (platform.md:122) | (none) | none |
| vd-swap | New chunks inactive, one flip, old vectors go inactive | confirmed (platform.md:124); no retention-delete DDL exists at the migration level, but the behavior is confirmed via i4-gc (alembic-and-scripts.md:96, missing at DDL layer only) | (none) | none |

## Phase 1 (17)

| panel | today | found | target | change |
|---|---|---|---|---|
| cm-agent | Router, answer_service, llm_client, prompt, citations, refusal, small_talk+clarification "the two short-circuits", pii, curated_knowledge_repo, answer_cache(remove) | drifted — omits `domain/identity.py`, `application/auth_context.py`, `server/token_verifier.py`; there are three short-circuits, not two (identity is the third) (rag_agent.md:76) | update the code-location list and short-circuit count | small |
| cm-platform | Models/roles, four API clients, settings, job queue; imports no feature | drifted — omits `platform/logging/`, imported by every client and main.py (platform.md:74) | add logging/ to the inventory | small |
| cm-alembic | 0001–0010 named; "live head on Supabase: 0009"; "target adds one migration, 0011" | confirmed for 0001–0010's names (alembic-and-scripts.md:73); drifted — the target's described 0011 doesn't match reality: the two RESTRICTIVE policies already shipped in 0010, and the real 0011 only adds `subject_hash` (alembic-and-scripts.md:74) | rewrite the whole migration-plan section against what 0010/0011/0012 actually shipped | large |
| cm-scripts | setup_supabase.py, seed_source_scope.py, seed_curated_knowledge.py, run_reconciliation_once.py, verify_knowledge_scope_backfill.py, verify_knowledge_scope_live.py, rotate_chat_api_key.py | confirmed, all seven (alembic-and-scripts.md:75-81) | (none) | none |
| cm-config | obi-general-test/mews-test/operacloud-test/toast-test; "next to it (planned): platforms.json" | confirmed today's list (platform.md:77-78; packages-config-infra-docs.md:59); drifted — platforms.json already exists, not planned (packages-config-infra-docs.md:60); code sample doesn't match the file's real object shape (packages-config-infra-docs.md:61) | (page stale, code ahead) | small |
| cm-web | ui/, api/chat-client.ts, server/(route-handlers, validation, "auth.ts"), model/, embed/(planned) | confirmed most locations (widget.md:83-84,86-87); drifted — `auth.ts` was deleted (widget.md:85); `embed/` is built and tested, not planned (widget.md:88) | update the file list and remove "(planned)" | small |
| tg-config | Path + today's 4 scopes; "also read by the widget build ... generates its scope list" | confirmed the file/loader (packages-config-infra-docs.md:67); drifted — the widget's copy is a hand-mirrored file guarded by a test, not build-time generated as claimed (widget.md:116) | either build a real generator or change the claim to "hand-mirrored, drift-tested" | small |
| r1-rewrite | Haiku rewrite; target output is {"query","parts"} JSON | drifted — `rewrite()` still returns a plain string only, never the parts JSON the coverage check needs; consistent with the panel's own `change` status (rag_agent.md:83) | rewrite() must emit the parts list — needed before r5-coverage can work | large |
| ks-edit | Path + "shape: a JSON list of lowercase slugs" | drifted — actual file is an object `{scopes:[{name,description}]}`, not a flat list (packages-config-infra-docs.md:69) | fix the shape description | small |
| ks-validate | Lowercase/unique/general-required checks at startup | not a Claims-table row in the owning platform synopsis; only cross-referenced as out-of-scope from `widget.md:117` | (audit gap flagged) | small |
| ks-deploy | "Widget build imports the same file and generates its scope list, without classified" | drifted — same hand-mirror issue as cm-config/tg-config (widget.md:118) | (see tg-config) | small |
| ks-widget | "Embed config sets knowledgeScope to the slug" | drifted — real embed path never sets a scope from embed config; comes from the verified token (widget.md:119) | (page describes a path the real embed doesn't use) | small |
| sc-frontend | "Embedded in a platform page with a scope from its config. A shared pilot token gates it." | drifted — pilot token retired; scope-from-embed-config model retired for the real /embed route (widget.md:123-124); rest confirmed (widget.md:125-126) | (page stale, code ahead) | small |
| sc-backend | "Owns... token verification, ..., search, rerank, coverage, generation, the citation and support checks, the audit trail" | drifted — coverage and support checks are named as already owned but do not exist yet (rag_agent.md:98); everything else confirmed across folders (confluence_sync.md:129; retrieval.md:124; entrypoint.md:71-77; evaluation.md:71) | (tracked under r5-coverage/r5-ground, Phase 3) | small |
| sc-kb | Models/schema, 0001-0010, knowledge_scopes.json, platforms.json(planned), seed scripts | drifted — migration range undercounts (0011,0012 exist); platforms.json already built, not planned (platform.md:129; alembic-and-scripts.md:100-101; packages-config-infra-docs.md:72) | update migration range and remove "(planned)" | small |
| em-token | "Today: Does not exist. The pilot uses one shared invite token..." | confirmed true only for `platform/` (platform.md:130); drifted — a full RS256 JWT flow (iss/aud/sub/iat/exp/company fields) is already built and tested for test-hosts, live-proven per commit 59385f4 (widget.md:128-130) | rewrite "Today" to reflect the built test-host flow; only real-platform wiring remains | large |
| em-backend | "rag_agent/server/token_verifier.py — (planned)"; "auth_context.py — (planned)" | drifted — both files already exist, fully built and tested (rag_agent.md:99); platforms.json also already built, not planned (packages-config-infra-docs.md:74-75) | rewrite "planned" labels; only real-platform onboarding remains | large |

## Phase 2 (31)

| panel | today | found | target | change |
|---|---|---|---|---|
| i1-webhook | Handler built and tested; "not reachable until public HTTPS URL" | confirmed (confluence_sync.md:86); needs live — only checkable once deployed (confluence_sync.md:87) | public URL with the AWS deploy | small |
| i2-classify | Order: gone → first-index → version guard → config → metadata/body | drifted — folder-ownership citation issue only; `_REBUILD_CLASSES` itself confirmed (confluence_sync.md:102) | (doc fix) | small |
| i1-sweep | Daily lightweight + 14-day complete sweep over source_scope roots | confirmed today (confluence_sync.md:94; alembic-and-scripts.md:95); missing — the target label sweep (CQL search across all spaces) does not exist (confluence_sync.md:95; platform.md:82) | build the daily label sweep | large |
| i1-enqueue | Idempotency key includes event_type; two different events at one version aren't coalesced | confirmed today's key shape (confluence_sync.md:91); missing — target partial-unique-index `ux_job_pending_sync_page` not present (confluence_sync.md:92; platform.md:79-80) | add the coalescing index + redesign the key | large |
| d-job | job_type/status/priority/attempts/lease columns | confirmed model shape, line ref off by 11 (platform.md:106); target partial-unique index on (page_id) WHERE status=pending not present (same gap as i1-enqueue) | add the pending-job index | large |
| ks-sweep | "The sweep walks folder roots from source_scope. A label search does not exist yet." | confirmed today, matching the panel's own words (alembic-and-scripts.md:95); missing — target CQL label sweep not built (confluence_sync.md:127) | (same as i1-sweep) | large |
| ks-orphan | "Pages with only that tag go out" | missing — target not implemented: `sync_service.py` computes `final_tags` but an empty result never triggers deactivate (confluence_sync.md:128) | wire empty-final-tags → deactivate | large |
| i2-hash | Five hashes (content/structure/attachment/access/labels) + pipeline stamps | confirmed storage on page_source/document_version (platform.md:86); computation confirmed present today, folder-ownership citation issue only | wire fingerprint as the version-uniqueness key (tracked under i4-staging) | small |
| d-page_source | Hashes, scoping, stamps; "target: + scope_state, + index_fingerprint" | confirmed today's columns (platform.md:107; ingestion.md:118, missing-here) | add scope_state + index_fingerprint columns | large |
| i2-labels | Labels intersected with scope list; conflict on 2+ provider labels | drifted — panel's own Code sample shows a `State` enum that doesn't exist; actual return is a `(tags, conflict, matched_labels)` tuple (confluence_sync.md:100); file-part confirmed (packages-config-infra-docs.md:66) | fix the code sample | small |
| tg-state | scope_state enum on page_source/chunk, ok/conflict/classified/unlabeled | missing — no such field or enum exists anywhere (confluence_sync.md:116; ingestion.md — same, per Known gaps) | build the whole enum + migration + policy wiring | large |
| tg-two | Zero label tags, conflict logged, page hidden everywhere | confirmed (confluence_sync.md:111) | (belt-and-suspenders fix ties to tg-state) | small |
| tg-conflict | State=conflict, visible to nobody, logged, heals on fix | confirmed (confluence_sync.md:118) | (none) | none |
| i2-gone | Trashed/archived/deleted/classified/unlabeled → deactivate | confirmed for status-based deactivation; drifted — "classified" and "unlabeled" triggers are not implemented anywhere (confluence_sync.md:104) | build classified/unlabeled deactivate triggers | large |
| tg-remove | "Today the page keeps its tags and stays indexed even with no recognized tag" | confirmed — matches design's own stated Today exactly (confluence_sync.md:109) | deactivate-on-unlabeled is the whole target, unbuilt | large |
| tg-classified | Add classified → deactivate + delete chunks | missing — no classified handling anywhere in the codebase (confluence_sync.md:110) | build the whole classified pipeline | large |
| tg-purge | Deactivate + DELETE chunk rows of every version | missing — no `delete(Chunk)` anywhere (confluence_sync.md:115) | build purge-on-classified | large |
| tg-deactivate | page_status updated, version superseded, chunks inactive | confirmed — `deactivate_page` exists and is called from i2-gone's triggers (confluence_sync.md:114) | (mechanism exists; new triggers are the gap, see tg-remove/i2-gone) | none |
| i2-rebuild | Body/structure/attachment/title/config change or first index → full rebuild | confirmed (confluence_sync.md:105; ingestion.md:71) | vector reuse removed (tracked under i3-embed) | small |
| i3-embed | "Today only changed children are embedded (stable_key reuse)" | confirmed today's reuse behavior (ingestion.md:88); missing — target (no reuse, every rebuild embeds the whole page) not built (ingestion.md:87, owned by platform for the call site) | remove stable_key reuse entirely | large |
| i3-attach | PDF/DOCX/XLSX/CSV/HTML/MD/text; images→empty+needs_ocr; caps 200/20MB | confirmed extraction types and failure-is-skipped behavior (ingestion.md:89-91,93); missing — caps (200/page, 20MB each) not enforced in this folder (ingestion.md:92) | enforce the caps | small |
| i4-staging | "Today: uniqueness is (document_id, cf_version, retrieval_schema_version, embedding_model)" | confirmed the insert (ingestion.md:97); drifted — the constraint was already widened to 7 columns by migration 0012, an intermediate shape neither the design's "today" nor its "target" describes (platform.md:92-93; alembic-and-scripts.md:89,93) | reconcile the target with what 0012 actually shipped | large |
| d-document_version | Unique today (4-col); unique target (document_id, index_fingerprint) via migration 0011 | drifted — 0012 already widened the constraint to 7 columns via a different mechanism than the design's index_fingerprint plan (ingestion.md:120, missing-here; platform.md:109; alembic-and-scripts.md:89-90) | (same reconciliation as i4-staging) | large |
| i4-stamp | source_type/source_id constants; "tags from source_scope union labels" | confirmed the stamping seam (ingestion.md:107); drifted — union-of-labels computation is done by the caller, not versioning.py (ingestion.md:108) | wire scope_state once it exists (tracked under tg-state) | small |
| s-classified | Label sets state=classified → deactivated, chunks deleted | missing — same root gap as tg-state (confluence_sync.md:116; ingestion.md:116) | (same as tg-state) | large |
| d-source_scope | "Today: Four active page roots with empty tags cover the four test pages. Nine old roots are inactive." | drifted — row-count is a live fact; "no longer read by sweeps" is target, not today: `reconciliation.py` still calls `resolve_space_scope` on every sweep (confluence_sync.md:122); table still exists per plan (alembic-and-scripts.md:91) | **[Decision needed]** "keep the table until label-gated ingestion is proven live, then drop it" — no confirmed timeline; genuinely open per the panel's own status `discuss` | blocked |
| ks-remove | "Pages with only that tag go out" | missing — depends on the ks-orphan/tg-remove gap above; the file-edit half of "remove a tag" is confirmed, the page-deactivation half is not (widget.md:120) | (same as ks-orphan) | large |
| tg-edit | page_updated with higher version → rebuild → activate with current labels' tags | confirmed (confluence_sync.md:112) | vector reuse removed (tracked under i3-embed) | none |
| tg-rebuild | Rebuild with the label read in this sync stamped onto the new version | confirmed (confluence_sync.md:119) | (same as tg-edit) | none |
| e-monitor | Index age, held-out recall, groundedness telemetry | missing — no such telemetry exists anywhere in the repo (evaluation.md:70) | build the whole freshness/recall monitor | large |
| tg-filter | App predicate `tags && :scopes` behind a flag, plus the 0010 RESTRICTIVE policy | missing at the design's target predicate (`scope_state='ok' AND tags && allowed_scopes`) — coded in migration 0010 but not applied live; app predicate is flag-gated (confluence_sync.md:117, owned by platform+retrieval) | apply 0010 to Supabase and turn scope_state='ok' on (tracked under r3-scope) | large |

## Phase 3 (28)

| panel | today | found | target | change |
|---|---|---|---|---|
| e-gold | "Does not exist. Current datasets: retrieval_smoke, permission, ambiguity, out_of_corpus, a few cases each" | drifted — dataset names/small counts confirmed (18 cases total vs the 150-250 target); "14-document fixture" is ambiguous under any file count found (evaluation.md:61) | author the 150-250 case gold set | large |
| e-split | Dev/held-out halves, tune on dev, report on held-out | missing — no dev/held-out split exists anywhere; all four datasets are single undivided files (evaluation.md:72) | build the split | large |
| e-stage1 | Recall at k before rerank | confirmed helpers exist (recall_at_k, etc.) (evaluation.md:64); missing — no recall@75-across-fused-candidates metric wired, no default k=75 (evaluation.md:65) | wire the fused-candidate recall@75 measurement | small |
| e-stage2 | Precision@5, NDCG@10, rerank lift | drifted — function fully implemented and tested but lives in `runner.py`, not a dedicated `rerank_lift.py` as the design states (evaluation.md:66); values confirmed (evaluation.md:67) | (file-location correction) | small |
| e-stage3 | Context-assembly metric: did the model get every required passage | missing — no such metric exists anywhere (evaluation.md:73) | build the stage-3 metric | large |
| e-stage4 | Essential facts, forbidden claims, citation support, refusal-when-expected | missing — no grading harness or judge model exists anywhere (evaluation.md:74) | build the whole stage-4 grading harness | large |
| r2-prov | Candidate dataclass on every candidate (ids, ranks, scores) | missing — `class Candidate` doesn't exist anywhere in retrieval (retrieval.md:92) | build provenance dataclass — Priority 1 infrastructure | large |
| r2-rrf | "Today fuses two lists of page ids"; target unit is child chunk id | confirmed formula and today's page-id fusion (retrieval.md:88,90); missing — chunk-id fusion (the target) not built (retrieval.md:91) | fuse by chunk id, not page id — Priority 1 | large |
| r4-texts | "Today: DISTINCT ON (page_id), one child per page, not necessarily the one that matched" | confirmed today's mechanism (retrieval.md:105); missing — no test proving exact-section retrieval, target (several children per page) not built (retrieval.md:106) | fetch by exact chunk id — Priority 1 | large |
| r5-parents | fetch_parent_texts opens a fresh session, re-applies source GUC only | confirmed behavior (both GUCs actually re-applied, ahead of the panel's own doubt) (retrieval.md:115-116); missing — no db test for `fetch_parent_context` (retrieval.md:117) | key parent expansion off the exact selected child id — Priority 1 | large |
| r2-curated | "fetch_curated_entries returns the first five active entries by id" | missing — no curated code anywhere in `retrieval/`; today's first-five-by-id mechanism confirmed in rag_agent (retrieval.md:93; rag_agent.md:85) | embed + tsv curated entries, retrieve by relevance | large |
| r1-ctx | Scopes resolved once per request, reused by fallback; principal passed separately | confirmed the resolve/classify/thread mechanics (retrieval.md:76-78); AuthContext dataclass and space_id field missing/drifted (rag_agent.md:79; retrieval.md:79-80) | full context redesign incl. space_id (Phase-4 embedding work) | large |
| ov-gate | Server key, limits, small talk, clarification flag, rewrite all run; identity from body | missing at the retrieval-folder level (owned by rag_agent); individual r1-* panels above already carry this stage's own deltas (retrieval.md:60) | (see individual r1-* rows) | small |
| r4-fallback | `_apply_crag_retry`: one retry with verbatim words if weak and rewrite differed | drifted only on cited line numbers; logic matches exactly (rag_agent.md:87) | (none) | none |
| cm-shared | rate_limiter.py, ttl_cache.py, hashing.py (hash_json, sha256_text) | confirmed, all three (shared.md:51-53) | (none) | none |
| r1-auth | "Today: One CHAT_API_KEY per deployment... No per-user identity." | drifted — stale: `_resolve_auth_context` already verifies a real per-user JWT via TokenVerifier when X-Obi-Token is present (rag_agent.md:77) | rewrite "Today" to reflect the built per-user flow | large |
| d-curated | "Target adds embedding vector(3072), tsv, scope_state; DDL in the 0011 migration" | drifted — none of these columns exist in any migration through 0012 (platform.md:115; alembic-and-scripts.md:87-88) | add the columns + seed-time embedding | large |
| r2-aclsql | Target: page-restriction predicate inside dense/keyword search, before LIMIT 75 | missing — today's searches have no restricted-page predicate at all; ACL applied later in the app, matching this panel's own "today" text under r3-acl (retrieval.md:95) | move lock 3 into the SQL searches | large |
| r3-scope | Migration 0010 coded and tested, not applied to Supabase; app predicate flag-gated | confirmed coded+tested (platform.md:100); needs live — not applied to Supabase per code alone (platform.md:101); flag defaults False in code, "on" claim unconfirmable from the folder (retrieval.md:98-99) | apply 0010 to Supabase + turn the flag on | large |
| r3-classified | Classified deleted outright, conflict hidden by policy | missing — same root gap as tg-state/i2-gone (retrieval.md:103; ingestion.md:114) | (see tg-state) | large |
| s-scope | Lock 2, ADR-0011/0014, applies to chunk and curated_knowledge_entry | drifted/partial — in-folder predicate touches only chunk; curated_knowledge_entry handling owned elsewhere (retrieval.md:122) | (same 0010-not-live gap, two tables) | large |
| r4-union | Merge both runs, dedupe by chunk id, rerank once against one query | not a Claims-table row in `rag_agent.md` (only cross-referenced from `retrieval.md:111`, no owning-folder row); today's actual behavior (pick-higher-of-two-runs) is confirmed via r4-fallback's own note | build the real union-rerank | large |
| r4-refuse | "Reasons today: no_candidates, weak_score, no_citations" | drifted — a fourth reason, `off_topic`, was added 2026-09-12 and isn't named on the panel (rag_agent.md:88) | update the reason list | small |
| r5-dedupe | Same parent twice→one block; neighbors merged; budget drops lowest first | missing — no dedupe/merge/token-budget logic exists anywhere; retrieved hits pass straight through (rag_agent.md:90) | build dedupe + budget trim | large |
| r5-coverage | "Does not exist. One strong passage is treated as enough for any question." | missing — confirms the design's own "does not exist" claim exactly (rag_agent.md:89; retrieval.md:113) | build the whole coverage-check module | large |
| r5-partial | Answer.partial/missing_parts fields; amber note in the widget | missing — no such fields exist anywhere, consistent with unbuilt status (rag_agent.md via retrieval.md:114; widget.md:112) | wire once r5-coverage exists | large |
| r5-ground | "Does not exist. A sentence passes today when its marker points at a real block, even when that block says something else." | missing — confirms the design's own "does not exist" claim exactly (rag_agent.md:94; widget.md:114) | build the whole batched support-check module — Priority 2 | large |
| d-query_trace | Retrieval half + answer half columns; "target adds token_subject(hashed), candidate_chunk_ids, decision" | confirmed writer functions pass every named field (retrieval.md:118); drifted — `subject_hash` already shipped via migration 0011 (half the target); `candidate_chunk_ids`/`decision` still absent (platform.md:114) | add the two remaining columns | small |

## Phase 4 (6)

| panel | today | found | target | change |
|---|---|---|---|---|
| w-token | "Today: shared invite token, ?access_token=, sessionStorage, x-widget-access-token" | missing — mechanism deleted, matching the panel's own note (widget.md:99,101-102); drifted — target (JWT per user, in-memory, bearer forwarding) is already built, ahead of "Planned" status (widget.md:100) | rewrite the panel's status; real work is only per-platform onboarding | large |
| sc-user | Company/integration/person shape example (Mews) | needs live — shape matches; the panel's literal example IDs are illustrative only (widget.md:127); shared.md:60 confirms no code claim to check | per-person Confluence permissions for embedded users remains an open target (section 11) | small |
| em-hostbackend | One endpoint on the platform's own server, signs the note | needs live — no code in this repo to check; the panel itself cites no file (platform.md:131) | **[Decision needed]** "the platform signs directly, or an auth service the two teams agree on does" — genuinely unresolved per the panel's own status `discuss` | blocked |
| em-kb | One database; row security shows only tag-matching, readable rows | not a Claims-table row in any synopsis (only a cross-reference in `shared.md:62`, "owned by platform/db RLS") | "the rows and policies do not change for this work" — per the panel's own Target/notes, no new build needed beyond tg-state/r3-scope | none |
| em-button | Round button + chat window from the Obi domain; CSP frame-ancestors | confirmed the accept-from-parent-only and CSP behavior (widget.md:131-132); drifted — `app/embed/page.tsx` is already built, not "(planned)" (widget.md:133) | (status label stale) | small |
| em-loader | obi.js: one script tag, fetch-at-click, postMessage handoff, silent renewal | drifted — already built and unit-tested, contradicting "Today: Does not exist" (widget.md:134); handoff/renewal confirmed (widget.md:135); "blocks sending until a new note arrives" is not quite true — an absent token degrades to general-only rather than blocking (widget.md:136) | (status label stale + minor behavior nuance) | small |

## Phase 5 (2)

| panel | today | found | target | change |
|---|---|---|---|---|
| e-ops | "A bounded in-process run measured p50 5.9s / p95 7.4s, ~$0.23/run" | needs live — numbers are a one-off manual local run, not reproducible from wired code; `latency_metrics.py` is unwired (evaluation.md:68-69) | build a real gold-set-driven latency/cost measurement pipeline | large |
| s-edge | "Today: One server key... No per-user identity reaches the backend." | drifted — a verified per-user AuthContext is already built from X-Obi-Token before rate limiting even runs, contradicting the stale claim (rag_agent.md:97); `auth.ts` cited by the panel no longer exists (widget.md:121-122) | rewrite "Today" to reflect the built lock-0 mechanism | large |

## Phase 6 (1)

| panel | today | found | target | change |
|---|---|---|---|---|
| e-judge | A different model grades answers at scale, validated against human grades | missing — no judge-model code exists anywhere in `apps/automation` (evaluation.md:75) | build the LLM-judge harness | large |

## Phase 7 (0)

_No panel's first reference is in Phase 7 — every panel Phase 7 substeps touch (cm-root, cm-infra, i1-webhook, em-loader, em-button, s-reader, s-anon, em-hostbackend) was already scheduled at an earlier phase._

## Unscheduled (16)

_No substep in `obi-action-plan.html` names these panel ids in a `design page:` refs line._

| panel | today | found | target | change |
|---|---|---|---|---|
| ov-receive | Webhook, ledger, queue, worker all run; no public URL yet | missing — target coalescing index doesn't exist at the DDL level (alembic-and-scripts.md:72); rest owned by confluence_sync, see i1-enqueue/i1-sweep | (same underlying gaps as i1-enqueue/i1-sweep) | large |
| ov-decide | Classification by hashes works; two named gaps | confirmed classification + attachment-only-never-rebuilds gap (ingestion.md:61-62); drifted — "version guard can skip a label change" needs a cross-feature/live check to pin down exactly (ingestion.md:63) | (mostly confirmed) | small |
| ov-build | Parent/child chunking, contextual notes, embeddings, keyword index, attachments all run | confirmed, all five sub-behaviors (ingestion.md:64-65) | vector reuse removed (tracked under i3-embed) | none |
| ov-activate | Staging, gate, swap, GC, rollback all run | confirmed, all five steps (ingestion.md:66) | (none beyond i4-* rows) | none |
| ov-auth | "Today: Does not exist. A shared invite token gates the pilot..." | drifted — stale: full per-user JWT verification already built and wired (rag_agent.md:74); widget.md:80-82 confirms the frontend half is built too | rewrite "Today" — drives 0.4.2 alongside r1-auth/s-edge/w-token/em-token | large |
| ov-eval | "No gold set exists. make eval runs a 14-document synthetic fixture." | confirmed no gold set; drifted — document count is ambiguous under any counting found (evaluation.md:53-54) | (tied to e-gold) | large |
| ov-search | Dense+keyword fused by page id; curated entries prepended after search | confirmed today's page-id fusion (retrieval.md:61); missing — curated-in-pool target not in this folder, matches today's actual first-five-by-id mechanism (retrieval.md:62) | fuse by chunk id + curated in pool — Priority 1 | large |
| ov-filter | Source RLS live; scope RLS coded not applied; page ACL runs before rerank | needs live for source RLS being "live" and for the empty-tags-public claim (retrieval.md:63,66); missing for scope-RLS-applied (retrieval.md:64); confirmed page-ACL ordering (retrieval.md:65) | apply migration 0010 to Supabase (tracked under r3-scope) | large |
| ov-judge | Cohere rerank one child/page; 0.10 threshold; fallback picks higher run | confirmed the rerank-shape mechanics only; threshold/fallback logic owned by rag_agent, see r4-weak/r4-union above (retrieval.md:67) | (see r4-weak, r4-union) | small |
| ov-answer | Parent expansion, generation, citation enforcement, image analysis, SSE, trace all run | confirmed, all named behaviors present (rag_agent.md:75) | coverage check + support check are the two large remaining target additions (tracked as r5-coverage/r5-ground) | large |
| cm-sync | Owns receive/decide/sweeps/label-to-tag; writes page_source/page_restriction/event_ledger/job/reconciliation_run | confirmed (confluence_sync.md:84); code-location citation for `change_detection.py` points at the wrong folder — it lives in `ingestion`, not `confluence_sync` (confluence_sync.md:85) | fix the code-location citation | small |
| cm-ingest | chunking.py, contextualizer.py, chunk_diff.py, attachment_extraction.py, versioning.py | drifted — list is accurate but incomplete, omits change_detection.py/normalization.py/tokenization.py/services.py/page_source_repo.py (ingestion.md:67); "writes document, document_version, chunk" omits page_source (ingestion.md:68) | complete the location list | small |
| cm-retrieval | retriever.py, search_repo.py, fusion.py, permission.py, knowledge_scope.py, trace_repo.py; "runs as rag_reader" | confirmed all six named modules (retrieval.md:68-73); drifted — "runs as rag_reader" is only a code comment in this folder, the actual binding lives in platform (retrieval.md:74) | (doc nuance; binding itself confirmed elsewhere) | small |
| cm-eval | run_baseline.py/runner.py, metrics/, datasets/ | confirmed structure and datasets (evaluation.md:55-58,60); drifted — "rerank lift" is claimed to live in metrics/ but actually lives in runner.py (evaluation.md:59) | move or re-cite the function's location | small |
| d-chunk | Parent/child rows; text; search columns; "target adds scope_state" | confirmed model shape, line ref off (platform.md:110; ingestion.md:121, missing-here) | add the scope_state column (same root gap as tg-state) | large |
| vd-model | "Today: OpenAI text-embedding-3-large 3072 (.env). Code default is Voyage voyage-3-large 1024." | needs live — code default confirmed as Voyage/1024; the claimed .env override to OpenAI/3072 cannot be checked from source, root `.env` is gitignored (platform.md:125) | **[Decision needed]** "Pick one as the default in code so a fresh deploy with no .env does not build a different index by surprise" — explicit open decision on the panel and in the brief's settings table (line ~980), unresolved | blocked |

---

## Design is wrong here (verdict drifted or missing)

_Every row above whose verdict is `drifted` or `missing`. Panel id · the design page's wrong
line · the right one, with `file:line`. This drives substep 0.4.2._

- **ov-corpus** — wrong: "Alembic head 0009 live; 0010 coded, not yet applied." — right: chain already runs through 0012; commit `2435127` records "0012 applied to Supabase" (alembic-and-scripts.md:70).
- **ov-widget** — wrong: "Shared invite token for the pilot." — right: pilot invite token already deleted, replaced by per-user JWT (widget.md:77).
- **cm-contracts** — wrong: "Planned: token-claims.json and iframe-messages.ts." — right: both already exist and are wired (packages-config-infra-docs.md:55).
- **i2-labels** — wrong: Code sample shows a `State` enum (CLASSIFIED/UNLABELED/OK). — right: actual return is `KnowledgeScopeResult(tags, conflict, matched_labels)` (confluence_sync.md:100).
- **i2-classify** — wrong: cites `confluence_sync/domain/change_detection.py:104-180`. — right: that file lives in `ingestion/domain/change_detection.py:104-180` (confluence_sync.md:102; ingestion.md:70-71).
- **i2-gone** — wrong: implies classified/unlabeled triggers already deactivate. — right: neither trigger exists anywhere (confluence_sync.md:104).
- **i2-meta / tg-retag** — wrong: cites `sync_service.py:180-189` for `_apply_metadata_only`. — right: that function is actually at `sync_service.py:268-302` (confluence_sync.md:106,113).
- **i3-blocks** — wrong: cites `ingestion/domain/normalize.py`. — right: file is `normalization.py` (ingestion.md:73).
- **i3-context** — wrong: code sample `f"{title} > {heading_path}\n\n{llm_note}\n\n{child_text}"`. — right: actual composition uses `_metadata_prefix`/`_compose`, joined differently, at `contextualizer.py:133-146` (ingestion.md:83).
- **i4-failed** — wrong: "Cleanup: GC deletes failed versions later." — right: `_gc_superseded` only ever selects `state==superseded`; a `failed`-state version is never GC'd (ingestion.md:109).
- **i4-staging / d-document_version** — wrong: describes today as the 4-column constraint and the target as `(document_id, index_fingerprint)`. — right: migration 0012 already widened the constraint to a 7-column key by a different mechanism; neither the design's "today" nor its "target" matches the live schema (platform.md:92-93; alembic-and-scripts.md:89-90,93).
- **tg-state / s-classified / r3-classified / d-chunk** — wrong: implies `scope_state` exists or is close to done. — right: the enum, both columns, and every consumer are entirely unbuilt (confluence_sync.md:116; ingestion.md:116; platform.md:110).
- **i1-sweep / ks-sweep** — wrong: implies the label sweep is close to shipping. — right: `search_pages_by_labels` does not exist anywhere in `platform/` (confluence_sync.md:95; platform.md:82).
- **i1-enqueue / d-job** — wrong: implies the coalescing index exists or is minor. — right: `ux_job_pending_sync_page` is not present in `Job.__table_args__` (confluence_sync.md:92; platform.md:80).
- **r1-auth / ov-auth / s-edge / em-token / em-backend / w-token** — wrong (all six panels): "Today: Does not exist" / "no per-user identity". — right: a full per-user RS256 JWT flow (verification, AuthContext construction, iframe handshake) is already built and live-proven for test hosts, per commit `59385f4` (rag_agent.md:74,77,97,99; widget.md:80,100,128-130,134).
- **r1-ctx / em-backend** — wrong: `AuthContext` code sample shows a `space_id` field. — right: the real dataclass has no `space_id` field (rag_agent.md:79,99).
- **r1-idem** — wrong: implies token-subject binding is still an open target. — right: the idempotency key already binds `token_subject`, not body principal (rag_agent.md:82).
- **r1-rewrite** — wrong: implies rewrite already lists question parts. — right: `rewrite()` still returns a plain string only, never the `{"query","parts"}` JSON (rag_agent.md:83).
- **r4-weak** — wrong: `refusal_min_rerank_score = 0.10`. — right: recalibrated to `0.05` as of 2026-09-12 (rag_agent.md:86).
- **r4-refuse** — wrong: "Reasons today: no_candidates, weak_score, no_citations." — right: a fourth reason, `off_topic`, was added 2026-09-12 (rag_agent.md:88).
- **r5-nocite** — wrong: implies both `no_citations` and `unsupported` refusal paths exist. — right: `RefusalReason` has no `unsupported` value; no support-check module exists to ever produce one (rag_agent.md:95).
- **r2-rrf / ov-search** — wrong: "Fuses two lists ... item ranked today: page id" framed as near-parity with the target. — right: fusion is fully by page id today; chunk-id fusion (the Priority-1 fix) is entirely unbuilt (retrieval.md:91).
- **r2-curated** — wrong: cites `retrieval/application/retriever.py` for curated candidate fusion. — right: no "curated" reference exists anywhere under `apps/automation/app/features/retrieval` (retrieval.md:93).
- **r3-source / s-writer** — wrong: cites `schema.py:52-68` ending before the policy statement. — right: `apply_chunk_rls` runs 53-77; the cited range cuts off before the actual `CREATE POLICY` text (retrieval.md:97; platform.md:99,116).
- **r3-scope / s-scope / ov-filter / tg-filter** — wrong: implies migration 0010 might already be live. — right: coded and tested, not applied to Supabase per the code alone; the app predicate defaults to off in code (platform.md:100-101; retrieval.md:98-99).
- **r2-aclsql** — wrong: implies a page-restriction predicate exists in the SQL searches. — right: `dense_search`/`keyword_search` have no restricted-page predicate at all (retrieval.md:95).
- **r4-union** — wrong: implies the union is reranked once. — right: today's code picks whichever run had the higher top score; scores from two different queries aren't on one scale (rag_agent.md:87, note under r4-fallback).
- **d-curated** — wrong: implies migration 0011 adds embedding/tsv/scope_state to curated_knowledge_entry. — right: none of these columns exist in any migration through 0012 (platform.md:115; alembic-and-scripts.md:87-88).
- **r5-coverage / r5-partial / r5-ground / e-stage3 / e-stage4** — wrong: these describe partly-built mechanisms. — right: each is confirmed fully unbuilt, matching the panels' own "does not exist" wording exactly (rag_agent.md:89-90,94; retrieval.md:113-114).
- **cm-alembic** — wrong: "the target adds one migration, 0011: scope_state, index_fingerprint, curated embeddings, two RESTRICTIVE policies, three query_trace columns." — right: the two policies shipped in 0010; the real 0011 only adds `subject_hash`; scope_state/index_fingerprint/curated columns are absent from every migration through 0012 (alembic-and-scripts.md:74).
- **e-gold / ov-eval** — wrong: "14-document synthetic fixture" as the working baseline. — right: the fixture is 6 current pages (`list_pages()` returns 6 ids); the "14" count is unverifiable under any counting found (evaluation.md:54,61).
- **vd-column / vd-question / vd-model** — wrong: assumes the deployed embedding dimension is settled at 3072. — right: code default is 1024 (Voyage); the `.env` override to 3072 cannot be checked from source (root `.env` is gitignored) (platform.md:119,125,127).
- **cm-web / sc-frontend** — wrong: cites `server/auth.ts`, "iframe bridge (planned)". — right: `auth.ts` was deleted; the iframe bridge is built and tested (widget.md:85,88,123-124).
- **w-composer** — wrong: "5 MB each" image cap. — right: no size check exists anywhere in `apps/web` (widget.md:94).
- **w-scope / ks-widget** — wrong: "set once, by the embedding page, as the knowledgeScope prop." — right: the real `/embed` frame never sets this prop; scope comes from the verified token (widget.md:96,119).
- **cm-config / tg-config / ks-deploy** — wrong: "the widget build ... generates its scope list ... (no hand-written copy, no drift test)." — right: it IS a hand-written copy, guarded by a runtime test, not a build-time generator (widget.md:89,116,118).
- **ks-edit** — wrong: "shape: a JSON list of lowercase slugs." — right: actual file is an object `{scopes:[{name,description}]}` (packages-config-infra-docs.md:69).
- **em-button / em-loader** — wrong: "(planned)" on `app/embed/page.tsx`; "Today: Does not exist" for obi.js. — right: both already built and unit-tested (widget.md:133-134).
- **em-loader** — wrong: "Obi.clear() ... blocks sending until a new note arrives." — right: `clear()` forgets the token and closes the panel; an absent token degrades to general-only rather than blocking (widget.md:136).
- **s-audit / d-query_trace** — wrong: implies `token_subject` is entirely unbuilt. — right: `subject_hash` already shipped via migration 0011 (platform.md:114,118).
- **sc-kb / ov-corpus / alembic panels generally** — wrong: "alembic/versions/ — 0001 to 0010." — right: the folder holds 12 files; 0011 and 0012 exist and are unlisted (platform.md:70,129; alembic-and-scripts.md:71,100).
- **cm-ingest** — wrong: location list omits `change_detection.py`, `normalization.py`, `tokenization.py`, `services.py`, `page_source_repo.py`; "writes document, document_version, chunk" omits `page_source`. — right: see ingestion.md:67-68.
- **cm-sync** — wrong: cites `domain/change_detection.py — classify` as a `confluence_sync` file. — right: it lives in `ingestion/domain/change_detection.py:104` (confluence_sync.md:85).
- **cm-retrieval** — wrong: "Runs as rag_reader" cited as this folder's own claim. — right: the binding is only a comment here; the real binding lives in `platform/db/engine.py` (retrieval.md:74).
- **cm-eval** — wrong: "rerank lift" listed under `metrics/`. — right: `evaluate_rerank_lift` lives in `runner.py`, not `metrics/` (evaluation.md:59).

## Code the design does not mention

_Collected from every synopsis's section 8 ("Not on the design page"), with folder._

**confluence_sync** (`apps/automation/app/features/confluence_sync/`)
- `application/knowledge_scope_backfill.py:1-71` — the PLAN 10.7 pre-flip coverage check, exported at the feature root but no panel names it (confluence_sync.md:132).
- `tests/test_scheduler.py:1-43` — tests `app.main._build_scheduler`'s dev-only fast-poll job (confluence_sync.md:133).
- `schemas/events.py:59-65,68-111` — `_as_int` and the nested/flattened webhook-payload tolerance (confluence_sync.md:134).

**ingestion** (`apps/automation/app/features/ingestion/`)
- `domain/tokenization.py` — `TokenCounter`, no panel names it directly (ingestion.md:125).
- `application/services.py` — `IngestionServices`/`build_ingestion_services`, the dependency-wiring bundle (ingestion.md:126).
- `domain/change_detection.py:80-101` — `index_config_changed` (ingestion.md:127).
- `application/contextualizer.py:34-80,125-129` — meta-refusal detection, real and tested, no panel (ingestion.md:128).
- `domain/normalization.py:149-170,173-181` — `build_sections`, `content_hash`/`structure_hash` (ingestion.md:129).

**retrieval** (`apps/automation/app/features/retrieval/`)
- `application/retriever.py:222,234` — `retrieve()` vs `retrieve_with_context()` as two distinct public methods (retrieval.md:127).
- `application/retriever.py:9-10` — the `RankFn` eval-harness seam (retrieval.md:128).
- `infrastructure/search_repo.py:52-55` — `KNOWLEDGE_SCOPE_WILDCARD = "*"` sentinel (retrieval.md:129).
- `__init__.py:15-16` — the feature-root import-boundary rule (ADR-0003 machinery, not a design claim) (retrieval.md:130).
- `infrastructure/search_repo.py:130-131` — `_vector_literal` helper (retrieval.md:131).

**rag_agent** (`apps/automation/app/features/rag_agent/`)
- `domain/identity.py:1-91`, `application/answer_service.py:207-214`, `infrastructure/llm_client.py:97-103,221-241`, `domain/prompt.py:136-186` — the entire per-user identity short-circuit, a third short-circuit alongside small-talk and clarification (rag_agent.md:102).
- `domain/refusal.py:24-34,42,79-80`, `settings.py:119-127`, `answer_service.py:113-116,296-302` — the `off_topic` refusal reason and its own threshold (rag_agent.md:103).
- `application/answer_service.py:130-132,289-302` — `_HANDOFF_REASONS`, which refusal reasons log a human-handoff line (rag_agent.md:104).
- `settings.py:178-186` — `chat_answer_cache_ttl_seconds`/`max_entries` backing `CachingAnswerService` (rag_agent.md:105).

**evaluation** (`apps/automation/app/features/evaluation/`)
- `metrics/fallback_metrics.py:18,27` — `fallback_rate`, `citation_grounding_rate`, exported and tested, no panel names them (evaluation.md:78).
- `run_baseline.py:93-157` — Markdown/JSON rendering of the rerank-lift report (evaluation.md:79).
- `README.md:1-85` — feature-local README on the five eval kinds (evaluation.md:80).

**platform** (`apps/automation/app/platform/`)
- `logging/setup.py` — `configure_logging`, `get_logger` (platform.md:134).
- `db/schema.py`'s `ensure_extensions`, `create_enum_types`, `drop_enum_types`, `create_all`, `drop_all`, `drop_chunk_rls`, `drop_chunk_scope_rls`, `drop_curated_scope_rls`, `enable_non_chunk_rls`, `disable_non_chunk_rls`, `apply_reader_rls`, `drop_reader_rls`, `_grant_extensions_access` (platform.md:135).
- `db/base.py` — `Base`, `NAMING_CONVENTION` (platform.md:136).
- `db/enums.py` — `ChangeClass`, `EventProcStatus`, `ReconStatus`, `PG_ENUMS` (platform.md:137).
- `clients/anthropic_client.py`'s `ImageBlock`, `cached_system_block` (platform.md:138).
- `clients/embeddings_client.py`'s `LocalEmbeddingProvider` (platform.md:139).
- `clients/reranker_client.py`'s `LocalReranker` (platform.md:140).
- `clients/confluence_client.py`'s `ConfluenceCircuitBreakerOpenError`, `list_space_pages`, `get_page`, `close()` (platform.md:141).
- `config/settings.py`'s chat/idempotency/answer-cache/HNSW/clarification/refusal-threshold settings block, ~lines 104-243 (platform.md:142).
- `config/platforms.py` (`PlatformRegistry`, `PlatformEntry`, `load_platform_registry`) and `config/platforms.json`/`platforms.local.json` (platform.md:143).
- `config/obi_identity.md` and `Settings.obi_identity_text`/`platform_registry` properties (platform.md:144).

**shared** (`apps/automation/app/shared/`)
- `hashing.py`'s six functions beyond `hash_json`/`sha256_text`: `sha256_bytes`, `normalize_text`, `canonical_json`, `hash_labels`, `hash_access_scope`, `hash_attachment_manifest` (shared.md:68).
- The boundary contract in `__init__.py:4-6` and its enforcement in `tools/check_feature_boundaries.py:46-103` (shared.md:69).
- `TTLCache`'s insertion-order (not LRU) eviction policy, documented only in its own docstring (shared.md:70).
- `SlidingWindowRateLimiter`'s `max_tracked_keys` bounded-memory fix, PLAN 4.6.4 (shared.md:71).

**alembic + scripts** (`apps/automation/alembic/`, `apps/automation/scripts/`)
- `alembic/versions/0011_query_trace_subject_hash.py` and `0012_widen_document_version_idem.py` — two shipped migrations no panel names individually (alembic-and-scripts.md:105).
- `alembic/env.py`, `alembic/script.py.mako` — environment wiring and the migration template (alembic-and-scripts.md:106).
- `scripts/setup_supabase.py`'s `_pgvector_version`, `_derive_reader_url`, `_check_anon_denied`, `_check_reader_scope_axis` internal helpers (alembic-and-scripts.md:107).
- `scripts/verify_knowledge_scope_live.py:187-209` — `_prove_receipt_entrypoint` (alembic-and-scripts.md:108).
- `scripts/rotate_chat_api_key.py` in its entirety — no panel references key rotation at all (alembic-and-scripts.md:109).

**widget** (`apps/web/`)
- `src/app/test-hosts/multi/page.tsx` + `multi-user-content.tsx` — the multi-user switcher proving per-user identity live, git `59385f4` (widget.md:142).
- `src/app/api/test-hosts/config.ts` and its four `TEST_HOSTS` entries — local-only RS256 scaffolding (widget.md:143).
- `src/features/chat/ui/menu.tsx`, `menu-item.tsx`, `icon-button.tsx`, `language-menu.tsx`, `contour-background.tsx`, `assistant-mark.tsx`, `image-lightbox.tsx`, `typing-indicator.tsx` — UI primitives, individually untested by any panel (widget.md:144).
- `src/components/ui/button.tsx` + `src/components/README.md` — an unused/placeholder-adjacent `components/` root (widget.md:145).
- `src/platform/README.md` — documentation stub (widget.md:146).
- `src/test-stubs/server-only.ts` — Vitest server-only shim (widget.md:147).
- `src/app/(site)/dev-preview-backdrop.tsx` — dev-only decorative wrapper (widget.md:148).
- `packages/contracts/src/token-claims.json` — already built (see cm-contracts verdict above) (widget.md:149).

**packages/config/infra/docs** (`packages/`, `config/`, `infra/`, `docs/`)
- `packages/contracts/package.json`, `tsconfig.json`; `packages/design-tokens/package.json`, `tsconfig.json` — pnpm-workspace manifests (packages-config-infra-docs.md:80).
- `packages/contracts/src/openapi/chat.yaml:1-389` — the full OpenAPI document, never walked panel-by-panel (packages-config-infra-docs.md:81).
- `config/platforms.local.json:1-72` — local-only override registry for browser testing (packages-config-infra-docs.md:82).
- `config/obi_identity.md:1-25` — the static-facts prompt block for the per-user identity path (packages-config-infra-docs.md:83).
- The large `docs/` prose corpus (`OBI-RAG-SYSTEM-A-Z.md`, `docs/final_design/*`, `docs/rag/*`, `docs/embedding/*`, runbooks, `obi-system-brief.md` itself, etc.) — none named by any of the 22 assigned panel ids in that synopsis's scope; per CLAUDE.md, archived and non-authoritative until reviewed (packages-config-infra-docs.md:84).
- `docs/adr/0006`, `0007`, `0010`, `0014` — four ADRs beyond `cm-docs`'s nine named ones; supersession chain spot-checked as internally consistent (packages-config-infra-docs.md:85).
- `apps/automation/tools/panel.py`, `tests/tools/test_panel.py`, `test_agent_guard.py` — the audit tooling itself (packages-config-infra-docs.md:86).

**entrypoint** (`apps/automation/app/main.py`)
- `_WORKER_OWNER = "in-process-worker"` constant (entrypoint.md:80).
- `dev_lightweight_reconcile` — the DEV-only fast-poll scheduler job, not named on cm-root's step 5 (entrypoint.md:81).
- `GET /health` — neither cm-root nor sc-backend's "today" line mentions a health probe (entrypoint.md:82).
- `app.state.rate_limiter` construction (entrypoint.md:83).
- `app/__init__.py:8` — `__version__ = "0.2.0"` (entrypoint.md:84).

## Needs live

_Every claim carrying that verdict in some synopsis — for substep 0.5.3 to check on staging._

- **ov-corpus** — whether the live Supabase `alembic_version` row is actually at head 0012, contradicting the design's "0009 live" claim (alembic-and-scripts.md:70).
- **cm-infra** — whether production is actually running on Supabase today, as the design claims (packages-config-infra-docs.md:63).
- **cm-docs** — whether an ADR exists for the fingerprint/scope_state/label-gated-ingestion/edge-token changes (cannot tell from static code alone) (packages-config-infra-docs.md:65).
- **i3-children** — the numeric value of `KIND_CHILD` (kind=1), defined in `platform/db/models.py`, not evidenced in the ingestion folder (ingestion.md:81).
- **i3-embed / vd-model / vd-column / vd-question** — the deployed embedding provider/model/dimension: code default is Voyage/1024; the claimed `.env` override to OpenAI/3072 cannot be checked from source (root `.env` is gitignored) (platform.md:89,119,125,127).
- **ov-filter** — whether source RLS is actually "live" on Supabase, and whether the "empty tags read as public" behavior is a live-policy fact distinct from the in-folder predicate (retrieval.md:63,66).
- **r3-scope / s-scope / tg-filter** — whether migration 0010 is actually applied to Supabase (coded and tested is confirmed from code; "not applied yet" is a live-store fact, contradicted in one place by commit `2435127`'s note that 0012 — downstream of 0010 — is already applied) (platform.md:101; alembic-and-scripts.md:82).
- **s-writer** — the Supabase-side owner role's actual RLS-exempt behavior in production; only the local compose role (`rag`) is confirmed from static files (packages-config-infra-docs.md:76).
- **sc-user** — the shape of a real per-person identity mapping in production; only the local test-host scaffolding is confirmed (widget.md:127).
- **e-ops** — the claimed p50 5.9s / p95 7.4s / $0.23-per-run latency-and-cost numbers: no code in the evaluation folder computes or stores them; they are a one-off manual local run recorded in `docs/rag/PLAN.md`, not reproducible from wired code (evaluation.md:68).
- **em-hostbackend** — the entire panel: no code in this repo implements or checks it; it describes a system outside the repo (platform.md:131).
- **ov-auth step 5** — that the backend verifies algorithm/signature/issuer/audience/expiry, as claimed by the design's diagram — confirmed in code for test hosts, but never proven end-to-end against a real platform's key (widget.md:82).

## Row count and change tally

- Rows in the table above: **192** (matches `panel.py --list`).
- Change column: **none 56 · small 78 · large 55 · blocked 3**.
