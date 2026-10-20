# Final docs

The authoritative design material for Obi and the audits taken against it. One line per item.

| item | what it holds | written by |
|---|---|---|
| `obi-rag-system-flow.html` | the design page *Obi, part by part* — every stage as a click panel with a today line, a target and tests. The source of truth. | design (owner) |
| `obi-action-plan.html` | the action plan — the only work list, one substep at a time. | design (owner) |
| `obi-system-brief.md` | the markdown brief generated from the design page by `tools/brief.py`. | `tools/brief.py` |
| `1-how-partners-integrate-with-obi/how-partners-integrate-with-obi.md` | the partner-facing guide: how Base and Data Hub embed Obi, the token they mint (`source_system`, `target_system`, `business_id`), and what they send back. | maintainers |
| `ledger.md` | the append-only record of finished substeps (commit, test count, deviations). | each substep |
| `progress-log.md` | the ledger's plain-English companion, one entry per finished substep. | each substep |
| `brief/` | operator runbooks: add a system, add a partner platform, run the embed test on localhost. | maintainers |
| `handover/` | label and partner documents: tagging guide, label administration, partner onboarding. | maintainers |
| `ingestion/`, `retrieval/` | one doc per component: what it does, why, how we know it works. | each substep |
| `0.5-regression-tests/` | the regression phase: harness, coverage map, CI gate proof, release audit, owner decisions. | substep 0.5 |
| `4-test-foundation/`, `phase-4-embed-security/` | test-foundation and embed-security evidence. | phase 4 |
| `5-integration-context/` | the integration-context catalog, contract, partner facts and phase-9 directed-connection evidence. | phase 5–9 |
| `sync-rules/` | the sync-rules plan, manual tests, routing test labels, widget hide notes. | sync-rules work |
| `agent-research/` | scratch research notes. Ad hoc and expected to be sparse or empty; see its own README. | ad hoc |

Naming convention for anything added here: no filename carries a bare relative word like
"today" or "latest" — date it (`YYYY-MM-DD`) the day it's written, since these are frozen
snapshots read long after that date. No duplicate basenames across sibling folders (two
different `tests.md` files is confusing when referenced without the full path) — prefer a name
that says what the file actually contains. Never keep a browser-download suffix like
`(1)`/`(3)` on a canonical file.
