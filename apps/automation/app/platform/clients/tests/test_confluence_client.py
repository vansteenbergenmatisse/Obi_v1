"""Confluence gateway restriction parsing — PLAN 4.6.1's group-only fail-closed fix.

Covers the CRITICAL finding: a page restricted only by Confluence group(s), with no
individually-restricted user, must not sync as unrestricted. Both `HttpConfluenceClient`
(live REST v2) and `FixtureConfluenceGateway` (offline/test double) share the same pure
resolver, so both are exercised here against the exact restriction-record shape each speaks.
"""

from __future__ import annotations

import httpx

from app.platform.clients.confluence_client import (
    GROUP_RESTRICTED_SENTINEL,
    HttpConfluenceClient,
    _resolve_read_restriction,
)
from app.platform.clients.fixture_confluence_client import FixtureConfluenceGateway
from app.platform.config import Settings


def _settings() -> Settings:
    return Settings(
        confluence_base_url="https://example.atlassian.net/wiki",
        confluence_email="svc@example.com",
        confluence_api_token="tok",
    )


# -- pure resolver -----------------------------------------------------------------------


def test_group_only_restriction_resolves_to_fail_closed_sentinel() -> None:
    restrictions = {"group": {"results": [{"id": "grp-finance", "name": "finance"}]}}
    assert _resolve_read_restriction(restrictions) == [GROUP_RESTRICTED_SENTINEL]


def test_user_and_group_restriction_keeps_only_resolved_users() -> None:
    # Mirrors fixture page-2002.json: a resolvable user alongside unresolved groups. Group
    # membership expansion is deferred (PLAN 4.6.2) — the user principal alone is not a bypass.
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


# -- FixtureConfluenceGateway (offline/test double shape) --------------------------------


class _StubLoader:
    """Minimal stand-in for `tests.fixtures.confluence.loader`, restrictions-only."""

    def __init__(self, restrictions: dict) -> None:
        self._restrictions = restrictions

    def load_restrictions(self, page_id: str) -> dict | None:
        return self._restrictions.get(page_id)


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


def test_fixture_gateway_set_restrictions_override_bypasses_resolution(monkeypatch) -> None:
    # The test-only mutator injects an already-resolved principal set directly (e.g. simulating
    # a future group-membership expansion) — it must not be reinterpreted by the resolver.
    stub = _StubLoader({"9001": {"restrictions": {"group": {"results": [{"id": "grp-finance"}]}}}})
    gateway = FixtureConfluenceGateway()
    monkeypatch.setattr("app.platform.clients.fixture_confluence_client._loader", lambda: stub)
    gateway.set_restrictions(9001, ["acct-expanded-member"])
    assert gateway.get_restrictions(9001) == ["acct-expanded-member"]
