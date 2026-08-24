"""Ingestion feature: token-aware chunking, versioning, and change detection.

Public surface. External code (confluence_sync, tests) imports the operations
and types that cross the boundary from `app.features.ingestion` — never from a
deeper module.

`normalization` is re-exported as a module (not as loose symbols) because
call sites use it qualified (norm.Block, norm.normalize_body, norm.content_hash,
norm.structure_hash); the numpy.linalg pattern keeps those call sites unchanged.

Internal rule: modules inside this feature MUST NOT import through this root
(`from app.features.ingestion import X`) — that raises ImportError during init.
They import each other by full submodule path.
"""

from __future__ import annotations

from .application.services import build_ingestion_services
from .application.versioning import (
    PageHashes,
    deactivate_page,
    reusable_active_children,
    rollback_to,
    stage_and_activate,
)
from .domain import normalization
from .domain.attachment_extraction import ExtractionResult, attachment_to_blocks, extract_attachment
from .domain.change_detection import (
    ChangeClass,
    TargetVersions,
    classify,
    decide_body_fetch,
    map_page_status,
)
from .infrastructure.page_source_repo import get_local_state

__all__ = [
    "ChangeClass",
    "ExtractionResult",
    "PageHashes",
    "TargetVersions",
    "attachment_to_blocks",
    "build_ingestion_services",
    "classify",
    "deactivate_page",
    "decide_body_fetch",
    "extract_attachment",
    "get_local_state",
    "map_page_status",
    "normalization",
    "reusable_active_children",
    "rollback_to",
    "stage_and_activate",
]
