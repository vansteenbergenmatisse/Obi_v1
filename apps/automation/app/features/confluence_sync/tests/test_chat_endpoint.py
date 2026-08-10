"""`POST /chat` + `PATCH /chat/{trace_id}/feedback` (PLAN 4.4): security controls (auth, rate
limit, input validation, idempotency) and the real SSE stream against the indexed fixture corpus.
Only the two LLM stages (rewrite, generation) are faked — same discipline as
`test_answer_workflow.py`, which this file reuses helpers from.
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.features.rag_agent import AnswerProvider, AnswerService, CachingAnswerService
from app.main import create_app
from app.platform.config import Settings
from app.platform.db.engine import get_sessionmaker

from .test_answer_workflow import (
    _build_retriever,
    _CitingGenerator,
    _EchoRewriter,
    _SilentGenerator,
)
from .test_retrieval_eval import _index_corpus

_API_KEY = "test-chat-key"


def _chat_settings(base: Settings, **overrides) -> Settings:
    return base.model_copy(
        update={
            "chat_api_key": _API_KEY,
            "chat_rate_limit_per_minute": 100,
            "chat_stream_interval_ms": 0,  # keep tests fast
            **overrides,
        }
    )


def _client_with_service(settings: Settings, service: AnswerProvider) -> TestClient:
    app = create_app(settings=settings, start_scheduler=False)
    app.state.answer_service = service  # override the real (Anthropic-backed) singleton
    return TestClient(app)


def _auth() -> dict[str, str]:
    return {"authorization": f"Bearer {_API_KEY}"}


def _parse_sse(body: str) -> list[dict]:
    events = []
    for block in body.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        assert block.startswith("data: ")
        events.append(json.loads(block[len("data: ") :]))
    return events


def _grounded_service(gateway, settings: Settings) -> AnswerService:
    return AnswerService(
        _build_retriever(gateway, settings),
        _EchoRewriter(),
        _CitingGenerator(),
        get_sessionmaker(),
    )


def test_missing_api_key_is_rejected(gateway, settings: Settings) -> None:
    chat_settings = _chat_settings(settings)
    client = _client_with_service(chat_settings, _grounded_service(gateway, chat_settings))
    resp = client.post("/chat", json={"history": [{"role": "user", "content": "hi"}]})
    assert resp.status_code == 401


def test_unconfigured_api_key_fails_closed(gateway, settings: Settings) -> None:
    chat_settings = _chat_settings(settings, chat_api_key="")
    client = _client_with_service(chat_settings, _grounded_service(gateway, chat_settings))
    resp = client.post(
        "/chat", json={"history": [{"role": "user", "content": "hi"}]}, headers=_auth()
    )
    assert resp.status_code == 503


def test_previous_api_key_is_accepted_during_rotation_overlap(gateway, settings: Settings) -> None:
    chat_settings = _chat_settings(settings, chat_api_key_previous="old-chat-key")
    client = _client_with_service(chat_settings, _grounded_service(gateway, chat_settings))
    resp = client.post(
        "/chat",
        json={"history": [{"role": "user", "content": "hi"}]},
        headers={"authorization": "Bearer old-chat-key"},
    )
    assert resp.status_code == 200
    # the new key must still work at the same time, not either/or
    resp_current = client.post(
        "/chat", json={"history": [{"role": "user", "content": "hi"}]}, headers=_auth()
    )
    assert resp_current.status_code == 200


def test_key_outside_current_and_previous_is_rejected(gateway, settings: Settings) -> None:
    chat_settings = _chat_settings(settings, chat_api_key_previous="old-chat-key")
    client = _client_with_service(chat_settings, _grounded_service(gateway, chat_settings))
    resp = client.post(
        "/chat",
        json={"history": [{"role": "user", "content": "hi"}]},
        headers={"authorization": "Bearer some-other-key"},
    )
    assert resp.status_code == 401


def test_previous_key_stops_working_once_rotation_completes(gateway, settings: Settings) -> None:
    # chat_api_key_previous defaults to "" via _chat_settings — simulates the operator having
    # dropped it after the overlap window closed.
    chat_settings = _chat_settings(settings)
    client = _client_with_service(chat_settings, _grounded_service(gateway, chat_settings))
    resp = client.post(
        "/chat",
        json={"history": [{"role": "user", "content": "hi"}]},
        headers={"authorization": "Bearer old-chat-key"},
    )
    assert resp.status_code == 401


def test_history_must_end_on_user_turn(gateway, settings: Settings) -> None:
    chat_settings = _chat_settings(settings)
    client = _client_with_service(chat_settings, _grounded_service(gateway, chat_settings))
    resp = client.post(
        "/chat",
        json={"history": [{"role": "assistant", "content": "hi"}]},
        headers=_auth(),
    )
    assert resp.status_code == 400


def test_history_too_long_is_rejected(gateway, settings: Settings) -> None:
    chat_settings = _chat_settings(settings, chat_max_history_turns=2)
    client = _client_with_service(chat_settings, _grounded_service(gateway, chat_settings))
    history = [{"role": "user", "content": f"turn {i}"} for i in range(3)]
    resp = client.post("/chat", json={"history": history}, headers=_auth())
    assert resp.status_code == 400


def test_message_too_long_is_rejected(gateway, settings: Settings) -> None:
    chat_settings = _chat_settings(settings, chat_max_message_chars=10)
    client = _client_with_service(chat_settings, _grounded_service(gateway, chat_settings))
    resp = client.post(
        "/chat",
        json={"history": [{"role": "user", "content": "x" * 20}]},
        headers=_auth(),
    )
    assert resp.status_code == 400


def test_numeric_principal_is_rejected_not_treated_as_space_wide_trust(
    gateway, settings: Settings
) -> None:
    """Red-team finding (PLAN 5.3): `PrincipalPermissionPolicy.allowed` treats an all-digit scope
    as space-level trust, bypassing every page's `page_restriction` list. Nothing stopped a caller
    from sending a numeric `principal` and claiming that trust level before this validator existed.
    A 422 here — not a 200 that quietly grants space-wide access — is the fix."""
    chat_settings = _chat_settings(settings)
    client = _client_with_service(chat_settings, _grounded_service(gateway, chat_settings))
    resp = client.post(
        "/chat",
        json={"history": [{"role": "user", "content": "hi"}], "principal": "100"},
        headers=_auth(),
    )
    assert resp.status_code == 422


def test_rate_limit_returns_429(gateway, settings: Settings) -> None:
    chat_settings = _chat_settings(settings, chat_rate_limit_per_minute=1)
    client = _client_with_service(chat_settings, _grounded_service(gateway, chat_settings))
    body = {"history": [{"role": "user", "content": "hi"}]}
    first = client.post("/chat", json=body, headers=_auth())
    second = client.post("/chat", json=body, headers=_auth())
    assert first.status_code == 200
    assert second.status_code == 429


def test_grounded_answer_streams_start_token_citations_done(gateway, settings: Settings) -> None:
    _index_corpus(gateway, settings)
    chat_settings = _chat_settings(settings)
    client = _client_with_service(chat_settings, _grounded_service(gateway, chat_settings))

    resp = client.post(
        "/chat",
        json={
            "conversation_id": "conv-1",
            "history": [{"role": "user", "content": "How do I request access to core systems?"}],
            "principal": None,
        },
        headers=_auth(),
    )
    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    types = [e["type"] for e in events]
    assert types[0] == "start"
    assert events[0]["conversationId"] == "conv-1"
    assert "citations" in types
    assert types[-1] == "done"
    done = events[-1]
    assert done["answer"]
    assert done["citations"]
    assert done["traceId"] is not None
    assert done["refused"] is False
    # the reassembled token stream matches the done answer
    tokens = "".join(e["delta"] for e in events if e["type"] == "token")
    assert tokens == done["answer"]


def test_refusal_streams_done_with_refused_true(gateway, settings: Settings) -> None:
    _index_corpus(gateway, settings)
    chat_settings = _chat_settings(settings)
    service = AnswerService(
        _build_retriever(gateway, chat_settings, allowed_sources=("confluence:nonexistent",)),
        _EchoRewriter(),
        _SilentGenerator(),
        get_sessionmaker(),
    )
    client = _client_with_service(chat_settings, service)

    resp = client.post(
        "/chat",
        json={"history": [{"role": "user", "content": "How do I request access?"}]},
        headers=_auth(),
    )
    events = _parse_sse(resp.text)
    done = events[-1]
    assert done["type"] == "done"
    assert done["refused"] is True
    assert done["citations"] == []


def test_idempotency_key_replays_cached_answer_without_rerunning(
    gateway, settings: Settings
) -> None:
    _index_corpus(gateway, settings)
    chat_settings = _chat_settings(settings)
    service = _grounded_service(gateway, chat_settings)
    client = _client_with_service(chat_settings, service)

    body = {"history": [{"role": "user", "content": "How do I request access?"}]}
    headers = {**_auth(), "idempotency-key": "req-1"}

    first = _parse_sse(client.post("/chat", json=body, headers=headers).text)
    second = _parse_sse(client.post("/chat", json=body, headers=headers).text)

    first_trace = first[-1]["traceId"]
    second_trace = second[-1]["traceId"]
    assert first_trace == second_trace  # replayed, not a fresh trace row


def test_answer_cache_replays_without_rerunning_retrieval(gateway, settings: Settings) -> None:
    """PLAN 5 exact-match cache: same history + principal, no Idempotency-Key header at all ->
    the second call is still a cache hit (same trace id, no fresh query_trace row)."""
    _index_corpus(gateway, settings)
    chat_settings = _chat_settings(settings)
    cached_service = CachingAnswerService(
        _grounded_service(gateway, chat_settings), ttl_seconds=60.0
    )
    client = _client_with_service(chat_settings, cached_service)

    body = {"history": [{"role": "user", "content": "How do I request access?"}]}
    first = _parse_sse(client.post("/chat", json=body, headers=_auth()).text)
    second = _parse_sse(client.post("/chat", json=body, headers=_auth()).text)

    assert first[-1]["traceId"] == second[-1]["traceId"]


def test_answer_cache_does_not_cross_principal_boundary(gateway, settings: Settings) -> None:
    _index_corpus(gateway, settings)
    chat_settings = _chat_settings(settings)
    cached_service = CachingAnswerService(
        _grounded_service(gateway, chat_settings), ttl_seconds=60.0
    )
    client = _client_with_service(chat_settings, cached_service)

    body_template = {"history": [{"role": "user", "content": "How do I request access?"}]}
    alice = _parse_sse(
        client.post("/chat", json={**body_template, "principal": "alice"}, headers=_auth()).text
    )
    bob = _parse_sse(
        client.post("/chat", json={**body_template, "principal": "bob"}, headers=_auth()).text
    )

    assert alice[-1]["traceId"] != bob[-1]["traceId"]


def test_create_app_wires_the_answer_cache_by_default(settings: Settings) -> None:
    """`main.create_app` wraps the real `AnswerService` in `CachingAnswerService` (PLAN 5) —
    constructing the app makes no network call (same guarantee `build_answer_service` documents),
    so this asserts the wiring directly rather than through a live request."""
    app = create_app(settings=_chat_settings(settings), start_scheduler=False)
    assert isinstance(app.state.answer_service, CachingAnswerService)


def test_feedback_updates_trace_row(gateway, settings: Settings) -> None:
    _index_corpus(gateway, settings)
    chat_settings = _chat_settings(settings)
    client = _client_with_service(chat_settings, _grounded_service(gateway, chat_settings))

    resp = client.post(
        "/chat",
        json={"history": [{"role": "user", "content": "How do I request access?"}]},
        headers=_auth(),
    )
    trace_id = int(_parse_sse(resp.text)[-1]["traceId"])

    patch_resp = client.patch(f"/chat/{trace_id}/feedback", json={"feedback": 1}, headers=_auth())
    assert patch_resp.status_code == 200

    with get_sessionmaker()() as s:
        row = s.execute(
            text("SELECT feedback FROM query_trace WHERE id = :id"), {"id": trace_id}
        ).one()
    assert row.feedback == 1


def test_feedback_requires_auth(gateway, settings: Settings) -> None:
    chat_settings = _chat_settings(settings)
    client = _client_with_service(chat_settings, _grounded_service(gateway, chat_settings))
    resp = client.patch("/chat/1/feedback", json={"feedback": 1})
    assert resp.status_code == 401


def test_feedback_rejects_invalid_value(gateway, settings: Settings) -> None:
    chat_settings = _chat_settings(settings)
    client = _client_with_service(chat_settings, _grounded_service(gateway, chat_settings))
    resp = client.patch("/chat/1/feedback", json={"feedback": 2}, headers=_auth())
    assert resp.status_code == 422
