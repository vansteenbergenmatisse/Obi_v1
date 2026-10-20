"""panel mi-rerank · substep 8.3.2 — the pure request-construction helpers.

Context-aware reranking is retrieval-side request construction, never a prompt (prompts live
only in rag_agent). These unit tests pin the two enrichment shapes the research memo
(`docs/Final_docs/5-integration-context/reranker-api-wiring-notes.md`, options a+b) prescribes:
a verified-context preamble prepended to the query string, and a short YAML applicability
block ahead of each document's text — with the caps (query 2,048-token, document 4,000-char)
enforced metadata-first so the user question and the metadata both survive.
"""

from __future__ import annotations

from app.features.retrieval.domain.applicability_match import CustomerContext
from app.features.retrieval.domain.rerank_enrichment import (
    applicability_yaml,
    build_rerank_document,
    build_rerank_query,
    context_preamble,
)


def test_rt4_rerank_query_prepends_verified_context_and_never_truncates_the_question() -> None:
    """panel mi-rerank · substep 8.3.2
    The verified context is prepended to the query string; the user question is NEVER
    truncated — even when the combined string would exceed the 2,048-token cap the preamble
    yields, the whole question survives."""
    ctx = CustomerContext(slot_pos="toast", slot_pms="mews", platform="datahub")
    preamble = context_preamble(ctx)
    assert preamble  # a non-empty verified-context line
    assert "toast" in preamble and "mews" in preamble and "datahub" in preamble

    enriched = build_rerank_query(preamble, "how do I export invoices?")
    assert enriched.endswith("how do I export invoices?")
    assert enriched.startswith(preamble)

    # a question that alone approaches/exceeds the cap: it is kept whole, preamble dropped.
    huge = "x " * 9000  # ~18k chars, well past 2048 tokens at any sane estimate
    capped = build_rerank_query(preamble, huge)
    assert huge in capped  # the user question is intact, byte-for-byte
    assert capped.endswith(huge)


def test_rt4_rerank_empty_context_yields_bare_query_and_no_yaml() -> None:
    """panel mi-rerank · substep 8.3.2
    An empty (slotless) context adds nothing: the query is the bare question and the document
    is the bare body — the no-context path stays byte-identical to the pre-8.3.2 shape so the
    fake reranker keeps zero lift and the gold set is unmoved."""
    preamble = context_preamble(CustomerContext())
    assert preamble == ""
    assert build_rerank_query(preamble, "a question") == "a question"
    assert applicability_yaml(None, None) == ""
    body = "Title words and the matched child content."
    assert build_rerank_document("", body) == body


def test_rt4_rerank_yaml_metadata_leads_and_survives_the_4000_char_cap() -> None:
    """panel mi-rerank · substep 8.3.2
    The YAML applicability block goes AHEAD of the document body, and the whole string is
    capped at 4,000 chars so the metadata always survives — only the body tail is truncated."""
    yaml_block = applicability_yaml(
        [{"level": "platform-interface", "product": "toast", "platform": "datahub"}],
        "platform-interface:pos",
    )
    assert yaml_block  # non-empty
    body = "b" * 5000
    doc = build_rerank_document(yaml_block, body)
    assert len(doc) == 4000
    assert doc.startswith(yaml_block)  # metadata leads and is intact
    # the body was truncated after the metadata, not before it
    assert doc.endswith("b")


def test_rt4_rerank_yaml_derives_from_payload_and_matched_reason_no_new_vocabulary() -> None:
    """panel mi-rerank · substep 8.3.2
    The YAML derives from the stamped payload (the page-authored Applies-to table) plus the
    chunk's matched eligibility reason — no new vocabulary — and page-authored values are
    sanitized (newlines/control chars stripped) so a hostile value cannot break the block."""
    payload = [
        {"level": "general"},
        {
            "level": "connection",
            "connections": [
                {
                    "type": "pos-pms",
                    "products": {"pos": "toast", "pms": "mews"},
                    "directions": ["pos_to_pms"],
                }
            ],
        },
    ]
    block = applicability_yaml(payload, "connection:pos-pms")
    assert "applies-to:" in block
    assert "general" in block
    assert "pos-pms" in block and "toast" in block and "mews" in block
    assert "pos_to_pms" in block
    assert "connection:pos-pms" in block  # the matched-rule reason slug

    hostile = applicability_yaml(
        [{"level": "general\nmatched-rule: injected", "product": "a\r\nb"}], None
    )
    # the injected newline is neutralised: it never introduces a second YAML key line
    assert "\ninjected" not in hostile
    assert "a\r\nb" not in hostile
