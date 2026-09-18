"""Contextual retrieval_content: deterministic fallback + Anthropic-backed path."""

from __future__ import annotations

import json

import httpx

from app.features.ingestion.application.contextualizer import (
    ContextItem,
    Contextualizer,
)
from app.platform.clients import AnthropicMessagesClient
from app.platform.config import Settings

ITEMS = [
    ContextItem(
        title="Onboarding Guide",
        heading_path=["Onboarding Guide", "Getting Access"],
        text="Request access via the IT portal.",
    ),
    ContextItem(
        title="Onboarding Guide",
        heading_path=["Onboarding Guide", "Key Contacts"],
        text="Reach the platform team on Slack.",
    ),
]


def test_fallback_prefixes_heading_path_deterministically() -> None:
    settings = Settings(anthropic_api_key="", contextualization_enabled=True)
    ctx = Contextualizer(settings, client=None)
    out_a = ctx.contextualize(document_text="full doc", items=ITEMS)
    out_b = ctx.contextualize(document_text="full doc", items=ITEMS)
    assert out_a == out_b  # deterministic offline
    # factual metadata prefix, then the verbatim chunk; no invented content
    assert "Getting Access" in out_a[0]
    assert out_a[0].endswith("Request access via the IT portal.")
    assert "Onboarding Guide" in out_a[0]


def test_disabled_returns_plain_chunk_text() -> None:
    settings = Settings(anthropic_api_key="key", contextualization_enabled=False)
    ctx = Contextualizer(settings, client=None)
    out = ctx.contextualize(document_text="doc", items=ITEMS[:1])
    assert out[0].endswith("Request access via the IT portal.")


def test_llm_path_sends_cached_document_and_prepends_context() -> None:
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body)
        return httpx.Response(
            200, json={"content": [{"type": "text", "text": "This chunk is about SSO access."}]}
        )

    http = httpx.Client(transport=httpx.MockTransport(handler))
    client = AnthropicMessagesClient(api_key="k", client=http)
    settings = Settings(
        anthropic_api_key="k",
        contextualization_enabled=True,
        routing_model="claude-haiku-4-5-20251001",
    )
    ctx = Contextualizer(settings, client=client)

    out = ctx.contextualize(document_text="THE FULL DOCUMENT", items=ITEMS[:1])

    assert "This chunk is about SSO access." in out[0]
    assert out[0].endswith("Request access via the IT portal.")  # verbatim chunk preserved
    # document context sent as a cached system block, once per chunk
    assert seen[0]["system"][0]["text"] == "THE FULL DOCUMENT"
    assert seen[0]["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert seen[0]["model"] == "claude-haiku-4-5-20251001"


def test_llm_failure_falls_back_without_raising() -> None:
    http = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500, json={})))
    client = AnthropicMessagesClient(api_key="k", client=http, max_retries=1)
    settings = Settings(anthropic_api_key="k", contextualization_enabled=True)
    ctx = Contextualizer(settings, client=client)
    out = ctx.contextualize(document_text="doc", items=ITEMS[:1])
    # degrades to the deterministic metadata prefix instead of crashing ingestion
    assert out[0].endswith("Request access via the IT portal.")
    assert "Getting Access" in out[0]


def test_llm_meta_refusal_is_discarded_and_falls_back_to_metadata() -> None:
    """A model meta-reply ("I don't have access to the document…") must never be baked into
    retrieval_content — it poisons the embedding + rerank signal and causes false refusals
    (PLAN 3b). It degrades to the deterministic metadata prefix, exactly like a transport error."""
    meta_replies = [
        "I don't have access to the overall document to provide context for this chunk.",
        "I do not have access to the overall document, so I cannot situate this chunk.",
        "I'm sorry, but no document was provided, so I can't add context.",
        "Without access to the full document, I'm unable to provide meaningful context.",
        # exact phrasings captured live on the obi-*-test pages (Opera Cloud / General Obi):
        "I cannot provide context for this chunk because the document provided contains only "
        "this single statement.",
        "I cannot provide context for this chunk because the document provided contains only "
        "the single sentence shown.",
        'I don\'t have access to the full document, only the chunk "grapes are the only fruit."',
    ]
    for reply in meta_replies:
        http = httpx.Client(
            transport=httpx.MockTransport(
                lambda r, _reply=reply: httpx.Response(
                    200, json={"content": [{"type": "text", "text": _reply}]}
                )
            )
        )
        client = AnthropicMessagesClient(api_key="k", client=http)
        settings = Settings(anthropic_api_key="k", contextualization_enabled=True)
        ctx = Contextualizer(settings, client=client)
        out = ctx.contextualize(document_text="THE FULL DOCUMENT", items=ITEMS[:1])
        # the meta-reply is discarded, not stored
        assert reply not in out[0], f"meta-refusal leaked into retrieval_content: {reply!r}"
        assert "access to" not in out[0].lower()
        # degrades to the deterministic metadata prefix + verbatim chunk
        assert "Getting Access" in out[0]
        assert out[0].endswith("Request access via the IT portal.")


