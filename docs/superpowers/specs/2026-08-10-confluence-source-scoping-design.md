# Design — Confluence source scoping (page/page-tree granularity)

> Status: **implemented (PLAN.md sub-step 3.5.6, shipped 2026-08-10).** Written via
> `superpowers:brainstorming` on 2026-08-10, then planned and built the same day. Companion
> status/history lives in `docs/rag/PLAN.md` §0 and `docs/rag/DESIGN.md` §10 /
> `docs/rag/how_this_works.md` §3, §4.7, §12. Two deviations from this document as originally
> written, both noted in DESIGN.md §10 and how_this_works.md §12: (1) the migration does not read
> `CONFLUENCE_SPACES` as a data seed — it's schema-only, seeding is a separate one-off script
> (`scripts/seed_source_scope.py`), to keep migrations environment-independent like 0001-0003; (2)
> `resolve_space_scope` takes *every* recorded root (active or not) rather than only active ones,
> so a space with rows that are all inactive is distinguishable from a space with no rows at all —
> otherwise deactivating a space's last root would silently revert to unrestricted instead of
> purging it. This document is the design of record for the feature; those files are pointers, not
> duplicates.

## 1. Problem

Confluence sync today operates at **whole-space granularity only**. `settings.confluence_scope_list`
(parsed from `CONFLUENCE_SPACES`) is defined but has **zero consumers anywhere in the app** (confirmed
by grep) — there is no way to sync "just this page" or "just this page-subtree" narrower than an
entire space.

The user wants that narrower granularity, inspired by a prior Omniboost project (Mewsy,
`knowledge/fetch_sources.json` + a recursive Confluence scraper that walks folder-root page IDs). Two
things from Mewsy are explicitly **not** wanted here:

- A checked-in JSON/YAML config file as the source of truth (rejected: "trash" — wants it in the
  actual DB-backed system, not flat files, and it needs to change without a redeploy).
- Mewsy's deletion check, which only fires when a *whole folder* is removed from its config — an
  individual page deleted upstream inside a still-configured folder is silently never cleaned up.

This repo's `reconciliation.py` already does deletion/drift correctly (diffs live pages against the
DB registry, deactivates vanished pages) — better than Mewsy's — but only at whole-space granularity.
The gap is real, but the *base logic* to build on is already right.

## 2. Decisions (from brainstorming)

| Question | Decision |
|---|---|
| Scope granularity | Yes — individual pages / page-subtrees ("folders"), narrower than a whole space |
| Storage | DB-backed table, not a checked-in config file |
| Deletion semantics | Purge — deactivate already-ingested content when its covering root is removed |
| Ownership | One-off (the user supplies IDs; no self-service CRUD yet) |
| Bot/tag scoping | Each configured root also carries `tags`, tying into the existing `tags` column on `page_source`/`chunk` |

## 3. Approaches considered

**Chosen — root-based recursive resolution feeding the existing reconciliation diff.** A new table
stores configured roots (page or space). A resolver computes the current descendant set of each root
**in-memory, with zero new Confluence API calls** — `ConfluencePageMeta.parent_id` is already returned
by `list_space_pages` (live client: `confluence_client.py:122-138`; fixture:
`fixture_confluence_client.py:150-163`), so resolving "descendants of root page X" is a pure tree-walk
over data already fetched. `reconciliation.py`'s `_sweep_space` (`:92-142`) already treats "the live
set" and "the registry diff" as separately-computed inputs — not deeply space-shaped — so it accepts
an optional narrower live set without a rewrite.

**Rejected — sync everything, filter at the edge.** Keep syncing whole spaces unchanged; add the scope
table as a post-hoc display/activation filter. Simpler to build, but wastes fetch/embed cost on
out-of-scope pages and doesn't purge on removal for free (ingestion never actually stops for
out-of-scope pages under this approach).

**Rejected — static flat list of page IDs per root, no recursive walk.** Wouldn't pick up new child
pages added later under a folder — defeats the "folder" behavior that's the actual point of this
feature.

## 4. Schema

New table `source_scope`, column-style matched to the existing `ReconciliationRun` model (int PK,
short strings, `server_default`, timestamps):

| Column | Type | Meaning |
|---|---|---|
| `id` | PK | |
| `root_type` | `String(16)` + CHECK (`space`\|`page`) | `space` = today's whole-space behavior (unchanged); `page` = subtree root |
| `root_id` | `String(128)` | the space key/id or the page id |
| `source_type` | `String(32)` | e.g. `confluence` — same domain as `chunk.source_type` |
| `tags` | `ARRAY(Text)` | bot/tag scoping applied to everything resolved under this root |
| `label` | `String`, nullable | human-readable name (Mewsy-style, informational only) |
| `is_active` | `bool`, `server_default true` | soft-disable a root without deleting its row/history |
| `created_at` / `updated_at` | timestamps, `func.now()` | |

Unique constraint on `(root_type, root_id)`.

## 5. Resolver

A pure function, no network calls:

```
resolve_scope_roots(live_pages: list[ConfluencePageMeta], roots: list[SourceScope])
    -> dict[root_id, set[page_id]]
```

