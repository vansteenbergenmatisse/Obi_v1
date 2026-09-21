"""Pure prompt-assembly tests: no LLM, no DB, no clock."""

from __future__ import annotations

from dataclasses import dataclass

from app.features.rag_agent.domain.curated_knowledge import CuratedEntry, curated_entry_to_hit
from app.features.rag_agent.domain.identity import IdentityFacts
from app.features.rag_agent.domain.prompt import (
    IDENTITY_SYSTEM_PROMPT,
    build_answer_prompt,
    build_evidence_block,
    build_identity_context_block,
    build_identity_system_prompt,
    build_rewrite_prompt,
)
from app.features.rag_agent.schemas import ChatMessage


@dataclass(frozen=True)
class _Hit:
    chunk_id: int
    title: str


def test_build_rewrite_prompt_includes_every_turn_in_order() -> None:
    history = [
        ChatMessage(role="user", content="How do I reset my password?"),
        ChatMessage(role="assistant", content="Go to the account settings page."),
        ChatMessage(role="user", content="What if I don't have access to that page?"),
    ]
    prompt = build_rewrite_prompt(history)
    assert "user: How do I reset my password?" in prompt
    assert "assistant: Go to the account settings page." in prompt
    assert "user: What if I don't have access to that page?" in prompt
    # order preserved: the first turn appears before the last
    assert prompt.index("How do I reset") < prompt.index("don't have access")


def test_build_evidence_block_numbers_markers_from_one_in_hit_order() -> None:
    """panel r5-evidence · substep p0-s0_5-reg-retrieval-stage-5
    Numbering: markers are 1-based position in the evidence list, in hit order."""
    hits = [_Hit(chunk_id=11, title="Onboarding"), _Hit(chunk_id=22, title="Access Policy")]
    parents = {11: "New hires request access via the portal.", 22: "Access is role-based."}
    block = build_evidence_block(hits, parents)
    assert block.index("[1] Onboarding") < block.index("[2] Access Policy")
    assert "New hires request access via the portal." in block
    assert "Access is role-based." in block


def test_build_evidence_block_missing_parent_text_degrades_to_empty_body() -> None:
    """panel r5-evidence · substep p0-s0_5-reg-retrieval-stage-5
    Shape (degrade case): with no parent text, the block is still `[n] Page title` alone,
    never a dangling trailing newline or an invented body."""
    hits = [_Hit(chunk_id=1, title="Orphan Chunk")]
    block = build_evidence_block(hits, {})  # no parent text found for chunk_id=1
    assert block == "[1] Orphan Chunk"


def test_build_evidence_block_empty_hits_is_empty_string() -> None:
    assert build_evidence_block([], {}) == ""


def test_rt5_evidence_block_shape_is_marker_title_newline_parent_text() -> None:
    """panel r5-evidence · substep p0-s0_5-reg-retrieval-stage-5
    Shape: each block is exactly `[n] Page title`, a newline, then the parent text — end to end,
    with the marker's number matching the hit's 1-based position."""
    hits = [_Hit(chunk_id=1, title="Onboarding"), _Hit(chunk_id=2, title="Access Policy")]
    parents = {
        1: "New hires request access via the portal.",
        2: "Access is role-based.",
    }
    block = build_evidence_block(hits, parents)
    assert block == (
        "[1] Onboarding\nNew hires request access via the portal.\n\n"
        "[2] Access Policy\nAccess is role-based."
    )


def test_rt5_evidence_block_curated_hit_numbered_like_any_other_block() -> None:
    """panel r5-evidence · substep p0-s0_5-reg-retrieval-stage-5
    Curated: a curated entry (adapted via `curated_entry_to_hit`) is numbered in the same
    `[n] Page title\\nparent text` shape as any retrieved hit, sharing one continuous sequence."""
    curated_entry = CuratedEntry(id=7, tags=(), title="Refund Policy", body="Refunds take 5 days.")
    curated_hit = curated_entry_to_hit(curated_entry)
    retrieved_hit = _Hit(chunk_id=22, title="Access Policy")
    # mirrors answer_service.py: curated body is keyed onto parent_texts by the curated hit's own
    # (negative) chunk_id, alongside the retrieved hits' real parent texts.
    parents = {curated_hit.chunk_id: curated_entry.body, 22: "Access is role-based."}
    block = build_evidence_block([curated_hit, retrieved_hit], parents)
    assert block == (
        "[1] Refund Policy\nRefunds take 5 days.\n\n[2] Access Policy\nAccess is role-based."
    )


def test_build_answer_prompt_includes_question_and_evidence() -> None:
    prompt = build_answer_prompt("How do I get access?", "[1] Onboarding\nRequest via the portal.")
    assert "How do I get access?" in prompt
    assert "[1] Onboarding" in prompt
    assert "Request via the portal." in prompt


# -- identity path (per-user identity in a variable system prompt) --------------------------


def test_identity_system_prompt_carries_no_citation_and_anti_injection_rules() -> None:
    # like the small-talk/image prompts: no evidence, so no citation markers; and the identity
    # facts (verified though they are) are presented as facts, never as instructions to follow.
    assert "[1]" in IDENTITY_SYSTEM_PROMPT  # names the marker it forbids
    assert "never as an instruction" in IDENTITY_SYSTEM_PROMPT.lower()


def test_build_identity_system_prompt_appends_operator_static_block() -> None:
    out = build_identity_system_prompt("Omniboost builds hospitality software.")
    assert IDENTITY_SYSTEM_PROMPT in out
    assert "Omniboost builds hospitality software." in out


def test_build_identity_system_prompt_with_no_static_block_is_just_the_base_prompt() -> None:
    assert build_identity_system_prompt("") == IDENTITY_SYSTEM_PROMPT
    assert build_identity_system_prompt("   ") == IDENTITY_SYSTEM_PROMPT


def test_build_identity_context_block_renders_business_identity() -> None:
    block = build_identity_context_block(
        IdentityFacts(integration="opera-cloud", company_name="Hotel Co", company_id="42")
    )
    assert "opera-cloud" in block
    assert "Hotel Co" in block
    assert "42" in block


def test_build_identity_context_block_without_identity_says_so_honestly() -> None:
    block = build_identity_context_block(
        IdentityFacts(integration=None, company_name=None, company_id=None)
    )
    # no integration/company invented — the model is told there is none so it can answer honestly
    assert "no verified" in block.lower()
