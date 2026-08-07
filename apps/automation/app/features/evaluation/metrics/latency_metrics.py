"""Latency measurement and target-checking utilities.

Pure functions plus a ``LatencyTimer`` context manager. Latency targets for the
RAG pipeline are declared as constants and checked by ``check_targets``.
Durations are handled in seconds throughout.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass, field

# Latency targets (seconds). These are the Phase-1 acceptance thresholds.
TTFT_P50_TARGET_S = 1.5  # time to first token, median
TTFT_P95_TARGET_S = 2.5  # time to first token, tail
END_TO_END_P95_TARGET_S = 10.0  # full answer, tail
RETRIEVAL_P95_TARGET_S = 1.5  # retrieval stage, tail

TARGETS: dict[str, float] = {
    "ttft_p50": TTFT_P50_TARGET_S,
    "ttft_p95": TTFT_P95_TARGET_S,
    "end_to_end_p95": END_TO_END_P95_TARGET_S,
    "retrieval_p95": RETRIEVAL_P95_TARGET_S,
}


def percentile(values: Sequence[float], p: float) -> float:
    """Return the ``p``-th percentile (0-100) of ``values``.

    Uses linear interpolation between the two nearest ranks (the same method as
    ``numpy.percentile`` default). Raises ValueError on empty input or when p is
    outside [0, 100].
    """
    if not values:
        raise ValueError("percentile requires at least one value")
    if not 0.0 <= p <= 100.0:
        raise ValueError("p must be between 0 and 100")
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    rank = (p / 100.0) * (len(ordered) - 1)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    frac = rank - low
    return float(ordered[low] + (ordered[high] - ordered[low]) * frac)


def summarize_latencies(samples: Sequence[float]) -> dict[str, float]:
    """Summarize a list of latency samples (seconds) into a report dict.

    Returns count, min, max, mean, p50, p95, and p99.
    """
    if not samples:
        return {
            "count": 0.0,
            "min": 0.0,
            "max": 0.0,
            "mean": 0.0,
            "p50": 0.0,
            "p95": 0.0,
            "p99": 0.0,
        }
    return {
        "count": float(len(samples)),
        "min": float(min(samples)),
        "max": float(max(samples)),
        "mean": sum(samples) / len(samples),
        "p50": percentile(samples, 50),
        "p95": percentile(samples, 95),
        "p99": percentile(samples, 99),
    }


def check_targets(
    report: dict[str, float],
    targets: dict[str, float] | None = None,
) -> dict[str, dict[str, float | bool]]:
    """Check a metrics report against latency targets.

    ``report`` maps a target name (e.g. ``"ttft_p95"``) to a measured value in
    seconds. Only names present in both ``report`` and ``targets`` are checked.
    Returns, per target name, a dict with ``measured``, ``target``, and
    ``passed`` (measured <= target).
    """
    targets = targets if targets is not None else TARGETS
    result: dict[str, dict[str, float | bool]] = {}
    for name, target in targets.items():
        if name not in report:
            continue
        measured = report[name]
        result[name] = {
            "measured": float(measured),
            "target": float(target),
            "passed": bool(measured <= target),
        }
    return result


@dataclass
class LatencyTimer:
    """Context manager that records elapsed wall-clock seconds.

    Optionally appends the elapsed duration to a shared ``samples`` list so a
    loop can collect many measurements:

        samples: list[float] = []
        for case in cases:
            with LatencyTimer(samples):
                run(case)
        report = summarize_latencies(samples)
    """

    samples: list[float] | None = None
    elapsed: float = field(default=0.0, init=False)
    _start: float = field(default=0.0, init=False)

    def __enter__(self) -> LatencyTimer:
        self._start = time.perf_counter()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.elapsed = time.perf_counter() - self._start
        if self.samples is not None:
            self.samples.append(self.elapsed)


__all__ = [
    "TTFT_P50_TARGET_S",
    "TTFT_P95_TARGET_S",
    "END_TO_END_P95_TARGET_S",
    "RETRIEVAL_P95_TARGET_S",
    "TARGETS",
    "percentile",
    "summarize_latencies",
    "check_targets",
    "LatencyTimer",
]
