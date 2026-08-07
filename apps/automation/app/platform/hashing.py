"""Deterministic hashing helpers used for change detection, dedup and stable identity.

All hashes are raw 32-byte SHA-256 (`bytes`), stored as BYTEA. Canonicalization is explicit so
the same logical content always yields the same digest regardless of dict ordering or whitespace.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from collections.abc import Iterable


def sha256_bytes(*parts: bytes) -> bytes:
    h = hashlib.sha256()
    for p in parts:
        h.update(p)
        h.update(b"\x1f")  # unit separator between parts
    return h.digest()


def sha256_text(*parts: str) -> bytes:
    return sha256_bytes(*[p.encode("utf-8") for p in parts])


def normalize_text(value: str) -> str:
    """NFC-normalize, strip, collapse internal whitespace runs. For hashing only."""
    value = unicodedata.normalize("NFC", value)
    return " ".join(value.split())


def canonical_json(obj: object) -> str:
    """Stable JSON: sorted keys, no insignificant whitespace."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def hash_json(obj: object) -> bytes:
    return sha256_text(canonical_json(obj))


def hash_labels(labels: Iterable[str]) -> bytes:
    return sha256_text(canonical_json(sorted({normalize_text(x) for x in labels})))


def hash_access_scope(read_account_ids: Iterable[str], space_key: str | None = None) -> bytes:
    """Permission fingerprint: sorted read-restriction principals + space key."""
    payload = {
        "space": space_key or "",
        "read": sorted(set(read_account_ids)),
    }
    return hash_json(payload)


def hash_attachment_manifest(attachments: Iterable[dict]) -> bytes:
    """Order-independent manifest hash of (id, version, fileSize, mediaType) tuples."""
    items = sorted(
        (
            str(a.get("id")),
            str(a.get("version", "")),
            str(a.get("fileSize", "")),
            str(a.get("mediaType", "")),
        )
        for a in attachments
    )
    return hash_json(items)
