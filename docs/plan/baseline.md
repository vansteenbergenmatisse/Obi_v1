# Baseline — the no-regression floor

`/obi-verify` reads this file to check that quality counts never rise (lint, types) and
that eval metrics never fall. **No baseline yet:** while this file has no numbers,
`/obi-verify` reports those levels as PASS with the note "no baseline yet" rather than
failing (ADR-0003 D1 sets the floor once numbers exist).

## Lint and types (counts must not rise above these)

- Ruff errors: _no baseline yet_
- Unformatted files (`ruff format --check`): _no baseline yet_
- Pyright errors: _no baseline yet_

## Eval (metrics must not fall below these)

- recall@75: _no baseline yet_
- P@5: _no baseline yet_
- NDCG@10: _no baseline yet_
- refusal rate: _no baseline yet_

Record the first real numbers here the moment the gold set (design section 10) exists, and
bump them only downward for counts / upward for metrics, never the reverse, without an ADR.
