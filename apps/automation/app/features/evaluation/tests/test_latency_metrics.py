"""Percentile correctness and target-check pass/fail."""

from __future__ import annotations

import math

from app.features.evaluation.metrics.latency_metrics import (
    LatencyTimer,
    check_targets,
    percentile,
    summarize_latencies,
)


def test_percentile_interpolation() -> None:
    values = [1.0, 2.0, 3.0, 4.0]
    assert percentile(values, 0) == 1.0
    assert percentile(values, 100) == 4.0
    # p50 of 4 evenly spaced values -> midpoint 2.5
    assert percentile(values, 50) == 2.5
    # single value
    assert percentile([7.0], 95) == 7.0


def test_percentile_p95_known() -> None:
    values = list(range(1, 101))  # 1..100
    # rank = 0.95 * 99 = 94.05 -> interp between values[94]=95 and values[95]=96
    assert math.isclose(percentile(values, 95), 95.05)


def test_summarize_latencies() -> None:
    samples = [0.1, 0.2, 0.3, 0.4, 0.5]
    report = summarize_latencies(samples)
    assert report["count"] == 5.0
    assert report["min"] == 0.1
    assert report["max"] == 0.5
    assert math.isclose(report["mean"], 0.3)
    assert report["p50"] == 0.3


def test_summarize_empty() -> None:
    report = summarize_latencies([])
    assert report["count"] == 0.0
    assert report["p95"] == 0.0


def test_check_targets_pass_and_fail() -> None:
    report = {
        "ttft_p50": 1.0,   # target 1.5 -> pass
        "ttft_p95": 3.0,   # target 2.5 -> fail
        "retrieval_p95": 1.5,  # target 1.5 (boundary) -> pass
    }
    checked = check_targets(report)
    assert checked["ttft_p50"]["passed"] is True
    assert checked["ttft_p95"]["passed"] is False
    assert checked["retrieval_p95"]["passed"] is True
    # end_to_end not in report -> not checked
    assert "end_to_end_p95" not in checked


def test_latency_timer_records_and_appends() -> None:
    samples: list[float] = []
    with LatencyTimer(samples) as timer:
        _ = sum(range(1000))
    assert timer.elapsed >= 0.0
    assert len(samples) == 1
    assert samples[0] == timer.elapsed
