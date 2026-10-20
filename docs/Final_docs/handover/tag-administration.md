# Label administration — changing which labels Obi recognizes

> **Audience:** operators with repo + deploy access.
> **Living doc:** describes the system after `ADR-routing-labels-sole-content-axis` (2026-10-12): the
> old knowledge-scope `obi-*-test` tags are retired, and routing labels are the only content axis.

This is NOT about labeling pages (see `tagging-guide.md`). This is about changing **which labels
exist** — which happens by changing the list of systems.

## Where the truth lives

- **`knowledge-base/config/product_catalog.json`** — THE single registry of systems (`toast`,
  `mews`, `opera-cloud`, `quickbooks-online`, `xero`), their role (`pos` / `pms` / `accounting`)
  and aliases. The recognized routing labels are derived from it: `obi-general`, `{id}-general`
  for every system, and `{id}-to-{pos|pms|accounting}`. Validated at boot by
  `backend/app/platform/config/product_catalog.py`; a bad entry stops the backend.
- **`knowledge-base/config/knowledge_scopes.json`** — holds only the reserved `classified` entry. It
  must be present (boot fails otherwise). A `classified` Confluence label removes a page from the
  index. Nothing else belongs in this file.
- **`knowledge-base/config/platforms.json`** — the partners (`base`, `datahub`, and the temporary
  `obi-test`) and which systems each may name as a source (`allowed_integrations`). Its
  `integrations` map keeps the valid system keys with empty lists; the old integration → scope
  mapping is retired.
- **`source_scope` table** — the ingestion allow-list: which Confluence space or page roots are
  eligible to ingest at all. It is not a content axis. One active space-level row authorizes the
  space today. Managed only via `backend/scripts/seed_source_scope.py` (insert / idempotent upsert /
  `--deactivate` / `--delete`).

**Deploying a config change:** the deployed backend reads the files baked into its image — a change
is `git commit` → Railway redeploy. `platforms.json` is additionally **cached in-process**: the
registry is served stale until **restart** (pinned by test — editing it without a restart does
nothing, by design).

## Adding a system (and with it, its labels)

Follow `../brief/add-an-integration.md`. In short: add the product to `product_catalog.json`, add it
to `enabled_sources` if it may open Obi as a source, add its key to `platforms.json` and to the
trusted partners' `allowed_integrations`, redeploy, then label pages `{id}-general` /
`{id}-to-{kind}`.

**Pages labelled before the system existed:** their label was not recognized when they last
synced, so they are not in the index. The reconciliation sweep searches Confluence for every
recognized routing label; the next **complete** sweep (default every 14 days) finds them. Run one
now with `cd backend && uv run python scripts/run_reconciliation_once.py`, or force a real event per
page (label toggle / trivial edit). NEW pages and newly-labelled pages work immediately.

## Removing a system

1. **First** remove it from every partner's `allowed_integrations` and from the `integrations` map in
   `platforms.json` — otherwise boot fails naming it.
2. Remove it from `enabled_sources` and `products` in `product_catalog.json`. Commit, redeploy.
3. Clean up: pages whose only routing labels were that system's are **not purged immediately**.
   They purge on each page's next real event, or in bulk on the next **complete reconciliation
   sweep** (run one now with the command above). Until then they are dead weight: no directed chat
   asks for those labels.

## Renaming a system

Treat it as remove + add in one commit (`platforms.json` renamed in the same commit, or boot fails),
then relabel the pages in Confluence to the new `{id}-…` labels and run one complete sweep. Until
both are done, the renamed system's content is partially or fully missing. If only the spelling a
partner sends differs, add an **alias** in `product_catalog.json` instead — no relabel needed.

## source_scope rows

- Space root with empty tags = every page in that space may be ingested (Decision D3) — today's
  production setup. Page roots cover their subtree only.
- Deactivating the last covering root → the sweep purges everything it covered.

## Verifying any of the above

```bash
# One page's full index state (chunks, versions, stamped tags, marker search; it does not print
# the routing labels yet):
cd backend && uv run python scripts/page_state.py <pageId> [marker]

# Directed routing against the live store (labels per connection):
cd backend && uv run python scripts/verify_directed_routing_live.py --help

# Backend is up:
curl -s https://obi-backend-production.up.railway.app/health

# Events and jobs (read-only), latest first:
#   event_ledger: event_type, page_id, delivery_id (non-null = real webhook), received_at
#   job: job_type, page_id, status, last_error
```

Local test runs: `make check` from the repo root; DB-marked tests refuse the production URL and
need `DATABASE_URL=postgresql+psycopg://rag:rag@localhost:5434/omniboost_rag` (or just `make test`).
