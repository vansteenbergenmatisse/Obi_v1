# webhook (Confluence event receiver)

- **Workflow:** ingestion (stage 1 — a published change enters the system)
- **Owning code:** `backend/app/features/confluence_sync/server/webhook.py` (`POST /confluence/events`), calling `application/event_service.py::ingest_event`
- **Design panel:** `i1-webhook` (valid delivery → 200 + one job; redelivery → 200 + no job) and `i1-checks` (the gate)
- **Status:** Implemented (handler) · **Proven live 2026-09-30** — the Forge bridge (`services/obi-confluence-sync/`) delivers real Confluence events to the Railway deployment; the 8-rule end-to-end run is recorded in the ledger ("Step 3 · Confluence webhook go-live"). The `i1-webhook` panel flip is batched with roadmap substep 4.7.

## What it does

`POST /confluence/events` is the front door of ingestion. Confluence calls it when a page is
published, changed, or removed. The handler is **state-mutating but fast**: it validates,
authenticates, and records the delivery, enqueues one job, and returns a small JSON ack in a few
milliseconds. It does no page fetch, parse, or index — that runs later on the worker. Concretely,
per request it: rate-limits per client IP, rejects an oversized body, verifies the HMAC signature,
parses the payload into an `EventEnvelope`, then hands off to `ingest_event`, which writes one
immutable `event_ledger` row and idempotently enqueues a `sync_page`/`delete_page` job. A
self-generated event (Obi's own edit) records the ledger row but enqueues no job.

The enqueued job now carries only `page_id` + a `reason` hint (no scopes/tags): the trigger/
ingestion split moved the decision into the worker, which re-derives the authoritative command
from the page's current state. See `trigger-and-ingestion-split.md` for the two-layer contract
this handler feeds.

## Why it does it

The webhook is what makes ingestion *fresh* rather than sweep-only: it is the path that carries a
publish to the vector store within the freshness target (see [[freshness]], 60 s SLA) when it is
up; the daily sweep ([[reindex-job]] is the corpus-wide cousin) is only the catch-all for anything
the webhook misses. The gate exists because this is an unauthenticated public endpoint mutating
state: the signature (HMAC-SHA256 over the raw body, constant-time compare) proves the caller is
Confluence and no one else; it **fails closed** (503) when the secret is unset, so a
misconfigured deploy refuses traffic rather than trusting it. The **event ledger is the sole
redelivery stop**: a byte-identical redelivery dedups on payload hash + `delivery_id` and never
reaches the job layer. Each delivery that *survives* ledger dedup is a real distinct event, and
its job idempotency key carries the event-ledger id (`sync_page:{page_id}:{event_id}` /
`delete_page:{page_id}:{event_id}`), so a second real label event or a re-trash after a restore
always enqueues its own job — completed jobs are never pruned, so a key built only from page
state would collide forever (label events carry no page version). Redundant jobs are cheap: the
worker re-decides on current state and its version guard turns a same-version resync into
`no_change` (no body fetch, no embed). The request body never decides access — origin is stamped
server-side (`origin=0`), consistent with project rule #2.

## How we know it works

Unit tests in `backend/app/features/confluence_sync/tests/test_webhook.py` (all green), each
protecting `i1-webhook` / `i1-checks`:

- `test_valid_signed_event_is_accepted_and_enqueued` — valid delivery → accepted + one job (`i1-webhook`).
- `test_duplicate_delivery_is_deduped` — redelivery → no second job (`i1-webhook`).
- `test_i1_two_distinct_label_deliveries_on_one_page_each_enqueue_a_job` /
  `test_i1_two_distinct_trash_deliveries_on_one_page_each_enqueue_a_job` — two REAL events on one
  page each enqueue their own job (`i1-ledger`; the idempotency-key-swallow regression: the old
  version-less keys collapsed every later label event / re-trash into the first-ever job).
- `test_i1_true_duplicate_label_delivery_still_enqueues_one_job` — the companion bound: a true
  duplicate still makes exactly one job, stopped at the event ledger (`i1-ledger`).
- `test_self_generated_event_enqueues_no_job` / `test_i1_self_ledger_row_marked_done_and_self_generated` — Obi's own edit records but enqueues nothing.
- `test_missing_signature_is_rejected` (401), `test_bad_signature_is_rejected` (401), `test_unset_secret_fails_closed` (503) — the auth gate (`i1-checks`).
- `test_oversized_body_is_rejected` (413), `test_rate_limit_returns_429` (429) — the size + rate gate.
- `test_s_audit_webhook_event_log_line_carries_type_page_actor_and_outcome` — the audit log line.

The handler also carries an inline `security_baseline` block (C1–C10) at the top of `webhook.py`.

**Live, repeatably (roadmap substep 4.3):** `backend/scripts/webhook_rules_live.py` is the
permanent form of the 2026-09-30 session runner — it drives ONLY real Confluence REST mutations
(labels, a body edit, a trash/restore) and then polls the database until the deployed path
(Confluence → Forge → Railway `POST /confluence/events` → event ledger → job → worker) has done the
work, reporting the new `origin=0` event-ledger rows per leg as the delivery evidence. It refuses
the offline fixture env, requires `--yes`, restores the original labels AND body in a `finally`,
and fingerprints a witness page before/after (rule 8). Its two safeguards are hermetically proven
in `test_webhook_rules_live_script.py` (`test_webhook_rules_live_refuses_without_yes`,
`test_webhook_rules_live_refuses_an_unconfigured_confluence`). One command:

```bash
cd backend && uv run python -u scripts/webhook_rules_live.py \
  --page-id 1670873122 --other-page-id 1670971395 \
  --scope-a obi-toast-test --scope-b obi-mews-test --yes
```

> The `obi-…-test` label names shown above are retired (ADR-routing-labels-sole-content-axis, 2026-10-12): index membership and
> routing now run on recognized **routing labels** (`obi-general`, `{slug}-general`,
> `{slug}-to-{pos|pms|accounting}`), not on the old knowledge-scope `-test` tags. A fresh live run
> should pass recognized routing labels; the two values are only the pair of labels the script flips
> to exercise the label-event path.

**The section below is superseded (kept as the record of the pre-Forge state).** The "not
reachable from Confluence" blocker was closed on 2026-09-30 by the Forge app deployment
(runbook `docs/runbooks/obi-confluence-sync-deploy.md`); the tunnel plan was never needed. `i1-webhook` is `unverified` for one reason only: the handler is not
reachable from Confluence until the backend has a public HTTPS URL. Closing that is substep
**2.0.2**, which is **blocked on owner-only resources** — see the ledger's `2.0.2 · need from you`
entry (2026-09-24). Required to complete 2.0.2 and flip `i1-webhook` to verified:

1. **`CONFLUENCE_WEBHOOK_SECRET`** — the shared secret value (lives only in the gitignored root `.env`).
2. **A reachable local/staging backend** to expose (the existing SEC-TUNNEL script tunnels the *frontend* `:3100`, not the backend, and issues a *rotating* hostname — it does not satisfy 2.0.2's "stable HTTPS name").
3. **Confluence site-admin access** to register the webhook URL + secret against the tunnel.
4. **A tunnel account / stable hostname** (cloudflared named tunnel or ngrok reserved domain).

The live proof, once those exist: publishing a test page creates one `event_ledger` row and one
job within seconds, and the tunnel address + restart command are documented here. This tunnel is
replaced by the AWS address in Phase 7.

## How to run the live test (2.0.2 runbook)

Route: `POST /confluence/events` (no prefix). Auth: `X-Hub-Signature-256: sha256=<HMAC-SHA256(raw
body, CONFLUENCE_WEBHOOK_SECRET)>`, constant-time; unset secret → 503, wrong/missing → 401.

**0. Set the secret.** Put `CONFLUENCE_WEBHOOK_SECRET=<a strong random string>` in the gitignored
root `.env` — the same value you give Confluence.

**1. Run the backend + DB.** `make up && make migrate && make api` (uvicorn on `:8000`). Point it
at your local dev DB (`postgresql://rag:rag@localhost:5434/omniboost_rag`) for a self-contained
test, or at staging.

**2. Fastest check — signed curl (no Confluence needed).** Proves handler + tunnel + secret before
you arrange Confluence admin. Sign the *exact* body you send:
```bash
SECRET="$CONFLUENCE_WEBHOOK_SECRET"
BODY='{"event_type":"page_updated","page_id":123456,"cf_version":7,"delivery_id":"smoke-001","actor_account_id":"tester"}'
SIG=$(printf '%s' "$BODY" | openssl dgst -sha256 -hmac "$SECRET" | sed 's/^.* //')
curl -sS -X POST http://localhost:8000/confluence/events \
  -H "Content-Type: application/json" \
  -H "X-Hub-Signature-256: sha256=$SIG" --data "$BODY"
```
Expect `200` with `{"accepted":true, ..., "job_id":<n>}`. Flip one byte of `SIG` → `401`; empty
`SECRET` → `503`; a `>512 KiB` body → `413`.

**3. Stand up the stable tunnel to `:8000`** (the requirement 2.0.2 adds). cloudflared *named*
tunnel or ngrok *reserved* domain — not a quick tunnel (its name rotates). Re-run step 2 against
`https://<stable-host>/confluence/events` to confirm it's reachable from outside.

**4. Register the webhook in Confluence** (site-admin): URL `https://<stable-host>/confluence/events`,
secret = `CONFLUENCE_WEBHOOK_SECRET`, events = page created/updated/moved/removed + label
added/removed (see `SYNC_EVENTS`/`DELETE_EVENTS` in `schemas/events.py`).

**5. Publish/edit a tagged test page**, then verify within seconds:
```bash
psql postgresql://rag:rag@localhost:5434/omniboost_rag \
  -c "select id, event_type, page_id, cf_version, proc_status, origin, self_generated, delivery_id, received_at from event_ledger order by id desc limit 3;" \
  -c "select id, job_type, status from job order by id desc limit 3;"
```
Pass = one fresh `event_ledger` row (`origin=0`, `proc_status` `received`/`queued`) and one `job`
(`job_type='sync_page'`) within seconds — this is `i1-webhook`'s live proof. Record the stable
tunnel address + its restart command right here, then flip `i1-webhook` to verified on the design
page.

> **Verified 2026-09-24 (server pinned to local dev DB, `ENABLE_BACKGROUND_JOBS=false`, throwaway
> secret):**
> - *Path A (localhost):* valid signed `page_updated` POST → `200 {"accepted":true,"job_id":1}`;
>   tampered signature → `401 invalid signature`; redelivery → `duplicate:true` with no second job;
>   left exactly one `event_ledger` row (`origin=0`, `proc_status=queued`) and one `pending`
>   `sync_page` job.
> - *Path B partial (public cloudflared quick tunnel):* the same signed POST sent to
>   `https://<random>.trycloudflare.com/confluence/events` **from the public internet** →
>   `200 {"accepted":true,"job_id":2}`; tampered → `401`; produced the `event_ledger` row + job.
>   This proves the full external path (internet → Cloudflare → tunnel → backend → DB).
>
> **What Path B does NOT yet prove (still owner-gated):** a *stable* hostname (quick tunnels
> rotate — 2.0.2 requires a named cloudflared tunnel or ngrok reserved domain, which needs a
> login), and Confluence itself registered as the sender firing on a real page publish. `i1-webhook`
> stays `unverified` until that real proof runs.
