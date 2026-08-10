# Phase 0 — Design docs & ADRs — Audit Findings

**Audited:** 2026-08-10
**Scope:** docs/rag/DESIGN.md, docs/rag/how_this_works.md, docs/adr/0003/0004/0005, cross-checked against apps/automation/app
**Verification run:**

```
cd apps/automation && uv run ruff check . 2>&1 | tail -5
# Found 2 errors. [*] 2 fixable with the `--fix` option.

uv run ruff format --check . 2>&1 | tail -5
# 17 files would be reformatted, 130 files already formatted

uv run pyright 2>&1 | tail -8
# 34 errors, 1 warning, 0 informations
```

Plus direct reads of: `retriever.py`, `search_repo.py`, `permission.py`, `refusal.py`,
`answer_service.py`, `reranker_client.py`, `settings.py`, `models.py`, `engine.py`,
`alembic/versions/0002_provider_tags_and_rls.py`, `infra/foundation/init/01-roles.sql`,
`infra/foundation/docker-compose.yml`, `rag_agent/server/router.py`, `FEATURES.md`, and
`docs/rag/PLAN.md`'s full ledger history for the ruff/pyright count trail.

## Security

- **[Informational, not a defect]** No new security issues found in the Phase 0 docs themselves.
  The security-relevant decisions in ADR-0004 (RLS default-deny, `set_config` bound-parameter GUC,
  role split) and ADR-0005 (cross-encoder-only rerank, forced citations, refusal threshold, CRAG
  cap, full `securing-http-and-llm-endpoints` control set on `POST /chat`) were verified against
  the actual code and match exactly — see "Confirmed correct" below. The one real security finding
  in this area (the numeric-`principal` space-trust bypass) was already found, fixed, and
  documented in PLAN.md §0 under 5.3 — it is not a Phase-0 gap, it's evidence Phase 0's own ADR-0004
  decision (`allowed()`'s space-vs-principal scope split) was working as designed once the HTTP
  boundary validation was added.

## Dead code / unused

- None found. Phase 0 has no code of its own. (`CONFLUENCE_SPACES`/`confluence_scope_list` dead-code
  removal was already called out and completed in Phase 3.5.6, documented in both DESIGN.md §10 and
  how_this_works.md §4.7/§12.)

## Plan / design deviations (docs vs. code disagree, or an ADR decision wasn't actually followed)

1. **`docs/rag/DESIGN.md` §1 "Confirmed gaps" paragraph (lines 91–95) is stale and self-contradicts
   the document's own banner.** It reads: *"no reranker... no request tracing; no query rewrite /
   answer generation / citations / refusal / CRAG; `POST /chat` absent... no caching."* Every one of
   these gaps was closed by Phases 3.5.2/3.5.4/4.1–4.4/5.2 respectively — confirmed live: the
   Cohere/Fake reranker exists (`platform/clients/reranker_client.py`), `query_trace` is written on
   every retrieval (`retriever.py:163-178`), the full `rag_agent.AnswerService` pipeline exists and
   is wired to a live `POST /chat` (`rag_agent/server/router.py`), and `CachingAnswerService` exists
   (`answer_cache.py`). The document's own banner at lines 15–33 correctly states all of this is
   `TODAY`/shipped through 5.3. §1 was evidently never rewritten after the original Phase-0 pass —
   it still describes the pre-3.5 system while the banner above it describes the post-5.3 system.
   Low severity (the banner is authoritative and correct), but confusing for anyone reading §1 in
   isolation, which is exactly how a "current pipeline as-built" section is meant to be read.

2. **`docs/rag/how_this_works.md` is materially stale relative to `DESIGN.md`, despite being its
   declared companion "as-built" explainer.** Only §§10 and 12 were updated for Phase 3.5+; §§1–9
   were left exactly as originally written for the pre-3.5 system:
   - Line 4 (top banner): *"It describes what runs today (Phases 1–3, verified: 99 tests green)."*
     Actual current state per DESIGN.md/PLAN.md: Phase 5.3 done, 219 backend + 39 web tests.
   - §1's mermaid diagram (lines 34–55) marks `rerank → parent expand → grounded answer → SSE chat`
     as `-.PLANNED.->` (a dotted, not-yet-built line). All of that is now built and shipped.
   - §7 (lines 461–462): *"Today this is a **library**... **not yet wired to an HTTP endpoint**
     (`retrieval/__init__.py:8-10`) — that is Phase 4."* Phase 4 is done; `rag_agent/server/router.py`
     wires retrieval to a live `POST /chat`. (`retrieval/__init__.py`'s own docstring is accurate —
     it says retrieval is consumed by the `rag_agent` answer workflow — so the *code* comment is
     fine; it's `how_this_works.md`'s framing of that fact as a future gap that is wrong.)
   - **§7.2 (lines 495–506) is the most concrete instance**: *"Today the policy is fed by
     **fixtures** (the DB stores only an access-scope *hash*, not principal lists). Phase 4 replaces
     this with real, queryable principal-list storage."* This is false as of Phase 4.3 — `page_restriction`
     is a real ORM table (`app/platform/db/models.py:160-178`, `alembic/versions/0005_page_restriction.py`)
     populated by `confluence_sync`'s `handle_sync_page` and queried fresh per search by
     `search_repo.fetch_page_scopes` (confirmed live in `retriever.py:137-142`). Anyone reading only
     `how_this_works.md`, which the doc's own header calls "the map you read alongside [PLAN.md]",
     would believe principal ACLs are still fixture-only — a materially wrong picture of the current
     security model.
   - **§3's table-by-table list (lines 142–154) omits `page_restriction` entirely.** It lists 9
     tables; the actual schema has **10** (`grep '__tablename__' models.py`: `page_source`,
     `page_restriction`, `document`, `document_version`, `chunk`, `event_ledger`, `job`,
     `reconciliation_run`, `source_scope`, `query_trace`). The section header itself says "(the 9
     tables)" (line 102) — already wrong even before counting `page_restriction`.

