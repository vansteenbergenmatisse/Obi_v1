"""Pydantic v2 schemas for the evaluation harness.

These describe eval cases, datasets, per-case results, and the aggregate report.
No clock is called inside these models: the report timestamp is passed in as an
ISO string so runs stay deterministic and reproducible.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

EvalKind = Literal["retrieval", "answer", "ambiguity", "permission", "latency"]


class EvalCase(BaseModel):
    """A single labelled evaluation case."""

    model_config = ConfigDict(extra="forbid")

    id: str
    question: str
    relevant_chunk_ids: list[str] = Field(default_factory=list)
    expected_answer: str | None = None
    scope: str | None = None
    kind: EvalKind = "retrieval"


class EvalDataset(BaseModel):
    """A named collection of eval cases."""

    model_config = ConfigDict(extra="forbid")

    name: str
    cases: list[EvalCase] = Field(default_factory=list)


class EvalResult(BaseModel):
    """Per-case outcome: the ranked ids returned and the metrics computed."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    kind: EvalKind
    ranked_ids: list[str] = Field(default_factory=list)
    relevant_ids: list[str] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)


class EvalReport(BaseModel):
    """Aggregate report for a dataset run.

    ``timestamp`` is supplied by the caller as an ISO string (or any deterministic
    marker such as ``"baseline"``); the model never reads the clock itself.
    """

    model_config = ConfigDict(extra="forbid")

    dataset_name: str
    timestamp: str
    k: int
    case_count: int
    aggregates: dict[str, float] = Field(default_factory=dict)
    results: list[EvalResult] = Field(default_factory=list)


class RerankLiftReport(BaseModel):
    """Before-vs-after rerank comparison for one dataset (PLAN 3.5.5).

    ``before`` is the fused, permission-filtered ranking *without* the cross-encoder
    (equivalently, the order-preserving ``FakeReranker``); ``after`` applies the real
    reranker. ``delta`` is ``after - before`` per metric. Keys are the two accuracy
    metrics the plan calls out: ``precision@{precision_k}`` and ``ndcg@{ndcg_k}``.
    The timestamp is passed in (no clock read), like the other reports.
    """

    model_config = ConfigDict(extra="forbid")

    dataset_name: str
    timestamp: str
    case_count: int
    precision_k: int
    ndcg_k: int
    reranker_model: str
    before: dict[str, float] = Field(default_factory=dict)
    after: dict[str, float] = Field(default_factory=dict)
    delta: dict[str, float] = Field(default_factory=dict)


__all__ = [
    "EvalKind",
    "EvalCase",
    "EvalDataset",
    "EvalResult",
    "EvalReport",
    "RerankLiftReport",
]