- `space` root → resolved set = every live page in that space (identical to today's behavior).
- `page` root → resolved set = the root page + every descendant found by walking `parent_id` chains
  over the already-fetched `list_space_pages()` result.
- Overlapping roots (nested `page` roots, or a `page` root inside an already-covered `space` root)
  resolve independently; downstream consumers union their coverage (§6).

`CONFLUENCE_SPACES` becomes a **one-time migration seed** — the migration inserts one `space`-type row
per configured space key, so behavior is unchanged until the first `page`-type root is added. The env
var stops being consumed at runtime after the migration; the table is the single source of truth.

## 6. Reconciliation integration

`_sweep_space` gains an optional parameter, `allowed_page_ids: set[int] | None`:

- `None` (no `page`-type roots configured for this space) → today's behavior, byte-for-byte unchanged.
- Set (from the resolver, when `page`-type roots exist) → the live set diffed against the registry is
  intersected with `allowed_page_ids` instead of the full space listing. `_registry_for_space` gets a
  page-id-filtered variant for the same reason.
- **Purge on removal**: a registry row not covered by the **union** of every still-active root's
  resolved set gets deactivated via the existing `deactivate_page` path — the same code reconciliation
  already uses for pages deleted upstream in Confluence. No new deletion logic; a page is purged only
  when *no* active root covers it anymore.
- **Tag propagation**: each newly-enqueued sync job carries the covering root's `tags` (union across
  covering roots if more than one), which flow through to `page_source.tags` / `chunk.tags` at the
  ingestion activation point (`versioning.py`) — extending the seam that already stamps
  `source_id`/`source_type` there today.

The resolver function is exported from `confluence_sync`'s public `__init__.py` alongside
`run_reconciliation` et al., per this repo's feature-boundary rule.

## 7. Migration

A new Alembic migration, `0004_source_scope` (`down_revision="0003_query_trace"`, the current head),
creates `source_scope` and backfills one `space`-type row per current `CONFLUENCE_SPACES` entry.
`downgrade()` drops the table; `confluence_scope_list` reverts to unused, matching today.
`CONFLUENCE_SPACES` must actually be set with real space keys before this backfill has anything to
seed — that's the existing, separately-tracked blocker in `PLAN.md` §0 ("Blockers / need from you"),
not new to this feature.

## 8. Ownership / management

No CRUD endpoint in this iteration. Rows are inserted directly (script or one-off migration data) with
IDs and tags supplied by the user, matching how the Confluence credentials were handled this session.
Self-service CRUD is deferred until it's a concrete requirement (ties to the already-recorded
multi-bot product goal in `PLAN.md` §1.1, but is not built now — proportionality gate).

## 9. Testing

- **Unit — resolver.** A `page` root resolves to itself + descendants only, never siblings. A `space`
  root resolves to everything in that space (regression: matches today). Overlapping roots union
  correctly. A page outside every root resolves to nothing.
- **Integration (DB-backed, extends `test_reconciliation.py`).** A `page`-type root syncs only its
  subtree, not sibling pages in the same space. Deactivating a root (`is_active=false`) purges its
  previously-synced, now-uncovered pages via `deactivate_page` — asserted as an actual
  zero-rows/`is_active=false` check, not a smoke test. Tags on ingested `page_source`/`chunk` rows
  match the covering root's `tags`.
- **Regression.** Existing space-level reconciliation tests pass unchanged — `_sweep_space` with
  `allowed_page_ids=None` must be provably identical to its current behavior.

## 10. Acceptance criteria

- `make check` green; `make boundaries` clean.
- Migration is reversible.
- A configured `page`-type root syncs and tags only its descendants, not the rest of its space.
- Removing a root purges exactly the pages no other active root still covers.
- With zero `page`-type roots configured, behavior is bit-for-bit identical to today's whole-space sync.
- No ruff/pyright regression vs. the ADR-0003 D1 baseline.

## 11. Explicit non-goals (this iteration)

- Self-service CRUD / admin UI for managing roots.
- Cross-source scoping (Zendesk/Notion/uploads) — Confluence only, per the repo's existing product
  decision not to generalize ingestion yet.
- OCR / image reading (separately tracked, unrelated gap — noted in `PLAN.md` §0, not in scope here).
- Re-tuning `refusal_min_rerank_score` or anything in the Phase 4 answer pipeline — this feature only
  touches ingestion scope, not retrieval/answer behavior.

## 12. Relationship to PLAN.md / DESIGN.md

This is a **Phase-3.5.3-adjacent** concern (provider tagging + reconciliation), not a new top-level
phase and not a blocker for Phase 4.2 (the answer workflow), which proceeds independently. Once this
spec is approved and planned, `PLAN.md` gets a new numbered sub-step (proposed: **3.5.6**, since it
extends the already-closed 3.5.3 reconciliation/tagging work) rather than reopening 3.5.3 itself, and
`DESIGN.md` §3/§10 plus `how_this_works.md` §3/§4/§12 get updated from "open design discussion" to
"as-built" once implemented.
