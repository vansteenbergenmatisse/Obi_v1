"""`POST /chat` + `PATCH /chat/{trace_id}/feedback` (PLAN 4.4): security controls (auth, rate
limit, input validation, idempotency) and the real SSE stream against the indexed fixture corpus.
Only the two LLM stages (rewrite, generation) are faked — same discipline as
`test_answer_workflow.py`, which this file reuses helpers from.
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.features.rag_agent import (
    AnswerProvider,
    AnswerService,
    CachingAnswerService,
    ClarificationReply,
    chat_router_module,
)
from app.main import create_app
from app.platform.config import Settings
from app.platform.db.engine import get_sessionmaker

from .test_answer_workflow import (
    _build_retriever,
    _CitingGenerator,
    _EchoRewriter,
    _ImageAnalyzingGenerator,
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


def test_too_many_images_on_a_turn_is_rejected(gateway, settings: Settings) -> None:
    """PLAN 7.4, ADR-0009 decision 7."""
    chat_settings = _chat_settings(settings, chat_max_images_per_turn=1)
    client = _client_with_service(chat_settings, _grounded_service(gateway, chat_settings))
    resp = client.post(
        "/chat",
        json={
            "history": [
                {
                    "role": "user",
                    "content": "what's in these?",
                    "images": [
                        {"mediaType": "image/png", "data": "YQ=="},
                        {"mediaType": "image/png", "data": "Yg=="},
                    ],
                }
            ]
        },
        headers=_auth(),
    )
    assert resp.status_code == 400


def test_oversized_image_is_rejected(gateway, settings: Settings) -> None:
    """PLAN 7.4, ADR-0009 decision 7."""
    chat_settings = _chat_settings(settings, chat_max_image_bytes=4)
    client = _client_with_service(chat_settings, _grounded_service(gateway, chat_settings))
    resp = client.post(
        "/chat",
        json={
            "history": [
                {
                    "role": "user",
                    "content": "what's in this?",
                    "images": [{"mediaType": "image/png", "data": "ZmFrZQ=="}],
                }
            ]
        },
        headers=_auth(),
    )
    assert resp.status_code == 400


def test_image_within_caps_is_accepted_and_analysis_reaches_the_done_event(
    gateway, settings: Settings
) -> None:
    """PLAN 7.3/7.4, ADR-0009: an image-bearing turn is accepted, the vision-analysis call runs,
    and its text arrives on the SSE `done` event's `imageAnalysis` field, distinct from `answer`."""
    _index_corpus(gateway, settings)
    chat_settings = _chat_settings(settings)
    service = AnswerService(
        _build_retriever(gateway, chat_settings),
        _EchoRewriter(),
        _ImageAnalyzingGenerator(),
        get_sessionmaker(),
    )
    client = _client_with_service(chat_settings, service)
    resp = client.post(
        "/chat",
        json={
            "history": [
                {
                    "role": "user",
                    "content": "How do I request access to core systems?",
                    "images": [{"mediaType": "image/png", "data": "ZmFrZQ=="}],
                }
            ],
        },
        headers=_auth(),
    )
    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    done = next(e for e in events if e["type"] == "done")
    assert done["imageAnalysis"] == "I see a diagram of the access-request flow."
    assert "I see a diagram" not in done["answer"]  # kept separate, not merged (decision 5)


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


def test_rate_limit_is_keyed_by_ip_not_by_rotating_principal(gateway, settings: Settings) -> None:
    """PLAN 4.6.4 fix: the limiter used to key on `principal` (if supplied) before falling back to
    client IP — trivially bypassed by sending a different `principal` on every call. Keying on IP
    only means a rotating principal from the same caller still hits the same bucket."""
    chat_settings = _chat_settings(settings, chat_rate_limit_per_minute=1)
    client = _client_with_service(chat_settings, _grounded_service(gateway, chat_settings))
    first = client.post(
        "/chat",
        json={"history": [{"role": "user", "content": "hi"}], "principal": "acct-alice"},
        headers=_auth(),
    )
    second = client.post(
        "/chat",
        json={"history": [{"role": "user", "content": "hi"}], "principal": "acct-bob"},
        headers=_auth(),
    )
    assert first.status_code == 200
    assert second.status_code == 429


