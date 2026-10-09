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

from .application.command_handler import apply_sync_command, target_versions
from .application.services import build_ingestion_services
from .application.versioning import (
    PageHashes,
    deactivate_page,
    purge_page,
    stage_and_activate,
)
from .domain import normalization
from .domain.applicability import (
    ANY,
    APPLIES_TO_LEVELS,
    WORKFLOW_BINDINGS,
    ApplicabilityRule,
    ApplicabilityValidationError,
    AppliesTo,
    ConnectionSpec,
    applies_to_payload,
    validate_applies_to,
    validate_rule,
)
from .domain.applies_to_parsing import AppliesToExtraction, extract_applies_to
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
    "ANY",
    "APPLIES_TO_LEVELS",
    "WORKFLOW_BINDINGS",
    "ApplicabilityRule",
    "ApplicabilityValidationError",
    "AppliesTo",
    "AppliesToExtraction",
    "ChangeClass",
    "ConnectionSpec",
    "ExtractionResult",
    "PageHashes",
    "TargetVersions",
    "applies_to_payload",
    "apply_sync_command",
    "attachment_to_blocks",
    "extract_applies_to",
    "build_ingestion_services",
    "classify",
    "deactivate_page",
    "decide_body_fetch",
    "extract_attachment",
    "get_local_state",
    "map_page_status",
    "normalization",
    "purge_page",
    "stage_and_activate",
    "target_versions",
    "validate_applies_to",
    "validate_rule",
]
