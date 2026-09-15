# evaluation

## Purpose (two lines)
A DB-free, pure-function harness (`apps/automation/app/features/evaluation/`) that scores a ranker's output against hand-labelled JSON datasets and a 6-page Confluence fixture corpus, and writes baseline/rerank-lift reports.
It is Phase 1's honest floor and the seam Phase 3-5 plug real retrieval/answer functions into (`app/features/evaluation/__init__.py:1-11`); no gold set, DB, or live model call exists inside it.

## Entry points
| symbol | file:line | called by |
|---|---|---|
| `evaluate()` | `app/features/evaluation/runner.py:43` | `run_baseline.run()` at `run_baseline.py:84`; `tests/test_runner_baseline.py:21,46,61,70` |
| `evaluate_rerank_lift()` | `app/features/evaluation/runner.py:84` | `tests/test_rerank_lift.py:29,53,66`; also `app/features/confluence_sync/tests/test_retrieval_eval.py:348` (outside this folder) |
| `run()` / `main()` | `app/features/evaluation/run_baseline.py:76`, `run_baseline.py:228` | `make eval` (`Makefile:32`: `python -m app.features.evaluation.run_baseline`) |
| `build_baseline_ranker()` | `app/features/evaluation/run_baseline.py:57` | `run()` at `run_baseline.py:79`; `tests/test_runner_baseline.py:20,69` |
| `load_dataset()` | `app/features/evaluation/run_baseline.py:51` | `run()` at `run_baseline.py:83`; `tests/test_runner_baseline.py:15` |
| `write_rerank_lift_reports()` | `app/features/evaluation/run_baseline.py:119` | `app/features/confluence_sync/tests/test_retrieval_eval.py:365` (outside this folder) — not called anywhere inside this folder's own runtime path |
| `load_corpus_loader()` | `app/features/evaluation/fixtures.py:31` | `build_baseline_ranker()` at `run_baseline.py:63`; `tests/test_fixtures_loader.py:9` |

## Reads and writes
| tables, files, queues touched | read or write | file:line |
|---|---|---|
| `app/features/evaluation/datasets/*.json` (retrieval_smoke, ambiguity, permission, out_of_corpus) | read | `run_baseline.py:33-39,51-54` |
| `apps/automation/tests/fixtures/confluence/` (manifest.json, page-*.json, versions/, labels/, restrictions/, attachments/) | read | `fixtures.py:21-23,31-41` |
| `apps/automation/eval-reports/baseline.json`, `baseline.md` | write | `run_baseline.py:160-178` |
| `apps/automation/eval-reports/rerank_lift.json`, `rerank_lift.md` | write | `run_baseline.py:119-131` |
| `apps/automation/eval-reports/rerank_lift.json` | read | `run_baseline.py:134-145` (`_print_saved_rerank_lift`) |
| No Postgres table — explicitly DB-free | — | `app/features/evaluation/__init__.py:1`; `README.md:3-6` |

## External calls
None. This feature makes no HTTP, LLM, embedding, or reranker call anywhere in its code; `metrics/fallback_metrics.py:3` states this is deliberate ("not an LLM-judge — that would need a live model call this DB-free harness deliberately avoids"). Confirmed by absence of any client import in `runner.py`, `run_baseline.py`, `fixtures.py`, or `metrics/*.py`.

## Tests present
| test file | behaviors asserted | panel ids |
|---|---|---|
| `tests/test_retrieval_metrics.py:16-77` | recall/precision/mrr/ndcg/hit_rate@k math, k=0, empty-relevant, duplicate collapsing | e-stage1 |
| `tests/test_latency_metrics.py:15-67` | percentile interpolation, `summarize_latencies`, `check_targets` pass/fail/boundary, `LatencyTimer` | e-ops |
| `tests/test_runner_baseline.py:18-72` | report structure, perfect-ranker recall=1.0, empty-ranker recall=0.0, timestamp is not a clock | cm-eval, e-stage1 |
| `tests/test_rerank_lift.py:28-76` | positive lift on precision@5/ndcg@10, zero lift when order unchanged, empty dataset safe | e-stage2 |
| `tests/test_fixtures_loader.py:12-88` | fixture dir exists, page ids = {1001,1002,1003,2001,2002,2003}, status coverage, version bodies differ, labels/restrictions/attachments load | e-gold, cm-eval |
| `tests/test_fallback_metrics.py:23-40` | `fallback_rate` mixed/all/none/empty, `citation_grounding_rate` full/partial/none/empty | none (no panel names this metric) |

