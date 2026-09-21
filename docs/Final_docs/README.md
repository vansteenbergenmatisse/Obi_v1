# Final docs

The authoritative design material for Obi and the audits taken against it. One line per item.

| item | what it holds | written by |
|---|---|---|
| `obi-rag-system-flow.html` | the design page *Obi, part by part* — every stage as a click panel with a today line, a target and tests. The source of truth. | design (owner) |
| `obi-action-plan.html` | the action plan — the only work list, one substep at a time. | design (owner) |
| `obi-system-brief.md` | the markdown brief generated from the design page by `tools/brief.py`. | `tools/brief.py` |
| `obi-embedding-implementation-prompt.md` | the embedding-work implementation prompt. | design (owner) |
| `agent-research/` | scratch research notes. Ad hoc and expected to be sparse or empty; see its own README. | ad hoc |
| `0.3-code-vs-design-audit-2026-09-14/` | the single, consolidated 0.3 home (merged 2026-09-18): one synopsis per code folder auditing the code against the design page at a pinned commit (substep 0.3.1), **plus** the test-suite inventory and infrastructure inventory (substep 0.3.2/0.3.3, `test-suite-inventory.md` / `infrastructure-inventory.md`). Frozen snapshot. See its own README. | substep 0.3.1–0.3.3 (obi-auditor runs) |
| `0.3-synopsis-2026-09-16/` | **Merged 2026-09-18 into `0.3-code-vs-design-audit-2026-09-14/`.** Retained only as redirect stubs (`README.md`, `test-suite-inventory.md`) so append-only ledger and frozen 0.4-review references still resolve. | redirect stub |

Naming convention for anything added here: no filename carries a bare relative word like
"today" or "latest" — date it (`YYYY-MM-DD`) the day it's written, since these are frozen
snapshots read long after that date. No duplicate basenames across sibling folders (two
different `tests.md` files is confusing when referenced without the full path) — prefer a name
that says what the file actually contains. Never keep a browser-download suffix like
`(1)`/`(3)` on a canonical file.
