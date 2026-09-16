# 0.4 design review — design-vs-code delta

Substep 0.4.1. Date: 2026-09-16.

**Ground truth audited (carried over from `0.3-code-vs-design-audit-2026-09-14`):**
- Commit: `bf7fece829e3ce1e9757e1bdb5fa538fbd6456ae`
- git describe: `green-baseline-151-gbf7fece`
- Date of the 0.3 audit: 2026-09-14

This folder does not re-audit the code. It builds one delta table from the 0.3 synopses,
the design brief and the action plan, all as they stand today (2026-09-16). Where the 0.3
synopses are silent on a claim, that gap is flagged in the table, not guessed at.

## Files read to build `delta.md`

- `docs/Final_docs/0.3-code-vs-design-audit-2026-09-14/README.md`
- `docs/Final_docs/0.3-code-vs-design-audit-2026-09-14/alembic-and-scripts.md`
- `docs/Final_docs/0.3-code-vs-design-audit-2026-09-14/confluence_sync.md`
- `docs/Final_docs/0.3-code-vs-design-audit-2026-09-14/entrypoint.md`
- `docs/Final_docs/0.3-code-vs-design-audit-2026-09-14/evaluation.md`
- `docs/Final_docs/0.3-code-vs-design-audit-2026-09-14/ingestion.md`
- `docs/Final_docs/0.3-code-vs-design-audit-2026-09-14/packages-config-infra-docs.md`
- `docs/Final_docs/0.3-code-vs-design-audit-2026-09-14/platform.md`
- `docs/Final_docs/0.3-code-vs-design-audit-2026-09-14/rag_agent.md`
- `docs/Final_docs/0.3-code-vs-design-audit-2026-09-14/retrieval.md`
- `docs/Final_docs/0.3-code-vs-design-audit-2026-09-14/shared.md`
- `docs/Final_docs/0.3-code-vs-design-audit-2026-09-14/tests.md`
- `docs/Final_docs/0.3-code-vs-design-audit-2026-09-14/widget.md`
- `docs/Final_docs/obi-system-brief.md` (read in full, in chunks, per this substep's explicit instruction — today/target text for all 192 panels)
- `docs/plan/decisions.md` (confirmed: holds only the `_pending_` placeholder row; no panel has a real decisions.md entry today)
- `docs/Final_docs/obi-action-plan.html` (grepped, not read whole, for `data-id="p` and `design page:` refs lines, to build the panel→phase map)
- `apps/automation/tools/panel.py --list` (the 192 panel ids and statuses)

## How the phase column in `delta.md` was built

`obi-action-plan.html`'s substep ids carry their phase as a prefix (`p0-…`, `p1-…`, … `p7-…`).
Each substep's `<div class="refs">design page: …</div>` line names the panel ids it closes.
For every panel id, its phase is the **lowest** phase number of any substep that names it — so a
panel referenced in both Phase 0 (a regression item) and a later phase sorts under Phase 0, per
the instruction "Phase 0 regression items first." A panel named by no substep at all sorts last,
under "unscheduled." This produced an exact, cross-checked partition of all 192 ids (verified the
per-prefix panel counts against `panel.py --list`'s 192 total twice).

## Summary (see `delta.md` for the full table and the three lists)

- Rows in `delta.md`: 192 (one per panel id from `panel.py --list`).
- Change column: `none` 56 · `small` 78 · `large` 55 · `blocked` 3.
- "design is wrong here" (drifted or missing verdict): see `delta.md`.
- "code the design does not mention": collected from every synopsis's section 8.
- "needs live": collected from every claim carrying that verdict.
- Audit gaps (no row in any 0.3 synopsis for that specific panel id): `tg-first`, `r5-evidence`,
  `r5-generate`, `r3-deny` (only mentioned in a Known-gaps note, not a Claims-table row),
  `r4-union` (only cross-referenced from `retrieval.md`, no owning-folder row), `em-kb` (only a
  cross-reference in `shared.md`), `ks-validate` (only a cross-reference in `widget.md`). Each
  still gets a full row in `delta.md`, flagged there.
