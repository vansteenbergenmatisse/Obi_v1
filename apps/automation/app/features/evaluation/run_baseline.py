"""Baseline evaluation entrypoint.

Run with:

    python -m app.features.evaluation.run_baseline

Loads the bundled datasets and scores them with a trivial baseline ranker, then
writes JSON and Markdown reports to ``apps/automation/eval-reports/`` and prints
a summary. This establishes the honest starting floor before real retrieval
(Phase 3-4) exists.

The baseline ranker returns the fixture page ids in a fixed, naive order
(manifest order), scoped by space when a numeric space id is given as the case
scope. It has no notion of relevance: the report exists to be beaten.

Determinism: the report timestamp is read from ``EVAL_RUN_TS`` if set, else the
literal ``"baseline"``. No clock is read.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from app.features.evaluation.fixtures import load_corpus_loader
from app.features.evaluation.runner import RankFn, evaluate
from app.features.evaluation.schemas import EvalDataset, EvalReport, RerankLiftReport
from app.platform.logging import get_logger

logger = get_logger(__name__)

_DATASET_DIR = Path(__file__).resolve().parent / "datasets"
_DATASET_FILES = ["retrieval_smoke.json", "ambiguity.json", "permission.json"]
_K = 5


def _reports_dir() -> Path:
    # app/features/evaluation/run_baseline.py -> parents[3] == apps/automation
    return Path(__file__).resolve().parents[3] / "eval-reports"


_RERANK_LIFT_JSON = "rerank_lift.json"


def load_dataset(path: Path) -> EvalDataset:
    """Load and validate an EvalDataset from a JSON file."""
    with path.open(encoding="utf-8") as handle:
        return EvalDataset.model_validate(json.load(handle))


def build_baseline_ranker() -> RankFn:
    """Build the trivial baseline ranker from the fixture corpus.

    Returns fixture page ids in manifest order, filtered to the scope's space
    when the scope is a numeric space id, excluding archived/trashed pages.
    """
    loader = load_corpus_loader()
    pages = loader.list_pages()
    ingestible = [p for p in pages if p["currentStatus"] == "current"]

    def rank_fn(question: str, scope: str | None) -> list[str]:
        candidates = ingestible
        if scope is not None and scope.isdigit():
            candidates = [p for p in ingestible if p["spaceId"] == scope]
        return [p["id"] for p in candidates]

    return rank_fn


def run() -> list[EvalReport]:
    """Run the baseline over all datasets and write reports. Returns the reports."""
    now_iso = os.environ.get("EVAL_RUN_TS", "baseline")
    rank_fn = build_baseline_ranker()

    reports: list[EvalReport] = []
    for file_name in _DATASET_FILES:
        dataset = load_dataset(_DATASET_DIR / file_name)
        report = evaluate(dataset, rank_fn, now_iso=now_iso, k=_K)
        reports.append(report)

    _write_reports(reports, now_iso)
    _print_summary(reports)
    _print_saved_rerank_lift()
    return reports


def render_rerank_lift_markdown(report: RerankLiftReport) -> str:
    """Render a before/after rerank-lift table (PLAN 3.5.5), comparable to the baseline format."""
    p_key = f"precision@{report.precision_k}"
    n_key = f"ndcg@{report.ndcg_k}"
    lines: list[str] = []
    lines.append("# Rerank Lift Report")
    lines.append("")
    lines.append(f"- Timestamp: `{report.timestamp}`")
    lines.append(f"- Dataset: `{report.dataset_name}` ({report.case_count} cases)")
    lines.append(f"- Reranker: `{report.reranker_model}`")
    lines.append(
        "- Before = fused + permission-filtered ranking (no cross-encoder); "
        "After = with the cross-encoder rerank."
    )
    lines.append("")
    lines.append("| Metric | Before | After | Δ |")
    lines.append("| --- | --- | --- | --- |")
    for key in (p_key, n_key):
        lines.append(
            f"| {key} | {report.before.get(key, 0.0):.4f} | "
            f"{report.after.get(key, 0.0):.4f} | {report.delta.get(key, 0.0):+.4f} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_rerank_lift_reports(report: RerankLiftReport) -> Path:
    """Persist the rerank-lift report as JSON + Markdown next to the baseline reports."""
    out_dir = _reports_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / _RERANK_LIFT_JSON
    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(report.model_dump(), handle, indent=2, sort_keys=True)
        handle.write("\n")
    md_path = out_dir / "rerank_lift.md"
    with md_path.open("w", encoding="utf-8") as handle:
        handle.write(render_rerank_lift_markdown(report))
    logger.info("rerank_lift_report_written", json=str(json_path), markdown=str(md_path))
    return json_path


def _print_saved_rerank_lift() -> None:
    """Echo the last measured rerank lift (PLAN 3.5.5) if a run has produced one.

    The numbers come from the DB-backed integration measurement (a live reranker key
    yields a real lift; CI's FakeReranker yields zero). This DB-free baseline entrypoint
    only surfaces what was saved, so `make eval` shows the before/after table.
    """
    json_path = _reports_dir() / _RERANK_LIFT_JSON
    if not json_path.exists():
        return
    with json_path.open(encoding="utf-8") as handle:
        report = RerankLiftReport.model_validate(json.load(handle))
    p_key = f"precision@{report.precision_k}"
    n_key = f"ndcg@{report.ndcg_k}"
    print()
    print(f"Rerank lift ({report.dataset_name}, reranker={report.reranker_model})")
    print("=" * 40)
    for key in (p_key, n_key):
        print(
            f"{key:<14} before={report.before.get(key, 0.0):.3f} "
            f"after={report.after.get(key, 0.0):.3f} "
            f"Δ={report.delta.get(key, 0.0):+.3f}"
        )
    print("=" * 40)


def _write_reports(reports: list[EvalReport], now_iso: str) -> None:
    out_dir = _reports_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "timestamp": now_iso,
        "k": _K,
        "reports": [r.model_dump() for r in reports],
    }
    json_path = out_dir / "baseline.json"
    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")

    md_path = out_dir / "baseline.md"
    with md_path.open("w", encoding="utf-8") as handle:
        handle.write(_render_markdown(reports, now_iso))

    logger.info(
        "baseline_reports_written", json=str(json_path), markdown=str(md_path)
    )


def _render_markdown(reports: list[EvalReport], now_iso: str) -> str:
    lines: list[str] = []
    lines.append("# Baseline Evaluation Report")
    lines.append("")
    lines.append(f"- Timestamp: `{now_iso}`")
    lines.append(f"- Cutoff k: {_K}")
    lines.append(
        "- Ranker: trivial baseline (manifest order, space-scoped, "
        "current-status only). No relevance modelling; this is the floor to beat."
    )
    lines.append("")
    for report in reports:
        lines.append(f"## Dataset: `{report.dataset_name}` ({report.case_count} cases)")
        lines.append("")
        lines.append("| Metric | Mean |")
        lines.append("| --- | --- |")
        for name in sorted(report.aggregates):
            lines.append(f"| {name} | {report.aggregates[name]:.4f} |")
        lines.append("")
        lines.append("| Case | Kind | recall@k | mrr | ranked (top 5) |")
        lines.append("| --- | --- | --- | --- | --- |")
        for result in report.results:
            recall = result.metrics.get(f"recall@{report.k}", 0.0)
            rr = result.metrics.get("mrr", 0.0)
            top = ", ".join(result.ranked_ids[:5]) or "(none)"
            lines.append(
                f"| {result.case_id} | {result.kind} | {recall:.3f} | "
                f"{rr:.3f} | {top} |"
            )
        lines.append("")
    return "\n".join(lines)


def _print_summary(reports: list[EvalReport]) -> None:
    print("Baseline evaluation summary")
    print("=" * 40)
    for report in reports:
        recall_key = f"recall@{report.k}"
        hit_key = f"hit_rate@{report.k}"
        recall = report.aggregates.get(recall_key, 0.0)
        mrr_val = report.aggregates.get("mrr", 0.0)
        hit = report.aggregates.get(hit_key, 0.0)
        print(
            f"{report.dataset_name:<18} cases={report.case_count:<3} "
            f"{recall_key}={recall:.3f} mrr={mrr_val:.3f} {hit_key}={hit:.3f}"
        )
    print("=" * 40)
    print(f"Reports written to {_reports_dir()}")


def main() -> int:
    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