def test_idempotency_cache_evicts_the_oldest_key_once_max_entries_exceeded(
    gateway, settings: Settings
) -> None:
    """PLAN 4.6.4 fix: the idempotency cache had no `max_entries` bound (unlike its Phase-5
    sibling, the exact-match answer cache) — unbounded distinct Idempotency-Key headers would grow
    it forever. Once the bound is exceeded, the oldest key stops being a cache hit."""
    _index_corpus(gateway, settings)
    chat_settings = _chat_settings(settings, chat_idempotency_cache_max_entries=2)
    service = _grounded_service(gateway, chat_settings)
    client = _client_with_service(chat_settings, service)
    body = {"history": [{"role": "user", "content": "How do I request access?"}]}

    first = _parse_sse(
        client.post("/chat", json=body, headers={**_auth(), "idempotency-key": "k1"}).text
    )
    client.post("/chat", json=body, headers={**_auth(), "idempotency-key": "k2"})
    client.post("/chat", json=body, headers={**_auth(), "idempotency-key": "k3"})  # evicts k1

    replay = _parse_sse(
        client.post("/chat", json=body, headers={**_auth(), "idempotency-key": "k1"}).text
    )
    assert replay[-1]["traceId"] != first[-1]["traceId"]  # k1 was evicted, not replayed


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


class _LeakyClarifyingGenerator:
    """Simulates a `generate_clarification` call that was talked into leaking extra content, so
    this test can assert the *wire* payload built from its return value stays confined to the
    whitelisted PLAN 9.3 fields regardless of what the collaborator returns."""

    def generate(self, query: str, evidence_block: str) -> str:
        raise AssertionError("generate must not be called: the clarification branch bypasses it")

    def generate_small_talk(self, query: str) -> str:
        raise AssertionError("generate_small_talk must not be called for a real question")

    def generate_image_analysis(self, query: str, images) -> str:
        raise AssertionError("generate_image_analysis must not be called: no test turn has images")

    def generate_clarification(self, query: str) -> ClarificationReply:
        return ClarificationReply(question="Which system do you mean?", options=["Muse", "Toast"])


class _AlwaysAmbiguousClassifier:
    def classify(self, query: str) -> bool:
        return True


def test_clarification_done_payload_never_leaks_internal_refusal_categories(
    gateway, settings: Settings
) -> None:
    """Red-team (PLAN 9.8): a clarifying turn is not a refusal and carries no `RefusalReason`
    category — this locks the `done` event's key set for that turn so a future change cannot
    accidentally start forwarding `refusal_reason` (or any other internal field) onto the wire
    alongside PLAN 9.3's additive clarification fields."""
    chat_settings = _chat_settings(settings)
    service = AnswerService(
        _build_retriever(gateway, chat_settings),
        _EchoRewriter(),
        _LeakyClarifyingGenerator(),
        get_sessionmaker(),
        clarification_classifier=_AlwaysAmbiguousClassifier(),
        enable_clarification_branch=True,
    )
    client = _client_with_service(chat_settings, service)

    resp = client.post(
        "/chat",
        json={"history": [{"role": "user", "content": "what are the limits?"}]},
        headers=_auth(),
    )
    done = _parse_sse(resp.text)[-1]

    assert done["type"] == "done"
    assert done["needsClarification"] is True
    assert done["clarificationQuestion"] == "Which system do you mean?"
    assert done["clarificationOptions"] == ["Muse", "Toast"]
    assert "refusalReason" not in done
    assert set(done.keys()) == {
        "type",
        "answer",
        "citations",
        "traceId",
        "refused",
        "imageAnalysis",
        "needsClarification",
        "clarificationQuestion",
        "clarificationOptions",
    }


class _LogRecorder:
    """Wraps the real bound logger, recording every call while still forwarding to it.

    Avoids relying on ``structlog.testing.capture_logs()``'s global processor swap, which is
    unreliable here: ``configure_logging``'s ``cache_logger_on_first_use=True`` means router.py's
    module-level ``log`` proxy resolves its processor chain on its *first-ever* call in the whole
    test run — by the time these tests run, dozens of earlier chat tests have already warmed it
    against the real console/JSON renderer, so a later ``capture_logs()`` context has no effect.
    """

    def __init__(self, real) -> None:
        self._real = real
        self.entries: list[dict] = []

    def __getattr__(self, name: str):
        real_method = getattr(self._real, name)

        def wrapper(event=None, **kwargs):
            self.entries.append({"event": event, **kwargs})
            return real_method(event, **kwargs)

        return wrapper


