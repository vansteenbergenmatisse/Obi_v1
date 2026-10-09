"""panel mi-filter · substep 8.3.1 — SQL shape + binding discipline for in-DB eligibility.

Mirrors ``test_search_repo_knowledge_scope.py``'s spy-session style: when the caller passes
no eligibility (the default — the internal/eval path), the emitted SQL is byte-for-byte the
pre-8.3.1 shape; when :class:`EligibilityParams` are passed, the applicability predicate
appears inside the one ``WHERE`` clause — before ``ORDER BY``/``LIMIT``, never a shortlist
cleaned up later — and every context value is bound, never interpolated. The derivation
tests pin that ``eligibility_params`` mirrors the matcher's own vocabulary (filled slots by
role, launch pairs from filled slots only, never a derived POS–Accounting pair).
"""

from __future__ import annotations

from typing import Any, cast

from sqlalchemy.orm import Session

from app.features.retrieval.domain.applicability_match import (
    ConnectionRecord,
    CustomerContext,
    eligibility_params,
)
from app.features.retrieval.infrastructure.search_repo import (
    dense_search,
    fetch_rerank_texts,
    keyword_search,
)
from app.platform.config.product_catalog import load_product_catalog

CATALOG = load_product_catalog()


class _SpySession:
    """Records the SQL text and bound params passed to `execute`; returns no rows."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def execute(self, clause: Any, params: dict[str, Any] | None = None) -> list[Any]:
        self.calls.append((str(clause), dict(params or {})))
        return []

    def as_session(self) -> Session:
        return cast(Session, self)


def _elig(context: CustomerContext):
    return eligibility_params(context, CATALOG)


def test_rt2_filter_sql_unchanged_when_no_eligibility() -> None:
    """panel mi-filter · substep 8.3.1
    Without eligibility params (the internal/eval path) the three query builders emit the
    pre-8.3.1 SQL byte-for-byte: no applicability predicate, no eligibility binds."""
    for call in (
        lambda s: keyword_search(s, "q", None, 10),
        lambda s: dense_search(s, [0.1, 0.2], None, 10, dim=2),
        lambda s: fetch_rerank_texts(s, [1, 2], None),
    ):
        spy = _SpySession()
        call(spy.as_session())
        sql, params = spy.calls[0]
        assert "applicability" not in sql
        assert not any(k.startswith("elig_") for k in params)


def test_rt2_filter_dense_predicate_applies_before_the_limit() -> None:
    """panel mi-filter · substep 8.3.1
    With eligibility params the dense search carries the applicability predicate inside the
    WHERE clause, textually before ORDER BY/LIMIT — access AND applicability inside the SQL,
    never an unrestricted shortlist cleaned up later."""
    spy = _SpySession()
    context = CustomerContext(slot_pos="toast", slot_pms="mews", platform="datahub")
    dense_search(spy.as_session(), [0.1, 0.2], None, 10, dim=2, eligibility=_elig(context))
    sql, params = spy.calls[0]
    assert "applicability IS NULL" in sql
    assert sql.index("applicability IS NULL") < sql.index("ORDER BY")
    assert sql.index("applicability IS NULL") < sql.index("LIMIT")
    assert params["elig_products"] == ["toast", "mews"]
    assert params["elig_platform"] == "datahub"
    assert "pos-pms" in params["elig_connections"]  # the one derived launch pair, bound


def test_rt2_filter_keyword_and_rerank_texts_carry_the_same_predicate() -> None:
    """panel mi-filter · substep 8.3.1
    The keyword search and the rerank-text fetch apply the same eligibility predicate as the
    dense search — a page the filter excludes can never be reranked back in."""
    context = CustomerContext(slot_pms="mews")
    for call in (
        lambda s: keyword_search(s, "q", None, 10, eligibility=_elig(context)),
        lambda s: fetch_rerank_texts(s, [1, 2], None, eligibility=_elig(context)),
    ):
        spy = _SpySession()
        call(spy.as_session())
        sql, params = spy.calls[0]
        assert "applicability IS NULL" in sql
        assert params["elig_products"] == ["mews"]


def test_rt2_filter_context_values_bound_never_interpolated() -> None:
    """panel mi-filter · substep 8.3.1
    A hostile slot value never reaches the SQL text — context values are bound parameters
    (same injection discipline as the scope GUCs)."""
    spy = _SpySession()
    hostile = "x'; DROP TABLE chunk; --"
    context = CustomerContext(slot_pos="toast", platform=hostile)
    dense_search(spy.as_session(), [0.1, 0.2], None, 10, dim=2, eligibility=_elig(context))
    sql, params = spy.calls[0]
    assert "DROP TABLE" not in sql
    assert params["elig_platform"] == hostile


def test_rt2_filter_params_mirror_the_matcher_derivation() -> None:
    """panel mi-filter · substep 8.3.1
    eligibility_params mirrors the matcher: filled slots only (role-checked against the
    catalog), launch pairs derived from filled slots only — three filled slots yield the
    POS–PMS and PMS–Accounting pairs, never a direct POS–Accounting pair — and real
    connection records ride along after the derived ones."""
    full = CustomerContext(slot_pos="toast", slot_pms="mews", slot_accounting="quickbooks-online")
    params = eligibility_params(full, CATALOG)
    assert params.products == ("toast", "mews", "quickbooks-online")
    assert [c.connection_type for c in params.connections] == ["pms-accounting", "pos-pms"]
    assert all(c.derived for c in params.connections)

    real = ConnectionRecord(
        connection_type="pos-accounting",
        products=(("accounting", "quickbooks-online"), ("pos", "toast")),
        directions=("pos_to_accounting",),
    )
    with_record = CustomerContext(slot_pos="toast", connections=(real,))
    params2 = eligibility_params(with_record, CATALOG)
    assert params2.products == ("toast",)
    assert params2.connections == (real,)  # no pair derivable from one slot

    # a product sitting in the wrong role slot never counts as filled (matcher parity)
    wrong_role = CustomerContext(slot_pms="toast")
    assert eligibility_params(wrong_role, CATALOG).products == ()
