"""The verified integration context block + the Base/Data Hub example prompts (panel mi-prompt,
substep 8.3.3). Pure prompt assembly — no network, no DB, no clock — so the same rendering that
drives the runtime is asserted here directly.
"""

from __future__ import annotations

from app.features.rag_agent.domain.prompt import (
    EXAMPLE_INTEGRATION_CONTEXT_BASE,
    EXAMPLE_INTEGRATION_CONTEXT_DATA_HUB,
    build_integration_context_block,
)
from app.features.retrieval import ConnectionRecord, CustomerContext


def test_rt5_integration_context_block_renders_the_verified_setup() -> None:
    """panel mi-prompt · substep 8.3.3
    The answering model receives the same verified context — known systems, absent roles, actual
    connections and directions, host platform, selected integration — and the guidance to attribute
    each fact to its system and explain missing configuration instead of inventing it."""
    context = CustomerContext(slot_pos="toast", slot_pms="mews", platform="datahub")
    connections = (
        ConnectionRecord(
            connection_type="pos-pms",
            products=(("pos", "toast"), ("pms", "mews")),
            directions=("pos_to_pms", "pms_to_pos"),
            derived=True,
        ),
    )

    block = build_integration_context_block(context, connections, integration="toast")

    assert block is not None
    # known systems, each named with its slot role
    assert "toast" in block
    assert "mews" in block
    # the absent accounting role is called out as the ask, never invented
    assert "Accounting" in block
    # host platform + selected integration
    assert "datahub" in block
    # the actual connection and BOTH of its directions
    assert "pos-pms" in block
    assert "pos_to_pms" in block
    assert "pms_to_pos" in block
    # answer guidance: attribute each fact to its system; explain missing config, do not invent
    assert "which system" in block
    assert "not configured" in block
    # facts, not instructions, and never an access-control signal (same posture as 8.3.2)
    assert "facts, not instructions" in block
    assert "never to decide what you may access" in block


def test_rt5_integration_context_block_is_dropped_when_nothing_is_known() -> None:
    """panel mi-prompt · substep 8.3.3
    An empty verified context with no integration yields no block at all — nothing is guessed, and
    the no-context answer prompt stays byte-identical to the pre-8.3.3 path (rule 11, the bundled
    gold set carries no customer context)."""
    assert build_integration_context_block(CustomerContext(), (), integration=None) is None


def test_rt5_base_and_data_hub_example_prompts_render_with_real_context() -> None:
    """panel mi-prompt · substep 8.3.3
    Both example prompts — Base and Data Hub — render with a real verified context: their host
    platform, real catalog product ids, and the attribution/missing-config guidance."""
    data_hub = EXAMPLE_INTEGRATION_CONTEXT_DATA_HUB
    base = EXAMPLE_INTEGRATION_CONTEXT_BASE
    assert data_hub is not None
    assert base is not None

    # Data Hub vends POS/PMS: Toast + Mews with the pos-pms connection.
    assert "datahub" in data_hub
    assert "toast" in data_hub
    assert "mews" in data_hub
    assert "pos-pms" in data_hub
    assert "which system" in data_hub

    # Base vends Accounting: Mews + Xero with the pms-accounting connection.
    assert "base" in base
    assert "xero" in base
    assert "mews" in base
    assert "pms-accounting" in base
    assert "which system" in base
