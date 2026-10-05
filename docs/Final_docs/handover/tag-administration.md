# Tag administration — changing the scope system itself

> **Audience:** operators with repo + deploy access.
> **Living doc:** describes the system as proven on 2026-10-03 (incl. the hardening-batch tests).
> Sections marked **⚠ changes with Step 5** describe behavior the roadmap's scope-restamp fix will alter — update them in that substep.

This is NOT about labeling pages (see `tagging-guide.md`). This is about changing **which labels
exist** — the knowledge scopes.

## Where the truth lives

- **`knowledge-base/config/knowledge_scopes.json`** — THE single canonical allowlist. The one place
  that decides which Confluence label is a knowledge scope. Read by the backend at boot (and
  per-access in-process), by the widget build, and by ingestion eligibility.
- Boot validation (pinned by `test_knowledge_scopes.py`): every `name` lowercase and unique;
  `obi-general-test` and `classified` must be present; violation = the backend exits non-zero.
- **`knowledge-base/config/platforms.json`** — which scopes each platform/integration may access.
  Cross-validated at load: mapping a scope that is **not** in `knowledge_scopes.json` fails loudly,
  naming the scope (pinned by `test_platform_registry_cache.py`). `classified` is never mappable;
  `obi-general-test` is always included automatically and never hand-listed.
- **`source_scope` table** — the authorization allow-rows. One active space-level row (id 23, space
  701857803, empty tags = all recognized scopes) authorizes recognized labels across the space.
  Managed only via `backend/scripts/seed_source_scope.py` (tested: insert / idempotent upsert /
  `--deactivate` / `--delete`).

**Deploying a config change:** the deployed backend reads the files baked into its image — a change
is `git commit` → Railway redeploy. The widget generates its scope list from the same file at
build → rebuild with `pnpm --filter web build:obi`. `platforms.json` is additionally **cached
in-process**: even where the file is re-read, the registry is served stale until **restart** (pinned
by test — editing it without a restart does nothing, by design loudly documented here).

## Adding a scope

1. Add the entry (`name` lowercase-unique, `label`, `description`) to `knowledge_scopes.json`.
2. If an integration should reach it, add it to that integration's list in `platforms.json`.
3. Commit, redeploy backend, rebuild widget.
4. Label the Confluence pages with the new scope name.

**⚠ changes with Step 5 — the restamp gap (finding A):** pages whose label existed **before** the
scope was recognized do **not** gain the new scope automatically — not from the webhook (no event
fired) and not from the complete sweep (the change detector keys on the page's raw labels, which
didn't change; pinned by `test_tags_scope_added_already_indexed_page_not_restamped_by_either_sweep`).
NEW pages and newly-labeled pages work immediately. **Workaround for pre-labeled pages:** force a
real event per page — remove + re-add the label, or make a trivial edit. Step 5's metadata-restamp
fix removes this workaround.

## Removing a scope

1. **First** remove it from every integration in `platforms.json` — otherwise the next boot (and,
   on a live process, the next registry access) fails with the scope's name.
2. Remove the entry from `knowledge_scopes.json`. Commit, redeploy, rebuild widget.
3. Clean up: pages carrying only that label are **not purged immediately**. They purge on each
   page's next real event, or in bulk on the next **complete reconciliation sweep** (default every
   14 days; run one now with `cd backend && uv run python scripts/run_reconciliation_once.py` —
   the sweep's CQL bug was fixed 2026-10-03, it works). Until then the stale rows are dead weight:
   unreachable by every customer token (their scopes never include the removed name) but visible to
   the internal `'*'` wildcard paths (eval, parent-text fetch).

## Renaming a scope

Remove + add in one commit (`platforms.json` renamed in the same commit or boot fails). Expect the
union of both gaps: old-tag content purges only via sweep/events, new-tag content needs the
finding-A workaround per page, and until both are done the renamed scope's corpus is partially or
fully empty **while `/health` happily lists the new name**. Relabel pages in Confluence to the new
name, then run one complete sweep, then force-restamp stragglers. Treat a rename as a small
migration, not a config tweak.

## source_scope rows

- Space root with empty tags = authorize all recognized scopes in that space (Decision D3) —
  today's production setup. Page roots cover their subtree only.
- Deactivating the last covering root → the sweep purges everything it covered.
- **⚠ changes with Step 5 — the narrowing leak (finding B):** narrowing a row's `tags` does NOT
  take effect on already-stamped chunks — no event fires, the lightweight sweep sees no drift, and
  even the complete sweep lands in `no_change`, so the revoked scope **keeps reading the content
  indefinitely** (proven at RLS level under the real reader role; pinned by
  `test_tags_narrowed_root_*` in `test_source_scope_lifecycle.py`). Until Step 5: after narrowing a
  row, force a real event on every affected page (label toggle / trivial edit). If the narrowing is
  security-motivated, do that **immediately**.

## Verifying any of the above

```bash
# One page's full index state (chunks, versions, tags, marker search):
cd backend && uv run python scripts/page_state.py <pageId> [marker]

# Live watcher — prints ADDED/CHANGED/DELETED as the vector DB moves (see ledger 2026-10-02):
#   the snippet in the session record / progress-log; polls page_source+chunk every 10s.

# What the deployed backend recognizes right now:
curl -s https://obi-backend-production.up.railway.app/health   # scopes list (classified never shown)

# Events and jobs (read-only), latest first:
#   event_ledger: event_type, page_id, delivery_id (non-null = real webhook), received_at
#   job: job_type, page_id, status, last_error
```

Local test runs: `make check` from the repo root; DB-marked tests refuse the production URL and
need `DATABASE_URL=postgresql+psycopg://rag:rag@localhost:5434/omniboost_rag` (or just `make test`).
