"""Pure decision tests for the trigger layer — one case per row of the event→command table.

No DB, no gateway: :func:`decide_command` is a pure function of the page's current
state. Parametrized over every recognized scope in ``knowledge_scopes.json`` so no
single tag (``obi-mews-test``) is special-cased.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.features.confluence_sync.domain.ingest_decision import (
    decide_command,
    resolve_scopes,
    should_ingest,
)
from app.platform.clients import ConfluencePageMeta
from app.platform.config.knowledge_scopes import load_recognized_knowledge_scopes
from schema.models import SourceScope

RECOGNIZED = load_recognized_knowledge_scopes()
SPACE_ID = 701857803
PAGE_ID = 1712324611


def _meta(
    *,
    page_id: int = PAGE_ID,
    space_id: int = SPACE_ID,
    parent_id: int | None = None,
    status: str = "current",
    version: int = 1,
) -> ConfluencePageMeta:
    return ConfluencePageMeta(
        page_id=page_id,
        space_id=space_id,
        parent_id=parent_id,
        title="A page",
        status=status,
        version_number=version,
        version_created_at=datetime(2026, 1, 1, tzinfo=UTC),
        source_url="https://example/wiki/x",
    )


def _row(root_type: str, root_id, tags: list[str], *, is_active: bool = True) -> SourceScope:
    return SourceScope(
        root_type=root_type,
        root_id=str(root_id),
        source_type="confluence",
        tags=list(tags),
        is_active=is_active,
    )


ALL_SCOPES = sorted(RECOGNIZED)


@pytest.mark.parametrize("scope", ALL_SCOPES)
class TestEventCommandTable:
    def test_unrestricted_space_labelled_page_upserts(self, scope: str) -> None:
        # No source_scope rows for the space -> unrestricted -> the label is the scope.
        cmd = decide_command(
            PAGE_ID, _meta(), [scope], [], {PAGE_ID}, RECOGNIZED, "sweep_discovery"
        )
        assert cmd.action == "upsert"
        assert cmd.scopes == (scope,)
        assert cmd.reason == "sweep_discovery"

    def test_space_root_authorizes_only_its_allowlist(self, scope: str) -> None:
        # A space root listing ALL scopes authorizes them; intersection keeps only the label.
        rows = [_row("space", SPACE_ID, ALL_SCOPES)]
        cmd = decide_command(PAGE_ID, _meta(), [scope], rows, {PAGE_ID}, RECOGNIZED, "tag_added")
        assert cmd.action == "upsert"
        assert cmd.scopes == (scope,)

    def test_tag_removed_last_label_deletes(self, scope: str) -> None:
        cmd = decide_command(PAGE_ID, _meta(), [], [], {PAGE_ID}, RECOGNIZED, "tag_removed")
        assert cmd.action == "delete"
        assert cmd.scopes == ()

    def test_page_gone_deletes(self, scope: str) -> None:
        cmd = decide_command(PAGE_ID, None, [scope], [], {PAGE_ID}, RECOGNIZED, "page_gone")
        assert cmd.action == "delete"

    def test_back_to_draft_deletes(self, scope: str) -> None:
        cmd = decide_command(
            PAGE_ID, _meta(status="draft"), [scope], [], {PAGE_ID}, RECOGNIZED, "back_to_draft"
        )
        assert cmd.action == "delete"

    @pytest.mark.parametrize("status", ["archived", "trashed", "deleted"])
    def test_non_current_status_deletes(self, scope: str, status: str) -> None:
        cmd = decide_command(
            PAGE_ID, _meta(status=status), [scope], [], {PAGE_ID}, RECOGNIZED, "page_gone"
        )
        assert cmd.action == "delete"

    def test_classified_label_deletes(self, scope: str) -> None:
        cmd = decide_command(
            PAGE_ID, _meta(), [scope, "classified"], [], {PAGE_ID}, RECOGNIZED, "edited"
        )
        assert cmd.action == "delete"

    def test_unauthorized_scope_in_scoped_space_deletes(self, scope: str) -> None:
        # Space is scoped, but the covering row authorizes a DIFFERENT scope only.
        other = next(s for s in ALL_SCOPES if s != scope)
        rows = [_row("space", SPACE_ID, [other])]
        cmd = decide_command(PAGE_ID, _meta(), [scope], rows, {PAGE_ID}, RECOGNIZED, "sweep_drift")
        assert cmd.action == "delete"

    def test_moved_out_of_scope_deletes(self, scope: str) -> None:
        # A page root covers subtree {900, 901}; this page (and its ancestors) are elsewhere.
        rows = [_row("page", 900, ALL_SCOPES)]
        cmd = decide_command(
            PAGE_ID,
            _meta(parent_id=500),
            [scope],
            rows,
            {PAGE_ID, 500},
            RECOGNIZED,
            "moved_out_of_scope",
        )
        assert cmd.action == "delete"

    def test_moved_into_scope_upserts(self, scope: str) -> None:
        # Same page root, but now an ancestor id matches the root -> covered.
        rows = [_row("page", 900, ALL_SCOPES)]
        cmd = decide_command(
            PAGE_ID,
            _meta(parent_id=900),
            [scope],
            rows,
            {PAGE_ID, 900},
            RECOGNIZED,
            "moved_into_scope",
        )
        assert cmd.action == "upsert"
        assert cmd.scopes == (scope,)

    def test_empty_tag_row_authorizes_all_recognized(self, scope: str) -> None:
        # D3: an empty-tags covering row authorizes every recognized scope.
        rows = [_row("space", SPACE_ID, [])]
        cmd = decide_command(PAGE_ID, _meta(), [scope], rows, {PAGE_ID}, RECOGNIZED, "edited")
        assert cmd.action == "upsert"
        assert cmd.scopes == (scope,)

    def test_all_roots_deactivated_deletes(self, scope: str) -> None:
        rows = [_row("space", SPACE_ID, ALL_SCOPES, is_active=False)]
        cmd = decide_command(PAGE_ID, _meta(), [scope], rows, {PAGE_ID}, RECOGNIZED, "sweep_drift")
        assert cmd.action == "delete"


def test_unknown_tag_is_not_a_scope() -> None:
    cmd = decide_command(
        PAGE_ID, _meta(), ["totally-unknown-label"], [], {PAGE_ID}, RECOGNIZED, "edited"
    )
    assert cmd.action == "delete"


def test_shared_page_keeps_multiple_recognized_scopes() -> None:
    two = ALL_SCOPES[:2]
    scopes = resolve_scopes(_meta(), two, [], {PAGE_ID}, RECOGNIZED)
    assert scopes == set(two)
    assert should_ingest(_meta(), two, [], {PAGE_ID}, RECOGNIZED) is True


def test_sweep_and_webhook_agree_for_same_state() -> None:
    rows = [_row("space", SPACE_ID, ALL_SCOPES)]
    a = decide_command(PAGE_ID, _meta(), [ALL_SCOPES[0]], rows, {PAGE_ID}, RECOGNIZED, "edited")
    b = decide_command(
        PAGE_ID, _meta(), [ALL_SCOPES[0]], rows, {PAGE_ID}, RECOGNIZED, "sweep_drift"
    )
    assert a.action == b.action
    assert a.scopes == b.scopes
