# Applicability schema ("Applies to")

- **Workflow:** ingestion
- **Owning code:** `backend/app/features/ingestion/domain/applicability.py` (schema, validation,
  `applies_to_payload` serializer) and `backend/app/features/ingestion/domain/applies_to_parsing.py`
  (the table parser), both exported from the feature root; stamping wired in
  `backend/app/features/ingestion/application/command_handler.py` (`_normalize_fetched_body`,
  the restamp drift check) and `application/versioning.py` (build/activate threading); the
  direction vocabulary from `backend/app/platform/config/product_catalog.py`
  (`connection_directions`); the platform vocabulary from
  `app/platform/config/platforms.py` (`PlatformRegistry.platform_keys`); storage by migration
  `knowledge-base/migrations/versions/0015_applicability_stamp.py` (nullable JSONB
  `applicability` on `chunk` and `page_source`)
- **Design panel:** `mi-applies` (section 05.2, Multi-integration context)
- **Status:** Implemented at database level (8.2.1 schema + 8.2.2 parse/stamp/restamp); not yet
  consumed by retrieval (matching is 8.2.3) and not yet proven live

## What it does

Validates one authored "Applies to" record — the field/value rows of one or more standard
tables in a Confluence page body — into a typed, immutable `AppliesTo` value: one or more
`ApplicabilityRule`s (OR between rules), each at one of the five §D.3 levels (general ·
software · platform-interface · connection · workflow) with optional variant requirements
(feature, accounting flow, version). Connection-level rules name the connection type, every
role side (a canonical product id or the explicit literal `any`) and the flow directions;
workflow rules require two or more connections linked through a shared concrete product, plus
explicit bindings (`same-instance`, `same-property`). Every rejection raises
`ApplicabilityValidationError` with a stable named `reason` slug (the slug also prefixes the
printable message, so a failed sync job's recorded error carries the name). Products, roles,
connection types and directions all resolve through the product catalog — one vocabulary,
aliases included.

Since 8.2.2 the record also **lands on the chunks**. At the body-fetch point the parser lifts
every Applies-to table out of the raw storage HTML *before* normalization — the table is
metadata, never chunk content, and never part of the content/structure hashes — then the
validated record serializes (`applies_to_payload`) onto `page_source.applicability` and every
chunk's `applicability` at build. On a sync whose content proved unchanged, the handler
compares the freshly parsed payload against the stamped one (exactly the §D.0 scopes-drift
pattern) and routes a mismatch — a changed **or removed** record — over the metadata-only
restamp path: same `document_version` id, zero embed calls, stale eligibility replaced, and
`current_cf_version` advanced so sweeps do not re-flag the consumed revision forever.
`SyncOutcome` reports `classes=["applicability_restamped"]`. An authored-but-invalid table
fails the sync loudly by named reason (the job fails; the previously indexed state survives
untouched) — never a silent fall-back to label-only. A page with no table keeps label-only
behavior (`applicability` stays NULL); a mixed-applicability page is **split** (the authoring
rule): one page carries one record, every chunk the same rules, so one broad page-level rule
never exposes unrelated instructions — several tables on one page OR together and are the
whole-page alternatives of §D.4, not per-section rules.

## Why it does it

Pages must be able to say "Mews connected to QuickBooks", not just "Mews" (plan.md §D.3), and
the semantics must never widen silently: `any` is authored explicitly, a missing required
field fails loudly (never a wildcard), an unknown field name fails loudly (a dropped condition
would widen the rule), and a page with no record keeps today's label-only behavior — the
documented §D.11 compatibility default, distinct from an empty (malformed) record. The
authoring approach — a body table, not content properties — was decided in substep 8.2.1 on
fetch-surface and change-detection evidence (`docs/Final_docs/5-integration-context/
applies-to-authoring.md` §1, decision memo §4b). Stripping the table before hashing is what
makes a table edit a *metadata* edit: §D.3 requires "a metadata edit updates existing chunks
and invalidates stale eligibility" over the §D.0 restamp route with the eight sync rules
unchanged — re-embedding an unchanged page for a metadata change would burn cost and violate
the restamp design. Applicability **never grants access**: membership stays labels-only and
RLS is untouched by migration 0015, so a record on an untagged or `classified` page grants
nothing — the record only narrows relevance once matching (8.2.3) consumes it.

## How we know it works

- `backend/app/features/ingestion/tests/test_applicability_schema.py` — 33 unit tests (8.2.1):
  every level validates, all five §D.3 worked examples are expressible, every named failure
  reason has a test asserting its slug.
- `backend/app/features/ingestion/tests/test_applies_to_parsing.py` — 7 unit tests (8.2.2):
  extraction + stripping (the stripped body hashes identically to a body authored without the
  table), content tables untouched, page-order OR of several tables, case/whitespace
  normalization at the parse edge, loud `malformed-table` / `duplicate-field` shapes.
- `backend/app/features/confluence_sync/tests/test_applicability_stamp.py` — 5 database tests
  (8.2.2, fixture page 3011, real sync path): first index stamps the record on page_source and
  every chunk with the table absent from chunk content; a table-only edit restamps with the
  SAME `document_version` id and zero embed calls (CountingEmbedder), then repeats as
  `no_change`; removing the table restamps back to NULL the same way; an invalid table fails
  the job with `unknown-product` in the recorded error while the v1 build survives; a record
  on an untagged or classified page yields zero rows.
- `knowledge-base/tests/test_migration_0015_applicability.py` — the migration round-trip:
  nullable jsonb columns at head, downgrade to 0014 removes them cleanly, re-upgrade restores.
- The eight-rule regression suite (`test_sync_rules_*.py`) stayed green unchanged.

Gaps, honestly: matching semantics (8.2.3) and retrieval filtering (8.3.1) are not built, so
the stamp is stored but not yet consumed; the live leg (a real Confluence page with a table)
is not run; per-section rules do not exist by design — the documented path for mixed pages is
splitting them.
