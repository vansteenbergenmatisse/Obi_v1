"""Filesystem loader for the Confluence fixture corpus.

Pure filesystem + JSON access to the fixtures in this directory. No database,
no network. Used by the evaluation harness and by tests to load pages, versions,
labels, restrictions, and attachment manifests programmatically.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


def fixtures_dir() -> Path:
    """Absolute path to the Confluence fixture corpus directory."""
    return Path(__file__).resolve().parent


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=1)
def load_manifest() -> dict[str, Any]:
    """Load the corpus manifest indexing all fixtures."""
    return _read_json(fixtures_dir() / "manifest.json")


def list_pages() -> list[dict[str, Any]]:
    """Return the manifest page index entries (not full page bodies)."""
    return list(load_manifest()["pages"])


def list_page_ids() -> list[str]:
    """Return every page id in the corpus, in manifest order."""
    return [page["id"] for page in load_manifest()["pages"]]


def _manifest_file_override(page_id: str) -> str | None:
    """The manifest's optional ``file`` key for a page's current-version fixture.

    Lets a fixture file's name encode both the page id and its labels (e.g.
    ``page-3002-obi-mews-test.json``, substep 0.5.1) instead of the default
    ``page-<id>.json``. Legacy pages carry no ``file`` key and are unaffected.
    """
    for page in load_manifest()["pages"]:
        if page["id"] == page_id:
            return page.get("file")
    return None


def load_page(page_id: str, version: int | None = None) -> dict[str, Any]:
    """Load a page fixture.

    When ``version`` is None, the current page fixture is returned: the manifest's
    per-page ``file`` override when set, else ``page-<id>.json``. When a version
    number is given, the snapshot from the ``versions/`` subfolder
    (``versions/page-<id>-v<version>.json``) is returned. Raises FileNotFoundError
    if the requested fixture does not exist.
    """
    page_id = str(page_id)
    base = fixtures_dir()
    if version is None:
        override = _manifest_file_override(page_id)
        path = base / override if override else base / f"page-{page_id}.json"
    else:
        path = base / "versions" / f"page-{page_id}-v{version}.json"
    if not path.exists():
        raise FileNotFoundError(f"No page fixture at {path}")
    return _read_json(path)


def available_versions(page_id: str) -> list[int]:
    """Return the version numbers available for a page, from the manifest."""
    page_id = str(page_id)
    for page in load_manifest()["pages"]:
        if page["id"] == page_id:
            return list(page.get("versionsAvailable", []))
    raise KeyError(f"Unknown page id: {page_id}")


def _load_optional(subdir: str, page_id: str) -> dict[str, Any] | None:
    path = fixtures_dir() / subdir / f"page-{page_id}.json"
    if not path.exists():
        return None
    return _read_json(path)


def load_labels(page_id: str) -> dict[str, Any] | None:
    """Load the labels fixture for a page, or None if the page has no labels."""
    return _load_optional("labels", str(page_id))


def load_restrictions(page_id: str) -> dict[str, Any] | None:
    """Load the read-restrictions fixture for a page, or None if unrestricted."""
    return _load_optional("restrictions", str(page_id))


def load_attachments(page_id: str) -> dict[str, Any] | None:
    """Load the attachment manifest for a page, or None if it has none."""
    return _load_optional("attachments", str(page_id))


@lru_cache(maxsize=1)
def _group_members_index() -> dict[str, list[str]]:
    path = fixtures_dir() / "group_members.json"
    if not path.exists():
        return {}
    return _read_json(path)


def load_group_members(group_id: str) -> list[str] | None:
    """Load a fixture group's member accountIds by group id (or name), or None if unknown."""
    index = _group_members_index()
    return list(index[group_id]) if group_id in index else None


def attachment_path(file_name: str) -> Path:
    """Absolute path to a raw attachment file under attachments/."""
    return fixtures_dir() / "attachments" / file_name


__all__ = [
    "fixtures_dir",
    "load_manifest",
    "list_pages",
    "list_page_ids",
    "load_page",
    "available_versions",
    "load_labels",
    "load_restrictions",
    "load_attachments",
    "attachment_path",
    "load_group_members",
]