def test_llm_real_context_first_person_is_not_discarded() -> None:
    """A legitimate blurb is kept even if it happens to start with a benign first-person clause —
    the detector keys on the specific 'no-access / not-provided' meta signals, not on 'I'."""
    http = httpx.Client(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(
                200,
                json={"content": [{"type": "text", "text": "This section explains SSO access."}]},
            )
        )
    )
    client = AnthropicMessagesClient(api_key="k", client=http)
    settings = Settings(anthropic_api_key="k", contextualization_enabled=True)
    ctx = Contextualizer(settings, client=client)
    out = ctx.contextualize(document_text="THE FULL DOCUMENT", items=ITEMS[:1])
    assert "This section explains SSO access." in out[0]


def test_i3_context_note_is_capped_at_128_tokens() -> None:
    """panel i3-context · substep p0-s0_5-reg-ingestion-stage-3
    Note: one or two sentences written by claude-haiku-4-5 from the whole page, max 128 tokens."""
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(
            200, json={"content": [{"type": "text", "text": "This chunk is about SSO access."}]}
        )

    http = httpx.Client(transport=httpx.MockTransport(handler))
    client = AnthropicMessagesClient(api_key="k", client=http)
    settings = Settings(
        anthropic_api_key="k",
        contextualization_enabled=True,
        routing_model="claude-haiku-4-5-20251001",
    )
    ctx = Contextualizer(settings, client=client)

    ctx.contextualize(document_text="THE FULL DOCUMENT", items=ITEMS[:1])

    assert seen[0]["max_tokens"] == 128


def test_document_text_is_truncated_to_cap() -> None:
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"content": [{"type": "text", "text": "ctx"}]})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    client = AnthropicMessagesClient(api_key="k", client=http)
    settings = Settings(
        anthropic_api_key="k", contextualization_enabled=True, contextualization_max_doc_chars=100
    )
    ctx = Contextualizer(settings, client=client)
    ctx.contextualize(document_text="x" * 5000, items=ITEMS[:1])
    assert len(captured[0]["system"][0]["text"]) <= 100


def test_vd_text_input_composed_title_heading_context_then_child_text() -> None:
    """panel vd-text · substep p0-s0_5-reg-the-vector-database
    Input: page title + heading path + context note + child text — the four pieces appear in
    that order in the text handed to the embedder, the context note preceding the untouched
    child text rather than replacing or reordering any of the other three."""
    http = httpx.Client(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(
                200,
                json={
                    "content": [{"type": "text", "text": "This section covers onboarding access."}]
                },
            )
        )
    )
    client = AnthropicMessagesClient(api_key="k", client=http)
    settings = Settings(anthropic_api_key="k", contextualization_enabled=True)
    ctx = Contextualizer(settings, client=client)

    item = ContextItem(
        title="Onboarding Guide",
        heading_path=["Onboarding Guide", "Getting Access"],
        text="Request access via the IT portal.",
    )
    out = ctx.contextualize(document_text="THE FULL DOCUMENT", items=[item])[0]

    title_idx = out.find("Onboarding Guide")
    heading_idx = out.find("Getting Access")
    context_idx = out.find("This section covers onboarding access.")
    child_idx = out.find("Request access via the IT portal.")

    assert -1 not in (title_idx, heading_idx, context_idx, child_idx)
    assert title_idx < heading_idx < context_idx < child_idx
    assert out.endswith("Request access via the IT portal.")  # verbatim child text, unaltered


def test_vd_text_size_lands_near_400_tokens() -> None:
    """panel vd-text · substep p0-s0_5-reg-the-vector-database
    Size: about 400 tokens — a real child window built at the chunking domain's own 400-token
    child_target composes, with its title/heading-path prefix, to a text that stays close to 400
    tokens (not the 150-token floor or the 750-token ceiling that bound raw child text alone)."""
    from app.features.ingestion.domain import normalization as norm
    from app.features.ingestion.domain.chunking import ChunkConfig, plan_chunks
    from app.features.ingestion.domain.tokenization import TokenCounter

    counter = TokenCounter()
    cfg = ChunkConfig()
    assert cfg.child_target == 400  # the size knob this panel's text is built from

    # 800 repeated words comfortably forces a full-target (400-token) first child window,
    # mirroring app/features/ingestion/tests/test_chunking.py's own child-sizing fixture.
    body = " ".join("lorem" for _ in range(800))
    html = f"<h1>Onboarding Guide</h1><h2>Getting Access</h2><p>{body}</p>"
    blocks = norm.normalize_body(html)
    plan = plan_chunks(page_id=3001, blocks=blocks, config=cfg, counter=counter)
    pp = next(pp for pp in plan if pp.parent.heading_path[-1] == "Getting Access")
    child = pp.children[0]
    assert child.tokens == cfg.child_target  # the raw child text lands exactly at 400

    settings = Settings(anthropic_api_key="", contextualization_enabled=False)
    ctx = Contextualizer(settings, client=None)
    item = ContextItem(title="Onboarding Guide", heading_path=child.heading_path, text=child.text)
    out = ctx.contextualize(document_text="doc", items=[item])[0]

    total = counter.count(out)
    assert 400 <= total <= 450  # "about 400": the 400-token child plus a short metadata prefix
