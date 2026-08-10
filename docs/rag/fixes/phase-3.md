# Phase 3 — Retrieval core — Audit Findings

**Audited:** 2026-08-10
**Scope:** apps/automation/app/features/retrieval (base fusion/permission-filter, excl. 3.5.x additions), apps/automation/app/features/evaluation (base harness)
**Verification run:**

```
cd apps/automation
uv run pytest app/features/retrieval/tests/ app/features/evaluation -q
  -> 35 passed in 0.36s

uv run pytest app/features/confluence_sync/tests/test_retrieval_eval.py -q   # bonus: DB-backed E2E proof for this feature, not in the required command list
  -> 10 passed in 1.87s

uv run ruff check app/features/retrieval app/features/evaluation
  -> All checks passed! (0 errors in scope)

uv run pyright 2>&1 | grep -A3 "retrieval\|evaluation"
  -> no matches; the repo-wide 34 pyright errors are all outside this scope (confirmed against
     app/platform/jobs/queue.py etc.) — no regression vs the ADR-0003 D1 baseline (2 ruff / 17
     unformatted / 34 pyright, none of which live in retrieval or evaluation)
```

## Security

- **[Medium — design smell, not a live exploit in this layer]** Dual-meaning `scope` string in the
  pure domain policy — `app/features/retrieval/domain/permission.py:28-39` (`space_id()`/`allowed()`).
  `allowed()` branches on `scope.isdigit()`: an all-digit string is treated as **space-level trust**
  (every page in that space is visible, restrictions ignored), any other string is treated as a
  **principal id** (checked against `page_restriction`). Both trust levels are carried in one
  untyped `str | None` parameter, distinguished only by a runtime string predicate. The docstring
  (`permission.py:1-15`) explains the duality clearly in prose, but explaining an ambiguous contract
  is not the same as removing the ambiguity: nothing in the type system stops a caller from passing
  a principal id that happens to be all-digits and having it silently reinterpreted as a space id
  (i.e., "grant this caller everything in that space" instead of "check this caller's own restriction
  list"). This is exactly the shape of bug a later Phase-5.3 red-team pass found and had to patch at
  the HTTP boundary (`rag_agent/server/router.py`) by validating the `principal` before it ever
  reaches this policy. That patch protects the one call path it covers today; it does not change
  `permission.py`'s own contract, so any other/future caller that builds a `PrincipalPermissionPolicy`
  and passes an unvalidated scope (another endpoint, a script, a batch job, a second bot integration)
  reintroduces the same class of bug with no compiler or test to catch it at the domain layer. Given
  it already caused one real vulnerability, treating it as "safe because the caller now validates" is
  fragile — the ambiguity is a property of the domain type, not of any one caller. **Direction:**
  split into two distinct, non-overlapping inputs at the domain boundary — e.g. `allowed(page_id, *,
  space_id: int | None = None, principal: str | None = None)` or a small tagged union
  (`SpaceScope(int) | PrincipalScope(str)`) — so "trust the whole space" and "check this principal"
  can never be confused by a caller that merely forgot to pre-validate. This is independent of, and
  should not be closed out by, the Phase-5.3 HTTP-layer patch.
- **Confirmed correct / no finding:** `search_repo._base_filters` (`search_repo.py:52-60`) is pure SQL
  string assembly (`is_active AND kind = 1 AND page_status = 'current'` [+ space/source predicates]) —
  grepped for any LLM/embedding/network call inside the filter path; the only `embedding`-named
  identifiers found are the pgvector column name and its `halfvec` cast in `dense_search`, not a
  filtering step. All query-derived values (`query`, `space_id`, `sources`, `qvec`) are passed as
  bound parameters, never interpolated. The "Deterministic SQL filtering (no LLM filters)" claim in
  PLAN.md/DESIGN.md holds for this code.
- **Confirmed correct:** the permission filter (`retriever.py:140-142`) runs strictly before the
  rerank slice (`retriever.py:146-147`) — matches the DESIGN.md "Ordering invariant (security-
  critical): rerank runs after the permission filter" — verified by reading the call order, not just
  the comment.

## Dead code / unused

- None found in `retrieval/` or `evaluation/` base scope. Everything read has at least one call site
  (production or test): `RetrievalResult.top_score`/`page_ids` are consumed by
  `rag_agent/application/answer_service.py` and asserted in
  `confluence_sync/tests/test_retrieval_eval.py`; `PrincipalPermissionPolicy.space_of`/`restrictions`
  are exercised both directly in unit tests and via fresh per-search instances in production
  (`retriever.py:141`).