## Known gaps
- `metrics/latency_metrics.py` is never imported outside itself and its own test — the panel's own words ("unwired") confirmed by `grep`: only `metrics/latency_metrics.py` and `tests/test_latency_metrics.py` reference `LatencyTimer`/`check_targets` (no reference in `runner.py` or `run_baseline.py`).
- `evaluate_rerank_lift`/`write_rerank_lift_reports` are exported at the feature root (`__init__.py:17-18`) but the DB-free `run_baseline.py` entrypoint only *reads back* a previously saved `rerank_lift.json` (`run_baseline.py:134-145`); it never calls `evaluate_rerank_lift` itself — the only caller that produces a fresh report is a DB-backed integration test in another feature (`app/features/confluence_sync/tests/test_retrieval_eval.py:331-365`).
- No gold set exists; `EvalCase` (`schemas.py:17-27`) carries none of the fields the design's gold-set panel requires (identity/scopes, essential facts, forbidden claims, corpus version) — only `id`, `question`, `relevant_chunk_ids`, `expected_answer`, `scope`, `kind`.
- Datasets are tiny: `retrieval_smoke.json` 6 cases, `permission.json` 3, `ambiguity.json` 3, `out_of_corpus.json` 1 (18 total), far short of the 150-250 target in `e-gold`.
- `fallback_metrics.py` functions (`fallback_rate`, `citation_grounding_rate`) are exported at the root and tested here, but no panel in this assignment names them or their wiring point.
- No dev/held-out split exists anywhere: all four datasets are single undivided files with no `dev`/`held_out` naming or field (see `e-split` row below).
- No essential-facts/forbidden-claims grading harness and no judge-model code exist anywhere in `apps/automation` (see `e-stage4`/`e-judge` rows below).

