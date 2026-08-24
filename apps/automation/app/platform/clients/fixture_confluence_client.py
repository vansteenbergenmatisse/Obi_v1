"""Fixture-backed Confluence gateway for offline runs and tests.

Adapts the on-disk fixture corpus (``tests/fixtures/confluence``) to the same
``ConfluenceGateway`` Protocol the live :class:`HttpConfluenceClient` implements, so the
worker, reconciliation, scheduler and tests can run with zero network access.

Beyond replaying the static corpus, the gateway exposes mutators so a test can drive
scenarios the corpus alone cannot express: advancing a page to a newer version, flipping a
page's status (trash/archive), changing read-restrictions or labels, and hiding a page to
simulate deletion or lost access. Mutations are in-memory only; the fixtures are never written.
"""

from __future__ import annotations

from datetime import datetime

from app.platform.clients.confluence_client import (
    ConfluenceGateway,
    ConfluencePage,
    ConfluencePageMeta,
    GroupRecord,
    _resolve_read_restriction,
)


def _loader():
    """Import the fixture loader lazily so shipped app code never hard-depends on ``tests``.

    The fixture corpus is an offline/test artifact that is not packaged in the deployed wheel.
    Importing it here (rather than at module top) keeps ``import app.main`` working in
    production, where only the live :class:`HttpConfluenceClient` is used.
    """
    from tests.fixtures.confluence import loader

    return loader


_DEFAULT_BASE = "https://omniboost.atlassian.net/wiki"
# Confluence statuses that never appear in a "list current pages" enumeration.
_NON_CURRENT = {"archived", "trashed", "deleted", "draft"}


def _parse_dt(value: str | None) -> datetime:
    if not value:
        return datetime.now().astimezone()
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _webui(base_url: str, page: dict) -> str:
    webui = (page.get("_links", {}) or {}).get("webui", "")
    if webui.startswith("http"):
        return webui
    root = base_url.rstrip("/")
    return f"{root}{webui}" if webui else f"{root}/pages/{page.get('id')}"


