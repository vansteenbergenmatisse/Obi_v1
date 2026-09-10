# 0014 — Customer/Knowledge-Scope Isolation Backstop (DB-level, fail-closed)

Status: Accepted
Date: 2026-09-10
Governs: apps/automation (platform/db, alembic, retrieval, rag_agent)
Relates to: ADR-0004 (source-keyed RLS isolation — the pattern this mirrors), ADR-0011 (knowledge-scope
tagging + the app-layer predicate — kept as defense-in-depth), ADR-0013 (managed Postgres, NO FORCE)

## Context

The four-customer boundary (`mews` / `opera-cloud` / `toast` / `general`, carried as `obi-*-test`
knowledge-scope tags) was enforced **only** by an app-layer predicate `tags && :scopes` at ~4 SQL call
sites, gated behind the `enable_knowledge_scope_filtering` feature flag — which **failed open**: flag
off, or a single dropped predicate, added no filter and returned **every customer's content to
everyone** (`retriever.py`, `curated_knowledge_repo.py`). All four scopes share one `source_id`, so the
ADR-0004 source policy does not separate them, and `curated_knowledge_entry` had no tenant policy at
all. Source isolation fails *closed*; the customer axis did not. This is Phase 11.1a, a gate before any
public deploy (the only per-request auth is one shared `CHAT_API_KEY` with no per-user→customer
binding).

Two options were considered:

- **(i) per-customer `source_id`** — stamp each customer's pages with their own `source_id` and reuse
  the ADR-0004 `chunk_source_read` policy. Rejected: needs a data migration re-stamping every customer
  page plus an ingestion change, and it **collapses the source axis into the customer axis**, which the
  design elsewhere deliberately keeps independent (a page can be re-sourced without touching its
  customer, and vice-versa).
- **(ii) scope-GUC RLS** — a second RLS policy on the customer axis, keyed on a new per-transaction GUC
  mirroring `app.allowed_sources`. Chosen: additive, reversible, no data migration, and it keeps the two
  axes orthogonal.

## Decision

**D1 — A second, `AS RESTRICTIVE` RLS policy per protected table.** Add `chunk_scope_read` on `chunk`
and `curated_knowledge_entry_scope_read` on `curated_knowledge_entry`, both keyed on a new
per-transaction GUC **`app.allowed_knowledge_scopes`** (mirroring `app.allowed_sources`). They are
`RESTRICTIVE` on purpose: PostgreSQL **ANDs** restrictive policies with the permissive ones, so a row is
visible only if it passes *both* the source policy **and** the scope policy. A second *permissive* policy
would OR, which would **weaken** isolation — the trap this avoids. Migration `0010_customer_scope_rls`;
DDL lives in `schema.apply_chunk_scope_rls` / `apply_curated_scope_rls` (shared by the migration and the
test harness, per the create_all==migration contract).

**D2 — Fail-closed semantics, with an explicit wildcard opt-out.** The policy predicate is
`current_setting('app.allowed_knowledge_scopes', true) = '*' OR cardinality(tags) = 0 OR tags &&
string_to_array(current_setting(...), ',')`:

- **Unset GUC** (a dropped call / bug) → `current_setting` is NULL → a *tagged* row is denied. **Fail
  closed** for the content that needs isolating.
- **A scope list** → tag-overlap, exactly like the app predicate.
- **`cardinality(tags) = 0`** → an **untagged chunk is global** (visible under any scope). This is the
  security floor, and it is deliberately *looser* than ADR-0011 Decision 1 (whose app-layer predicate
  drops untagged chunks when scope-filtering is ON): the backstop's job is only to guarantee no *tagged*
  customer content crosses, while keeping an untagged / single-tenant corpus and the always-on `general`
  base working. When the flag is on, the stricter app predicate ANDs on top.
- **`'*'`** → unrestricted, an *explicit* opt-out for the internal/eval path (`knowledge_scopes is
  None`). The public `/chat` path always resolves a real, non-empty scope list via
  `resolve_allowed_scopes` (always includes `obi-general-test`), so it never sets `'*'`.

**D3 — Enforcement is independent of the feature flag.** The retriever and curated read set
`app.allowed_knowledge_scopes` on **every** reader transaction (`apply_knowledge_scope`, from the raw
`knowledge_scopes` argument), regardless of `enable_knowledge_scope_filtering`. The flag now governs
**only** the redundant app-layer `tags && :scopes` predicate (recall/planner + the ADR-0011 Decision-1
untagged-drop), not the security boundary. Consequence — an intentional contract change: passing
`knowledge_scopes` now isolates tagged content at the DB even with the flag off (previously it was
ignored). The GUC is set with a **bound** `set_config(..., true)` parameter, never interpolated — same
injection discipline as `apply_source_scope`.

**D4 — The owner is unaffected.** `chunk`/`curated` are owned by the writer, which is exempt from RLS by
ownership + `NO FORCE` (ADR-0013), so ingestion and trace writes are untouched. Only the non-owner
`rag_reader` (the read path) is subject to the policy.

## Consequences

- **Acceptance met:** with the app-layer predicate deliberately bypassed (flag off), a cross-customer
  query returns **zero** rows for tagged content; the always-on general base and untagged/global content
  still return; the source axis is unchanged. Proven by `test_customer_isolation_backstop.py` (direct
  reader reads, no app predicate) and `test_migration_0010_scope_rls.py` (RESTRICTIVE, round-trips).
- **Not a full multi-tenant auth story.** This closes the *data-layer* fail-open. It does **not** add a
  per-user→customer binding at the edge (still one shared `CHAT_API_KEY`); that is 11.1c + the deferred
  AWS deploy. The scope a request receives is still trusted from the caller.
- **Live apply is a plain `alembic upgrade head`** on Supabase (head `0009` → `0010`). The `rag_reader`
  already has the `extensions` grant (P0, 2026-09-10), so no new operator step beyond running the
  migration.
- Distinct axis from Phase 13.1 (0009 restored reader *read-access*); 0010 adds the tenant policy 0009
  deliberately did not.