def test_chat_request_log_includes_refusal_reason_when_refused(
    gateway, settings: Settings, monkeypatch
) -> None:
    """PLAN 4.6.12: refusal_reason (computed since PLAN 4.1, tested since PLAN 4.2) reaches an
    observable surface — the chat_request structured log line — instead of only ever being
    checked by an assertion inside the process."""
    _index_corpus(gateway, settings)
    chat_settings = _chat_settings(settings)
    service = AnswerService(
        _build_retriever(gateway, chat_settings, allowed_sources=("confluence:nonexistent",)),
        _EchoRewriter(),
        _SilentGenerator(),
        get_sessionmaker(),
    )
    client = _client_with_service(chat_settings, service)
    recorder = _LogRecorder(chat_router_module.log)
    monkeypatch.setattr(chat_router_module, "log", recorder)

    client.post(
        "/chat",
        json={"history": [{"role": "user", "content": "How do I request access?"}]},
        headers=_auth(),
    )

    chat_request_logs = [e for e in recorder.entries if e["event"] == "chat_request"]
    assert len(chat_request_logs) == 1
    assert chat_request_logs[0]["refused"] is True
    assert chat_request_logs[0]["refusal_reason"]  # populated, not None/empty


def test_chat_request_log_has_no_refusal_reason_when_not_refused(
    gateway, settings: Settings, monkeypatch
) -> None:
    _index_corpus(gateway, settings)
    chat_settings = _chat_settings(settings)
    client = _client_with_service(chat_settings, _grounded_service(gateway, chat_settings))
    recorder = _LogRecorder(chat_router_module.log)
    monkeypatch.setattr(chat_router_module, "log", recorder)

    client.post(
        "/chat",
        json={"history": [{"role": "user", "content": "How do I request access to core systems?"}]},
        headers=_auth(),
    )

    chat_request_logs = [e for e in recorder.entries if e["event"] == "chat_request"]
    assert len(chat_request_logs) == 1
    assert chat_request_logs[0]["refused"] is False
    assert chat_request_logs[0]["refusal_reason"] is None


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


def test_idempotency_key_replay_with_different_principal_is_not_the_first_callers_answer(
    gateway, settings: Settings
) -> None:
    """PLAN 4.6.3 fix: the idempotency cache used to key only on the raw `Idempotency-Key` header,
    so a replay with a different `principal` silently returned the first caller's cached Answer —
    a cross-principal leak. Binding the key to (principal, history) means a mismatched principal
    is treated as a fresh request (a distinct trace id), not a replay."""
    _index_corpus(gateway, settings)
    chat_settings = _chat_settings(settings)
    service = _grounded_service(gateway, chat_settings)
    client = _client_with_service(chat_settings, service)

    body = {"history": [{"role": "user", "content": "How do I request access?"}]}
    headers = {**_auth(), "idempotency-key": "shared-key"}

    alice = _parse_sse(
        client.post("/chat", json={**body, "principal": "acct-alice"}, headers=headers).text
    )
    bob = _parse_sse(
        client.post("/chat", json={**body, "principal": "acct-bob"}, headers=headers).text
    )

    assert alice[-1]["traceId"] != bob[-1]["traceId"]


def test_idempotency_key_replay_with_different_history_is_not_the_first_callers_answer(
    gateway, settings: Settings
) -> None:
    """Same fix as above, for a mismatched `history` under the same reused idempotency key."""
    _index_corpus(gateway, settings)
    chat_settings = _chat_settings(settings)
    service = _grounded_service(gateway, chat_settings)
    client = _client_with_service(chat_settings, service)

    headers = {**_auth(), "idempotency-key": "shared-key"}

    first = _parse_sse(
        client.post(
            "/chat",
            json={"history": [{"role": "user", "content": "How do I request access?"}]},
            headers=headers,
        ).text
    )
    second = _parse_sse(
        client.post(
            "/chat",
            json={"history": [{"role": "user", "content": "A completely different question?"}]},
            headers=headers,
        ).text
    )

    assert first[-1]["traceId"] != second[-1]["traceId"]


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
