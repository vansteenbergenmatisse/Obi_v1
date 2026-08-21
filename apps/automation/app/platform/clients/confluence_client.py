"""Confluence Cloud REST API v2 client.

Read-only gateway used by synchronization and reconciliation. Uses cursor-based pagination,
strict per-request timeouts, and bounded retry/backoff on transient failures, plus a
consecutive-failure circuit breaker (PLAN 4.6.7) mirroring ``embeddings_client.py``'s /
``anthropic_client.py``'s pattern: persistent instance state (this client is documented
"instantiate once and reuse" across a sync run), tripped by consecutive whole-request failures
(after internal retries are exhausted), not individual HTTP attempts. A ``Protocol`` is defined so
tests (and offline runs) can substitute a fixture-backed gateway with identical shape.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Protocol, runtime_checkable

import httpx
from pydantic import BaseModel
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.platform.config import Settings
from app.platform.logging import get_logger

log = get_logger("confluence_client")

# httpx.HTTPStatusError is only ever raised inside `_get_with_retry` for a >=500 response (a 4xx
# is returned as a normal Response, never raised, there) — so including it here retries 5xx and
# never a 4xx, closing the gap where `how_this_works.md` already documented "retry on 5xx" as
# real behavior it wasn't (PLAN 4.6.7).
_RETRYABLE = (httpx.TransportError, httpx.TimeoutException, httpx.HTTPStatusError)


class ConfluenceCircuitBreakerOpenError(RuntimeError):
    """Raised when the client's consecutive-failure circuit breaker is open (PLAN 4.6.7)."""


def _log_before_retry(retry_state) -> None:
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    log.warning(
        "confluence_client_retry",
        attempt=retry_state.attempt_number,
        error=str(exc) if exc else None,
    )


class ConfluencePageMeta(BaseModel):
    page_id: int
    space_id: int
    parent_id: int | None
    title: str
    status: str  # current | archived | trashed | draft | deleted
    version_number: int
    version_created_at: datetime
    source_url: str


class ConfluencePage(ConfluencePageMeta):
    body_storage: str = ""


@runtime_checkable
class ConfluenceGateway(Protocol):
    def get_page_meta(self, page_id: int) -> ConfluencePageMeta | None: ...
    def get_page(self, page_id: int) -> ConfluencePage | None: ...
    def list_space_pages(self, space_id: int) -> list[ConfluencePageMeta]: ...
    def get_labels(self, page_id: int) -> list[str]: ...
    def get_restrictions(self, page_id: int) -> list[str]: ...
    def get_attachments(self, page_id: int) -> list[dict]: ...


# Returned in place of a group-only restriction's principals when group membership could not be
# expanded to real account ids (no resolver given, or the resolver found no members). No real
# caller is ever this literal string, so a page keyed by it is inaccessible to everyone but the
# sync/admin path — fail-closed rather than silently unrestricted.
GROUP_RESTRICTED_SENTINEL = "__unresolved_group_restriction__"

# One Confluence group record as it appears in a restriction payload: `{"id": ..., "name": ...}`.
GroupRecord = dict


def _resolve_read_restriction(
    restrictions: dict,
    resolve_group: Callable[[GroupRecord], list[str]] | None = None,
) -> list[str]:
    """Resolve one Confluence read-restriction record's principals.

    Individual-user restrictions are always directly resolvable. Group restrictions need
    ``resolve_group`` (PLAN 4.6.2) to expand a group record to its member account ids — each
    caller supplies its own (a live REST lookup, cached per sync run, for
    :class:`HttpConfluenceClient`; a fixture-backed lookup for
    :class:`~app.platform.clients.fixture_confluence_client.FixtureConfluenceGateway`). Without a
    resolver, or when the resolver returns no members for every group on the record (API
    call failed, or the group control plane says no members are visible with the current
    token's scope), this must fail closed rather than silently becoming unrestricted: dropping
    ``restrictions.group`` entirely and returning ``[]`` (PLAN 4.6.1's finding) would let a page
    restricted only by group sync as world-readable through the chatbot.
    """
    users = (restrictions.get("user") or {}).get("results", []) or []
    groups = (restrictions.get("group") or {}).get("results", []) or []
    principals = [u["accountId"] for u in users if u.get("accountId")]
    if not groups:
        return principals
    if resolve_group is None:
        return principals if principals else [GROUP_RESTRICTED_SENTINEL]
    expanded = list(principals)
    for group in groups:
        for account_id in resolve_group(group):
            if account_id not in expanded:
                expanded.append(account_id)
    return expanded if expanded else [GROUP_RESTRICTED_SENTINEL]