## Claims from the design
| panel | claim | file:line | verdict | note |
|---|---|---|---|---|
| ov-eval | "No gold set exists." | `app/features/evaluation/datasets/` (4 files); `schemas.py:17-27` | confirmed | no gold-set fields or dataset exist anywhere in this folder |
| ov-eval | "make eval runs a 14-document synthetic fixture." | `Makefile:32`; `fixtures.py:21-23`; `tests/test_fixtures_loader.py:18-21` | drifted | `make eval` and the fixture wiring are real, but `list_pages()` returns exactly 6 page ids (`test_fixtures_loader.py:21`); the fixture dir holds 6 current pages + 3 archived versions of page 1001 + 3 attachment files = 12 files, not 14 under any counting found — evidence is ambiguous on what "document" counts |
| cm-eval | "A DB-free baseline runner over synthetic fixtures." | `run_baseline.py:1-18`; `fixtures.py:1-8` | confirmed | matches exactly |
| cm-eval | "Latency helpers exist but are unwired." | `metrics/latency_metrics.py:1-138` | confirmed | only self-referenced and test-referenced, never called from `runner.py` or `run_baseline.py` |
| cm-eval | "No gold set." | (same as ov-eval above) | confirmed | — |
| cm-eval | "`run_baseline.py, runner.py` — make eval" | `run_baseline.py:76-90`; `runner.py:43-81`; `Makefile:32` | confirmed | — |
| cm-eval | "`metrics/` — precision, ndcg, rerank lift, fallback rate, latency helpers" | `metrics/retrieval_metrics.py:44,76`; `metrics/fallback_metrics.py:18,27`; `metrics/latency_metrics.py` | drifted | precision/ndcg/fallback-rate/latency helpers are indeed under `metrics/`, but "rerank lift" (`evaluate_rerank_lift`) is not in `metrics/` at all — it lives in `runner.py:84-134` |
| cm-eval | "`datasets/` — retrieval_smoke, permission, ambiguity, out_of_corpus" | `datasets/retrieval_smoke.json`, `datasets/permission.json`, `datasets/ambiguity.json`, `datasets/out_of_corpus.json` | confirmed | all four files present exactly as named |
| e-gold | "Does not exist. Current datasets: retrieval_smoke, permission, ambiguity, out_of_corpus over a 14-document fixture, a few cases each." | `datasets/*.json` (6, 3, 3, 1 cases respectively) | drifted | dataset names and small case counts confirmed; "14-document fixture" has the same discrepancy noted under ov-eval above |
| e-gold | "`features/evaluation/datasets/` — JSON cases" | `app/features/evaluation/datasets/` | confirmed | — |
| e-gold | "`features/evaluation/schemas.py` — EvalKind: retrieval, answer, ambiguity, permission, latency" | `schemas.py:14` | confirmed | `EvalKind = Literal["retrieval", "answer", "ambiguity", "permission", "latency"]` matches exactly |
| e-stage1 | "`features/evaluation/metrics/` — recall, precision, ndcg helpers exist" | `metrics/retrieval_metrics.py:31,44,76` | confirmed | `recall_at_k`, `precision_at_k`, `ndcg_at_k` all present |
| e-stage1 | "Measures recall at 75 across the fused candidate list; per branch too" | — | missing | no "recall@75" constant, fused-candidate concept, or per-branch metric exists anywhere in this folder; `recall_at_k` takes an arbitrary `k` with no default of 75 (`retrieval_metrics.py:31`) |
| e-stage2 | "`features/evaluation/rerank_lift.py` — evaluate_rerank_lift" | `runner.py:84-134` | drifted | the function exists and is fully implemented and tested, but there is no `rerank_lift.py` file anywhere in this folder — it lives in `runner.py`, not a dedicated module as the design states |
| e-stage2 | "Measures precision at 5, NDCG at 10, and the rerank lift (before versus after)" | `runner.py:91-92,105-134` | confirmed | `evaluate_rerank_lift(..., precision_k=5, ndcg_k=10)` defaults match exactly |
| e-ops | "A bounded in-process run measured p50 5.9 s and p95 7.4 s end to end on six queries, about 0.23 dollars per run." | — | needs live | no code in this folder computes or stores these numbers; `latency_metrics.py` is unwired (see cm-eval row) and no cost-tracking code exists here. `docs/rag/PLAN.md:1232-1233` records this as a live/manual run on the local (non-Supabase-reader) path, outside this folder |
| e-ops | "`features/evaluation/metrics/latency_metrics.py` — helpers, unwired" | `metrics/latency_metrics.py:1-138` | confirmed | matches the "Known gaps" finding above verbatim |
| e-monitor | "Index age... Held-out recall... Groundedness..." (freshness/recall telemetry) | — | missing | panel lists no "Code locations" section at all; repo-wide search for index-age/held-out-recall/freshness-target telemetry found nothing in `apps/automation` — not owned by this folder or any other found |
| sc-backend | "apps/automation: FastAPI, five feature folders (confluence_sync, ingestion, retrieval, rag_agent, evaluation)..." | `apps/automation/app/features/` (dirs: `rag_agent`, `ingestion`, `retrieval`, `evaluation`, `confluence_sync`) | confirmed | `evaluation` is one of exactly five feature directories, matching the panel; the rest of this panel (webhook, search, generation) is owned by other features, not audited here |
| e-split | "Split the cases once, by hand, into two halves... Tune prompts, thresholds and k on dev. Report on held-out. Never tune against it." | — | missing | no dev/held-out split exists anywhere in `apps/automation`: `grep` for `held_out` returns no hits, and all four datasets (`datasets/*.json`) are single undivided files with no dev/held-out field or naming |
| e-stage3 | "Measures whether every required passage is inside the evidence block after parent expansion, dedupe and the budget cut" | `app/platform/config/settings.py:189` (`evidence_token_budget`); `app/features/retrieval/application/retriever.py`, `app/features/retrieval/infrastructure/search_repo.py` (parent expansion) | missing | owned by retrieval (parent expansion) and platform/config (the `evidence_token_budget` setting is defined but not consumed by any feature, per `grep`) — no stage-3 evaluation metric exists in this folder or anywhere else; `schemas.py` has no evidence-block or budget-cut fields |
| e-stage4 | "Measures essential facts present, forbidden claims absent, every claim supported by its citation, refusal when expected... Graded by humans first, then a validated judge model" | `app/features/rag_agent/domain/citations.py`, `app/features/rag_agent/domain/refusal.py` | missing | the underlying citation/refusal mechanism this metric would grade is owned by rag_agent; no essential-facts/forbidden-claims grading harness or judge model exists anywhere — `EvalCase` (`schemas.py:17-27`) has no such fields |
| e-judge | "A different model grades answers at scale, checked against human grades first" | — | missing | no judge-model code exists anywhere in `apps/automation`; every "judge" hit found (`app/features/rag_agent/domain/prompt.py:102-123`, `app/features/rag_agent/domain/clarification.py:112-114`) is the unrelated ambiguity-classifier's plain-English wording, not an LLM-judge tool — not owned by any other folder either |

## Not on the design page
- `metrics/fallback_metrics.py:18,27` (`fallback_rate`, `citation_grounding_rate`, PLAN 9.7 / ADR-0008 decision 7) — exported at the feature root (`__init__.py:16`) and tested (`tests/test_fallback_metrics.py`), but no panel in this assignment's list names them.
- `run_baseline.py:93-157` — Markdown/JSON rendering of the rerank-lift report (`render_rerank_lift_markdown`, `write_rerank_lift_reports`, `_print_saved_rerank_lift`) is implementation detail not mentioned on any panel.
- `README.md:1-85` — a feature-local README documenting "the five eval kinds" and the Phase 3-5 plug-in contract; not referenced by any panel's "Where in the code" line.
