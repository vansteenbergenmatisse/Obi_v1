# Eligibility filtering inside the database (§D.5)

> **SUPERSEDED for routing by Option A (ADR-0020), 2026-10-12 (substep 9.4.1).** The slot/
> applicability eligibility predicate below is kept for provenance and still ships as code, but the
> routing axis is now the directed-connection **hard label filter** — see
> `directed-label-hardfilter.md` (panel `mi-hardfilter`). The `_ELIGIBILITY_CLAUSE` here and the new
> `labels && :session_labels` overlap are independent predicates in the same `_base_filters`; a
> directed chat carries session labels, the slot eligibility rides only on the (now legacy) slot
> context.

- **Workflow:** retrieval
- **Owning code:** `backend/app/features/retrieval/infrastructure/search_repo.py` (the
  `_ELIGIBILITY_CLAUSE` applicability predicate inside `_base_filters`, consumed by
  `keyword_search` / `dense_search` / `fetch_rerank_texts`);
  `backend/app/features/retrieval/domain/applicability_match.py`
  (`EligibilityParams` + `eligibility_params`, exported from the retrieval root);
  `backend/app/features/retrieval/application/retriever.py` (the `customer_context`
  parameter on `retrieve`/`retrieve_with_context`); `rag_agent`'s `answer_service.py`
  builds the `CustomerContext` from the verified `AuthContext` slots + host platform.
- **Design panel:** `mi-filter` (section 05.2 · Multi-integration context)
- **Status:** Unverified (coded and db-proven against the matcher oracle; no live customer
  token carries slots yet, so no production question has flowed through it — Phase A
  validates live)

## What it does

One filtered search: when a request carries a verified customer context, the search SQL
adds an applicability predicate to the same `WHERE` clause that already carries the access
filters (active/child/current, source list, knowledge-scope overlap, RLS underneath) —
before `ORDER BY`/`LIMIT`, never an unrestricted shortlist cleaned up later. Eligible =
chunks with **no** applicability record (both SQL `NULL` and jsonb `null` — absence never
excludes, the §D.11 default) plus chunks whose stamped record matches the context under the
§D.4 semantics: general always; software/platform-interface for a product actually filling
its role's slot (platform-interface additionally requires the verified host platform key);
connection/workflow rules only when satisfied by a connection the company actually has —
the derived launch pairs (POS+PMS, PMS+Accounting; a direct POS–Accounting pair is never
derived) plus any real records, each rule ANDing on the SAME connection with every required
direction enabled, `any` binding to the connection's concrete product, and a rule carrying
variants never matching (unverifiable at launch). Up to `rerank_candidate_k` (a setting,
default 75) eligible chunks return; fewer is served as-is, never padded, never refetched.
The rerank-text fetch applies the same predicate, so an excluded page can never be reranked
back in; parent expansion and the curated lookup stay access-only — §D.5 scopes eligibility
to the candidate search, and a parent/curated row is only ever reached from ids that came
out of the filtered search (ADR-0014 posture, unchanged). The context values are bound
parameters (`:elig_products`, `:elig_platform`, `:elig_connections`); the SQL text is
static. Without a context (the internal/eval path) the emitted SQL is byte-for-byte the
pre-8.3.1 shape.

## Why it does it

§D.5 is the design of record: apply access AND applicability conditions inside the
database/vector-search function, before the final result limit — the database itself only
hands back pieces this customer's setup may use; the prompt never enforces eligibility.
Applicability narrows INSIDE what access already allows: RLS, the scope GUCs and page
permissions are untouched and still apply first (never-bend rule 3), and the request body
never decides — the `CustomerContext` is built from the gate-verified `AuthContext` slots
and the verified issuer's platform key (8.1.3), threaded through both the first retrieve
and the CRAG retry. The SQL deliberately MIRRORS `match_applicability` (8.2.3) instead of
inventing a second vocabulary — the pure matcher is the specification and the db test
oracle, and 8.3.4 will read its reason slugs for attribution. One documented bound: the
workflow distinct-assignment is encoded as "every spec satisfied AND distinct satisfying
connections ≥ specs", which equals the matcher (Hall's condition) for every launch-reachable
input — derived connections are one-per-type and real connection records cannot exist yet
(§D.13/O1) — and for every two-connection workflow; a 3+-spec workflow against multiple
same-type REAL connection records would need a true matching and is revisited when §D.1's
richer context record lands.

