---
name: obi-audit
description: Audit one folder or one design section of Obi: verify every claim against the code and write a synopsis in the fixed format. Read-only. Used by obi-auditor in Phase 0.
allowed-tools: Read, Grep, Glob, Write, Bash(git log:*), Bash(git blame:*), Bash(python3 apps/automation/tools/panel.py:*)
---
# /obi-audit <folder or panel ids> -> <output path>

Procedure
1. Inventory: Glob the folder; list entry points (routers, job handlers, CLI scripts, schedulers) and the public root exports.
2. Claims: for each panel in the assignment run python3 apps/automation/tools/panel.py <id>; take its today line and every "Where in the code" path (with line numbers) as claims. For a folder with no panel list, use python3 apps/automation/tools/panel.py --grep <folder name> to find them.
3. Evidence: for each claim, Grep and Read to the file:line. Verdict: confirmed (matches), drifted (exists but differs; say exactly how), missing (not found), needs live (only checkable against staging or production).
4. Extras: list every module, function or table in the folder that no panel mentions.
5. Write the synopsis in this template and nothing more:

# <folder or section>
## Purpose (two lines)
## Entry points
| symbol | file:line | called by |
## Reads and writes
| tables, files, queues touched | read or write | file:line |
## External calls
| client | endpoint | timeout, retry, breaker present? | file:line |
## Tests present
| test file | behaviors asserted | panel ids |
## Known gaps
(TODOs, dead code, behaviors with no test; one line each with file:line)
## Claims from the design
| panel | claim | file:line | verdict | note |
## Not on the design page
(one line each with file:line)

Rules: file:line for everything; never edit code; never guess; stay inside the assignment; if two files disagree, record both. Write the synopsis with the Write tool to the output path under docs/Final_docs/ — never a shell redirect (the guard hook blocks redirects and blocks writes outside docs/Final_docs/).
