"""Confluence gateway restriction parsing — PLAN 4.6.1's fail-closed fix + 4.6.2's expansion.

Covers the CRITICAL finding (4.6.1): a page restricted only by Confluence group(s), with no
individually-restricted user, must not sync as unrestricted. And the real fix (4.6.2): group
membership resolves to real account ids via a per-client-instance cache, falling back to the
same fail-closed sentinel when a group can't be expanded (no resolver, or the resolver finds no
members). Both `HttpConfluenceClient` (live REST v2 restrictions + v1 group-membership) and
`FixtureConfluenceGateway` (offline/test double) share the same pure resolver, so both are
exercised here against the exact restriction-record shape each speaks.
"""

from __future__ import annotations

import httpx
import pytest
import structlog.testing

from app.platform.clients.confluence_client import (
    GROUP_RESTRICTED_SENTINEL,
    ConfluenceCircuitBreakerOpenError,
    HttpConfluenceClient,
    _resolve_read_restriction,
)
from app.platform.clients.fixture_confluence_client import FixtureConfluenceGateway
from app.platform.config import Settings


def _settings(*, breaker_threshold: int = 5) -> Settings:
    return Settings(
        confluence_base_url="https://example.atlassian.net/wiki",
        confluence_email="svc@example.com",
        confluence_api_token="tok",
        confluence_breaker_threshold=breaker_threshold,
    )


# -- pure resolver -----------------------------------------------------------------------


def test_group_only_restriction_resolves_to_fail_closed_sentinel() -> None:
    restrictions = {"group": {"results": [{"id": "grp-finance", "name": "finance"}]}}
    assert _resolve_read_restriction(restrictions) == [GROUP_RESTRICTED_SENTINEL]


def test_user_and_group_restriction_without_resolver_keeps_only_resolved_users() -> None:
    # No `resolve_group` given (the pre-4.6.2 default): a resolvable user alongside groups keeps
    # only the user — matches every caller before a member-lookup existed.
    restrictions = {
        "user": {"results": [{"accountId": "acct-carol"}]},
        "group": {"results": [{"id": "grp-hr"}, {"id": "grp-finance"}]},
    }
    assert _resolve_read_restriction(restrictions) == ["acct-carol"]


def test_user_only_restriction_is_unaffected() -> None:
    restrictions = {"user": {"results": [{"accountId": "acct-alice"}]}}
    assert _resolve_read_restriction(restrictions) == ["acct-alice"]


def test_no_restriction_entries_resolves_to_unrestricted() -> None:
    assert _resolve_read_restriction({}) == []


def test_group_restriction_expands_via_resolver() -> None:
    # PLAN 4.6.2: with a resolver, group members are unioned into the principal list.
    restrictions = {"group": {"results": [{"id": "grp-finance"}]}}
    resolved = _resolve_read_restriction(restrictions, resolve_group=lambda g: ["acct-erin"])
    assert resolved == ["acct-erin"]


def test_group_and_user_restriction_expands_and_unions_via_resolver() -> None:
    restrictions = {
        "user": {"results": [{"accountId": "acct-carol"}]},
        "group": {"results": [{"id": "grp-hr"}, {"id": "grp-finance"}]},
    }
    members = {"grp-hr": ["acct-dave"], "grp-finance": ["acct-erin", "acct-dave"]}
    resolved = _resolve_read_restriction(restrictions, resolve_group=lambda g: members[g["id"]])
    # union, no duplicate acct-dave (both groups carry it), original order preserved.
    assert resolved == ["acct-carol", "acct-dave", "acct-erin"]


def test_group_restriction_resolver_finding_no_members_still_fails_closed() -> None:
    # A resolver that runs (unlike the no-resolver default) but finds nobody — e.g. the live
    # lookup failed, or the group is genuinely empty — must not collapse to open access.
    restrictions = {"group": {"results": [{"id": "grp-finance"}]}}
    resolved = _resolve_read_restriction(restrictions, resolve_group=lambda g: [])
    assert resolved == [GROUP_RESTRICTED_SENTINEL]


# -- HttpConfluenceClient (live REST v2 shape) -------------------------------------------