- `evaluation/metrics/latency_metrics.py` (percentile/`LatencyTimer`/`check_targets`/`TARGETS`) is
  fully unit-tested (`tests/test_latency_metrics.py`) but is **not imported by `runner.py`,
  `run_baseline.py`, or re-exported from `evaluation/__init__.py`**. Not dead (it has real tests and a
  documented Phase-5 landing spot in the feature's own `README.md` §"How Phase 3-5 plug in real
  retrieval"), but it is currently inert with respect to any runnable pipeline — nothing calls
  `check_targets` or `summarize_latencies` today. Flag for whoever wires Phase 5 latency gating; not a
  Phase-3 defect.
- No `TODO`/`FIXME`/`XXX` markers and no commented-out code blocks found under
  `app/features/retrieval` or `app/features/evaluation` (grepped both).

## Plan / design deviations (docs vs. code disagree, or an acceptance criterion isn't actually met)

- **`evaluation/README.md` "five eval kinds" vs. `schemas.EvalKind` (doc/code disagreement).** The
  README (`app/features/evaluation/README.md:9-28`) lists the five kinds as *retrieval, answer,
  security, latency, permission*, with "`ambiguity` is a sub-kind of answer/retrieval" mentioned only
  parenthetically. The actual `Literal` in `schemas.py:14` is
  `["retrieval", "answer", "ambiguity", "permission", "latency"]` — there is **no `"security"` kind
  at all**; `ambiguity` is a first-class literal, not a footnote. Confirmed against the three bundled
  datasets (`retrieval_smoke.json`→`retrieval`, `ambiguity.json`→`ambiguity`,
  `permission.json`→`permission`) — none uses `"security"`. This is a stale/aspirational doc, not a
  code bug, but it will actively mislead whoever writes the Phase-5 "security" eval dimension the
  README promises exists into thinking there's a schema slot for it already.
- **`FEATURES.md`'s evaluation public-surface list is stale relative to `evaluation/__init__.py`.**
  `FEATURES.md:84` lists the public surface as `evaluate, load_dataset, load_corpus_loader,
  datasets_dir, confluence_fixtures_dir, RankFn`, plus the four `Eval*` types — it does **not**
  mention `evaluate_rerank_lift`, `RerankLiftReport`, or `write_rerank_lift_reports`, all three of
  which are exported in `evaluation/__init__.py:20-34`'s `__all__` today. This is presumably a 3.5.5
  documentation gap (the rerank-lift additions are the Phase-3.5 agent's code, not mine to fix), but
  it directly touches the base harness's own contract doc, so flagging here: whoever closes out 3.5.5
  documentation should update this list.
- No deviation found in the core claims this feature owns: RRF math, dense/keyword candidate_k=40
  (now 75 post-3.5.2, out of my scope to re-verify), tie-break by keyword rank, permission-before-
  rerank ordering, and the injectable `RankFn` seam all match PLAN.md §2/§3 and DESIGN.md §1/§2 as
  described.

## Test coverage gaps

- `permission.py`'s `allowed()` has direct unit coverage for: space-scope grants/blocks
  (`test_fusion_and_permission.py::test_space_scope_grants_space_and_blocks_others`), principal-scope
  grants/blocks (`test_principal_scope_blocks_unauthorized`), and the DB-backed integration proves
  real leak-prevention (`test_retrieval_eval.py::test_permission_no_leak_and_authorized_access`,
  `test_permission_enforcement_is_db_backed_not_fixture_fed`). **Gap:** no test anywhere (unit or
  integration) exercises the specific collision this audit flags above — an all-digit *principal* id
  colliding with the space-scope branch (e.g. `scope="12345"` intended as a principal, but
  `space_of.get(page_id) == 12345` happening to be true or false by coincidence). Given this is
  exactly the shape of the Phase-5.3 finding, a regression test asserting the *domain policy itself*
  cannot be confused this way (independent of the HTTP-layer validation) would be valuable — today
  only the HTTP layer is guarded, so a directly-constructed `PrincipalPermissionPolicy` used from a
  new call site has zero regression protection against this ambiguity.
- `reciprocal_rank_fusion` unit tests (`test_rrf_rewards_top_ranks_and_agreement`,
  `test_rrf_weights_apply`) check *relative* ordering but never assert the literal formula
  `1/(k0+rank)` against a hand-computed number the way `test_retrieval_metrics.py` does for
  ndcg/mrr/precision (e.g. `dcg = 1.0/math.log2(2) + ...`). Low risk (the ordering assertions do
  transitively pin the formula's shape), but a hand-computed numeric assertion for RRF would make a
  future accidental change (e.g. `k0` default drift, or rank becoming 0-based) fail loudly instead of
  only shifting relative order in edge cases.
- `evaluate_rerank_lift`'s harness plumbing (mean-delta aggregation, empty-dataset safety) is
  well covered by `test_rerank_lift.py` (attributed to 3.5.5 per the task scope, but I did verify the
  underlying `_aggregate`/mean-delta arithmetic it shares with `evaluate()` is exercised and correct).
  No gap found in the base `evaluate()`/`_aggregate()` plumbing itself: report structure, perfect-
  ranker, empty-ranker, and clock-determinism are all directly tested
  (`test_runner_baseline.py`).

## Deferred / future ideas

- Split `PrincipalPermissionPolicy.allowed()`'s single ambiguous `scope: str | None` into two typed
  parameters or a tagged union (see Security finding above) — independent of and prior to any future
  new caller of this policy.
- Wire `evaluation/metrics/latency_metrics.py` into an actual runnable path (Phase 5, per the
  feature's own README) — currently tested but inert.
- Reconcile `evaluation/README.md`'s "five eval kinds" prose (and its "security" kind) with the real
  `EvalKind` literal, and refresh `FEATURES.md`'s evaluation public-surface bullet to include the
  3.5.5 rerank-lift exports — both are small, low-risk doc fixes, not code changes.
- Consider a hand-computed numeric unit test for `reciprocal_rank_fusion` (see Test coverage gaps)
  to pin the literal formula, not just relative ordering.

## Confirmed correct

- **RRF fusion formula** (`fusion.py:14-28`) is textbook Reciprocal Rank Fusion:
  `score(item) = Σ_lists weight / (k0 + rank)`, rank 1-based (`enumerate(lst, start=1)`), default
  `k0=60`, default equal weights, accumulated via a `defaultdict(float)` so an item's absence from one
  list simply omits that list's term rather than penalizing it with a zero-rank term. This exactly
  matches both the module docstring and PLAN.md's "research's 'swap weighted-sum→RRF' is done" /
  DESIGN.md's `score = Σ 1/(60+rank)`. Verified by re-deriving the math against the code, not by
  trusting the function name or docstring.
- **Deterministic SQL filtering** — no LLM/embedding call anywhere inside `_base_filters` or the
  query-building path in `search_repo.py`; all user-controlled values are bound parameters.
- **Permission-filter-before-rerank ordering** in `retriever.py` matches the documented
  security-critical invariant.
- **`RankFn` injection seam** (`runner.py:30`, `RankFn = Callable[[str, str | None], list[str]]`) is
  unchanged and still the same seam the baseline ranker, the real `HybridRetriever.retrieve`, and the
  rerank-lift before/after functions all plug into — no runner change needed to swap rankers, exactly
  as PLAN.md/DESIGN.md/how_this_works.md describe.
- **Metrics correctness** (`retrieval_metrics.py`): recall/precision/mrr/ndcg/hit_rate all dedupe
  the ranked list to first-occurrence before scoring (so a repeated id can't be double-counted or
  artificially push a later id out of the `k`-window), and NDCG's IDCG normalization correctly caps
  ideal hits at `min(len(relevant), k)`. Hand-verified against `test_retrieval_metrics.py`'s
  hand-computed NDCG case.
- **Eval harness base structure** (`runner.evaluate`, `_aggregate`, `schemas.py`) — pure with respect
  to time (`now_iso` passed in, never read from a clock), `extra="forbid"` on every Pydantic model
  (rejects malformed dataset JSON rather than silently dropping fields), and the report shape is
  unchanged since Phase 1 so before/after comparisons stay valid.
- **35/35 unit tests pass** in the audited scope; **0** ruff errors in scope; **0** pyright errors
  attributable to this scope (all 34 repo-wide errors are elsewhere); bonus DB-backed integration
  suite (`confluence_sync/tests/test_retrieval_eval.py`, 10 tests) also passes, independently
  corroborating the RRF/permission-filter/tracing behavior against a real indexed corpus.
