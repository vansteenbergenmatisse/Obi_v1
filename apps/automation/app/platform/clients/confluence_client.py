"""Confluence Cloud REST API v2 client.

Read-only gateway used by synchronization and reconciliation. Uses cursor-based pagination,
strict per-request timeouts, and bounded retry/backoff on transient failures. A ``Protocol`` is
defined so tests (and offline runs) can substitute a fixture-backed gateway with identical shape.
"""

from __future__ import annotations

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

_RETRYABLE = (httpx.TransportError, httpx.TimeoutException)


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

    def close(self) -> None:
        self._client.close()

    @retry(
        retry=retry_if_exception_type(_RETRYABLE),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.3, max=4),
        reraise=True,
    )
    def _get(self, url: str, params: dict | None = None) -> httpx.Response:
        resp = self._client.get(url, params=params)
        if resp.status_code >= 500:
            resp.raise_for_status()
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
        # v2 read-restriction principals; returns [] when not accessible/none.
        resp = self._get(f"{self._api}/pages/{page_id}/restrictions")
        if resp.status_code >= 400:
            return []
        principals: list[str] = []
        for r in resp.json().get("results", []):
            if r.get("operation") != "read":
                continue
            for u in (r.get("restrictions", {}).get("user", {}) or {}).get("results", []):
                if u.get("accountId"):
                    principals.append(u["accountId"])
        return principals
