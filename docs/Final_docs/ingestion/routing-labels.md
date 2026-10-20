# Raw routing labels on every chunk

- **Workflow:** ingestion
- **Owning code:** `backend/app/features/ingestion/application/versioning.py` (build-path stamp),
  `backend/app/features/ingestion/application/command_handler.py` (metadata-only restamp),
  `backend/app/features/ingestion/application/backfill_labels.py` (idempotent backfill),
  `knowledge-base/schema/models.py` + `knowledge-base/migrations/versions/0016_chunk_labels.py`
  (the `labels` column, GIN index and RLS policy), `knowledge-base/schema/schema.py`
  (`apply_chunk_labels_rls`)
- **Design panel:** `mi-labels`
- **Status:** Implemented (database-level; live corpus relabel is substep 9.5.1). Since ADR-routing-labels-sole-content-axis
  (2026-10-12) routing labels are **also the index-membership axis**, not only the routing/relevance
  axis — see "Membership" below.

## What it does

Every stored piece of a page remembers the exact Confluence labels it was published with. Ingestion
reads the raw labels Confluence already hands it (`gateway.get_labels`, the unresolved list) and
stamps them, verbatim, onto a `labels text[]` column on both `chunk` and `page_source` — once on
a build and again, with no re-embed, whenever a label-only change arrives over the metadata-only
path. These raw `labels` are the live routing **and** membership axis. (The `tags` column it once
stood beside — the resolved knowledge-scope ∩ authorized set — is retired by ADR-routing-labels-sole-content-axis and left as
inert data; nothing reads it after migration 0018.)

### Membership (ADR-routing-labels-sole-content-axis)

Routing labels are now the sole index-membership axis as well as the content/routing axis. A page is
in the index when it is **published + carries at least one recognized routing label + is not
`classified`**. "Recognized" means a label matching one of the product-catalog routing forms —
`obi-general`, `{slug}-general`, `{slug}-to-{pos|pms|accounting}` — enumerated by
`ProductCatalog.all_routing_labels()`. `ingest_decision` / `sync_service` decide membership on that
set (removing the last recognized routing label removes the page — empty → `delete`), and the
`reconciliation` discovery sweep keys its label search on the same set. This replaces the retired
knowledge-scope `-test` tag axis (`obi-general-test` etc.), which ADR-knowledge-scope-tagging-and-filtering had used for membership;
`classified` is unchanged as the overriding delete/exclusion signal (never-bend rule 5).

Migration 0016 adds the column (default `'{}'`), a partial GIN `ix_chunk_labels_gin ... WHERE
is_active` for the overlap the hard filter will run, and — for the directed-connection routing axis
(ADR-directed-source-target-routing-labels D1) — an `app.allowed_labels` GUC plus a RESTRICTIVE `chunk_labels_read` RLS policy that
mirrors `chunk_scope_read` in shape. That policy is a deliberate no-op until substep 9.4.1 sets the
GUC: an unset/empty GUC and the `'*'` sentinel opt out, and only a real label list filters by
`labels && ...`. A `backfill_labels(gateway)` CLI stamps the raw labels onto pages indexed before the
column existed; it only writes rows that have drifted, so running it twice is safe.

## Why it does it

The directed-connection hard filter (ADR-directed-source-target-routing-labels) routes each chat on the four label boxes a page
carries — `toast-to-pms` ≠ `mews-to-pos`, a distinction the retired tag axis could not express.
Storing the raw labels is the prerequisite: the 9.4.1 filter reads `labels`. Labels restamp without
a re-embed (ADR-directed-source-target-routing-labels D3) because a label change never changes an embedding. The policy rides the
RLS/GUC layer (D1) so that no read can run looser than the search (never-bend rule 3). Labels are
the routing/relevance and (since ADR-routing-labels-sole-content-axis) membership axis, not the access boundary: source
isolation (lock 1, `chunk_source_read`) remains the fail-closed fence and is untouched. (The former
knowledge-scope lock 2 is retired — ADR-routing-labels-sole-content-axis.) Dropping the column, index and policy on downgrade
loosens no isolation (never-bend rule 11).

## How we know it works

- `test_in2_chunk_carries_raw_labels` (database, panel `mi-labels`) — a build stamps the exact raw
  labels on every chunk and the registry row, distinct from the resolved `tags`.
- `test_in2_label_only_change_restamps_labels_no_reembed` (database, `mi-labels`, D3) — a label-only
  edit restamps `labels` as a metadata-only change: same `document_version`, zero embed calls.
- `test_in2_backfill_labels_twice_is_idempotent` (database, `mi-labels`) — the backfill stamps
  previously-empty chunks and a second run writes nothing and creates/destroys no rows.
- `test_sec_labels_policy_is_noop_when_guc_unset` and `test_sec_labels_policy_overlaps_when_guc_set`
  (database, `mi-labels`, D1) — with the GUC unset the RESTRICTIVE policy is a no-op (existing
  isolation unchanged); with it set, only overlapping connection labels are visible and `'*'` opts
  out.
- `test_0016_adds_labels_column_index_and_policy` and
  `test_0016_downgrade_drops_everything_then_upgrade_restores` (database, KB migration chain) — the
  migration adds the two columns, the GIN index and the RESTRICTIVE policy, and downgrades drop all
  of them while the source + scope policies and chunk RLS survive.
- Not yet proven: the live corpus relabel and a live isolation spot-check are owner/content work
  under substep 9.5.1; the enforcing GUC wiring on the retrieval path is substep 9.4.1.
