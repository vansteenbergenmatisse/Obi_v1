# Runbook · Deploy Obi Confluence Sync (the Forge webhook app), and roll back

Obi Confluence Sync (`services/obi-confluence-sync/`) is a private Atlassian Forge app installed on
`omniboost.atlassian.net`. It is the delivery leg of substep 2.0.2: Confluence Cloud has **no
native outgoing webhooks** (no admin UI; `/rest/webhooks/1.0` is unsupported-internal; new private
Connect installs closed March 2026; Confluence Automation has no label-removed/page-restored
triggers and cannot compute an HMAC header), so a Forge app subscribing to the page + label
product events is the sanctioned path. The app normalizes each event to the receiver's flat shape,
signs the exact body string with HMAC-SHA256, and POSTs it to
`https://obi-backend-production.up.railway.app/confluence/events`.

Receiver contract: `docs/Final_docs/ingestion/webhook.md`. Backend deploy:
`docs/runbooks/railway-backend-deploy.md`.

## What the app forwards (and what it drops)

- Events: page created / updated / moved / trashed / restored / deleted + label added / removed
  (`avi:confluence:*`; `removed:label` maps to the receiver's `label_deleted`).
- In-code filters: **pages only** (`content.type === "page"` — label events on whiteboards,
  databases, spaces, templates are dropped) and **space 701857803 only** (key `SupOnb`, URL alias
  `omnidoc`). Manifest `filter.expression` is deliberately not used — unproven for label events,
  which may carry no `content` at all.
- `delivery_id` is a hash over event fields only (never wall clock), so a Forge redelivery is
  byte-deterministic and the backend event ledger dedups it.
- 4xx from the backend is terminal (no retry storm); network errors and 5xx request a Forge retry
  (max 4, exponential backoff). A 401 in the Forge logs = the Forge and Railway secrets diverged;
  a 503 = the backend secret is unset.

## Documented platform limits to know (Atlassian docs, checked 2026-09-29)

- Trigger events "may take up to **3 minutes**" to reach the app. **Owner-resolved 2026-09-29:
  no hard latency SLA — correctness over speed.** A change must land *properly* (right scope,
  right content, purges purge); minutes of delay are acceptable. The 60 s
  `freshness_target_seconds` stays only as an internal telemetry/aspiration number, not a gate;
  the reconciliation sweep stays the backstop.
- Payloads over **200 kB are silently not delivered**; no delivery-order guarantee; duplicates
  occur. All safe: the event is only a doorbell (the worker refetches state) and the sweep
  catches drops.
- One purge does not emit per-descendant deleted events — again the sweep's job.

## Owner inputs required

1. **Atlassian API token** (scoped, app "Forge", from id.atlassian.com → Security → API tokens)
   for `forge login`, as a user of the site; **site/org-admin rights** on omniboost.atlassian.net
   to run `forge install` and consent to the scopes. Note the scope list includes
   `write:confluence-content` — the events reference requires it merely to *subscribe* to
   trashed/deleted page events; the app never writes to Confluence.
2. **`CONFLUENCE_WEBHOOK_SECRET`** — the same value in two places: the Railway service variable
   (already set for the backend) and the encrypted Forge production variable (step 4 below).
   Never in code, logs, or chat.

## Deploy steps (from `services/obi-confluence-sync/`)

```bash
# 0. Prereqs: Node 22.x or 24.x
npm install -g @forge/cli
forge login                      # scoped API token; or FORGE_EMAIL / FORGE_API_TOKEN env vars
npm install

# 1. One-time app registration — writes app.id into manifest.yml. NEVER run twice
#    (re-registering disconnects environments, variables and storage).
forge register "Obi Confluence Sync"

# 2. Static checks
forge lint

# 3. Secret BEFORE deploy — variable changes only take effect on the next deploy.
forge variables set --environment production --encrypt CONFLUENCE_WEBHOOK_SECRET "<value>"

# 4. Deploy, then install on the site (installer must be a site admin).
forge deploy -e production
forge install -e production --site omniboost.atlassian.net --product confluence
```

Later manifest/scope changes: `forge deploy -e production` then
`forge install -e production --site omniboost.atlassian.net --product confluence --upgrade`.
Code-only changes need only the deploy. After `forge register` writes `app.id`, commit the
manifest change and the generated `package-lock.json`.

## First proof (in order — stop at the first failure)

1. **Signed curl** straight at Railway proves secret parity before touching Confluence: build any
   valid JSON body, sign it with the secret, expect 200 `{"accepted": …}`; then flip one body
   byte and expect 401.
2. **Label smoke**: add label `obi-toast-test` to Toast Testpage `1670873122`, watch
   `forge logs -e production` for `delivered label_added page=1670873122`, and run (from
   `backend/`): `DATABASE_URL=<supabase> uv run python scripts/smoke_webhook.py 1670873122
   --require-tag obi-toast-test`. Remove the label; confirm the purge with
   `scripts/page_state.py`.
3. **Trash → restore** the test page (manual UI legs); confirm purge then rebuild.
4. Only then the full 8-rule live run (Toast changed, Mews `1670971395` untouched) — owner
   sign-off required first: `scripts/verify_sync_rules.py` is stamped STAGING ONLY.

Pre-flight on Railway: `ENABLE_BACKGROUND_JOBS=true` must be set, or events ledger but never
drain.

## Rollback

- **Stop deliveries**: uninstall the app from the site (admin UI → Manage apps, or
  `forge uninstall -e production --site omniboost.atlassian.net --product confluence`). The
  backend needs no change — no deliveries, no jobs; the reconciliation sweep keeps the corpus
  converging at its own cadence.
- **Bad handler**: `forge deploy -e production` the previous code (git revert in
  `services/obi-confluence-sync/`).
- **Secret rotation**: set the new value in Railway AND `forge variables set --encrypt`, then
  `forge deploy`. Order: Railway first (the backend accepts only the one secret — a mismatch
  window shows as 401s in `forge logs`, retried up to 4 times).
