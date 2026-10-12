# Runbook · test the Option A directed-connection routing engine (Phase 9)

How to prove the directed `source → target` routing works end to end, and what a good result looks
like at each gate. Written for the owner (the agent cannot reach production).

There are **two tracks**. Do **Track A first** — it proves the whole engine with no production risk
and no backup. Track B is only for going live on the real store.

- **Track A — local, recommended.** Pull the relabelled real Confluence pages into a *local*
  database and test against them. Nothing in production changes.
- **Track B — production.** The same steps against Supabase, for go-live. Irreversible migrate →
  confirm a backup first.

Both assume the root `.env` has the Confluence credentials (the sync already uses them) and, for
Track A, Docker running.

---

## Track A — local end to end (no production)

### Gate 1 · local DB at head

```
make up
make migrate
cd backend && DATABASE_URL=postgresql+psycopg://rag:rag@localhost:5434/omniboost_rag \
  uv run alembic -c ../knowledge-base/migrations/alembic.ini current
```

**Good result:** the last line prints `0017_chat_session (head)`.

### Gate 2 · pull the relabelled corpus into local, confirm the labels landed

```
cd backend
DATABASE_URL=postgresql+psycopg://rag:rag@localhost:5434/omniboost_rag \
  uv run python scripts/run_reconciliation_once.py
```

This sweeps Confluence and ingests every published page carrying a recognized scope tag
(`obi-general-test`) — which is every one of your routing test pages. Then check one:

```
DATABASE_URL=postgresql+psycopg://rag:rag@localhost:5434/omniboost_rag \
  uv run python scripts/page_state.py <page_id_of_a_test_page>
```

**Good result:**
- The five core pages (and any extension pages) are indexed — each has a `page_source` row,
  `page_status=current`, one active doc version, and active child chunks.
- `page_source.tags` is `['obi-general-test']` on every test page.
- The active chunks carry the page's one routing label in their `labels` column
  (`obi-general`, `toast-general`, `mews-general`, `toast-to-pms`, `mews-to-pos`, …).
- If a page indexed but its `labels` is empty, run the backfill once:
  `DATABASE_URL=…local… uv run python scripts/backfill_labels.py` (idempotent), then re-check.

### Gate 3 · isolation — the headline test

The clean, human-visible way is the widget:

```
make web-dev        # Next.js dev server on :3000
```

Open the app. In the local/test build a **"Simulated test context"** bar appears. To drive a
**directed connection**, mint a directed token from the built-in test host:

- `GET /api/test-hosts/toast/obi-token?form=directed` → a **Toast → Mews** note.
- `GET /api/test-hosts/opera-cloud/obi-token?form=directed` → an **Opera Cloud → Toast** note (the
  other direction, for the switch test).

Ask a question that would pull each marker page, and read the citations.

**Good result — Toast → Mews:** answers cite the pages labelled `obi-general`, `toast-general`,
`mews-general`, `toast-to-pms` (markers: *golden apples, grapes, red bananas, silver pears*) and
**never** the `mews-to-pos` page (*bronze plums*).

**Good result — the switch:** renew the note to **Mews → Toast** (or Opera Cloud → Toast). The open
thread resets to a fresh chat, and now it cites `mews-to-pos` (*bronze plums*) and **never**
`toast-to-pms` (*silver pears*). That one flip proves direction and isolation at once.

**Fast cross-check (DB only, one command):** `scripts/verify_directed_routing_live.py` sets a
`rag_reader` session exactly as the gate does (`app.allowed_sources` / `allowed_knowledge_scopes` /
`allowed_labels`) and prints, per page, whether the connection can see it versus whether it should:

```
cd backend
DATABASE_URL=postgresql+psycopg://rag:rag@localhost:5434/omniboost_rag \
DATABASE_READER_URL=postgresql+psycopg://rag_reader:rag_reader@localhost:5434/omniboost_rag \
ENV=local uv run python scripts/verify_directed_routing_live.py --source toast --target mews --mirror
```

**Good result:** `RESULT: PASS` for both `toast -> mews` and the mirrored `mews -> toast`, every
row's `visible` matching `expected`, and `RLS enforced: True`. Exit code 0. If it prints
`RLS enforced: False` it refuses to call it a pass — set `DATABASE_READER_URL` to the `rag_reader`
DSN (locally the role's password is `rag_reader`; set it once with
`ALTER ROLE rag_reader WITH LOGIN PASSWORD 'rag_reader';` as the owner if auth fails). Exit 2 means
nothing is indexed yet — run Gate 2 first.

### Gate 4 · Phase A (human validation)

Follow `docs/Final_docs/5-integration-context/phase-a-validation-cases.md`. A person asks real
questions through the widget under a known connection and confirms:

- Every sentence in an answer cites a real source that backs it.
- A question with no supporting page **refuses with a reason** rather than guessing.
- Nothing from another connection appears.
- Switching the connection starts a clean thread.

**Good result:** every case matches its expected include/exclude, recorded in that doc as human
evidence (never marked passed without it).

---

## Track B — production (go-live only, irreversible migrate)

Do this only when Track A is green and you are ready to serve the real store. **Confirm a recent
Supabase backup first** — the migrate is upgrade-only and cannot be rolled back on Supabase
(never-bend rule 1).

1. **Migrate** (note the `.env` quote gotcha — `DATABASE_URL` is double-quote-wrapped; pass it
   unquoted, never print it):
   ```
   cd backend
   export DATABASE_URL="$(python3 -c "print([l.split('=',1)[1].strip().strip(chr(34)) for l in open('../.env') if l.startswith('DATABASE_URL=')][0])")"
   uv run alembic -c ../knowledge-base/migrations/alembic.ini current        # expect 0014 before
   uv run alembic -c ../knowledge-base/migrations/alembic.ini upgrade head   # applies 0015/0016/0017
   uv run alembic -c ../knowledge-base/migrations/alembic.ini current        # expect 0017 (head)
   unset DATABASE_URL
   ```
   **Only ever `upgrade` on Supabase — never `downgrade`.**
   **Good result:** `0017_chat_session (head)`, and an existing non-directed chat still answers
   (the label policy is inert until a connection sets the GUC, so normal traffic is unchanged).

2. **Re-sync** the relabelled corpus into prod: `make reingest` (uses the prod `.env`), then
   `scripts/page_state.py <page_id>` — same "good result" as Track A Gate 2.

3. **Live isolation:** run the same `scripts/verify_directed_routing_live.py --source toast
   --target mews --mirror` against prod — point `DATABASE_URL` + `DATABASE_READER_URL` at Supabase
   (the reader URL must be the `rag_reader` role so RLS bites). Expect `RESULT: PASS` both ways and
   `RLS enforced: True`. Also drive the deployed widget with a directed token for the human view.
   Save the output into `docs/Final_docs/5-integration-context/phase-9-isolation-run.txt`.

4. Only after Phase A passes: send the partner replies
   (`docs/Final_docs/5-integration-context/phase-9-partner-replies.md`).

---

## What "the engine is proven" means at the end

- Track A green = the routing logic, the directed gate, the hard filter and the widget switch all
  work against the real relabelled content.
- Track B green = the same on the production store, ready to serve.
- Only then is `mi-hardfilter` honestly `built` rather than `unverified`.
