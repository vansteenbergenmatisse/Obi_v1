"""Pure unit tests for RRF fusion and the permission policy."""

from __future__ import annotations

from app.features.retrieval.domain.fusion import reciprocal_rank_fusion
from app.features.retrieval.domain.permission import PrincipalPermissionPolicy, classify_scope


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


def test_classify_scope_splits_digit_strings_from_principal_ids() -> None:
    assert classify_scope("100") == (100, None)
    assert classify_scope("acct-alice") == (None, "acct-alice")
    assert classify_scope(None) == (None, None)


def test_space_scope_grants_space_and_blocks_others() -> None:
    policy = PrincipalPermissionPolicy(
        space_of={1002: 100, 2002: 200}, restrictions={1002: {"acct-alice"}}
    )
    assert policy.allowed(1002, space_id=100, principal=None) is True  # space trust ignores ACL
    assert policy.allowed(2002, space_id=100, principal=None) is False  # different space


def test_principal_scope_blocks_unauthorized() -> None:
    policy = PrincipalPermissionPolicy(
        space_of={1002: 100, 2002: 200},
        restrictions={1002: {"grp-engineering", "acct-alice"}, 2002: {"grp-hr", "acct-carol"}},
    )
    assert policy.allowed(1002, space_id=None, principal="acct-alice") is True  # listed
    assert policy.allowed(2002, space_id=None, principal="acct-alice") is False  # no leak
    assert policy.allowed(1002, space_id=None, principal="unauthorized-user") is False


def test_numeric_principal_argument_is_never_reinterpreted_as_space_trust() -> None:
    """PLAN 4.6.6: allowed() must never re-derive space-vs-principal trust from string shape.

    Passing an all-digit value as ``principal=`` (bypassing ``classify_scope`` at the boundary,
    e.g. a future direct caller that forgets to classify first) must be checked as an ordinary
    principal id, never silently promoted to space-level trust — the exact bug class the 5.3
    HTTP-layer fix (``ChatRequestBody.principal`` validator) only closed for one caller.
    """
    policy = PrincipalPermissionPolicy(space_of={2002: 200}, restrictions={2002: {"acct-alice"}})
    assert policy.allowed(2002, space_id=None, principal="200") is False


def test_r3_acl_principalless_reader_default_denies_restricted_pages() -> None:
    """panel r3-acl · gap CIP-5 (v1 defense-in-depth invariant).

    Page-level principal ACL is enforced only in this app-layer policy today — 0009 gives
    ``page_restriction`` a coarse ``USING(true)`` reader policy, so there is no DB/RLS backstop
    behind this method (a known, disclosed defense-in-depth gap; safe in v1 only because
    ``build_auth_context`` sets ``principal=None`` for every embedded user). This test PINS the
    load-bearing invariant so it can never be silently bypassed before a real per-principal ACL
    (and its DB backstop) is enabled: with a restriction set present, a principal-less reader
    (``principal=None``) sees an unrestricted page and is DENIED a restricted one.
    """
    policy = PrincipalPermissionPolicy(
        space_of={1002: 100, 2002: 100},
        restrictions={2002: {"acct-alice"}},  # 2002 restricted; 1002 unrestricted
    )
    # unrestricted page: a principal-less reader may see it
    assert policy.allowed(1002, space_id=None, principal=None) is True
    # restricted page: a principal-less reader is default-denied (no identity -> unrestricted only)
    assert policy.allowed(2002, space_id=None, principal=None) is False
