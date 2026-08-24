# Data ingestion — phase-by-phase

> The **write path**: how a Confluence page becomes searchable rows in Postgres. Covers
> `app/features/confluence_sync/` (get data in) and `app/features/ingestion/` (turn a page into
> chunks + embeddings). For the **read path** (hybrid search, the answer runtime, chat), see
> [`../retrieval/README.md`](../retrieval/README.md). For the full end-to-end narrative in one
> file, see [`../how_this_works.md`](../how_this_works.md); for the authoritative task-by-task
> history, see [`../PLAN.md`](../PLAN.md).

Each file below covers exactly one main phase, only where that phase actually changed something on
the ingestion side — a phase with no ingestion-relevant work (e.g. Phase 3's retrieval core, Phase
4's answer runtime, Phase 9's fallback classifier) has no file here; see the retrieval folder
instead.

| Phase | What it covers on the ingestion side | Status | File |
|---|---|---|---|
| **0** | Design docs & ADRs that shape ingestion's boundary and write-role split | ✅ done | [phase-0.md](./phase-0.md) |
| **1** | Confluence sync: webhook, job queue, worker, change classification, reconciliation | ✅ done | [phase-1.md](./phase-1.md) |
| **2** | The ingestion transform: chunking, contextual retrieval, versioning/activation/rollback | ✅ done | [phase-2.md](./phase-2.md) |
| **3.5** | Provider tagging (writer-side stamp) + Confluence source scoping | ✅ done (3.5.3, 3.5.6) | [phase-3.5.md](./phase-3.5.md) |
| **4.6** | Fixes-backlog items that landed in `confluence_sync`/`ingestion`: group-restriction fail-closed, rollback hash restore, client hardening, event-dedup fix, attachment wiring | ✅ done | [phase-4.6.md](./phase-4.6.md) |
| **6** | Supabase vector store migration & deploy (writer-role/connection impact) | ⬜ todo (deferred) | [phase-6.md](./phase-6.md) |
| **10** | Knowledge-scope tagging (writer-side half): recognized-scope config, label-driven per-page tags unioned with `source_scope`, corpus migration | 10.1–10.2 ✅ done, 10.7 ⬜ not started | [phase-10.md](./phase-10.md) |

**Deliberately out of scope here:**

- **Phase 4.7 (Obi widget chat UI)** and **Phase 4.8 (frontend/backend repo separation, moved
  out)** are frontend/`apps/web` concerns, not ingestion. See
  [`../OBI-WIDGET-DESIGN.md`](../OBI-WIDGET-DESIGN.md) and
  [`../../future-ideas/IDEAS.md`](../../future-ideas/IDEAS.md).
- **Phase 7 (vision-grounded image analysis)** is about images pasted/screenshotted into the chat
  widget, analyzed at answer time — not Confluence page attachments. It's entirely retrieval/answer
  runtime work; see `../retrieval/phase-7.md`. Confluence *page* attachment extraction
  (PDF/DOCX/XLSX/CSV/HTML) is a genuine ingestion concern and is covered under Phase 4.6 here
  (sub-step 4.6.13 + this session's wiring).
- **Phase 5 and Phase 9** are answer-runtime/optimization work with no ingestion-side change.

**Keep this folder current.** Per the root `CLAUDE.md`, when ingestion-side code changes, update
the relevant phase file (or add a new one for a new phase) in the same change — don't let this
drift the way `how_this_works.md` once did (see Phase 4.6.14 in `PLAN.md`).
