"""Worker + sync-service guarantees: first index, atomic re-index, version guard, metadata-only,
delete/deactivate."""

from __future__ import annotations

import pytest

from app.features.confluence_sync.application.sync_service import target_versions
from app.features.confluence_sync.application.worker import run_once
from app.features.ingestion import build_ingestion_services, decide_body_fetch, get_local_state
from app.platform.db.enums import DocState, PageStatus
from app.platform.db.models import DocumentVersion, PageSource

from ._helpers import (
    active_child_chunks,
    active_version,
    active_versions_count,
    count_versions,
    enqueue_delete,
    enqueue_sync,
    index_page,
    read,
    restricted_principals,
)

pytestmark = (
    pytest.mark.db
)  # substep 0.5.1: real local Postgres via this dir's session-scoped conftest


def test_first_index_creates_active_version_and_chunks(gateway, settings):
    index_page(gateway, settings, 1001, version=3)

    av = active_version(1001)
    assert av is not None
    assert av.cf_version == 3
    assert active_versions_count(1001) == 1
    chunks = active_child_chunks(1001)
    assert len(chunks) > 0
    with read() as s:
        assert s.get(PageSource, 1001) is not None


def test_content_change_swaps_version_atomically(gateway, settings):
    index_page(gateway, settings, 1001, version=1)
    assert active_version(1001).cf_version == 1
    assert count_versions(1001) == 1

    gateway.set_version(1001, 3)
    enqueue_sync(1001, 3, key="sync:1001:v3")
    result = run_once(gateway, settings, owner="test")

    assert result is not None and result.status == "succeeded"
    assert result.outcome.action == "indexed"
    assert active_version(1001).cf_version == 3
    assert count_versions(1001) == 2  # old retained for rollback
    assert active_versions_count(1001) == 1  # exactly one active — no mixed versions
    # every active child chunk belongs to the new active version
    new_id = active_version(1001).id
    assert {c.doc_version_id for c in active_child_chunks(1001)} == {new_id}


def test_contextualization_version_bump_rebuilds_at_same_cf_version(gateway, settings):
    """A pipeline-config bump (parser/chunker/contextualization version) must force a rebuild at the
    SAME cf_version without colliding on uq_document_version_idem (PLAN 3b/3c regression).

    Before the constraint was widened to include the pipeline-version columns, a config-only bump
    tried to create a second document_version row at the same (document_id, cf_version,
    retrieval_schema_version, embedding_model), raised IntegrityError, and the re-embed silently
    failed — pinning the corpus to the old (e.g. meta-refusal-poisoned) contextualization. Observed
    live on the obi-*-test pages: Toast/Mews stuck on contextualization_version=1."""
    index_page(gateway, settings, 1001, version=1)
    assert active_version(1001).contextualization_version == settings.contextualization_version
    assert count_versions(1001) == 1

    bumped = settings.model_copy(
        update={"contextualization_version": settings.contextualization_version + 1}
    )
    enqueue_sync(1001, 1, key="sync:1001:ctxbump")  # SAME cf_version — only the config changed
    result = run_once(gateway, bumped, owner="test")

    assert result is not None and result.status == "succeeded", result
    assert result.outcome.action == "indexed"  # config change routes to a rebuild, not no_change
    assert active_version(1001).contextualization_version == bumped.contextualization_version
    assert count_versions(1001) == 2  # new version created, old retained for rollback
    assert active_versions_count(1001) == 1  # exactly one active — no mixed versions


def test_version_guard_drops_stale_update(gateway, settings):
    index_page(gateway, settings, 1001, version=3)
    assert count_versions(1001) == 1

    # a delayed/out-of-order delivery carrying an older version; source is still at v3
    enqueue_sync(1001, 2, key="sync:1001:stale-v2")
    result = run_once(gateway, settings, owner="test")

    assert result.status == "succeeded"
    assert result.outcome.action == "no_change"
    assert count_versions(1001) == 1  # no downgrade, no new version