3. **Broken internal anchor in `how_this_works.md`.** The table of contents (line 17) links to
   `#3-the-data-model-the-7-tables`, but the actual heading at line 102 was updated to `## 3. The
   data model (the 9 tables)` — the auto-generated anchor for that heading is
   `#3-the-data-model-the-9-tables`, not `-7-tables`. The TOC entry was never updated when the
   heading was, so the in-doc link is dead. (And per finding 2, "9" itself is now stale too — it
   should be 10.)

4. **Pyright's error count silently crept above the ADR-0003 D1 baseline, and the drift was never
   flagged or recorded.** ADR-0003 (`docs/adr/0003-Feature-Boundary-Enforcement.md` D1) fixes the
   no-regression baseline at **"Ruff 2 errors + 25 unformatted files, Pyright 31 errors / 1
   warning."** Tracing PLAN.md's own ledger entries chronologically: at the Phase 3.5.5 exit gate
   and again at 3.5.6 (lines 650, 666, 677), pyright is reported "31/1, exactly at baseline." By
   Phase 4.3's ledger entry (line 740, "no new pyright error type") and every entry after, the
   reported count is **34 errors** — reported as "unchanged" relative to the *previous session's*
   count, never reconciled against ADR-0003's original 31. Live re-verification today confirms the
   current actual count is still 34 errors / 1 warning (see Verification run above) and 17
   unformatted files (ruff-check itself is unchanged at 2). Nobody's ledger entry between 3.5.6 and
   4.3 states *what* the 3 new pyright errors are, *why* they don't count as a regression, or
   records an accepted deviation for them the way PLAN.md's "Deviations already taken" section does
   for other decisions. This is exactly the failure mode CLAUDE.local.md §2's gate exists to catch
   ("no ruff/pyright regression vs the ADR-0003 D1 baseline") — the gate has been checking
   session-over-session stability (34 == 34 == 34) rather than the ADR's actual fixed baseline
   (31), so a real 3-error regression shipped silently sometime during Phase 4.1/4.2 and has been
   carried forward as the new normal ever since. Not a security or correctness bug, but a
   governance-gate miss worth calling out explicitly since Phase 0 is precisely the layer meant to
   keep this kind of baseline honest.

## Test coverage gaps

Phase 0 has no code of its own, so there is nothing to unit-test directly. The one gap worth naming:
**nothing automated checks documentation accuracy** — the staleness in finding 2 (a materially wrong
claim about the permission model's data source) could ship silently for phases at a time, as it did
here, because no test or lint step diffs `how_this_works.md`'s prose against the code it describes.
This is a process/tooling gap, not a missing unit test on any shipped feature.

## Deferred / future ideas

- **No ADR exists for the Phase 5 caching design or the `CHAT_API_KEY` rotation mechanism.** Both are
  durable architectural decisions (cache key scoping by `(history, principal)`, TTL/eviction policy,
  dual-key overlap-window rotation) documented only in DESIGN.md §7/PLAN.md §0, not in a
  `docs/adr/*.md` file the way ADR-0004/0005 captured the RLS and answer-pipeline decisions. Not a
  stack deviation (so not strictly required by the global CLAUDE.md's ADR rule), but worth
  considering for consistency now that ADR-0003/0004/0005 have set the precedent of one ADR per
  durable decision in this project.
- Phase 0's own explicit non-goal ("no code in this phase") was honored — confirmed no application
  code changed as part of Phase 0's commit (`d793bb1`, docs-only per PLAN.md's progress table).
- Phase 5's remaining scope (5.4 live-LLM red-team + latency/cost proof, embedder bake-off blocked on
  Confluence token + `VOYAGE_API_KEY`, adaptive routing) is openly tracked as not-yet-built in both
  DESIGN.md §9 and PLAN.md §0 — consistent, not a gap in Phase 0's own deliverables.
