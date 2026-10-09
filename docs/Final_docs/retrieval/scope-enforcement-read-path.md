# Scope enforcement on the read path (RLS GUCs + search filters)

- **Workflow:** retrieval
- **Owning code:** `backend/app/features/retrieval/infrastructure/search_repo.py` (the GUC
  appliers `apply_source_scope` / `apply_knowledge_scope` / `apply_hnsw_gucs` and the search SQL);
  consumed by `retriever.py` (one search transaction), parent expansion, and the curated lookup in
  `rag_agent`.
- **Design panel:** `r3-scope` · `tg-filter`
- **Status:** Implemented

## What it does

Every database read in retrieval runs inside a transaction that first sets two RLS GUCs from the
request's one authorization context: `app.allowed_sources` (source axis) and
`app.allowed_knowledge_scopes` (customer/knowledge-scope axis), both via
`set_config(..., is_local=true)` with bound parameters. The RESTRICTIVE Postgres policies read
those GUCs: a chunk is visible only when its `tags` array overlaps the allowed scopes
(`tags && string_to_array(guc, ',')`), with `'*'` as the explicit internal opt-out sentinel and an
unset/empty GUC failing closed to zero rows. The search SQL carries the same filters as its own
predicates (active, child kind, current status, source list, scope overlap) for correctness and
planner use — RLS stays the security net underneath. Since 8.3.1 the same `WHERE` clause also
carries the applicability/eligibility predicate when a verified customer context is present
(`eligibility-filtering.md`): it narrows INSIDE what these access filters already allow and never
replaces them — parent expansion and the curated lookup stay access-only, reached solely from ids
the filtered search produced.

Scope *values* are validated at this choke point before being joined into the GUC: `None` means
the internal/eval wildcard; a list may not contain an element with an embedded `,` or `*` —
either raises `ValueError` before any SQL runs, because the policy splits the GUC on commas and
compares the whole value to `'*'`, so such an element would semantically widen access (the G14
finding, closed 2026-10-05).

## Why it does it

Never-bend rule 3: one authorization context per request, and no read runs under looser rules
than the search. ADR-0014 made RLS the flag-independent backstop (the app-layer
`enable_knowledge_scope_filtering` predicate is redundant defence, default off), and ADR-0004 set
the bound-parameter GUC discipline after the injection review. `is_local=true` scopes each GUC to
its transaction so pooled connections cannot leak one request's scopes into the next. Binding
alone stops SQL-syntax injection but not value-semantics collision — that is why the element
validation exists: `string_to_array` cannot tell one element containing `"mews,toast"` from two
elements, and a joined value of `"*"` is indistinguishable from the intentional sentinel. Scopes
normally come from the trusted tag map via the verified token, so this is defence-in-depth, but
before 2026-10-05 nothing at any layer enforced it (proven by a live probe as `rag_reader`).

## How we know it works

- **Unit** (`retrieval/tests/test_search_repo_gucs.py`): both appliers emit bound-param SQL
  (never interpolated), `None` → `'*'`, `[]` → `''` (fail closed); the hnsw GUC whitelist rejects
  an injection string. `retrieval/tests/test_s_reader_session_binding.py` pins that
  `dense_search`, `fetch_page_scopes` and `fetch_rerank_texts` each run on the one GUC-bound
  reader session (G10).
- **Database** (`confluence_sync/tests/test_customer_isolation_backstop.py`): cross-scope read
  blocked under `rag_reader`; unset GUC denies; `'*'` opt-out works; empty tags visible to no
  scope (0014 fail-closed floor); overlap-not-equality; GUC transaction-locality on a reused
  pooled connection (G13); the two semantic-injection cases — embedded comma cannot widen,
  `["*"]` as data cannot unlock the opt-out (G14, red-first: both probes returned foreign rows
  before the fix). `test_reader_vector_access.py` proves a nearer-but-forbidden ANN hit is never
  returned. `test_retrieval_knowledge_scope.py` proves the backstop flag-on and flag-off.
- **Live:** the 2026-09-25 3d proof on Supabase (as `rag_reader`, empty tags visible to no scope,
  per-scope corpus counts correct, `'*'` returns all) — recorded in
  `docs/Final_docs/sync-rules/plan.md` §0.
- Proof fragments for the 4.2 additions: `docs/Final_docs/4-test-foundation/test-proof.md`.
