"""Pure prompt-assembly tests: no LLM, no DB, no clock."""

from __future__ import annotations

from dataclasses import dataclass

from app.features.rag_agent.domain.prompt import (
    build_answer_prompt,
    build_evidence_block,
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
    hits = [_Hit(chunk_id=11, title="Onboarding"), _Hit(chunk_id=22, title="Access Policy")]
    parents = {11: "New hires request access via the portal.", 22: "Access is role-based."}
    block = build_evidence_block(hits, parents)
    assert block.index("[1] Onboarding") < block.index("[2] Access Policy")
    assert "New hires request access via the portal." in block
    assert "Access is role-based." in block


def test_build_evidence_block_missing_parent_text_degrades_to_empty_body() -> None:
    hits = [_Hit(chunk_id=1, title="Orphan Chunk")]
    block = build_evidence_block(hits, {})  # no parent text found for chunk_id=1
    assert block == "[1] Orphan Chunk"


def test_build_evidence_block_empty_hits_is_empty_string() -> None:
    assert build_evidence_block([], {}) == ""


def test_build_answer_prompt_includes_question_and_evidence() -> None:
    prompt = build_answer_prompt("How do I get access?", "[1] Onboarding\nRequest via the portal.")
    assert "How do I get access?" in prompt
    assert "[1] Onboarding" in prompt
    assert "Request via the portal." in prompt
