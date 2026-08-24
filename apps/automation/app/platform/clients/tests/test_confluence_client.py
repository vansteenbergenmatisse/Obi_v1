"""Confluence gateway restriction parsing — PLAN 4.6.1's fail-closed fix + 4.6.2's expansion.

Covers the CRITICAL finding (4.6.1): a page restricted only by Confluence group(s), with no
individually-restricted user, must not sync as unrestricted. And the real fix (4.6.2): group
membership resolves to real account ids via a per-client-instance cache, falling back to the
same fail-closed sentinel when a group can't be expanded (no resolver, or the resolver finds no
members). Both `HttpConfluenceClient` (live REST v1 restrictions + v1 group-membership — v2
restrictions is unusable, see `get_restrictions`'s own docstring) and `FixtureConfluenceGateway`
(offline/test double) share the same pure resolver, so both are exercised here against the exact
restriction-record shape each speaks.
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


# -- HttpConfluenceClient (live REST v1 restriction shape) -------------------------------


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


def test_http_client_restriction_fetch_failure_fails_closed() -> None:
    # PLAN 4.6.2's 2026-08-21 finding: a request failure on the restriction fetch itself (e.g.
    # the real-world 418 hit when the old v2 endpoint was used) must not be read as "no
    # restrictions" — that was fail-open, silently making every page world-readable whenever the
    # endpoint errored.
    client = HttpConfluenceClient(
        _settings(),
        client=httpx.Client(
            transport=httpx.MockTransport(lambda r: httpx.Response(418, text="teapot"))
        ),
    )
    assert client.get_restrictions(9001) == [GROUP_RESTRICTED_SENTINEL]


def test_http_client_restrictions_use_v1_content_endpoint() -> None:
    # Locks the real, working endpoint shape (confirmed live, 2026-08-21) so a regression back to
    # the non-functional v2 path (`/api/v2/pages/{id}/restrictions`) fails a test, not silently.
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        return httpx.Response(200, json={"results": []})

    client = HttpConfluenceClient(
        _settings(), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    client.get_restrictions(9001)
    assert seen["path"] == "/wiki/rest/api/content/9001/restriction"


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
        if request.url.path.endswith("/restriction"):
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
        if request.url.path.endswith("/restriction"):
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
        if request.url.path.endswith("/restriction"):
            return httpx.Response(
                200, json=_restrictions_response(page_id=9001, group_id="grp-finance")
            )
        return httpx.Response(403, json={"message": "forbidden"})

    client = HttpConfluenceClient(
        _settings(), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    # the member lookup failed (403, no scope) — must not collapse to open access.
    assert client.get_restrictions(9001) == [GROUP_RESTRICTED_SENTINEL]


# -- HttpConfluenceClient pagination (`_links.next` cursor join) -------------------------
#
# Confluence Cloud's `_links.next` is site-root-relative (e.g. "/wiki/api/v2/pages?cursor=...")
# and already includes the "/wiki" context path `self._base` also carries — naively
# concatenating the two doubled it ("/wiki/wiki/api/v2/pages?..."), a 404 that only surfaces
# once a space/group has more than one page of results. Found live 2026-08-21 syncing a real
# >100-page space; every test above this point mocks a single-page response, so it never
# exercised the `next`-link join at all. Fixed via `httpx.URL(base).join(next_link)`.


def test_http_client_list_space_pages_paginates_without_doubling_wiki_prefix() -> None:
    seen_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.path)
        if len(seen_paths) == 1:
            return httpx.Response(
                200,
                json={
                    "results": [{"id": "1", "spaceId": "100", "title": "One", "status": "current"}],
                    "_links": {"next": "/wiki/api/v2/pages?cursor=abc"},
                },
            )
        return httpx.Response(
            200,
            json={
                "results": [{"id": "2", "spaceId": "100", "title": "Two", "status": "current"}],
                "_links": {},
            },
        )

    client = HttpConfluenceClient(
        _settings(), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    pages = client.list_space_pages(100)
    assert [p.page_id for p in pages] == [1, 2]
    assert seen_paths == ["/wiki/api/v2/pages", "/wiki/api/v2/pages"]


def test_http_client_group_member_lookup_paginates_without_doubling_wiki_prefix() -> None:
    seen_member_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/restriction"):
            return httpx.Response(
                200, json=_restrictions_response(page_id=9001, group_id="grp-finance")
            )
        seen_member_paths.append(request.url.path)
        if len(seen_member_paths) == 1:
            return httpx.Response(
                200,
                json={
                    "results": [{"accountId": "acct-erin"}],
                    "_links": {"next": "/wiki/rest/api/group/by-id/grp-finance/member?cursor=x"},
                },
            )
        return httpx.Response(200, json={"results": [{"accountId": "acct-dave"}], "_links": {}})

    client = HttpConfluenceClient(
        _settings(), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    assert client.get_restrictions(9001) == ["acct-erin", "acct-dave"]
    assert seen_member_paths == [
        "/wiki/rest/api/group/by-id/grp-finance/member",
        "/wiki/rest/api/group/by-id/grp-finance/member",
    ]


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


# -- HttpConfluenceClient.download_attachment (fixes/phase-2 wiring) --------------------


def test_get_attachments_includes_download_link() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "att1",
                        "title": "notes.pdf",
                        "mediaType": "application/pdf",
                        "fileSize": 100,
                        "version": {"number": 1},
                        "downloadLink": "/rest/api/content/9001/child/attachment/att1/download",
                    }
                ]
            },
        )

    client = HttpConfluenceClient(
        _settings(), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    out = client.get_attachments(9001)
    assert out[0]["downloadLink"] == "/rest/api/content/9001/child/attachment/att1/download"


def test_download_attachment_returns_bytes_on_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=b"hello attachment", headers={"content-type": "text/plain"}
        )

    client = HttpConfluenceClient(
        _settings(), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    data = client.download_attachment(
        "/rest/api/content/9001/child/attachment/att1/download", max_bytes=1_000
    )
    assert data == b"hello attachment"


def test_download_attachment_follows_cross_host_redirect_without_forwarding_auth() -> None:
    # Confirmed live (fixes/phase-2 research): Confluence 302s the download URL to a signed
    # media.atlassian.com URL. httpx must be told to follow it — and must NOT forward the Basic
    # Auth header to that third-party host (a credential leak otherwise). The injected client
    # carries real auth here (unlike other tests in this file) specifically so this negative
    # assertion has something to check — an unauthenticated MockTransport client could never prove
    # a header was dropped, since it was never sent in the first place.
    seen_auth_headers: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_auth_headers.append(request.headers.get("authorization"))
        if request.url.host == "example.atlassian.net":
            return httpx.Response(
                302, headers={"location": "https://media.example.com/binary?token=abc"}
            )
        assert request.url.host == "media.example.com"
        return httpx.Response(200, content=b"the real bytes")

    authed_client = httpx.Client(
        transport=httpx.MockTransport(handler), auth=httpx.BasicAuth("user@example.com", "token")
    )
    client = HttpConfluenceClient(_settings(), client=authed_client)
    data = client.download_attachment("/rest/api/content/9001/attachment/download", max_bytes=1_000)
    assert data == b"the real bytes"
    assert len(seen_auth_headers) == 2
    assert seen_auth_headers[0] is not None and seen_auth_headers[0].startswith("Basic ")
    assert seen_auth_headers[1] is None


def test_download_attachment_aborts_past_cap_even_if_content_length_lied() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        # 10 bytes advertised, but the real stream is much larger — the cap must still bind.
        return httpx.Response(200, content=b"x" * 500, headers={"content-length": "10"})

    client = HttpConfluenceClient(
        _settings(), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    assert client.download_attachment("/download/x", max_bytes=100) is None


def test_download_attachment_returns_none_on_4xx() -> None:
    client = HttpConfluenceClient(
        _settings(),
        client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(404))),
    )
    assert client.download_attachment("/download/gone", max_bytes=1_000) is None


def test_download_attachment_retries_5xx_then_succeeds() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 2:
            return httpx.Response(503)
        return httpx.Response(200, content=b"ok")

    client = HttpConfluenceClient(
        _settings(), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    assert client.download_attachment("/download/x", max_bytes=1_000) == b"ok"
    assert calls["n"] == 2


def test_download_attachment_empty_link_returns_none() -> None:
    client = HttpConfluenceClient(
        _settings(),
        client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200))),
    )
    assert client.download_attachment("", max_bytes=1_000) is None


# -- FixtureConfluenceGateway.download_attachment (fixes/phase-2 wiring) ----------------


def test_fixture_gateway_download_attachment_resolves_real_fixture_file() -> None:
    gateway = FixtureConfluenceGateway()
    attachments = gateway.get_attachments(1001)
    checklist = next(a for a in attachments if a["title"] == "welcome-checklist.txt")
    data = gateway.download_attachment(checklist["downloadLink"], max_bytes=10_000)
    assert data is not None
    assert b"Sign the code of conduct" in data


def test_fixture_gateway_download_attachment_unknown_link_returns_none() -> None:
    gateway = FixtureConfluenceGateway()
    assert gateway.download_attachment("/download/does-not-exist", max_bytes=10_000) is None


def test_fixture_gateway_download_attachment_oversized_returns_none() -> None:
    gateway = FixtureConfluenceGateway()
    attachments = gateway.get_attachments(1001)
    checklist = next(a for a in attachments if a["title"] == "welcome-checklist.txt")
    assert gateway.download_attachment(checklist["downloadLink"], max_bytes=1) is None


def test_fixture_gateway_set_attachment_content_overrides_bytes() -> None:
    gateway = FixtureConfluenceGateway()
    attachments = gateway.get_attachments(1001)
    checklist = next(a for a in attachments if a["title"] == "welcome-checklist.txt")
    gateway.set_attachment_content(checklist["downloadLink"], b"overridden content")
    data = gateway.download_attachment(checklist["downloadLink"], max_bytes=10_000)
    assert data == b"overridden content"


def test_fixture_gateway_set_attachment_content_none_simulates_failure() -> None:
    gateway = FixtureConfluenceGateway()
    attachments = gateway.get_attachments(1001)
    checklist = next(a for a in attachments if a["title"] == "welcome-checklist.txt")
    gateway.set_attachment_content(checklist["downloadLink"], None)
    assert gateway.download_attachment(checklist["downloadLink"], max_bytes=10_000) is None


def test_fixture_gateway_set_restrictions_override_bypasses_resolution(monkeypatch) -> None:
    # The test-only mutator injects an already-resolved principal set directly (e.g. simulating
    # a future group-membership expansion) — it must not be reinterpreted by the resolver.
    stub = _StubLoader({"9001": {"restrictions": {"group": {"results": [{"id": "grp-finance"}]}}}})
    gateway = FixtureConfluenceGateway()
    monkeypatch.setattr("app.platform.clients.fixture_confluence_client._loader", lambda: stub)
    gateway.set_restrictions(9001, ["acct-expanded-member"])
    assert gateway.get_restrictions(9001) == ["acct-expanded-member"]
