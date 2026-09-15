---
name: obi-change
description: The procedure for implementing one substep of the Obi action plan. Use whenever a substep id is given. Ends with a ledger entry and a stop.
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---
# /obi-change <substep id>

Without a substep id: reply "Give me a substep id from the action plan" and do nothing — no marker, no files.

1. Read and open the marker
   - grep -n "<substep id>" docs/design/obi-action-plan.html and read that block: Must be true, Proof, refs. If the id is not in the plan, reply "substep <id> is not in the plan", write no marker, and stop.
   - Create the active-substep marker so the implementer's Write/Edit are permitted: `mkdir -p .obi && printf '%s\n' "<substep id>" > .obi/active-substep`. (The guard hook blocks every Write/Edit until this file exists.)
   - For every panel id in refs: `python3 apps/automation/tools/panel.py <id>`. Never open the design page or the brief in full.
   - Read docs/plan/decisions.md and the rows for those panels in docs/plan/delta.md.
2. Test first
   - With /obi-test-writer write the test(s) for every "Must be true" sentence at the levels the substep names.
   - Run them. New behavior: they fail for the stated reason. Regression: they pass.
3. Implement
   - The smallest change that makes the tests pass. Only the folders the placement rules in CLAUDE.md allow for that stage. New symbols exported from the feature root.
   - Touched files clean under `uv run ruff check`, `uv run ruff format`, `uv run pyright`. Untouched files not reformatted.
4. Verify
   - /obi-verify at the levels the substep names. `make check` green (from the repository root). No lint or type count above the baseline.
   - If the change touches an HTTP endpoint, an LLM call or outbound network: run the securing-http-and-llm-endpoints checklist and write the result in the hand-back.
5. Record
   - For each panel closed: `python3 apps/automation/tools/panel.py <id> --status <word> --today "<one sentence>"`.
   - Regenerate the brief: `python3 apps/automation/tools/brief.py`.
   - Update the ingestion or retrieval phase doc for the stage touched.
   - Append one line to docs/plan/ledger.md: `<substep id> · <date> · <commit> · tests: <count> (<names>) · levels: <list> · deviations: <text or none> · defaults built to: <list or none>`.
6. Hand back
   - Files changed, test names, the ledger entry, the verify table.
7. Stop and close the marker
   - Remove the marker: `rm -f .obi/active-substep`.
   - Ask for /compact-ultra. Do not start the next substep.

Never: disable row security; invent connection strings, keys or numbers; edit archived docs; change a target line on the design page; skip a level.
