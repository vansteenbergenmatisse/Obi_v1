# Confluence trigger layer — split trigger from ingestion

> **Historical (pre-migration 0018):** the obi-*-test tags below are retired; see ADR-routing-labels-sole-content-axis.

## Context

**Problem that started this.** A published page "Mews Page 2" (id `1712324611`, space `701857803`) with the valid tag `obi-mews-test` was never ingested. Root cause: discovery depends on `source_scope` roots, not tags — the sweep drops any page not under a root at `reconciliation.py:169`, before the (already correct) tag-based membership logic in `sync_service.handle_sync_page` ever runs. Webhooks are dead (`event_ledger` empty, unreachable in dev).

**Why a two-layer split, not just a patch.** Ingestion (chunking, metadata, embeddings) is about to change a lot. Those changes must **never** break the ability to notice a page changed and decide what to do with it. So we separate the two concerns hard, with one small contract between them:

- **Trigger layer** — watches Confluence (webhooks + the 30s sweep) and decides *what should happen* to a page. Never chunks or embeds.
- **Ingestion layer** — takes a command and does the work: fetch, chunk, embed, write metadata, or delete from the vector DB. Knows nothing about webhooks or sweeps.

Triggering must work all the time regardless of what ingestion looks like. The sweep is always the safety net, even once webhooks work.

---

## The two layers and the command between them

```
Confluence
   │  webhooks (page + label events)              ┌────── 30s reconciliation sweep (safety net) ──────┐
   ▼                                              ▼                                                    │
┌───────────────────── TRIGGER LAYER  (app/features/confluence_sync) ───────────────────────────────┐│
│  webhook receiver → event ledger → job queue                                                       ││
│  sweep → CQL discovery:  list_pages_by_label(space_id, tags)   [CQL uses  space.id = <id> ]         ││
│  worker(page_id, reason):                                                                           ││
│        fetch current state (meta, labels, ancestry, source_scope rows)                             ││
│        should_ingest(...)  →  decide_command(...)                                                   ││
│                              │                                                                       ││
└──────────────────────────────┼─────────────────────────────────────────────────────────────────────┘
                               ▼
                 SyncCommand(page_id, action, scopes, reason)      ← the ONLY contract between layers
                               ▼
┌───────────────────── INGESTION LAYER  (app/features/ingestion) ───────────────────────────────────┐
│  apply_sync_command(cmd):                                                                           │
│     upsert → fetch body · normalize · chunk · contextualize · embed · version · swap · write meta   │
│     delete → purge every row for page_id from the vector DB                                         │
│  (no knowledge of webhooks, sweeps, or source_scope)                                                │
└────────────────────────────────────────────────────────────────────────────────────────────────-─┘
```

### The contract
```python
# app/shared/sync_command.py  (pure; no platform/feature imports)
@dataclass(frozen=True)
class SyncCommand:
    page_id: int
    action: Literal["upsert", "delete"]
    scopes: tuple[str, ...]   # knowledge-scope tags the page belongs to (upsert); () for delete
    reason: str               # why this command was produced (see reason vocabulary below)
```