def test_http_client_group_only_restriction_fails_closed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "operation": "read",
                        "restrictions": {
                            "group": {"results": [{"id": "grp-finance", "name": "finance"}]}
                        },
                    }
                ]
            },
        )

    client = HttpConfluenceClient(
        _settings(), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    assert client.get_restrictions(9001) == [GROUP_RESTRICTED_SENTINEL]


def test_http_client_user_restriction_unaffected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "operation": "read",
                        "restrictions": {"user": {"results": [{"accountId": "acct-alice"}]}},
                    }
                ]
            },
        )

    client = HttpConfluenceClient(
        _settings(), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    assert client.get_restrictions(9001) == ["acct-alice"]


def test_http_client_no_restrictions_returns_empty() -> None:
    client = HttpConfluenceClient(
        _settings(),
        client=httpx.Client(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"results": []}))
        ),
    )
    assert client.get_restrictions(9001) == []


def _restrictions_response(*, page_id: int, group_id: str) -> dict:
    return {
        "results": [
            {
                "operation": "read",
                "restrictions": {"group": {"results": [{"id": group_id, "name": group_id}]}},
            }
        ]
    }


def test_http_client_group_restriction_expands_via_group_member_lookup() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/restrictions"):
            return httpx.Response(
                200, json=_restrictions_response(page_id=9001, group_id="grp-finance")
            )
        assert request.url.path == "/wiki/rest/api/group/by-id/grp-finance/member"
        return httpx.Response(200, json={"results": [{"accountId": "acct-erin"}], "_links": {}})

    client = HttpConfluenceClient(
        _settings(), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    assert client.get_restrictions(9001) == ["acct-erin"]


def test_http_client_group_member_lookup_is_cached_across_pages() -> None:
    calls = {"restrictions": 0, "members": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/restrictions"):
            calls["restrictions"] += 1
            return httpx.Response(
                200, json=_restrictions_response(page_id=9001, group_id="grp-finance")
            )
        calls["members"] += 1
        return httpx.Response(200, json={"results": [{"accountId": "acct-erin"}], "_links": {}})

    client = HttpConfluenceClient(
        _settings(), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    assert client.get_restrictions(9001) == ["acct-erin"]
    assert client.get_restrictions(9002) == ["acct-erin"]  # a second page, same group
    assert calls["restrictions"] == 2
    assert calls["members"] == 1  # not re-fetched for the second page


def test_http_client_group_member_lookup_failure_stays_fail_closed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/restrictions"):
            return httpx.Response(
                200, json=_restrictions_response(page_id=9001, group_id="grp-finance")
            )
        return httpx.Response(403, json={"message": "forbidden"})

    client = HttpConfluenceClient(
        _settings(), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    # the member lookup failed (403, no scope) — must not collapse to open access.
    assert client.get_restrictions(9001) == [GROUP_RESTRICTED_SENTINEL]


# -- HttpConfluenceClient retry/breaker/logging (PLAN 4.6.7) -----------------------------


def test_http_client_retries_on_5xx_then_succeeds() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 2:
            return httpx.Response(503)
        return httpx.Response(200, json={"results": []})

    client = HttpConfluenceClient(
        _settings(), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    assert client.get_restrictions(9001) == []
    assert calls["n"] == 2  # first 503 was retried, not surfaced as a failure


def test_http_client_4xx_is_not_retried() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(404)

    client = HttpConfluenceClient(
        _settings(), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    assert client.get_page_meta(9001) is None
    assert calls["n"] == 1  # a 404 is a normal response, never retried


def test_http_client_breaker_trips_after_consecutive_failures() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503)

    client = HttpConfluenceClient(
        _settings(breaker_threshold=2), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(httpx.HTTPStatusError):
        client.get_labels(9001)  # 1st whole-request failure (after 3 internal retry attempts)
    with pytest.raises(httpx.HTTPStatusError):
        client.get_labels(9001)  # 2nd whole-request failure -> trips the breaker
    calls_before_open = calls["n"]
    with pytest.raises(ConfluenceCircuitBreakerOpenError):
        client.get_labels(9001)  # breaker open -> rejected before any HTTP call
    assert calls["n"] == calls_before_open  # no new request was attempted


def test_http_client_success_resets_the_breaker() -> None:
    # fail (3 raw attempts), succeed, fail again (3 raw attempts), succeed again. With
    # breaker_threshold=2, the second failure must NOT trip the breaker -- proving a success
    # resets the consecutive-failure counter rather than the two failures accumulating across it.
    statuses = iter([503, 503, 503, 200, 503, 503, 503, 200])

    def handler(request: httpx.Request) -> httpx.Response:
        status = next(statuses)
        return httpx.Response(status, json={"results": []} if status == 200 else None)

    client = HttpConfluenceClient(
        _settings(breaker_threshold=2),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(httpx.HTTPStatusError):
        client.get_labels(9001)  # 1st consecutive failure
    assert client.get_labels(9002) == []  # succeeds -> resets the counter to 0
    with pytest.raises(httpx.HTTPStatusError):
        client.get_labels(9003)  # a fresh single failure, not the 2nd of an accumulated streak
    assert client.get_labels(9004) == []  # breaker is not open -> a real request still goes out


def test_http_client_logs_retry_and_status_lines() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    client = HttpConfluenceClient(
        _settings(breaker_threshold=100),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    with structlog.testing.capture_logs() as logs, pytest.raises(httpx.HTTPStatusError):
        client.get_labels(9001)

    events = [entry["event"] for entry in logs]
    assert "confluence_client_5xx" in events
    assert "confluence_client_retry" in events


# -- FixtureConfluenceGateway (offline/test double shape) --------------------------------


class _StubLoader:
    """Minimal stand-in for `tests.fixtures.confluence.loader`, restrictions + group members."""

    def __init__(self, restrictions: dict, group_members: dict | None = None) -> None:
        self._restrictions = restrictions
        self._group_members = group_members or {}

    def load_restrictions(self, page_id: str) -> dict | None:
        return self._restrictions.get(page_id)

    def load_group_members(self, group_id: str) -> list[str] | None:
        return self._group_members.get(group_id)


def test_fixture_gateway_group_only_restriction_fails_closed(monkeypatch) -> None:
    stub = _StubLoader(
        {
            "9001": {
                "pageId": "9001",
                "operation": "read",
                "restrictions": {"group": {"results": [{"id": "grp-finance"}]}},
            }
        }
    )
    gateway = FixtureConfluenceGateway()
    monkeypatch.setattr("app.platform.clients.fixture_confluence_client._loader", lambda: stub)
    assert gateway.get_restrictions(9001) == [GROUP_RESTRICTED_SENTINEL]


def test_fixture_gateway_no_restriction_fixture_is_unrestricted(monkeypatch) -> None:
    stub = _StubLoader({})
    gateway = FixtureConfluenceGateway()
    monkeypatch.setattr("app.platform.clients.fixture_confluence_client._loader", lambda: stub)
    assert gateway.get_restrictions(9001) == []


def test_fixture_gateway_group_restriction_expands_via_group_members_fixture(monkeypatch) -> None:
    stub = _StubLoader(
        restrictions={"9001": {"restrictions": {"group": {"results": [{"id": "grp-finance"}]}}}},
        group_members={"grp-finance": ["acct-erin"]},
    )
    gateway = FixtureConfluenceGateway()
    monkeypatch.setattr("app.platform.clients.fixture_confluence_client._loader", lambda: stub)
    assert gateway.get_restrictions(9001) == ["acct-erin"]


def test_fixture_gateway_set_group_members_override(monkeypatch) -> None:
    # The test-only mutator overrides the fixture-file lookup directly, e.g. to simulate a group
    # a real deployment would resolve differently than the static fixture corpus.
    stub = _StubLoader(
        restrictions={"9001": {"restrictions": {"group": {"results": [{"id": "grp-finance"}]}}}},
        group_members={"grp-finance": ["acct-erin"]},
    )
    gateway = FixtureConfluenceGateway()
    monkeypatch.setattr("app.platform.clients.fixture_confluence_client._loader", lambda: stub)
    gateway.set_group_members("grp-finance", ["acct-overridden-member"])
    assert gateway.get_restrictions(9001) == ["acct-overridden-member"]


def test_fixture_gateway_set_restrictions_override_bypasses_resolution(monkeypatch) -> None:
    # The test-only mutator injects an already-resolved principal set directly (e.g. simulating
    # a future group-membership expansion) — it must not be reinterpreted by the resolver.
    stub = _StubLoader({"9001": {"restrictions": {"group": {"results": [{"id": "grp-finance"}]}}}})
    gateway = FixtureConfluenceGateway()
    monkeypatch.setattr("app.platform.clients.fixture_confluence_client._loader", lambda: stub)
    gateway.set_restrictions(9001, ["acct-expanded-member"])
    assert gateway.get_restrictions(9001) == ["acct-expanded-member"]
