# Evaluation Harness

Accuracy-first RAG needs measurable evals. This feature is the Phase-1
evaluation harness: pure, database-free functions plus hand-labelled datasets
that score retrieval against the Confluence fixture corpus. It establishes an
honest baseline floor before real retrieval exists, and it is the seam that
Phase 3-5 plug real retrieval and answer functions into.

## The five eval kinds

`EvalKind` (`schemas.py`) is a closed `Literal` of exactly five values — `EvalCase.kind` names the
dimension it exercises:

- **retrieval** — did the right chunks/pages come back in the top k? Scored by
  the metrics below (recall, precision, mrr, ndcg, hit rate).
- **answer** — is the generated answer faithful to the retrieved context and to
  `expected_answer`? (Answer grading plugs in at Phase 5; the schema already
  carries `expected_answer`.)
- **ambiguity** — is the question under-specified enough that the system should
  ask to clarify rather than guess? Driven by the `ambiguity.json` dataset.
- **latency** — do TTFT, retrieval, and end-to-end times meet the targets in
  `metrics/latency_metrics.py`? Checked by `check_targets`.
- **permission** — given a caller's scope, are only pages they may read
  returned? Driven by the `permission.json` dataset and the fixture
  `access_scope` restrictions. This is also where cross-scope leak / restricted-
  content checks live — there is no separate `security` kind.

## Layout

```
evaluation/
  metrics/
    retrieval_metrics.py   recall@k, precision@k, mrr, ndcg@k, hit_rate@k
    latency_metrics.py     percentile, LatencyTimer, summarize, targets, check
  schemas.py               EvalCase, EvalDataset, EvalResult, EvalReport (Pydantic v2)
  datasets/
    retrieval_smoke.json   hand-labelled retrieval cases over the fixtures
    ambiguity.json         under-specified questions
    permission.json        access-scope / status cases
  fixtures.py              locates + loads the Confluence fixture corpus (no DB)
  runner.py                evaluate(dataset, rank_fn, now_iso, k) -> EvalReport
  run_baseline.py          `python -m` entrypoint; writes eval-reports/baseline.{json,md}
  tests/                   unit tests for metrics, latency, loader, runner
```

## Running

From `apps/automation/` with the venv active:

```bash
# establish / refresh the baseline floor
python -m app.features.evaluation.run_baseline
# -> writes apps/automation/eval-reports/baseline.json and baseline.md

# run the tests
pytest app/features/evaluation -q
```

Determinism: `run_baseline` stamps the report timestamp from `EVAL_RUN_TS` if
set, else the literal `"baseline"`. `evaluate` never reads the clock; the
timestamp is always passed in as `now_iso`.

## How Phase 3-5 plug in real retrieval

`evaluate` takes an injected ranker:

```python
def rank_fn(question: str, scope: str | None) -> list[str]: ...
```

The baseline ranker (`build_baseline_ranker`) returns fixture page ids in naive
manifest order, space-scoped, current-status only. It models no relevance, so
its `mrr` and `ndcg` are low by design. That is the floor.

- **Phase 3-4 (retrieval):** replace `rank_fn` with real hybrid/vector
  retrieval returning chunk ids. The datasets, metrics, and report format do not
  change, so every run is directly comparable to the baseline.
- **Phase 5 (answer):** add an answer function graded against
  `EvalCase.expected_answer`; extend the report with answer-quality aggregates.
- **Latency:** wrap retrieval and generation in `LatencyTimer`, feed samples to
  `summarize_latencies`, and gate a release with `check_targets`.

The point of Phase 1 is that these numbers exist and are honest before any of
that lands, so improvement is measurable rather than asserted.
