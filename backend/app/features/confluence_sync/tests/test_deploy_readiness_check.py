"""MIG-02 / ADR-0014: ``setup_supabase.check_deploy_readiness`` must gate the reader path.

Migration 0010 installs the RESTRICTIVE customer-scope RLS policies (``chunk_scope_read`` on
``chunk``, ``curated_knowledge_entry_scope_read`` on ``curated_knowledge_entry``) that are Obi's
fail-closed tenant backstop. ``alembic upgrade head`` applies them, but nothing otherwise blocks a
deploy where head < 0010 or a downgrade left them dropped — the customer axis then silently fails
OPEN (GAP MIG-02). This check reads the catalog and refuses the deploy unless both policies are
present (AS RESTRICTIVE, FOR SELECT) and RLS is ENABLEd on each table; these tests are the
deterministic proof of that gate, mapping to the same live isolation panel as the source-axis
verify-isolation checks.

Both tests run inside a single connection's transaction and roll back, so no committed schema change
touches the session-scoped harness (this dir's conftest applies ``chunk_scope_read`` at session
scope, but not the curated analogue). ``check_deploy_readiness`` takes that open connection so the
whole set-up + assertion + rollback stays in one transaction (the db-test rollback rule).
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

import scripts.setup_supabase as setup_supabase
from app.platform.config import Settings
from schema import engine as engine_mod
from schema import schema
from schema.engine import session_scope

from ._helpers import index_page

pytestmark = (
    pytest.mark.db
)  # substep 0.5.1: real local Postgres via this dir's session-scoped conftest


def test_deploy_readiness_reports_ready_when_scope_rls_present(capsys) -> None:
    """MIG-02 / ADR-0014 — with both 0010 scope policies in place the gate reports READY (rc 0).

    Protects the live-isolation panel's deploy gate: ``chunk_scope_read`` is applied session-wide by
    the harness; the curated analogue is applied here in this transaction so the full post-0010
    posture holds, then rolled back. The check must see both policies (RESTRICTIVE/SELECT, RLS on).
    """
    conn = engine_mod.get_engine().connect()
    try:
        # chunk_scope_read is applied + committed by the conftest; add the curated analogue so the
        # full migration-0010 posture holds in this transaction (apply_* also ENABLEs curated RLS).
        schema.apply_curated_scope_rls(conn)

        rc = setup_supabase.check_deploy_readiness(conn=conn)
        out = capsys.readouterr().out

        assert rc == 0, out
        assert "chunk.chunk_scope_read: present=True" in out
        assert "curated_knowledge_entry.curated_knowledge_entry_scope_read: present=True" in out
        assert "restrictive_select=True" in out and "rls_enabled=True" in out
        assert "reader path safe to expose" in out
    finally:
        conn.rollback()  # discard the curated policy — harness left exactly as the conftest set it
        conn.close()


def test_deploy_readiness_fails_closed_when_scope_rls_absent(capsys) -> None:
    """MIG-02 / ADR-0014 — a missing scope policy MUST block the deploy (non-zero + names the gap).

    Reproduces head < 0010 / a downgrade that dropped the backstop by dropping both scope policies
    inside this transaction, then rolls back so ``chunk_scope_read`` (the conftest's committed
    policy) is restored intact. Without this gate the customer/tenant axis fails OPEN.
    """
    conn = engine_mod.get_engine().connect()
    try:
        # Both uncommitted; rolled back below. drop_curated is idempotent (the harness never
        # applied the curated scope policy, so this is a no-op there).
        schema.drop_chunk_scope_rls(conn)
        schema.drop_curated_scope_rls(conn)

        rc = setup_supabase.check_deploy_readiness(conn=conn)
        captured = capsys.readouterr()

        assert rc != 0, captured.out
        # The failure names what is missing and refuses to expose the reader path.
        assert "chunk_scope_read' on 'chunk' is ABSENT" in captured.err
        assert (
            "curated_knowledge_entry_scope_read' on 'curated_knowledge_entry' is ABSENT"
            in captured.err
        )
        assert "Do NOT expose the reader path" in captured.err
    finally:
        conn.rollback()  # restores chunk_scope_read (the DROP was never committed) — harness intact
        conn.close()


def test_deploy_readiness_fails_loudly_on_untagged_active_chunks(
    gateway, settings: Settings, capsys
) -> None:
    """X2 (4.2 audit, owner-accepted 2026-10-05) — an untagged ACTIVE chunk must BLOCK the deploy.

    Post-0014 an active chunk with ``tags = {}`` is not a leak (fail-closed: visible to no scope)
    but it IS content silently dark to every customer — post-membership-gate it indicates a
    regression. The gate must fail non-zero and name the page instead of the old skip-as-pass.
    Data is committed via the real sync path then mutated by SQL; the dir's autouse truncation
    cleans it up.
    """
    index_page(gateway, settings, 1001, 1)  # commits real chunk rows for page 1001
    with session_scope() as s:
        s.execute(text("UPDATE chunk SET tags = '{}' WHERE page_id = 1001"))

    conn = engine_mod.get_engine().connect()
    try:
        schema.apply_curated_scope_rls(conn)  # policy half of the gate passes; only X2 can fail

        rc = setup_supabase.check_deploy_readiness(conn=conn)
        captured = capsys.readouterr()

        assert rc != 0, captured.out
        assert "untagged ACTIVE chunk" in captured.err
        assert "1001" in captured.err  # the failure names the dark page
    finally:
        conn.rollback()
        conn.close()


def test_deploy_readiness_ignores_untagged_inactive_chunks(
    gateway, settings: Settings, capsys
) -> None:
    """X2 guard — untagged INACTIVE chunks (GC remnants) do not block the deploy.

    Only ACTIVE rows can be silently dark content; inactive rows never reach retrieval at all.
    """
    index_page(gateway, settings, 1001, 1)
    with session_scope() as s:
        s.execute(text("UPDATE chunk SET tags = '{}', is_active = false WHERE page_id = 1001"))

    conn = engine_mod.get_engine().connect()
    try:
        schema.apply_curated_scope_rls(conn)

        rc = setup_supabase.check_deploy_readiness(conn=conn)
        out = capsys.readouterr().out

        assert rc == 0, out
        assert "untagged ACTIVE chunks: 0" in out
    finally:
        conn.rollback()
        conn.close()
