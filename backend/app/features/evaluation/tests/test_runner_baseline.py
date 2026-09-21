"""Runner structure plus a perfect-ranker sanity check."""

from __future__ import annotations

from pathlib import Path

from app.features.evaluation.run_baseline import build_baseline_ranker, load_dataset
from app.features.evaluation.runner import evaluate
from app.features.evaluation.schemas import EvalCase, EvalDataset, EvalReport

_DATASET_DIR = Path(__file__).resolve().parents[1] / "datasets"


def _smoke_dataset() -> EvalDataset:
    return load_dataset(_DATASET_DIR / "retrieval_smoke.json")


def test_report_structure() -> None:
    dataset = _smoke_dataset()
    ranker = build_baseline_ranker()
    report = evaluate(dataset, ranker, now_iso="test-ts", k=5)

    assert isinstance(report, EvalReport)
    assert report.dataset_name == "retrieval_smoke"
    assert report.timestamp == "test-ts"
    assert report.k == 5
    assert report.case_count == len(dataset.cases)
    assert len(report.results) == len(dataset.cases)
    # every case metric block carries the @k keys
    for result in report.results:
        assert "recall@5" in result.metrics
        assert "mrr" in result.metrics
        assert "ndcg@5" in result.metrics
    assert "recall@5" in report.aggregates


def test_perfect_ranker_scores_recall_one() -> None:
    dataset = _smoke_dataset()

    # stub ranker that returns exactly the relevant ids for each case, ranked first
    relevant_by_question = {c.question: c.relevant_chunk_ids for c in dataset.cases}

    def perfect(question: str, scope: str | None) -> list[str]:
        return list(relevant_by_question[question])

    report = evaluate(dataset, perfect, now_iso="perfect", k=5)
    assert report.aggregates["recall@5"] == 1.0
    assert report.aggregates["mrr"] == 1.0
    assert report.aggregates["hit_rate@5"] == 1.0


def test_empty_ranker_scores_zero() -> None:
    dataset = EvalDataset(
        name="tiny",
        cases=[EvalCase(id="c1", question="q", relevant_chunk_ids=["x"])],
    )

    def empty(question: str, scope: str | None) -> list[str]:
        return []

    report = evaluate(dataset, empty, now_iso="empty", k=5)
    assert report.aggregates["recall@5"] == 0.0
    assert report.aggregates["hit_rate@5"] == 0.0
    assert report.aggregates["mrr"] == 0.0


def test_now_iso_is_not_a_clock() -> None:
    dataset = _smoke_dataset()
    ranker = build_baseline_ranker()
    r1 = evaluate(dataset, ranker, now_iso="fixed", k=5)
    r2 = evaluate(dataset, ranker, now_iso="fixed", k=5)
    assert r1.timestamp == r2.timestamp == "fixed"
