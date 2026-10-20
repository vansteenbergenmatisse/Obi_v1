"""ADR-routing-labels-sole-content-axis Path B: ``setup_supabase.check_deploy_readiness`` must gate
the reader path.

Under Path B (migration 0018 ``retire_knowledge_scope_rls``) the fail-closed tenant fence is NOT the
retired knowledge-scope RESTRICTIVE policies — it is the PERMISSIVE source policy plus RLS ENABLEd:

* ``chunk.chunk_source_read`` — PERMISSIVE, FOR SELECT, keyed on ``app.allowed_sources`` (lock 1,
  source/company isolation, never-bend rule 1). A single PERMISSIVE SELECT policy on an RLS-enabled
  table is deny-by-default: the non-owner ``rag_reader`` sees only rows the policy admits, and an
  unset GUC admits none.
* ``curated_knowledge_entry.curated_knowledge_entry_reader_read`` — PERMISSIVE, FOR SELECT TO
  ``rag_reader`` (created by ``schema.apply_reader_rls``; applied in production by
  ``setup_supabase.py provision-reader``).

``alembic upgrade head`` + ``provision-reader`` put this fence in place, but nothing otherwise
blocks a deploy where the source policy is missing or RLS is disabled — the tenant axis then
silently fails OPEN. This check reads the catalog and refuses the deploy unless both policies are
present (PERMISSIVE, FOR SELECT) and RLS is ENABLEd on each table; these tests are the deterministic
proof of that gate. The retired ``chunk_scope_read`` / ``curated_knowledge_entry_scope_read``
policies are NOT asserted (0018 dropped them, ADR-routing-labels-sole-content-axis); the
``chunk_labels_read`` routing axis is
reported but, being fail-OPEN by design, never blocks the deploy.

Each test runs inside a single connection's transaction and rolls back, so no committed schema
change touches the session-scoped harness. The harness (``app.tests.db_harness``) applies
``apply_chunk_rls`` (``chunk_source_read``) at session scope but deliberately not
``apply_reader_rls`` — so each test that needs the curated reader policy applies it in-transaction
and rolls it back. ``check_deploy_readiness`` takes that open connection so the whole set-up +
assertion + rollback stays in one transaction (the db-test rollback rule).
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

import scripts.setup_supabase as setup_supabase
from schema import engine as engine_mod
from schema import schema

pytestmark = (
    pytest.mark.db
)  # substep 0.5.1: real local Postgres via this dir's session-scoped conftest


def test_deploy_readiness_reports_ready_under_path_b(capsys) -> None:
    """ADR-routing-labels-sole-content-axis Path B — source fence + curated reader policy in place
    -> gate is READY (rc 0).

    Protects the live-isolation panel's deploy gate on a correctly-migrated Path B store (0018
    applied): ``chunk_source_read`` is applied session-wide by the harness; the curated reader
    policy is applied here in-transaction (as ``provision-reader`` does in production), then rolled
    back. The check must see both policies (PERMISSIVE/SELECT, RLS ENABLEd) and pass.
    """
    conn = engine_mod.get_engine().connect()
    try:
        # apply_reader_rls ENABLEs RLS on curated_knowledge_entry and creates the PERMISSIVE
        # curated_knowledge_entry_reader_read policy (TO rag_reader) — the Path B curated posture.
        schema.apply_reader_rls(conn)

        rc = setup_supabase.check_deploy_readiness(conn=conn)
        out = capsys.readouterr().out

        assert rc == 0, out
        assert (
            "chunk.chunk_source_read: present=True permissive_select=True rls_enabled=True" in out
        )
        assert (
            "curated_knowledge_entry.curated_knowledge_entry_reader_read: present=True "
            "permissive_select=True rls_enabled=True" in out
        )
        assert "reader path safe to expose" in out
    finally:
        conn.rollback()  # discard the reader policies — harness left exactly as the conftest set it
        conn.close()


def test_deploy_readiness_fails_when_source_policy_absent(capsys) -> None:
    """ADR-routing-labels-sole-content-axis Path B — a missing ``chunk_source_read`` MUST block the
    deploy (non-zero + names).

    Reproduces a store whose lock-1 source/company fence was never applied or was dropped: with the
    curated reader policy present (so curated is NOT the gap), ``drop_chunk_rls`` removes
    ``chunk_source_read`` and disables chunk RLS inside this transaction, then rolls back. The gate
    must refuse — without the source policy the tenant axis fails OPEN (never-bend rule 1).
    """
    conn = engine_mod.get_engine().connect()
    try:
        schema.apply_reader_rls(conn)  # curated half passes; isolate the chunk-fence gap
        schema.drop_chunk_rls(conn)  # drop chunk_source_read AND disable chunk RLS

        rc = setup_supabase.check_deploy_readiness(conn=conn)
        captured = capsys.readouterr()

        assert rc != 0, captured.out
        assert "chunk_source_read' on 'chunk' is ABSENT" in captured.err
        assert "row security is NOT enabled on 'chunk'" in captured.err
        assert "Do NOT expose the reader path" in captured.err
    finally:
        conn.rollback()  # restores chunk_source_read (DROP never committed) — harness intact
        conn.close()


def test_deploy_readiness_fails_when_chunk_rls_disabled(capsys) -> None:
    """ADR-routing-labels-sole-content-axis Path B — chunk RLS DISABLED MUST block the deploy even
    when the policy still exists.

    A PERMISSIVE policy is inert if row security is off (every row is returned), so the gate asserts
    ``relrowsecurity`` independently of policy presence. Here ``chunk_source_read`` stays present
    but RLS is turned off on ``chunk``; the gate must still refuse. Rolled back.
    """
    conn = engine_mod.get_engine().connect()
    try:
        schema.apply_reader_rls(conn)  # curated half passes; isolate the RLS-disabled signal
        conn.execute(text("ALTER TABLE chunk DISABLE ROW LEVEL SECURITY"))

        rc = setup_supabase.check_deploy_readiness(conn=conn)
        captured = capsys.readouterr()

        assert rc != 0, captured.out
        assert "row security is NOT enabled on 'chunk'" in captured.err
        # The policy itself is still present — the failure is the disabled RLS, not a gone policy.
        assert "chunk.chunk_source_read: present=True" in captured.out
        assert "Do NOT expose the reader path" in captured.err
    finally:
        conn.rollback()
        conn.close()


def test_deploy_readiness_fails_when_curated_reader_policy_absent(capsys) -> None:
    """ADR-routing-labels-sole-content-axis Path B — a missing curated reader policy MUST block the
    deploy (non-zero + names).

    The harness never applies ``apply_reader_rls``, so without it ``curated_knowledge_entry`` has
    no reader policy and RLS off — the exact state of a store where ``provision-reader`` never ran.
    The gate must refuse: the curated layer is part of the reader path and must be fenced first.
    """
    conn = engine_mod.get_engine().connect()
    try:
        # Deliberately do NOT apply_reader_rls — curated reader policy absent, curated RLS off.
        rc = setup_supabase.check_deploy_readiness(conn=conn)
        captured = capsys.readouterr()

        assert rc != 0, captured.out
        assert (
            "curated_knowledge_entry_reader_read' on 'curated_knowledge_entry' is ABSENT"
            in captured.err
        )
        assert "Do NOT expose the reader path" in captured.err
    finally:
        conn.rollback()
        conn.close()
