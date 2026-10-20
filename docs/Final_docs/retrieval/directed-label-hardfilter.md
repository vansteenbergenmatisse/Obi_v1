# The directed-connection hard label filter (Option A Stage 6)

- **Workflow:** retrieval
- **Owning code:** `backend/app/features/retrieval/infrastructure/search_repo.py` (the
  `labels && :session_labels` overlap in `_base_filters`, threaded through `keyword_search` /
  `dense_search` / `fetch_rerank_texts`; `apply_allowed_labels` sets the `app.allowed_labels` GUC);
  `backend/app/features/retrieval/application/retriever.py` (the `session_labels` parameter on
  `retrieve`/`retrieve_with_context`, set on the search transaction; parent expansion stays exempt);
  `backend/app/features/rag_agent/application/answer_service.py` (`_resolve_directed_routing` feeds
  the session labels + connection block); `knowledge-base/schema/schema.py` +
  `knowledge-base/migrations/versions/0016_chunk_labels.py` (the RESTRICTIVE `chunk_labels_read`
  policy + the `labels` column and its partial GIN index).
- **Design panel:** `mi-hardfilter` (section 05.2 · Multi-integration context); supersedes
  `mi-filter`/`mi-match` for routing (ADR-directed-source-target-routing-labels).
- **Status:** Unverified (coded and db-proven against seeded labels; the Confluence relabel to the
  new label scheme is the parallel owner/content task 9.5.1, and the formal routing-off-vs-on gold
  dataset is 9.5.2 — no production question has flowed through it yet)

## What it does

When a chat is one directed `source → target` connection, chat-start stores its four routing
labels (`obi-general`, `{source.slug}-general`, `{target.slug}-general`, `{source.slug}-to-{target.kind}`)
on the session row. Every question's search then hard-filters on those labels before top-k: the
`labels && :session_labels` overlap is added to `_base_filters` at the exact spot of the `tags`
overlap, bound (never interpolated), and threaded identically through both candidate queries
(keyword + dense) AND the rerank-text fetch — so an excluded page can never be reranked back in.
The same list is set as the `app.allowed_labels` GUC in the same transaction as the scope GUC, so
the RESTRICTIVE `chunk_labels_read` RLS policy (migration 0016) and the app predicate agree: two
layers, never one. An unlabelled chunk overlaps nothing, so it is invisible under an active
connection (D2, self-gating). Parent expansion is label-EXEMPT — the matched child already passed
the filter, and its parent shares the same page (the GUC is set to the `'*'` opt-out there). A
legacy/slot/tokenless chat carries no session labels, so the overlap is omitted entirely and the
GUC is set to `'*'` — the filter is a no-op (labels are the relevance axis, not the access fence).

## Why it does it

`mi-hardfilter` is the design of record for Option A (ADR-directed-source-target-routing-labels): a directed chat may never retrieve
a wrong-connection page — a Toast→Mews chat can never see a `toast-to-accounting` or `mews-to-pos`
page, at any vector similarity — and filtering before top-k shrinks the candidate set the reranker
and the model see. The two-layer enforcement (GUC + RLS policy AND app predicate) keeps never-bend
rule 1 (RLS) and rule 3 (no read looser than the search) both intact; a `WHERE`-only filter would
violate rule 3 and was rejected (D1). Labels are deliberately fail-OPEN on an unset/opt-out GUC
because they are the routing/relevance axis, not the access boundary — source isolation (lock 1)
and customer-scope isolation (lock 2) remain the fail-closed fence and are untouched. The label
values are bound parameters, so a hostile label string can never reach the SQL text (rule 10), and
a value carrying a comma or `'*'` is rejected before the join (it would otherwise widen the
predicate or hit the opt-out). The connection comes only from the verified token/session, never the
request body (rules 2–3). The filter is never behind a flag — it is a hard filter.

## How we know it works

- **Unit** (`retrieval/tests/test_search_repo_labels.py`, 8 tests, panel mi-hardfilter): the label
  overlap is omitted when `session_labels` is `None` (byte-for-byte the pre-9.4.1 SQL) and appears
  as a bound `labels && :session_labels` in keyword/dense/rerank SQL when given; a hostile label
  string rides as a bound value, never in the SQL text; `apply_allowed_labels` binds via
  `set_config` (never interpolated) and opts out with `'*'` on `None`.
- **Database** (`retrieval/tests/test_label_hardfilter_db.py`, 5 tests, panels mi-hardfilter/
  mi-match): a Toast→Mews chat gets the EXACT include set and never a `toast-to-accounting`/
  `mews-to-pos` page at any similarity (every seeded chunk shares one embedding + body, so only the
  filter removes one); an empty-labels chunk is never served under an active connection (D2); the
  rerank-text fetch is already label-filtered (an excluded id handed in directly is dropped); recall
  equals an exact filtered baseline computed outside the DB (no loss, no leak); a legacy chat with
  no session labels is a no-op (an unlabelled chunk is still served — locks 1–2 are the fence).
- **Wiring** (`rag_agent/tests/test_answer_service.py`, 2 tests, panels mi-session/mi-hardfilter):
  a directed chat threads its four labels into the retriever and the connection block into the
  prompt, resolving the catalog once per chat; a legacy chat threads `None` for both.
- **Eval (rule 11), substep 9.5.2:** the labelled connection gold stage `connection_routing.json`
  (its `EvalCase`s carry the four directed-connection `session_labels`) plus `evaluate_routing_lift`
  record the routing-off-vs-on before/after number — the rule-11 gate on this filter. The DB test
  `retrieval/tests/test_eval_routing_db.py` seeds the labelled pages hermetically (the Confluence
  relabel is still the parallel owner task 9.5.1) and runs the real `HybridRetriever` with labels
  off then on; the result is written to `backend/eval-reports/routing_lift.{json,md}` and printed by
  `make eval`. Numbers (2 cases, k=50): recall `1.000 → 1.000` (no gold-set loss), served_precision
  `0.167 → 0.333` (noise removed), served_count `6.0 → 3.0` (candidate set narrowed). The bundled
  baseline datasets are unchanged against their recorded floor (retrieval_smoke/ambiguity/permission/
  out_of_corpus/mixed_connection all unmoved). Honest note: this is proven on seeded labels + a gold
  stage, not yet on a relabeled live corpus (9.5.1).
- **Break-it:** removing the `labels && :session_labels` clause lets every wrong-connection page
  leak back into the Toast→Mews result — the db exact-exclude assertions go red; restored green. For
  the 9.5.2 eval gate, feeding the routing-on side no session labels collapses off == on, so the
  narrowing deltas drop to zero and the `served_precision` / `served_count` asserts go red
  (`test_eval_routing_off_vs_on_break_it_no_labels_is_zero_lift`).

Not yet proven live: the Confluence corpus is not relabelled to the new scheme yet (owner/content
task 9.5.1), so no production question has run through the filter. The labelled routing-off-vs-on
before/after gold numbers now exist (substep 9.5.2, above); the live relabel + a production question
through them is still 9.5.1.
