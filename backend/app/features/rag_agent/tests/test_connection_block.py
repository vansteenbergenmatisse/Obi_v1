"""Unit tests for build_connection_block (panel mi-session, substep 9.2.1).

Pure-string rendering of the directed-connection block chat-start writes into the system prompt
(ADR-0020 chat-start step 3) — no DB, no catalog mutation, so these run at the unit level.
"""

from __future__ import annotations

from app.features.rag_agent.domain.prompt import build_connection_block
from app.platform.config.product_catalog import load_product_catalog


def test_rt1_connection_block_names_both_systems_and_direction() -> None:
    """panel mi-session · substep 9.2.1
    A known source/target renders both systems, the direction and the business id."""
    catalog = load_product_catalog()
    src = catalog.resolve_system("toast")
    tgt = catalog.resolve_system("mews")
    block = build_connection_block(src, tgt, "B-3075")
    assert "Toast (POS)" in block
    assert "Mews (PMS)" in block
    assert "POS → PMS" in block
    assert "B-3075" in block
    assert "this connection only" in block


def test_rt1_connection_block_unknown_system_says_so() -> None:
    """panel mi-session · substep 9.2.1
    An unrecognized source/target renders an 'unknown' block, never invents a system (step 5)."""
    block = build_connection_block(None, None, "B-9")
    assert "B-9" in block
    assert "could not be recognized" in block.lower()
    # never fabricates a direction for a connection it could not resolve
    assert "→" not in block