def _webui(base_url: str, links: dict) -> str:
    webui = links.get("webui", "")
    if webui.startswith("http"):
        return webui
    root = base_url.rstrip("/")
    return f"{root}{webui}" if webui else root


class HttpConfluenceClient:
    """Live REST v2 client. Instantiate once and reuse (connection pooling)."""

    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        self._settings = settings
        base = settings.confluence_base_url.rstrip("/")
        self._api = f"{base}/api/v2"
        self._base = base
        self._client = client or httpx.Client(
            auth=httpx.BasicAuth(settings.confluence_email, settings.confluence_api_token),
            timeout=settings.provider_timeout_seconds,
            headers={"Accept": "application/json"},
        )
        # group id/name -> member accountIds, cached for this client's lifetime (PLAN 4.6.2):
        # a sync run reuses one client instance across every page, so a group shared by many
        # pages (e.g. a whole space's HR docs) is fetched once, not once per page.
        self._group_members_cache: dict[str, list[str]] = {}
        # C4 circuit breaker (PLAN 4.6.7): persists for this client's lifetime, tripped by
        # consecutive whole-request failures (each already internally retried up to 3 times).
        self._breaker_threshold = settings.confluence_breaker_threshold
        self._consecutive_failures = 0

    def close(self) -> None:
        self._client.close()

    def _get(self, url: str, params: dict | None = None) -> httpx.Response:
        if self._consecutive_failures >= self._breaker_threshold:
            raise ConfluenceCircuitBreakerOpenError(
                "confluence circuit breaker open after "
                f"{self._consecutive_failures} consecutive request failures"
            )
        try:
            resp = self._get_with_retry(url, params)
        except Exception:
            self._consecutive_failures += 1
            raise
        self._consecutive_failures = 0
        return resp

    @retry(
        retry=retry_if_exception_type(_RETRYABLE),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.3, max=4),
        before_sleep=_log_before_retry,
        reraise=True,
    )
    def _get_with_retry(self, url: str, params: dict | None = None) -> httpx.Response:
        resp = self._client.get(url, params=params)
        if resp.status_code >= 500:
            log.warning("confluence_client_5xx", url=url, status=resp.status_code)
            resp.raise_for_status()
        elif resp.status_code >= 400:
            log.warning("confluence_client_4xx", url=url, status=resp.status_code)
        return resp

    def _meta_from_json(self, data: dict) -> ConfluencePageMeta:
        version = data.get("version", {}) or {}
        return ConfluencePageMeta(
            page_id=int(data["id"]),
            space_id=int(data.get("spaceId") or 0),
            parent_id=int(data["parentId"]) if data.get("parentId") else None,
            title=data.get("title", ""),
            status=data.get("status", "current"),
            version_number=int(version.get("number", 1)),
            version_created_at=version.get("createdAt") or datetime.now().astimezone(),
            source_url=_webui(self._base, data.get("_links", {})),
        )

    def get_page_meta(self, page_id: int) -> ConfluencePageMeta | None:
        resp = self._get(f"{self._api}/pages/{page_id}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return self._meta_from_json(resp.json())

    def get_page(self, page_id: int) -> ConfluencePage | None:
        resp = self._get(f"{self._api}/pages/{page_id}", params={"body-format": "storage"})
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()
        meta = self._meta_from_json(data)
        body = ((data.get("body") or {}).get("storage") or {}).get("value", "")
        return ConfluencePage(**meta.model_dump(), body_storage=body)

    def list_space_pages(self, space_id: int) -> list[ConfluencePageMeta]:
        """Follow cursor-based pagination to enumerate every page in a space."""
        pages: list[ConfluencePageMeta] = []
        params: dict = {"limit": 100, "space-id": space_id, "status": "current"}
        url = f"{self._api}/pages"
        while True:
            resp = self._get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            for item in data.get("results", []):
                pages.append(self._meta_from_json(item))
            next_link = (data.get("_links", {}) or {}).get("next")
            if not next_link:
                break
            url = next_link if next_link.startswith("http") else f"{self._base}{next_link}"
            params = None  # cursor is embedded in next_link
        return pages

    def get_labels(self, page_id: int) -> list[str]:
        resp = self._get(f"{self._api}/pages/{page_id}/labels")
        if resp.status_code >= 400:
            return []
        return [r.get("name", "") for r in resp.json().get("results", [])]

    def get_attachments(self, page_id: int) -> list[dict]:
        resp = self._get(f"{self._api}/pages/{page_id}/attachments")
        if resp.status_code >= 400:
            return []
        out = []
        for r in resp.json().get("results", []):
            out.append(
                {
                    "id": r.get("id"),
                    "title": r.get("title"),
                    "mediaType": r.get("mediaType"),
                    "fileSize": r.get("fileSize"),
                    "version": (r.get("version", {}) or {}).get("number"),
                }
            )
        return out

    def get_restrictions(self, page_id: int) -> list[str]:
        """Read-restriction principals for a page.

        Uses REST **v1** (``/rest/api/content/{id}/restriction``), not v2. The v2 equivalent
        (``/api/v2/pages/{id}/restrictions``) is documented by Atlassian as still "under
        construction" and returns a non-standard 418 in practice — confirmed live against a real
        Confluence Cloud instance (PLAN 4.6.2, 2026-08-21 update); v1 is the endpoint that
        actually works today, and its response shape (``results[].operation`` /
        ``restrictions.user.results[].accountId`` / ``restrictions.group.results[]``) is exactly
        what ``_resolve_read_restriction`` already expects, confirmed against real pages, no
        parsing change needed.

        Fails **closed** on any request failure (``GROUP_RESTRICTED_SENTINEL``, the same sentinel
        4.6.1 established for an unresolvable group restriction) rather than treating an error as
        "no restrictions". The old v2 path's ``>=400 -> []`` was fail-*open*: since that endpoint
        never actually worked, every synced page persisted with zero restriction rows — silently
        world-readable regardless of its real Confluence ACL — until this fix (PLAN 4.6.2's
        2026-08-21 finding, live-confirmed against real synced pages before this fix landed).
        """
        resp = self._get(
            f"{self._base}/rest/api/content/{page_id}/restriction",
            params={"expand": "restrictions.user,restrictions.group"},
        )
        if resp.status_code >= 400:
            return [GROUP_RESTRICTED_SENTINEL]
        principals: list[str] = []
        for r in resp.json().get("results", []):
            if r.get("operation") != "read":
                continue
            principals.extend(
                _resolve_read_restriction(r.get("restrictions", {}) or {}, self._group_members)
            )
        return principals

    def _group_members(self, group: GroupRecord) -> list[str]:
        """Resolve one restriction's Confluence group to its member accountIds (PLAN 4.6.2)."""
        cache_key = group.get("id") or group.get("name")
        if not cache_key:
            return []
        if cache_key in self._group_members_cache:
            return self._group_members_cache[cache_key]
        members = self._fetch_group_members(group.get("id"), group.get("name"))
        self._group_members_cache[cache_key] = members
        return members

    def _fetch_group_members(self, group_id: str | None, group_name: str | None) -> list[str]:
        """Fetch a Confluence group's member accountIds.

        UNVERIFIED against a live Confluence instance — the Confluence API token has been dead
        (401/403, see PLAN.md blocker #3) for this whole engagement, so this endpoint has never
        actually been exercised outside a mocked transport. REST API v2 has no group-membership
        endpoint yet, so this uses v1's id-based endpoint (falling back to the deprecated
        name-based one when only a name is available, since restriction payloads sometimes omit
        `id`). **Confirm the exact path/response shape once the token works** (PLAN 4.6.2) —
        until then, a wrong path/shape fails the request, which `_group_members` caches as `[]`
        and `_resolve_read_restriction` turns into the same fail-closed sentinel 4.6.1 already
        proved correct — never a silent open-access regression.
        """
        if group_id:
            url = f"{self._base}/rest/api/group/by-id/{group_id}/member"
        elif group_name:
            url = f"{self._base}/rest/api/group/{group_name}/member"
        else:
            return []
        members: list[str] = []
        params: dict | None = {"limit": 200}
        while url:
            resp = self._get(url, params=params)
            if resp.status_code >= 400:
                log.warning(
                    "confluence_group_members_fetch_failed",
                    group_id=group_id,
                    group_name=group_name,
                    status=resp.status_code,
                )
                return members
            data = resp.json()
            for r in data.get("results", []):
                account_id = r.get("accountId")
                if account_id:
                    members.append(account_id)
            next_link = (data.get("_links", {}) or {}).get("next")
            if not next_link:
                break
            url = next_link if next_link.startswith("http") else f"{self._base}{next_link}"
            params = None  # cursor is embedded in next_link, matching list_space_pages
        return members
