"""Worker + sync-service guarantees: first index, atomic re-index, version guard, metadata-only,
delete/deactivate."""

from __future__ import annotations

import inspect
from datetime import UTC, datetime

import pytest
from sqlalchemy import event, func, select, update
from sqlalchemy.orm import Session as SASession

from app.features.confluence_sync.application.event_service import (
    JOB_DELETE_PAGE,
    JOB_RECONCILE_SPACE,
    JOB_SYNC_PAGE,
)
from app.features.confluence_sync.application.sync_service import SyncOutcome, target_versions
from app.features.confluence_sync.application.worker import HANDLERS, drain, run_once
from app.features.ingestion import build_ingestion_services, decide_body_fetch, get_local_state
from app.platform.db.engine import session_scope
from app.platform.db.enums import DocState, JobStatus, PageStatus
from app.platform.db.models import Chunk, DocumentVersion, Job, PageRestriction, PageSource

from ._helpers import (
    active_child_chunks,
    active_version,
    active_versions_count,
    child_chunks_for_version,
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


def test_vd_swap_new_chunks_and_vectors_inserted_inactive(gateway, settings):
    """panel vd-swap · substep p0-s0_5-reg-the-vector-database
    Every new chunk row a rebuild flushes to the database — parent and child, vector included —
    reaches the database with is_active=False; nothing new is ever written already-live. Captured
    via a before_flush hook: at flush time (before the later pointer-flip UPDATE runs), every
    pending Chunk the rebuild adds already carries is_active=False."""
    index_page(gateway, settings, 1001, version=1)  # baseline v1, outside the capture window

    captured_flags: list[bool] = []

    def _capture_before_flush(session, flush_context, instances):
        for obj in session.new:
            if isinstance(obj, Chunk):
                captured_flags.append(obj.is_active)

    event.listen(SASession, "before_flush", _capture_before_flush)
    try:
        gateway.set_version(1001, 3)
        enqueue_sync(1001, 3, key="sync:1001:v3-inactive-insert")
        result = run_once(gateway, settings, owner="test")
    finally:
        event.remove(SASession, "before_flush", _capture_before_flush)

    assert result is not None and result.status == "succeeded"
    assert captured_flags, "expected the rebuild to flush new Chunk rows"
    assert all(flag is False for flag in captured_flags)


def test_vd_swap_pointer_flip_is_one_atomic_transaction(gateway, settings, monkeypatch):
    """panel vd-swap · substep p0-s0_5-reg-the-vector-database
    A failure that happens after stage_and_activate has already deactivated the old version and
    activated the new one, but before the job's own transaction commits, leaves the old version
    still active and its chunks still active: deactivating the old and activating the new are one
    transaction, not two independent writes -- either both land or neither does."""
    import app.features.confluence_sync.application.worker as worker_module

    index_page(gateway, settings, 1001, version=1)
    v1 = active_version(1001)
    assert v1 is not None and v1.cf_version == 1
    v1_child_ids = {c.id for c in active_child_chunks(1001)}
    assert v1_child_ids

    def boom(*args, **kwargs):
        raise RuntimeError("boom-after-activate")

    # complete_job runs in run_once's "transaction 2", right after the handler (which already ran
    # stage_and_activate's pointer flip in-session) -- same still-uncommitted transaction. Forcing
    # the raise here, unconditionally, proves the flip and the commit are one unit regardless of
    # whether anything else (like a restriction change) happens to run in between -- the same
    # technique test_i1_handle_and_complete_roll_back_together_on_handler_failure uses above,
    # applied here to an existing active version instead of a first index, so the flip itself (not
    # just the first insert) is what gets proven atomic.
    monkeypatch.setattr(worker_module, "complete_job", boom)

    gateway.set_version(1001, 3)
    enqueue_sync(1001, 3, key="sync:1001:atomic-flip-fail")
    result = run_once(gateway, settings, owner="test")

    assert result is not None and result.status == "failed"
    assert result.error is not None and "boom-after-activate" in result.error

    # the old version's flip-off and the new version's flip-on rolled back together: v1 is still
    # the one and only active version, its chunks are still active, and no v3 row survived.
    after = active_version(1001)
    assert after is not None and after.id == v1.id and after.cf_version == 1
    assert count_versions(1001) == 1
    assert {c.id for c in active_child_chunks(1001)} == v1_child_ids


def test_vd_swap_old_vectors_go_inactive_at_once_but_rows_persist(gateway, settings):
    """panel vd-swap · substep p0-s0_5-reg-the-vector-database
    The instant a rebuild activates, the superseded version's child rows leave the live
    (is_active) set at once -- same transaction, no lag -- yet the rows and their vectors are not
    deleted: they persist, same ids, embeddings intact, until i4-gc's own two-more-versions
    retention window reaps them (proven separately by test_versioning_gc.py; not re-proven here)."""
    index_page(gateway, settings, 1001, version=1)
    v1_id = active_version(1001).id

    before = child_chunks_for_version(v1_id)
    assert before
    assert all(c.is_active for c in before)
    assert all(c.embedding is not None for c in before)

    gateway.set_version(1001, 3)
    enqueue_sync(1001, 3, key="sync:1001:v3-old-inactive")
    result = run_once(gateway, settings, owner="test")
    assert result is not None and result.status == "succeeded"

    after = child_chunks_for_version(v1_id)
    # same rows, still carrying their vectors, but no longer in the live/HNSW set
    assert {c.id for c in after} == {c.id for c in before}
    assert all(c.is_active is False for c in after)
    assert all(c.embedding is not None for c in after)


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


def test_rt3_duplicate_restriction_principal_stores_one_row_per_account_id(gateway, settings):
    """panel r3-groups · substep p0-s0_5-reg-retrieval-stage-3
    Stored: one page_restriction row per (page, account id) — an account id that appears more
    than once in the resolved restriction list (e.g. an individually-restricted user who is also
    a member of a restricted group, so group expansion would otherwise add it a second time)
    persists as exactly one row, not one per source it came from.
    """
    # `set_restrictions` injects an already-resolved principal list directly (bypassing group
    # expansion itself, which is covered separately in platform/clients/tests/
    # test_confluence_client.py) — the duplicate here stands in for what expansion's own union
    # already guards against upstream (_resolve_read_restriction), proving the storage layer
    # (_replace_restrictions) does not blindly insert one row per list entry.
    gateway.set_restrictions(2002, ["acct-carol", "acct-carol", "acct-dave"])
    index_page(gateway, settings, 2002, version=1)

    assert restricted_principals(2002) == {"acct-carol", "acct-dave"}
    with read() as s:
        row_count = s.execute(
            select(func.count()).select_from(PageRestriction).where(PageRestriction.page_id == 2002)
        ).scalar_one()
    assert row_count == 2  # one row per distinct account id, not three


def test_permission_change_is_metadata_only(gateway, settings):
    """panel i2-meta · a label/permission-only change updates in place, active version unchanged."""
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


def test_d_page_restriction_unchanged_hash_leaves_rows_untouched(gateway, settings):
    """panel d-page_restriction · substep p0-s0_5-reg-the-relational-database
    page_restriction is written by confluence_sync as delete-plus-insert ONLY when
    access_scope_hash changes: a metadata-only resync driven by an unrelated change (a label
    swap, not a permission change) must leave the page's restriction rows byte-for-byte
    untouched, not rewrite them with an identical value. Proved by planting a sentinel
    `created_at` on the existing rows directly (bypassing the server default) and asserting it
    survives the resync -- a delete+insert would reset it to the write's own timestamp."""
    index_page(gateway, settings, 2002, version=1)
    assert restricted_principals(2002) == {"acct-carol", "acct-dave", "acct-erin"}

    sentinel = datetime(2000, 1, 1, tzinfo=UTC)
    with session_scope() as s:
        s.execute(
            update(PageRestriction)
            .where(PageRestriction.page_id == 2002)
            .values(created_at=sentinel)
        )

    # A label change (not a restriction change) still triggers a metadata-only sync — proving
    # the guard is keyed on access_scope_hash specifically, not on "some metadata changed".
    gateway.set_labels(2002, ["finance", "confidential", "extra-marker"])
    enqueue_sync(2002, 1, key="sync:2002:label-only-restrictions-preserved")
    result = run_once(gateway, settings, owner="test")

    assert result is not None
    assert isinstance(result.outcome, SyncOutcome)
    assert result.outcome.action == "metadata_only"
    assert restricted_principals(2002) == {"acct-carol", "acct-dave", "acct-erin"}  # unchanged
    with read() as s:
        stamps = (
            s.execute(select(PageRestriction.created_at).where(PageRestriction.page_id == 2002))
            .scalars()
            .all()
        )
    assert stamps and all(ts == sentinel for ts in stamps)  # untouched: no delete+insert fired


def test_i2_fetch_always_refetches_meta_labels_restrictions_attachments_even_when_unchanged(
    gateway, settings
):
    """panel i2-fetch · substep 0.5.2
    Every sync unconditionally re-fetches page meta, labels, restrictions and the attachment
    list -- even a true no-op resync where nothing at all changed -- because a change can only
    be detected by comparing against a fresh fetch. Only the body fetch is conditional on
    decide_body_fetch (proved separately by
    test_in2_body_fetch_skipped_when_unchanged_required_on_version_bump)."""
    index_page(gateway, settings, 1001, version=3)

    calls = {"meta": 0, "labels": 0, "restrictions": 0, "attachments": 0}
    orig_meta = gateway.get_page_meta
    orig_labels = gateway.get_labels
    orig_restrictions = gateway.get_restrictions
    orig_attachments = gateway.get_attachments

    def spy_meta(page_id):
        calls["meta"] += 1
        return orig_meta(page_id)

    def spy_labels(page_id):
        calls["labels"] += 1
        return orig_labels(page_id)

    def spy_restrictions(page_id):
        calls["restrictions"] += 1
        return orig_restrictions(page_id)

    def spy_attachments(page_id):
        calls["attachments"] += 1
        return orig_attachments(page_id)

    gateway.get_page_meta = spy_meta
    gateway.get_labels = spy_labels
    gateway.get_restrictions = spy_restrictions
    gateway.get_attachments = spy_attachments

    enqueue_sync(1001, 3, key="sync:1001:noop-resync")  # same version, nothing changed at all
    result = run_once(gateway, settings, owner="test")

    assert result is not None
    assert isinstance(result.outcome, SyncOutcome) and result.outcome.action == "no_change"
    assert calls == {"meta": 1, "labels": 1, "restrictions": 1, "attachments": 1}


def test_i2_inplace_writes_page_source_and_every_active_chunk(gateway, settings):
    """panel i2-inplace · substep 0.5.2
    A metadata-only update writes page_source's own access_scope_hash column -- not only its
    chunks -- and every active chunk of the page, not just the first of several."""
    index_page(gateway, settings, 2002, version=1)
    before_chunks = active_child_chunks(2002)
    assert len(before_chunks) >= 2, "need >1 active chunk to prove 'every', not just the first"
    scope_before = before_chunks[0].access_scope
    with read() as s:
        ps_before = s.get(PageSource, 2002)
        assert ps_before is not None
        hash_before = ps_before.access_scope_hash

    gateway.set_restrictions(2002, ["acct-brand-new-person"])  # no version bump
    enqueue_sync(2002, 1, key="sync:2002:inplace-writes")
    result = run_once(gateway, settings, owner="test")

    assert result is not None
    assert isinstance(result.outcome, SyncOutcome) and result.outcome.action == "metadata_only"
    with read() as s:
        ps_after = s.get(PageSource, 2002)
        assert ps_after is not None
        assert ps_after.access_scope_hash != hash_before  # page_source row itself was written

    after_chunks = active_child_chunks(2002)
    assert len(after_chunks) == len(before_chunks)
    assert all(c.access_scope != scope_before for c in after_chunks)  # EVERY chunk, not just one


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


def test_i1_handle_handler_set_covers_sync_delete_reconcile():
    """panel i1-handle · substep 0.5.2
    HANDLERS wires exactly the three job types the panel names -- sync_page, delete_page,
    reconcile_space -- no more, no fewer."""
    assert set(HANDLERS.keys()) == {JOB_SYNC_PAGE, JOB_DELETE_PAGE, JOB_RECONCILE_SPACE}


def test_i1_handle_and_complete_roll_back_together_on_handler_failure(
    gateway, settings, monkeypatch
):
    """panel i1-handle · substep 0.5.2
    The index mutation and the succeeded status transition commit together, or neither does: a
    handler that raises after it has already staged the new version/chunks in-session must leave
    the job failed (not succeeded), complete_job never having run, and no partial index change
    persisted."""
    import app.features.confluence_sync.application.sync_service as sync_service

    # stage_and_activate (the real index mutation: new DocumentVersion + active chunks) runs
    # first in handle_sync_page's rebuild branch; _replace_restrictions runs right after it, still
    # inside the same (uncommitted) transaction 2. Raising here proves the earlier, already
    # flushed mutation is rolled back too, not just skipped.
    def boom(*args, **kwargs):
        raise RuntimeError("boom-mid-handler")

    monkeypatch.setattr(sync_service, "_replace_restrictions", boom)

    enqueue_sync(1001, 3, key="sync:1001:atomic-fail")
    result = run_once(gateway, settings, owner="test")

    assert result is not None and result.status == "failed"
    assert result.error is not None and "boom-mid-handler" in result.error

    # no partial index mutation persisted: no DocumentVersion, no active chunks for the page
    assert active_version(1001) is None
    assert count_versions(1001) == 0
    assert active_child_chunks(1001) == []

    # complete_job never ran: the job itself carries the failure, not success
    with read() as s:
        job = s.get(Job, result.job_id)
        assert job is not None
        assert job.status == JobStatus.failed
        assert job.last_error is not None and "boom-mid-handler" in job.last_error


def test_i1_handle_drain_default_cap_is_100():
    """panel i1-handle · substep p0-s0_5-reg-ingestion-stage-1
    drain()'s max_jobs defaults to exactly 100 -- the specific number the panel names, not just
    the cap mechanism (test_i1_handle_drain_stops_at_max_jobs_cap proves the mechanism with an
    overridden, cheaper value)."""
    assert inspect.signature(drain).parameters["max_jobs"].default == 100


def test_i1_handle_drain_stops_at_max_jobs_cap(gateway, settings):
    """panel i1-handle · substep 0.5.2
    drain() processes at most max_jobs jobs per tick even when more jobs remain queued -- the
    cap bounds one tick, it does not drain the whole backlog."""
    page_ids = [1001, 1002, 1003, 2001, 2002]
    for i, page_id in enumerate(page_ids):
        gateway.set_version(page_id, 1)
        enqueue_sync(page_id, 1, key=f"drain-cap:{i}")

    results = drain(gateway, settings, owner="test", max_jobs=3)

    assert len(results) == 3
    with read() as s:
        pending = s.execute(
            select(func.count(Job.id)).where(Job.status == JobStatus.pending)
        ).scalar_one()
    assert pending == len(page_ids) - 3
