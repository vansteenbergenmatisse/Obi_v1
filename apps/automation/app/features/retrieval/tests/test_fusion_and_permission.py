"""Pure unit tests for RRF fusion and the permission policy."""

from __future__ import annotations

from app.features.retrieval.domain.fusion import reciprocal_rank_fusion
from app.features.retrieval.domain.permission import PrincipalPermissionPolicy


def test_rrf_rewards_top_ranks_and_agreement() -> None:
    dense = ["a", "b", "c"]
    keyword = ["b", "a", "d"]
    scores = reciprocal_rank_fusion([dense, keyword])
    # "a" and "b" both appear high in both lists; ranked above "c"/"d" that appear in only one
    ranked = sorted(scores, key=lambda x: -scores[x])
    assert set(ranked[:2]) == {"a", "b"}
    assert ranked[-1] in {"c", "d"}


def test_rrf_weights_apply() -> None:
    scores = reciprocal_rank_fusion([["a"], ["b"]], weights=[3.0, 1.0])
    assert scores["a"] > scores["b"]


def test_space_scope_grants_space_and_blocks_others() -> None:
    policy = PrincipalPermissionPolicy(
        space_of={1002: 100, 2002: 200}, restrictions={1002: {"acct-alice"}}
    )
    assert policy.space_id("100") == 100
    assert policy.allowed(1002, "100") is True   # space-level trust ignores restriction
    assert policy.allowed(2002, "100") is False  # different space


def test_principal_scope_blocks_unauthorized() -> None:
    policy = PrincipalPermissionPolicy(
        space_of={1002: 100, 2002: 200},
        restrictions={1002: {"grp-engineering", "acct-alice"}, 2002: {"grp-hr", "acct-carol"}},
    )
    assert policy.allowed(1002, "acct-alice") is True    # listed principal
    assert policy.allowed(2002, "acct-alice") is False   # not in the HR/finance set -> no leak
    assert policy.allowed(1002, "unauthorized-user") is False