`scopes` is **authoritative**: the trigger computes `recognized_labels ∩ authorized_tags` and the ingestion layer writes exactly those — it never re-derives membership. `delete` is idempotent (purging a page that isn't indexed is a no-op), which is what makes the event table below collapse to one rule.

### The port (dependency inversion, so trigger imports nothing from ingestion)
```python
# app/features/confluence_sync/application/ports.py  (trigger owns the interface it needs)
class IngestionSink(Protocol):
    def apply(self, session, cmd: SyncCommand, gateway, settings) -> SyncOutcome: ...
```
Ingestion satisfies this **structurally** — it exposes `apply_sync_command(session, cmd, gateway, settings)` and never imports the Protocol. `app/main.py` injects the ingestion function into the trigger worker. No import edge exists in either direction except both feature roots importing `SyncCommand` from `shared`.

---

## The one rule: `should_ingest`

Kept from the prior plan, unchanged in spirit:

```
should_ingest(status, labels, space_id, self_and_ancestor_ids, active_source_scope_rows, recognized) -> bool
  status != 'current'                         -> False   # draft / archived / trashed / deleted
  'classified' in labels                      -> False   # reserved label always removes
  recognized_labels = labels ∩ recognized;  empty -> False
  authorized = union of tags of active rows covering the page
               (space root: root_id == space_id;  page root: int(root_id) ∈ ancestor ids;
                a covering row with EMPTY tags => all recognized tags — see Decision D3)
  recognized_labels ∩ authorized != empty     -> True  else False
```

`decide_command` wraps it:
```
decide_command(page_id, meta_or_None, labels, rows, recognized, reason) -> SyncCommand
  meta is None (gone/inaccessible)  -> SyncCommand(page_id, "delete", (), reason)
  should_ingest(...) is True        -> SyncCommand(page_id, "upsert", tuple(recognized ∩ authorized), reason)
  else                              -> SyncCommand(page_id, "delete", (), reason)
```

Both the webhook worker and the sweep worker call this same function on the page's **current** state, so the two paths always agree.

---

## Full event → command table

Every row is `decide_command` applied to the page's state *after* the event. No per-event branching in the decision — only `reason` differs.

| Event (webhook or sweep observation) | Page state after event | `should_ingest` | Command | `reason` |
|---|---|---|---|---|
| Allowed tag **added** | current, allowed tag in allowed space/folder | True | **upsert** | `tag_added` |
| Tag **removed** (last allowed one) | current, no allowed tag | False | **delete** | `tag_removed` |
| Tagged page **edited** | current, still tagged + allowed | True | **upsert** | `edited` |
| Page **deleted / archived / trashed** | meta gone, or status non-current | False | **delete** | `page_gone` |
| Page **moved out** of an allowed folder | current, tagged, location not allowed | False | **delete** | `moved_out_of_scope` |
| Page **moved into** an allowed folder | current, tagged, location allowed | True | **upsert** | `moved_into_scope` |
| Page reverts to **draft** | status = draft (not published) | False | **delete** | `back_to_draft` |
| Sweep finds drift on a known page | (re-evaluated) | either | upsert/delete | `sweep_drift` |
| Sweep discovers a new tagged page (CQL) | current, allowed | True | **upsert** | `sweep_discovery` |

Note: "delete on draft/move-out" is safe because `delete` is idempotent — if the page was never indexed, it's a no-op.

---

## Discovery, sweep, allow-list (kept from prior plan)

- **Allow-list lives in `source_scope`.** A row's `tags` are both the stamp and the allow-list. **Empty tags = all tags allowed** in that row's coverage (Decision D3 — preserves the 4 existing empty-tag page-roots).
- **CQL label discovery.** New gateway method `list_pages_by_label(space_id, labels)`. The CQL MUST use `space.id = <id> AND label in (...)` — a bare `space = <number>` is read as a space *key*, not id.
- **Sweep is the safety net.** It runs every 30s regardless of webhook health: enumerate each known space, union `source_scope`-covered pages with CQL-discovered tagged pages, enqueue a minimal `(page_id, reason)` job per candidate. The worker re-evaluates `decide_command` on current state.
- Webhooks and the sweep both enqueue the same minimal job and flow through the same worker → same decision function.

---

## Boundary split — enforced by `make check`

Today `app/features/confluence_sync/application/sync_service.py:11-25` imports ~13 symbols from `app.features.ingestion` (`stage_and_activate`, `classify`, `purge_page`, `build_ingestion_services`, `normalization`, …). The split **removes that edge entirely**.

Rules:
1. **Trigger imports nothing from ingestion** — not the root, not internals. Enforced by adding a forbidden edge (`app.features.confluence_sync` → `app.features.ingestion`) to `backend/tools/check_feature_boundaries.py` so `make boundaries` (hence `make check`) fails the build if reintroduced.
2. **Ingestion knows nothing of triggers** — no import of `confluence_sync`, no notion of webhooks/sweeps. It only imports `SyncCommand` from `shared` plus its own internals.
3. `SyncCommand` lives in `app/shared/` (pure — satisfies the existing "shared imports no platform/feature" rule). The `IngestionSink` port lives in the trigger layer (it may reference platform types); ingestion matches it structurally.

---

## Files that move or change

**New**
- `backend/app/shared/sync_command.py` — `SyncCommand` (the contract).
- `backend/app/features/confluence_sync/application/ports.py` — `IngestionSink` Protocol.
- `backend/app/features/confluence_sync/domain/ingest_decision.py` — `should_ingest` + `decide_command` (pure; reuses `scope_resolver.resolve_scope_roots` for subtree coverage).
- `backend/app/features/ingestion/application/command_handler.py` — `apply_sync_command(session, cmd, gateway, settings)`.

**Move (trigger → ingestion)** — the "do the work" half of today's `handle_sync_page`:
- Body fetch + `normalize` + `classify` rebuild-vs-metadata + `stage_and_activate` + metadata-only path + restriction writes + `purge_page`, plus the private helpers `_apply_metadata_only`, `_replace_restrictions`, `_attachment_blocks` → into `command_handler.py`. `classify` (rebuild vs metadata) is an ingestion-internal optimization; the trigger only ever says "upsert".

**Change**
- `backend/app/features/confluence_sync/application/sync_service.py` → shrinks to a trigger orchestrator (fetch state → `decide_command` → call injected sink). Drops **all** `app.features.ingestion` imports.
- `backend/app/features/confluence_sync/application/worker.py` — dispatch each job through `decide_command` + the injected `IngestionSink`, not ingestion internals.
- `backend/app/features/confluence_sync/application/reconciliation.py::_sweep_space` — union CQL-discovered pages; enqueue minimal `(page_id, reason)` jobs; add discovered ids to the orphan `in_scope` set.
- `backend/app/features/confluence_sync/application/event_service.py` — carry `reason`; keep the liberal enqueue (the worker's decision is authoritative).
- `backend/app/platform/clients/confluence_client.py` + `fixture_confluence_client.py` — add `list_pages_by_label` (Protocol + Http impl w/ CQL `space.id`; fixture filters in-memory pages by space + label, honoring `_NON_CURRENT`).
- `backend/app/features/ingestion/__init__.py` — export `apply_sync_command`; import `SyncCommand` from `shared`. Symbols previously exported only for `confluence_sync` may become internal again (optional cleanup).
- `backend/app/main.py` — wire the concrete ingestion sink into the trigger worker.
- `backend/tools/check_feature_boundaries.py` — add the forbidden trigger→ingestion edge.
- Docs: `docs/Final_docs/ingestion/*` (new "trigger vs ingestion" + reconciliation/webhook updates), ledger + progress-log entries.

---

## Tests, split by layer

All parametrized over **every tag** in `knowledge_scopes.json` (`load_recognized_knowledge_scopes()`), never hardcoding `obi-mews-test`.

### Trigger tests (use a **fake ingestion sink** — capture emitted `SyncCommand`s; assert nothing about chunks/embeddings)
Must pass even if ingestion is fully swapped out.
- One test **per row of the event→command table** above: given the event + page state + seeded `source_scope` rows, assert the exact `SyncCommand(action, scopes, reason)` reaching the fake sink.
- New top-level tagged page, space has roots, **lightweight** sweep → `upsert` command emitted (the original bug).
- Same, **complete** sweep.
- `label_added` webhook → `upsert` command (today only `page_updated` is tested).
- Tag in a folder where it is **not** allowed → `delete` (or no upsert) from **both** sweep and webhook.
- Unknown tag → no `upsert`.
- Draft page with an allowed tag → `delete`/skip (fails today: draft isn't in `_GONE_STATUSES`).
- Removing the tag → `delete` command.
- Pages under existing roots with **no** tag → behaves as before.
- Sweep and webhook produce the **same** command for the same page (one case table, both entry points).

### Ingestion tests (feed `SyncCommand`s **directly** — no webhooks, no sweeps)
- `upsert` with N scopes → page indexed, chunks written, scopes stamped == `cmd.scopes`.
- `delete` → `page_row_counts == 0` (hard purge, current behavior).
- `upsert` on an unchanged page → metadata-only / no re-embed (reuses `CountingEmbedder`).

### Contract test (one)
- A `SyncCommand` produced by the trigger's `decide_command` is accepted and correctly applied by the ingestion `apply_sync_command` — the two halves fit.

---

## Security baseline (securing-http-and-llm-endpoints)
```yaml
security_baseline:
  applies: true
  surfaces:
    - id: POST /confluence/events (webhook receiver — unchanged controls)
      tier: STATE-MUTATING
      controls:
        C1_auth:        { status: covered, mechanism: "HMAC X-Hub-Signature-256, unchanged" }
        C2_rate_limit:  { status: covered, mechanism: "existing per-endpoint limiter" }
        C3_input:       { status: covered, mechanism: "parse_webhook_payload schema" }
        C7_idempotency: { status: covered, mechanism: "event dedup + job idempotency_key" }
        C9_audit:       { status: covered, mechanism: "event_ledger row per delivery" }
    - id: gateway.list_pages_by_label (new outbound Confluence CQL call)
      tier: STATE-MUTATING
      controls:
        C3_input:   { status: covered, mechanism: "CQL from config tags (trusted) + int space.id; IN-list encoded; no request-body input" }
        C4_timeout: { status: covered, mechanism: "reuses HttpConfluenceClient._get timeout + circuit breaker" }
        C10_abuse:  { status: opted_out, justification: "internal Confluence API; per-space bounded query; no per-user cost surface" }
```

---

## Operator action (owner runs — not me, not now)
For the live fix, seed one space-level allow row so `obi-*-test` are allowed across space `701857803`:
```sql
INSERT INTO source_scope (root_type, root_id, source_type, tags, is_active, label)
VALUES ('space', '701857803', 'confluence',
        ARRAY['obi-general-test','obi-mews-test','obi-operacloud-test','obi-toast-test'],
        true, 'omnidoc space (all obi-*-test scopes)');
```
Then a sweep emits `SyncCommand(1712324611, "upsert", (...), "sweep_discovery")`. Exact force-ingest command supplied at report time; I will not run it.

---

## Decisions I need from you before coding

- **D1 — Contract shape.** `SyncCommand(page_id, action, scopes, reason)` exactly as above, `scopes` authoritative, in `app/shared/`? (Recommended.)
- **D2 — Decision timing.** Re-evaluate `decide_command` in the **worker** on current state (idempotent, survives races), with jobs carrying only `(page_id, reason)`? (Recommended over deciding at enqueue.)
- **D3 — Empty `source_scope.tags` = all tags allowed** in that coverage (backward-compat for the 4 existing empty-tag roots). Confirm, or switch to strict "empty = nothing" (which requires re-seeding before deploy).
- **D4 — Minimal contract vs double-fetch.** Ingestion re-fetches page meta/body by `page_id` (trigger already fetched meta to decide). Accept the small double-fetch to keep the contract minimal? (Recommended.)
- **D5 — `reason` vocabulary.** Fix the closed set: `tag_added, tag_removed, edited, page_gone, moved_out_of_scope, moved_into_scope, back_to_draft, sweep_drift, sweep_discovery`. OK / additions?
- **D6 — Job queue stays the trigger→ingestion mediation** (crash safety), with the sink called inside the worker transaction? (Recommended.)

## Open (not in scope)
- Live webhook reachability (owner-gated: stable HTTPS + Confluence admin + `CONFLUENCE_WEBHOOK_SECRET`). The sweep safety net makes webhooks unnecessary for correctness.
- A brand-new space with only tagged pages and no `source_scope` row still isn't swept until a row for that space exists (space selection = known ∪ rooted spaces).

---

*Stopping here per instruction — awaiting go-ahead before any code.*
