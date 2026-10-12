"""Unit tests for the routing-lift measurement (substep 9.5.2, panel mi-hardfilter).

Pure and deterministic: hand-crafted off/on rankers stand in for retrieval with the directed-
connection hard label filter off vs on, so the recall / served_precision / served_count math is
verified without a DB or a hosted key.
"""

from __future__ import annotations

from app.features.evaluation.runner import evaluate_routing_lift
from app.features.evaluation.schemas import EvalCase, EvalDataset, RoutingLiftReport

# Off serves every candidate (wrong-connection pages included); on serves only the in-connection
# ones. The one relevant page survives both — recall holds, precision rises, count falls.
_RELEVANT = ["95103"]
_OFF = ["95101", "95102", "95103", "95104", "95105", "95106"]  # all six candidates
_ON = ["95101", "95102", "95103"]  # label-filtered to the in-connection three


def _dataset() -> EvalDataset:
    return EvalDataset(
        name="routing_fixture",
        cases=[
            EvalCase(
                id="cr-01",
                question="q1",
                relevant_chunk_ids=_RELEVANT,
                session_labels=["obi-general", "toast-general", "mews-general", "toast-to-pms"],
            ),
        ],
    )


def test_eval_routing_on_narrows_while_recall_holds() -> None:
    """panel mi-hardfilter · substep 9.5.2
    Routing on keeps recall (no gold-set loss) while served_precision rises, served_count falls."""
    report = evaluate_routing_lift(
        _dataset(),
        off_fn=lambda case: _OFF,
        on_fn=lambda case: _ON,
        now_iso="unit",
    )
    assert isinstance(report, RoutingLiftReport)
    assert report.case_count == 1
    assert report.retrieve_k == 50

    # recall holds: the relevant page survives the label filter.
    assert report.before["recall"] == 1.0
    assert report.after["recall"] == 1.0
    assert report.delta["recall"] == 0.0

    # served_precision rises: 1/6 off -> 1/3 on.
    assert report.before["served_precision"] == 1 / 6
    assert report.after["served_precision"] == 1 / 3
    assert report.delta["served_precision"] > 0.0

    # served_count falls: 6 off -> 3 on.
    assert report.before["served_count"] == 6.0
    assert report.after["served_count"] == 3.0
    assert report.delta["served_count"] == -3.0


def test_eval_routing_no_lift_when_labels_change_nothing() -> None:
    """panel mi-hardfilter · substep 9.5.2
    If the label filter removes nothing (off == on), there is no narrowing — the break-it shape:
    an on path that drops the session labels collapses to this zero-lift case."""
    report = evaluate_routing_lift(
        _dataset(),
        off_fn=lambda case: _OFF,
        on_fn=lambda case: _OFF,
        now_iso="unit",
    )
    assert report.delta["served_precision"] == 0.0
    assert report.delta["served_count"] == 0.0
    assert report.before == report.after


def test_eval_routing_empty_dataset_is_safe() -> None:
    """panel mi-hardfilter · substep 9.5.2
    An empty labelled dataset yields zeros, never a divide-by-zero."""
    report = evaluate_routing_lift(
        EvalDataset(name="empty", cases=[]),
        off_fn=lambda case: _OFF,
        on_fn=lambda case: _ON,
        now_iso="unit",
    )
    assert report.case_count == 0
    assert report.before == {"recall": 0.0, "served_precision": 0.0, "served_count": 0.0}
    assert report.delta == {"recall": 0.0, "served_precision": 0.0, "served_count": 0.0}