- Consider a lightweight recurring check (even just a PLAN.md checklist item at each phase gate)
  that re-reads `how_this_works.md`'s "TODAY" framing against the same phase being closed out in
  PLAN.md, since DESIGN.md's own banner is clearly being kept current at every phase gate while
  how_this_works.md is not — the asymmetry is the root cause of findings 2–3.

## Confirmed correct

- **ADR-0004 RLS mechanism, byte-for-byte.** `chunk_source_read` policy, `FORCE ROW LEVEL SECURITY`,
  and the default-deny proof are implemented exactly as decided (`schema.apply_chunk_rls`, invoked
  from `alembic/versions/0002_provider_tags_and_rls.py`). The scope GUC is set via
  `set_config('app.allowed_sources', :s, true)` with a **bound** parameter
  (`search_repo.py:38-48`), never `SET LOCAL` — confirmed distinct from the separate, deliberately
  `SET LOCAL`-based HNSW GUCs (`apply_hnsw_gucs`, which use a whitelisted-value f-string specifically
  *because* those are server-validated ints/enums, not user-supplied secrets — the code comment at
  `search_repo.py:19` correctly explains why `SET LOCAL` is fine there but not for the scope GUC).
- **Role split exactly as ADR-0004 decision 4 specifies.** `infra/foundation/init/01-roles.sql`
  creates `rag_reader LOGIN ... NOBYPASSRLS` with `GRANT SELECT`+`ALTER DEFAULT PRIVILEGES`; the
  compose superuser `rag` stays the writer/owner (a documented deviation from a separate
  `rag_writer` role, recorded in PLAN.md's "Deviations already taken" — not silent).
- **pgvector pinned by digest, ≥ 0.8, exactly as ADR-0004 decision 7 requires**:
  `pgvector/pgvector:pg16@sha256:1d5335...` (0.8.5), `docker-compose.yml:7`.
- **ADR-0005 cross-encoder-only rule.** `reranker_client.py`'s docstring and implementation
  (`FakeReranker`/`CohereReranker`/`LocalReranker`) match the ADR verbatim — "cross-encoder rerankers
  only — never a general chat model asked to reorder."
- **Rerank ordering invariant (security-critical) holds in code.** `retriever.py:_search` computes
  the DB-backed permission filter (`live_policy.allowed`) before slicing `to_rerank` and calling
  `self._reranker.rerank(...)` — a document the principal cannot see is never sent to the reranker,
  exactly as DESIGN.md §2's "Ordering invariant" and ADR-0005 decision 3 require.
  `candidate_k`/`rerank_depth` both default to 75 in `settings.py`, matching ADR-0005 decision 3 and
  the config table in DESIGN.md §7.
- **Answer-pipeline call order matches the documented deviation exactly.** `answer_service.py`'s
  `answer()` runs `retrieve_with_context → _apply_crag_retry → decide_refusal → fetch_parent_texts
  → generate → enforce_citations`, matching DESIGN.md §2's explicit note that the real call order
  (rerank → CRAG → refusal → parent-expansion → generation) differs from the diagram's presentation
  order, and matching ADR-0005 decisions 5/7/8. `decide_refusal` refuses on `top_score is None` or
  `< threshold` (`refusal.py:23-36`); `_apply_crag_retry` retries once, only when the rewrite changed
  the query and the result was weak, keeping whichever run scored higher
  (`answer_service.py:108-127`) — exactly ADR-0005 decision 8's "keep whichever scored higher."
- **Forced-citation degrade-to-refusal.** `answer_service.py:84-94`: zero surviving citation markers
  after `enforce_citations` degrades to a refusal rather than an empty string, matching DESIGN.md §5
  and ADR-0005 decision 6.
- **Fixed-workflow-not-agent-loop.** `AnswerService.answer()` is a single straight-line method with
  no LLM-driven branching or tool-calling loop — matches ADR-0005 decision 5/§"Reason" and DESIGN.md
  §8's "REJECT: Self-RAG / agent loop."
- **Test-fixture rule honored.** Confirmed `reranker_provider` forced to `fake` in the hermetic test
  settings (referenced consistently across DESIGN.md §7, PLAN.md, and ADR-0005 decision 4); CI/offline
  runs are deterministic per the `_OFFLINE_ENVS` fallback in `reranker_client.py`.
- **ADR-0003 D1's ruff-check and ruff-format numbers are still within the "no regression" band**
  for ruff specifically: 2 errors (== baseline) and 17 unformatted (< the 25 baseline, i.e. improved,
  not regressed) — only the pyright count actually drifted (see deviation 4 above).
