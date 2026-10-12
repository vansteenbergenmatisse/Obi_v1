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
    # substep 9.5.2 (panel mi-hardfilter): the four directed-connection routing labels a chat is
    # bound to (``obi-general``, ``{source}-general``, ``{target}-general``,
    # ``{source}-to-{target.kind}``). Empty on a context-free/legacy case — the hard label filter
    # is then a no-op, so every pre-9.5.2 dataset loads unchanged.
    session_labels: list[str] = Field(default_factory=list)


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


class RoutingLiftReport(BaseModel):
    """Routing-off vs routing-on comparison for one labelled connection dataset (substep 9.5.2,
    panel mi-hardfilter). This is the rule-11 before/after number that gates the 9.4.1 directed-
    connection hard label filter.

    ``before`` is retrieval with NO session labels — the pre-9.4.1 no-op path, where every
    candidate (wrong-connection pages included) is served. ``after`` is retrieval under the chat's
    four directed-connection labels, where the hard filter narrows the candidate set. ``delta`` is
    ``after - before`` per metric. The three metrics:

    * ``recall`` — fraction of the relevant pages served. It must NOT drop off→on (no gold-set
      loss, never-bend rule 11); the filter removes wrong-connection noise, never the answer.
    * ``served_precision`` — relevant / served count. It RISES off→on as wrong-connection pages
      are removed from the served set.
    * ``served_count`` — mean number of pages served. It FALLS off→on as routing narrows.

    The timestamp is passed in (no clock read), like the other reports.
    """

    model_config = ConfigDict(extra="forbid")

    dataset_name: str
    timestamp: str
    case_count: int
    retrieve_k: int
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
    "RoutingLiftReport",
]