## How we know it works

- **Unit** (`retrieval/tests/test_eligibility_filter_sql.py`, 5 tests, panel mi-filter, in
  `make test`): no-context SQL unchanged byte-for-byte; the predicate sits before
  `ORDER BY`/`LIMIT` in all three query builders; a hostile context value never reaches the
  SQL text (bound, never interpolated); `eligibility_params` mirrors the matcher's
  derivation (role-checked slots, launch pairs only, never a derived POS–Accounting pair).
  `rag_agent/tests/test_answer_service.py::test_rt1_answer_threads_the_verified_slots_into_retrieval_as_customer_context`
  pins that `answer()` builds the context from the VERIFIED auth slots and passes it to
  retrieval (and nothing for a slotless token beyond the empty context).
- **Database** (`test_eligibility_filter_db.py`, 11 tests): inclusion AND exclusion per
  slot and per pair; the excluded-chunk-IS-the-query-vector case (never returned at any
  similarity, dense and keyword); fewer-than-75 served as-is, never padded (the cap read
  from `rerank_candidate_k`); absence never excludes (legacy parity for the one-filled-slot
  token and the empty context); platform-interface and workflow follow the matcher; the
  rerank-text fetch enforces the same predicate; the matcher-as-oracle sweep (5 contexts ×
  11 payload shapes: SQL result set == matcher verdicts exactly); the exact-filtered-
  baseline recall test (filtered top-8 == the exact baseline computed outside the DB).
  Each mechanism was inverted one at a time (break-it: predicate dropped, absence-excludes,
  platform ignored, retriever not threading, answer service not threading) — red, then
  green on restore.
- **Eval (rule 11):** `make eval` before and after the change — every number identical to
  the 4.5 baseline floor (`docs/plan/baseline.md`). Honest note: the bundled runner scores
  the fixture baseline ranker with no customer context, so it proves no regression on the
  no-context path; it cannot see the filter itself (no gold case carries slots yet — Step 6
  adds mixed-scope cases).
- Downstream (consumes this filter's output): context-aware reranking (8.3.2, panel
  mi-rerank) now enriches the rerank query and documents from the same verified context and
  the matched reason — building only from the already-eligible candidate set this filter
  produces, never widening it (see `rerank.md`). Per-slot attribution (8.3.4) is still planned.
- **Worked-example reproduction (8.5.1, panels mi-validate/mi-match/mi-filter):**
  `backend/app/features/retrieval/tests/test_worked_examples_db.py` (5 db tests, one per §D.9
  example) seeds a small corpus whose stamped payloads realise each example's include/exclude
  documentation categories, then runs the REAL `HybridRetriever.retrieve_with_context` under the
  example's verified context and asserts the EXACT set of included page ids AND the EXACT set of
  excluded page ids (never a count), with each hit's `attribution` as the inspectable inclusion
  reason. Example 5 (Toast/OperaCloud + Mews/QuickBooks, modelled by two real connection records
  with empty slots per context-contract §9) proves a Toast/Mews pair guide is never eligible —
  the cross-matching guard. Red-first shown by the break-it inversion: dropping
  `_ELIGIBILITY_CLAUSE` makes every excluded page leak back and all five go red; restored green.
  The `mixed_connection` eval stage (5 §D.9 questions) extends the gold set; the existing four
  stages stay at the 4.5 floor and the new stage records its own first baseline
  (`docs/plan/baseline.md` §8.5.1) — honest note: the context-free bundled ranker gates the
  questions' RANKING, not eligibility (the include/exclude proof is the db tests above).
- Not yet proven: no live token carries slots (platforms don't mint the structured context
  yet), so no production question has flowed through the filter; Phase A (8.5.2) provides the
  human/live evidence.
