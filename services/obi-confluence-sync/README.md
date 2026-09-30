# Obi Confluence Sync (Forge app)

A private Atlassian Forge app for `omniboost.atlassian.net`: subscribes to the Confluence page +
label product events and forwards each as an HMAC-SHA256-signed POST to the deployed backend's
`POST /confluence/events`. This is the delivery leg of ingestion substep 2.0.2 — Confluence Cloud
has no native outgoing webhooks, so this app is the doorbell that makes ingestion webhook-fresh.

- **What it sends**: the receiver's flat JSON shape (`event_type`, `page_id`, `cf_version`,
  `space_id`, `status`/`label`, `event_timestamp`, `delivery_id`, `actor_account_id`), signed as
  `X-Hub-Signature-256: sha256=<HMAC of the exact body string>`.
- **What it drops in code**: non-page content (whiteboards, space labels, …) and anything outside
  space `701857803` (`SupOnb`, alias `omnidoc`).
- **Files**: `manifest.yml` (events, scopes, egress), `src/index.js` (the one handler),
  `package.json` (npm — this dir is deliberately outside the pnpm workspace; Forge CLI expects
  npm here).
- **Deploy / install / prove / roll back**: `docs/runbooks/obi-confluence-sync-deploy.md`.
- **Receiver contract + tests**: `docs/Final_docs/ingestion/webhook.md`,
  `backend/app/features/confluence_sync/server/webhook.py`.

The secret (`CONFLUENCE_WEBHOOK_SECRET`) lives only in Railway and as an encrypted Forge
production variable — never in this directory, the repo, or logs.
