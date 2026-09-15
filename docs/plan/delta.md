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
| _pending_ | | | | | |
