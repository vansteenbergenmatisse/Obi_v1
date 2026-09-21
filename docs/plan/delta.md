# Delta — code versus the design page

The gap between what the repository does today and what the design page targets.
One row per panel. Filled by the Phase-0 audit (`obi-auditor` / `/obi-audit`) reading
each panel with `python3 apps/automation/tools/panel.py <id>` and proving each claim
against `file:line`.

Verdicts: **confirmed** (code matches the today line), **drifted** (exists but differs;
say how), **missing** (not in code), **needs live** (only checkable against staging or
production).

| panel | today line (design) | code file:line | verdict | delta to implement | substep |
|---|---|---|---|---|---|
| i2-labels | scope_state written as `ok`/`conflict`/`classified`/`unlabeled` (design schema defines `CREATE TYPE scope_state AS ENUM(...)`) | no `scope_state` enum, column, or those 4 state values exist anywhere (`grep` clean); state is the tag set on `chunk.tags`/`page_source.tags` + a transient conflict flag from `resolve_knowledge_scope_tags` (`confluence_sync/domain/knowledge_scope.py`) | drifted — enum model unbuilt | decision-needed: build the `scope_state` enum, OR ratify tags-only (amend rule #5 + design page, then ADR-0016) | decision-needed (owner 2026-09-18: "just note it") |
| i2-gone / tg-classified | `classified` label → page deactivated + chunks deleted; losing the last tag → page out of index | deactivation is by Confluence status (trashed/deleted/archived, `_GONE_STATUSES`) + loss of source-scope root coverage (reconciliation purge); `classified` is a forbidden config slug (`platforms.py`), not a delete trigger; a label-only change that empties tags keeps the page active (`test_scope_tagging_retag.py`) | missing — tag-loss/classified rules not implemented | decision-needed: implement, OR amend rule #5 + design page | decision-needed (owner 2026-09-18) |
| (index gate, rule #5) | a page is in the index only if published AND carries a tag from the tag map | no published+tag indexing gate; a page with zero recognized labels is still indexed with empty `tags` (merely invisible to scoped retrieval since `tags && ARRAY[...]` never matches empty) | missing | decision-needed: implement the gate, OR amend rule #5 + design page | decision-needed (owner 2026-09-18) |

> Added 2026-09-18 during the cm-docs ADR work. These three rows are one cohesive code-vs-design
> delta: the design's label→scope_state→classification model (rule #5 + the `scope_state` enum) is
> only partially built (tags + a conflict flag + status-based deactivation). It is why ADR-0015
> (fingerprints) and ADR-0017 (edge-token) are clean retroactive ADRs, ADR-0016 (scope_state as
> tags) carries a divergence caveat, and the 4th ADR (label-gated ingestion) was not written. The
> owner chose to just note it for now (see `docs/plan/decisions.md` `live-0.5.3-cm-docs` and
> `docs/future-ideas.md` cm-docs-adrs).

> Update 2026-09-21 (owner direction, recorded from substep 1.2.2). The owner made
> `knowledge-base/config/knowledge_scopes.json` the single canonical allowlist (entries now carry
> `name` + `label` + `description`) and had the widget generate its list from it (substep 1.2.2,
> done). The owner further directed that this SAME file govern Confluence ingestion eligibility:
> a page is eligible only if it carries ≥1 label matching an entry's `name`; pages with no approved
> label are not ingested; multiple approved labels → ingest once, associate with every matching
> scope; unrelated labels never become scopes; `platforms.json` still gates per-platform access.
> This assigns the three "decision-needed" rows above to **substep 2.2.4 (Label-gated membership,
> unconditional)** — the requirements are recorded verbatim in that substep's block in
> `docs/Final_docs/obi-action-plan.html`. It also supersedes requirement-wise the resolver's
> current "2+ provider labels ⇒ conflict, zero tags" behavior (`resolve_knowledge_scope_tags`),
> which requirement (4) changes to "ingest once, associate with all". Not built in 1.2.2 (widget
> display only); to be built in 2.2.4.