def test_in2_body_fetch_skipped_when_unchanged_required_on_version_bump(gateway, settings):
    """panel i2-fetch · substep 0.5.2
    decide_body_fetch must skip the body fetch when the served version has not moved past what
    is already indexed (and the pipeline config is unchanged), and must require it once a newer
    revision exists -- asserted against the real decision function, not a re-implementation."""
    index_page(gateway, settings, 1001, version=3)

    services = build_ingestion_services(settings)
    target = target_versions(settings, embedding_model=services.embedding_model)
    with read() as s:
        local = get_local_state(s, 1001)
    assert local is not None and local.current_cf_version == 3

    meta = gateway.get_page_meta(1001)
    assert meta is not None and meta.version_number == 3

    assert decide_body_fetch(local, meta, target) is False  # same version served again

    newer_meta = meta.model_copy(update={"version_number": 4})
    assert decide_body_fetch(local, newer_meta, target) is True  # a newer revision exists


def test_first_index_persists_restrictions(gateway, settings):
    """PLAN 4.3: the real principal list, not just its hash, lands in page_restriction.

    Fixture `page-2002.json` carries a resolvable `acct-carol` user restriction alongside
    `grp-hr`/`grp-finance` group restrictions. Per PLAN 4.6.2, group membership is expanded via
    `group_members.json` (`grp-hr` -> `acct-dave`, `grp-finance` -> `acct-erin`) and unioned into
    the persisted set — the user principal is not a bypass of that expansion, both apply. The
    fail-closed sentinel PLAN 4.6.1 introduced for a page restricted ONLY by an unresolvable group
    is covered separately by
    `platform/clients/tests/test_confluence_client.py::test_group_only_restriction_fails_closed`.
    """
    index_page(gateway, settings, 2002, version=1)
    assert restricted_principals(2002) == {"acct-carol", "acct-dave", "acct-erin"}


def test_permission_change_is_metadata_only(gateway, settings):
    index_page(gateway, settings, 2002, version=1)
    before = active_child_chunks(2002)
    assert before, "expected active chunks after first index"
    scope_before = before[0].access_scope
    assert restricted_principals(2002) == {"acct-carol", "acct-dave", "acct-erin"}

    gateway.set_restrictions(2002, ["acct-brand-new-person"])  # no version bump
    enqueue_sync(2002, 1, key="sync:2002:perm")
    result = run_once(gateway, settings, owner="test")

    assert result.outcome.action == "metadata_only"
    assert count_versions(2002) == 1  # NO re-embed / new version
    after = active_child_chunks(2002)
    assert after and after[0].access_scope != scope_before  # scope propagated to chunks
    # PLAN 4.3: the persisted ACL is a full replace, not an append — the old principal is gone
    assert restricted_principals(2002) == {"acct-brand-new-person"}


def test_dropped_restriction_leaves_page_unrestricted(gateway, settings):
    """PLAN 4.3: clearing a page's restrictions removes its page_restriction rows entirely."""
    index_page(gateway, settings, 2002, version=1)
    assert restricted_principals(2002)  # starts restricted

    gateway.set_restrictions(2002, [])  # no version bump
    enqueue_sync(2002, 1, key="sync:2002:perm-cleared")
    result = run_once(gateway, settings, owner="test")

    assert result.outcome.action == "metadata_only"
    assert restricted_principals(2002) == set()  # unrestricted now (no rows, not empty-set rows)


def test_delete_deactivates_page(gateway, settings):
    index_page(gateway, settings, 1001, version=3)
    assert active_child_chunks(1001)

    enqueue_delete(1001, "trashed", key="del:1001")
    result = run_once(gateway, settings, owner="test")

    assert result.outcome.action == "deactivated"
    assert active_child_chunks(1001) == []
    with read() as s:
        assert s.get(PageSource, 1001).page_status == PageStatus.trashed


@pytest.mark.xfail(strict=True, reason="tg-deactivate is Planned; built in 2.2.4")
def test_delete_marks_the_active_version_superseded(gateway, settings):
    """panel tg-deactivate · substep 2.5
    Does: page_status updated, active version superseded, chunks inactive — deactivate_page must
    flip the deactivated page's DocumentVersion.state, not only the page and its chunks."""
    index_page(gateway, settings, 1001, version=3)
    deactivated_version_id = active_version(1001).id

    enqueue_delete(1001, "trashed", key="del:1001:supersede")
    result = run_once(gateway, settings, owner="test")

    assert result.outcome.action == "deactivated"
    with read() as s:
        dv = s.get(DocumentVersion, deactivated_version_id)
        assert dv.state == DocState.superseded