class FixtureConfluenceGateway:
    """In-memory, mutable gateway serving the Confluence fixture corpus.

    Satisfies :class:`ConfluenceGateway`. All page ids are integers on the wire (matching the
    live client and the ORM), even though the fixture files key pages by string id.
    """

    def __init__(self, base_url: str = _DEFAULT_BASE) -> None:
        self._base_url = base_url
        # page_id -> version number to serve (defaults to the manifest's current version)
        self._served_version: dict[int, int] = {}
        # page_id -> status override (defaults to the served fixture's status)
        self._status: dict[int, str] = {}
        # page_id -> label names / restriction account ids (None = use fixture)
        self._labels: dict[int, list[str]] = {}
        self._restrictions: dict[int, list[str]] = {}
        # group id/name -> member accountIds (None = use the group_members.json fixture)
        self._group_members: dict[str, list[str]] = {}
        # pages that behave as gone/inaccessible (get_page_meta/get_page return None)
        self._hidden: set[int] = set()
        # download_link -> raw bytes override (None = resolve via the attachment manifest's
        # `file` field on disk, the default path every corpus attachment already takes)
        self._attachment_content: dict[str, bytes | None] = {}

    # -- mutators (test/offline control surface) --------------------------------------

    def set_version(self, page_id: int, version: int) -> None:
        self._served_version[int(page_id)] = int(version)

    def set_status(self, page_id: int, status: str) -> None:
        self._status[int(page_id)] = status

    def set_labels(self, page_id: int, labels: list[str]) -> None:
        self._labels[int(page_id)] = list(labels)

    def set_restrictions(self, page_id: int, account_ids: list[str]) -> None:
        self._restrictions[int(page_id)] = list(account_ids)

    def set_group_members(self, group_id: str, account_ids: list[str]) -> None:
        """Override a group's fixture-backed membership (PLAN 4.6.2 test control)."""
        self._group_members[group_id] = list(account_ids)

    def hide(self, page_id: int) -> None:
        """Simulate deletion / lost access: reads return None."""
        self._hidden.add(int(page_id))

    def unhide(self, page_id: int) -> None:
        self._hidden.discard(int(page_id))

    def set_attachment_content(self, download_link: str, data: bytes | None) -> None:
        """Override one attachment's binary content, keyed by its manifest `downloadLink`.

        `None` simulates a failed/unreachable download (matches the live client's fail-soft
        return). Bypasses the on-disk `file` resolution entirely — e.g. to simulate an oversized
        attachment without committing a large fixture file.
        """
        self._attachment_content[download_link] = data

    # -- internal ---------------------------------------------------------------------

    def _raw_page(self, page_id: int) -> dict | None:
        loader = _loader()
        pid = int(page_id)
        version = self._served_version.get(pid)
        try:
            loader.available_versions(str(pid))  # KeyError => unknown page
        except KeyError:
            return None
        # Prefer an explicit version snapshot; fall back to the base file, which holds the
        # page's current version (most corpus pages have no per-version snapshots).
        if version is not None:
            try:
                return loader.load_page(str(pid), version=version)
            except FileNotFoundError:
                pass
        try:
            return loader.load_page(str(pid))
        except FileNotFoundError:
            return None

    def _meta_from_raw(self, raw: dict) -> ConfluencePageMeta:
        pid = int(raw["id"])
        version = raw.get("version", {}) or {}
        status = self._status.get(pid) or raw.get("status") or "current"
        return ConfluencePageMeta(
            page_id=pid,
            space_id=int(raw.get("spaceId") or 0),
            parent_id=int(raw["parentId"]) if raw.get("parentId") else None,
            title=raw.get("title", ""),
            status=status,
            version_number=int(version.get("number", 1)),
            version_created_at=_parse_dt(version.get("createdAt")),
            source_url=_webui(self._base_url, raw),
        )

    # -- ConfluenceGateway Protocol ---------------------------------------------------

    def get_page_meta(self, page_id: int) -> ConfluencePageMeta | None:
        if int(page_id) in self._hidden:
            return None
        raw = self._raw_page(page_id)
        return self._meta_from_raw(raw) if raw else None

    def get_page(self, page_id: int) -> ConfluencePage | None:
        if int(page_id) in self._hidden:
            return None
        raw = self._raw_page(page_id)
        if raw is None:
            return None
        meta = self._meta_from_raw(raw)
        body = ((raw.get("body") or {}).get("storage") or {}).get("value", "")
        return ConfluencePage(**meta.model_dump(), body_storage=body)

    def list_space_pages(self, space_id: int) -> list[ConfluencePageMeta]:
        """Enumerate current (live) pages in a space, mirroring the REST v2 filter."""
        out: list[ConfluencePageMeta] = []
        for entry in _loader().list_pages():
            if int(entry["spaceId"]) != int(space_id):
                continue
            pid = int(entry["id"])
            if pid in self._hidden:
                continue
            meta = self.get_page_meta(pid)
            if meta is None or meta.status in _NON_CURRENT:
                continue
            out.append(meta)
        return out

    def get_labels(self, page_id: int) -> list[str]:
        pid = int(page_id)
        if pid in self._labels:
            return list(self._labels[pid])
        data = _loader().load_labels(str(pid))
        if not data:
            return []
        return [r.get("name", "") for r in data.get("results", [])]

    def get_restrictions(self, page_id: int) -> list[str]:
        pid = int(page_id)
        if pid in self._restrictions:
            return list(self._restrictions[pid])
        data = _loader().load_restrictions(str(pid))
        if not data:
            return []
        return _resolve_read_restriction(
            data.get("restrictions", {}) or {}, self._group_members_for
        )

    def _group_members_for(self, group: GroupRecord) -> list[str]:
        """Fixture-backed group-membership lookup (4.6.2), overridable via `set_group_members`."""
        group_id = group.get("id") or group.get("name")
        if not group_id:
            return []
        if group_id in self._group_members:
            return list(self._group_members[group_id])
        return list(_loader().load_group_members(group_id) or [])

    def get_attachments(self, page_id: int) -> list[dict]:
        data = _loader().load_attachments(str(int(page_id)))
        if not data:
            return []
        out: list[dict] = []
        for r in data.get("results", []):
            out.append(
                {
                    "id": r.get("id"),
                    "title": r.get("title"),
                    "mediaType": r.get("mediaType"),
                    "fileSize": r.get("fileSize"),
                    "version": (r.get("version", {}) or {}).get("number"),
                    "downloadLink": (r.get("_links", {}) or {}).get("download"),
                }
            )
        return out

    def download_attachment(self, download_link: str, *, max_bytes: int) -> bytes | None:
        if download_link in self._attachment_content:
            data = self._attachment_content[download_link]
        else:
            data = self._read_fixture_attachment(download_link)
        if data is None:
            return None
        return data if len(data) <= max_bytes else None

    def _read_fixture_attachment(self, download_link: str) -> bytes | None:
        """Resolve a manifest `downloadLink` to its on-disk fixture file's bytes."""
        for entry in _loader().list_pages():
            manifest = _loader().load_attachments(entry["id"])
            if not manifest:
                continue
            for r in manifest.get("results", []):
                if (r.get("_links", {}) or {}).get("download") != download_link:
                    continue
                file_name = r.get("file")
                if not file_name:
                    return None
                path = _loader().attachment_path(file_name)
                return path.read_bytes() if path.exists() else None
        return None


# static assertion that the fixture gateway satisfies the Protocol
_: type[ConfluenceGateway] = FixtureConfluenceGateway
