"""The trigger/ingestion split, tested by layer (docs/plans/confluence-trigger-layer.md).

* **Trigger** tests use a fake IngestionSink and assert only the emitted :class:`SyncCommand` —
  they must pass even if ingestion is swapped out entirely.
* **Ingestion** tests feed :class:`SyncCommand`s straight to ``apply_sync_command`` — no webhook,
  no sweep.
* **Contract** test: a command produced by the trigger's decision is accepted and correctly
  applied by ingestion — the two halves fit.
"""

from __future__ import annotations

import pytest

from app.features.confluence_sync.application.sync_service import (
    handle_sync_page,
)
from app.features.ingestion import apply_sync_command  # test-exempt from the forbidden edge
from app.platform.clients import ConfluenceGateway
from app.platform.config import Settings
from app.shared.sync_command import SyncCommand, SyncOutcome
from schema.engine import session_scope
from schema.models import PageSource, SourceScope

from ._helpers import active_child_chunks, index_page, page_row_counts, read

pytestmark = pytest.mark.db

_PAGE = 1001  # space 100; parent of 1002 in the fixture corpus
_CHILD = 1002


class _CapturingSink:
    """A fake IngestionSink: records every command, does no ingestion work."""

    def __init__(self) -> None:
        self.commands: list[SyncCommand] = []

    def __call__(
        self, session, cmd: SyncCommand, gateway: ConfluenceGateway, settings: Settings
    ) -> SyncOutcome:
        self.commands.append(cmd)
        return SyncOutcome(action="captured", classes=[], page_id=cmd.page_id)


def _add_scope_root(root_type: str, root_id: str, tags: list[str]) -> None:
    with session_scope() as s:
        s.add(SourceScope(root_type=root_type, root_id=root_id, tags=tags))


# --- Trigger layer (fake sink) ---------------------------------------------------------------


def test_tagged_page_emits_upsert_with_authoritative_scope(gateway, settings):
    gateway.set_labels(_PAGE, ["toast-general"])
    sink = _CapturingSink()
    with session_scope() as s:
        handle_sync_page(
            s, page_id=_PAGE, gateway=gateway, settings=settings, reason="tag_added", sink=sink
        )
    assert len(sink.commands) == 1
    cmd = sink.commands[0]
    assert (cmd.action, cmd.scopes, cmd.reason) == ("upsert", ("toast-general",), "tag_added")


def test_untagged_page_emits_delete(gateway, settings):
    gateway.set_labels(_PAGE, ["some-unrelated-label"])
    sink = _CapturingSink()
    with session_scope() as s:
        handle_sync_page(s, page_id=_PAGE, gateway=gateway, settings=settings, sink=sink)
    assert sink.commands[0].action == "delete"
    assert sink.commands[0].scopes == ()


def test_space_row_authorizes_tagged_page_original_bug(gateway, settings):
    """The 'Mews Page 2 never ingested' fix: a tagged page under no page-root is authorized by a
    space-level source_scope row (the operator's live fix) → upsert with its own label's scope."""
    _add_scope_root("space", "100", ["obi-general", "mews-general", "toast-general"])
    gateway.set_labels(_PAGE, ["mews-general"])
    sink = _CapturingSink()
    with session_scope() as s:
        handle_sync_page(
            s,
            page_id=_PAGE,
            gateway=gateway,
            settings=settings,
            reason="sweep_discovery",
            sink=sink,
        )
    cmd = sink.commands[0]
    assert cmd.action == "upsert"
    assert cmd.scopes == ("mews-general",)  # intersection: only the page's own label, not all 3


def test_tagged_page_outside_coverage_in_scoped_space_deletes(gateway, settings):
    # A page-root covering only the child 1002 scopes the space; the parent 1001 is uncovered.
    _add_scope_root("page", str(_CHILD), ["mews-general"])
    gateway.set_labels(_PAGE, ["mews-general"])
    sink = _CapturingSink()
    with session_scope() as s:
        handle_sync_page(s, page_id=_PAGE, gateway=gateway, settings=settings, sink=sink)
    assert sink.commands[0].action == "delete"


def test_gone_page_emits_delete(gateway, settings):
    gateway.hide(_PAGE)
    sink = _CapturingSink()
    with session_scope() as s:
        handle_sync_page(
            s, page_id=_PAGE, gateway=gateway, settings=settings, reason="page_gone", sink=sink
        )
    assert sink.commands[0].action == "delete"


# --- Ingestion layer (direct SyncCommands) ---------------------------------------------------


def test_apply_upsert_stamps_exactly_the_command_scopes(gateway, settings):
    gateway.set_labels(_PAGE, ["ignored-by-ingestion"])  # ingestion never re-derives membership
    gateway.set_version(_PAGE, 1)
    cmd = SyncCommand(page_id=_PAGE, action="upsert", scopes=("toast-general",), reason="edited")
    with session_scope() as s:
        outcome = apply_sync_command(s, cmd, gateway, settings)
    assert outcome.action == "indexed"
    children = active_child_chunks(_PAGE)
    assert children and all(set(c.tags) == {"toast-general"} for c in children)
    with read() as s:
        assert set(s.get(PageSource, _PAGE).tags) == {"toast-general"}


def test_apply_delete_hard_purges(gateway, settings):
    index_page(gateway, settings, _PAGE, version=1)
    assert active_child_chunks(_PAGE)
    cmd = SyncCommand(page_id=_PAGE, action="delete", scopes=(), reason="page_gone")
    with session_scope() as s:
        outcome = apply_sync_command(s, cmd, gateway, settings)
    assert outcome.action == "purged"
    assert page_row_counts(_PAGE) == {
        "chunk": 0,
        "document_version": 0,
        "document": 0,
        "page_source": 0,
        "page_restriction": 0,
    }


def test_apply_delete_on_unindexed_is_skipped(gateway, settings):
    cmd = SyncCommand(page_id=_PAGE, action="delete", scopes=(), reason="tag_removed")
    with session_scope() as s:
        outcome = apply_sync_command(s, cmd, gateway, settings)
    assert outcome.action == "skipped"  # idempotent no-op, nothing was indexed


# --- Contract: the two halves fit ------------------------------------------------------------


def test_contract_trigger_command_applied_by_ingestion(gateway, settings):
    """A command produced by the trigger's decision is accepted and applied by ingestion, and the
    scopes stamped equal the scopes the trigger decided."""
    _add_scope_root("space", "100", ["obi-general", "mews-general"])
    gateway.set_labels(_PAGE, ["mews-general"])
    gateway.set_version(_PAGE, 1)
    captured: list[SyncCommand] = []

    def spy_sink(session, cmd, gateway_, settings_):
        captured.append(cmd)
        return apply_sync_command(session, cmd, gateway_, settings_)

    with session_scope() as s:
        outcome = handle_sync_page(
            s, page_id=_PAGE, gateway=gateway, settings=settings, sink=spy_sink
        )

    assert outcome.action == "indexed"
    assert captured[0].action == "upsert"
    assert captured[0].scopes == ("mews-general",)
    with read() as s:
        assert set(s.get(PageSource, _PAGE).tags) == set(captured[0].scopes)
