# Baseline — the no-regression floor

`/obi-verify` reads this file to check that quality counts never rise (lint, types) and
that eval metrics never fall (ADR-0003 D1). **First real numbers recorded 2026-10-05**
(roadmap Step 4, substep 4.1 — sync-rules §15.2 golf 0), at commit `a8c3421` + the
uncommitted sync-rules/plan.md pointer edit. Counts may only go down and metrics only up;
the reverse needs an ADR.

## Lint and types (counts must not rise above these)

Measured from `backend/` with `uv run ruff check .`, `uv run ruff format --check .`,
`uv run pyright` (pyright 1.1.411 pinned by uv).

- Ruff errors: **18** (15 × E501 line-too-long, 2 × SIM115, 1 × E741)
- Unformatted files (`ruff format --check`): **1** (`app/features/confluence_sync/tests/test_ingestion_pipeline.py`; 247 already formatted)
- Pyright errors: **43** (plus 1 warning)

## Test suite (the `make check` floor, same run)

- Boundaries: **exit 0**
- Backend: **1033 passed + 1 xfailed** (the xfail is `test_in3_attachment_edit_reembeds_page`, strict, "needs 2.4.1")
- Knowledge-base: **45 passed**

## Eval (metrics must not fall below these)

`make eval` = the bundled gold set (13 cases) scored by the trivial baseline ranker
(fixture manifest order, no relevance) — the honest floor that real retrieval must beat.
Deterministic: the 2026-10-05 run reproduced `backend/eval-reports/` byte-identical to the
committed reports.

Per stage (k=5):

| stage | cases | recall@5 | mrr | hit_rate@5 |
|---|---|---|---|---|
| retrieval_smoke | 6 | 1.000 | 0.750 | 1.000 |
| ambiguity | 3 | 1.000 | 0.667 | 1.000 |
| permission | 3 | 0.667 | 0.250 | 0.667 |
| out_of_corpus | 1 | 0.000 | 0.000 | 0.000 |

Rerank lift (retrieval_smoke, reranker `rerank-v3.5` over the baseline ranker's candidates):

- precision@5: before 0.200 → after 0.200 (Δ +0.000)
- ndcg@10: before 1.000 → after 0.877 (Δ −0.123)

**Metric-name note (honesty):** the original placeholders here (recall@75, P@5, NDCG@10,
refusal rate) are what the design's section-10 gold set will eventually report; today's
runner produces recall@5 / mrr / hit_rate@5 per stage plus the rerank-lift pair above, and
no refusal rate. `/obi-verify` compares like-for-like against the table above. When the
runner grows the design-named metrics, record their first values here in a new section —
never overwrite these floors.

## 4.5 — the before-gate confirmation (2026-10-05)

Roadmap substep 4.5 (sync-rules §15.2 golf 4) re-ran `make eval` after the 4.2/4.3 test-foundation
work landed in the working tree: **every number above is unchanged** (retrieval_smoke 1.000 /
0.750 / 1.000 · ambiguity 1.000 / 0.667 / 1.000 · permission 0.667 / 0.250 / 0.667 ·
out_of_corpus 0.000; rerank lift p@5 0.200→0.200, ndcg@10 1.000→0.877). These numbers are hereby
THE before-gate: every later retrieval-touching change (Steps 5–6 included) must show its
before-and-after against this table (rule 11). Mixed-scope gold questions (a Toast question under
an Opera token etc.) are added when multi-scope lands — in Step 6, scored against this same floor.
