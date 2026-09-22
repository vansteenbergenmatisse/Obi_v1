"""`POST /chat` + `PATCH /chat/{trace_id}/feedback` (PLAN 4.4): security controls (auth, rate
limit, input validation, idempotency) and the real SSE stream against the indexed fixture corpus.
Only the two LLM stages (rewrite, generation) are faked — same discipline as
`test_answer_workflow.py`, which this file reuses helpers from.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.features.rag_agent import (
    Answer,
    AnswerProvider,
    AnswerService,
    AuthContext,
    CachingAnswerService,
    ClarificationReply,
    VerifiedClaims,
    chat_router_module,
)
from app.features.retrieval import HybridRetriever
from app.main import create_app
from app.platform.clients import build_embedding_provider, build_reranker
from app.platform.config import Settings
from schema.engine import get_reader_sessionmaker, get_sessionmaker

from ._helpers import index_page
from .test_answer_workflow import (
    _build_retriever,
    _CitingGenerator,
    _EchoRewriter,
    _ImageAnalyzingGenerator,
    _SilentGenerator,
)
from .test_retrieval_eval import _build_policy, _index_corpus

pytestmark = (
    pytest.mark.db
)  # substep 0.5.1: real local Postgres via this dir's session-scoped conftest

_API_KEY = "test-chat-key"


def _write_test_platforms() -> str:
    """AUTH-1/CIP-A1/CIP-A2 (gap repair): build_auth_context now gates on the ACTIVE platform +
    its allowed_integrations, so a verified token is only served when its issuer is an ACTIVE
    registry entry allowed to assert its integration. The committed platforms.json has only the
    placeholder `datahub` active (mews/toast/opera-cloud are inactive), so these functional /chat
    tests point at a purpose-built registry whose issuers ARE active with the right allow-lists:
      - `test-iss` (the default `_StubTokenVerifier()` issuer, integration=None) active, no
        integrations -> a general-only tokened request is served (its token_subject still drives
        the rate-limit / idempotency / answer-cache keys these tests assert on);
      - `https://app.mews.com` active, allowed ["mews"]; `https://pos.toasttab.com` active, allowed
        ["toast"] -> the mews/toast isolation + scope tests resolve to their own scopes only.
    Written once per test session under a temp dir; `_chat_settings` wires it via `platforms_path`.
    """
    d = Path(tempfile.mkdtemp(prefix="obi-chat-platforms-"))
    path = d / "platforms.json"

    def _p(issuer: str, allowed: list[str]) -> dict:
        return {
            "issuer": issuer,
            "jwks_url": f"{issuer}/jwks",
            "domains": [],
            "lifetime_minutes": 60,
            "algs": ["RS256"],
            "active": True,
            "allowed_integrations": allowed,
        }

    path.write_text(
        json.dumps(
            {
                "platforms": {
                    "test-iss": _p("test-iss", []),
                    "mews": _p("https://app.mews.com", ["mews"]),
                    "toast": _p("https://pos.toasttab.com", ["toast"]),
                },
                "integrations": {
                    "mews": ["obi-mews-test"],
                    "toast": ["obi-toast-test"],
                    "opera-cloud": ["obi-operacloud-test"],
                },
            }
        )
    )
    return str(path)


# Session-stable path; individual tests may still override `platforms_path` via `_chat_settings`.
_TEST_PLATFORMS_PATH = _write_test_platforms()


def _chat_settings(base: Settings, **overrides) -> Settings:
    return base.model_copy(
        update={
            "chat_api_key": _API_KEY,
            "chat_rate_limit_per_minute": 100,
            "chat_stream_interval_ms": 0,  # keep tests fast
            "platforms_path": _TEST_PLATFORMS_PATH,  # see _write_test_platforms (gap repair)
            **overrides,
        }
    )


def _client_with_service(settings: Settings, service: AnswerProvider) -> TestClient:
    app = create_app(settings=settings, start_scheduler=False)
    app.state.answer_service = service  # override the real (Anthropic-backed) singleton
    return TestClient(app)


def _auth() -> dict[str, str]:
    return {"authorization": f"Bearer {_API_KEY}"}


class _StubTokenVerifier:
    """Test double for `TokenVerifier` (PLAN 11.1c): maps a raw `X-Obi-Token` value to a
    `VerifiedClaims`, a raised `TokenError`, or (default) a subject-only claim whose subject is the
    header value itself. Set as `app.state.token_verifier` to drive the /chat auth path
    deterministically without real JWT signing/JWKS."""

    def __init__(self, claims_by_token: dict[str, object] | None = None) -> None:
        self._claims = claims_by_token or {}

    def verify(self, raw: str) -> VerifiedClaims:
        mapped = self._claims.get(raw)
        if isinstance(mapped, Exception):
            raise mapped
        if isinstance(mapped, VerifiedClaims):
            return mapped
        return VerifiedClaims(
            issuer="test-iss", subject=raw, company_id=None, company_name=None, integration=None
        )


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


def test_r1_limits_history_must_end_on_a_user_turn(gateway, settings: Settings) -> None:
    """panel r1-limits, check (b): history 1-20 turns, must end on a user turn."""
    chat_settings = _chat_settings(settings)
    client = _client_with_service(chat_settings, _grounded_service(gateway, chat_settings))
    resp = client.post(
        "/chat",
        json={"history": [{"role": "assistant", "content": "hi"}]},
        headers=_auth(),
    )
    assert resp.status_code == 400


def test_r1_limits_empty_history_is_rejected(gateway, settings: Settings) -> None:
    """panel r1-limits · substep p0-s0_5-reg-retrieval-stage-1
    History must be 1 to 20 turns: zero turns is below the lower bound and is rejected
    (enforced by `ChatRequestBody.history`'s `Field(min_length=1)`, not `_validate_history`,
    so this is a distinct code path from the other history/message/image limit checks below).
    """
    chat_settings = _chat_settings(settings)
    client = _client_with_service(chat_settings, _grounded_service(gateway, chat_settings))
    resp = client.post("/chat", json={"history": []}, headers=_auth())
    assert resp.status_code in (400, 422)


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


def test_r1_limits_image_caps_enforced_on_every_turn_not_only_the_last(
    gateway, settings: Settings
) -> None:
    """panel r1-limits · substep p0-s0_5-reg-retrieval-stage-1
    Images are checked on every turn, not just the newest: a too-many-images violation on an
    older, non-final turn is still rejected even though the final turn is itself within caps.
    """
    chat_settings = _chat_settings(settings, chat_max_images_per_turn=1)
    client = _client_with_service(chat_settings, _grounded_service(gateway, chat_settings))
    resp = client.post(
        "/chat",
        json={
            "history": [
                {
                    "role": "user",
                    "content": "what were in the earlier ones?",
                    "images": [
                        {"mediaType": "image/png", "data": "YQ=="},
                        {"mediaType": "image/png", "data": "Yg=="},
                    ],
                },
                {
                    "role": "user",
                    "content": "what's in this one?",
                },
            ]
        },
        headers=_auth(),
    )
    assert resp.status_code == 400


def test_image_within_caps_is_accepted_and_analysis_reaches_the_done_event(
    gateway, settings: Settings
) -> None:
    """panel r5-stream · substep p0-s0_5-reg-retrieval-stage-5
    PLAN 7.3/7.4, ADR-0009: an image-bearing turn is accepted, the vision-analysis call runs,
    and its text arrives on the SSE `done` event's `imageAnalysis` field, distinct from `answer`
    (the `done (with imageAnalysis)` half of the Events check)."""
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


class _SpyAnswerService:
    """PLAN 11.1c (ADR-0014): records the AuthContext `POST /chat` forwards into
    `AnswerService.answer` — proves the *verified token* (not the request body) drives scope,
    without needing a real scoped corpus. The per-integration token->scope resolution itself is
    proven in test_router_auth_context.py; here we only prove the tokenless/body-ignored path."""

    def __init__(self) -> None:
        self.calls: list[AuthContext] = []

    def answer(self, history, auth: AuthContext):
        self.calls.append(auth)
        return Answer(text="ok", refused=False, trace_id="1")


def test_tokenless_request_forwards_general_only_and_ignores_body_scope(
    gateway, settings: Settings
) -> None:
    """PLAN 11.1c: with no X-Obi-Token the service receives the general-only context, and a body
    `knowledge_scope` is NOT authoritative — it never reaches the service as scope (the verified
    token is the only scope source; token integration->scope resolution is covered by
    test_router_auth_context.py)."""
    chat_settings = _chat_settings(settings)
    spy = _SpyAnswerService()
    client = _client_with_service(chat_settings, spy)

    resp = client.post(
        "/chat",
        json={"history": [{"role": "user", "content": "hi"}], "knowledge_scope": "obi-mews-test"},
        headers=_auth(),
    )

    assert resp.status_code == 200
    assert spy.calls[0].allowed_scopes == ("obi-general-test",)
    assert spy.calls[0].token_subject is None


def test_malformed_knowledge_scope_is_rejected(gateway, settings: Settings) -> None:
    """PLAN 10.5, ADR-0011 decision 6: shape-validated, not whitelisted — a value that could
    never be a real scope (spaces, punctuation) is a 422, but an unrecognized-yet-well-shaped
    value is still accepted (degrades gracefully inside `AnswerService`, see
    `test_answer_service.py`)."""
    chat_settings = _chat_settings(settings)
    client = _client_with_service(chat_settings, _grounded_service(gateway, chat_settings))
    resp = client.post(
        "/chat",
        json={
            "history": [{"role": "user", "content": "hi"}],
            "knowledge_scope": "not a real scope!",
        },
        headers=_auth(),
    )
    assert resp.status_code == 422


# PLAN 11.1c (ADR-0014): the pre-existing "principal" and "knowledge_scope" cases are gone — body
# principal is now ignored and body knowledge_scope no longer affects scope, so a tokenless replay
# differing only by those fields legitimately shares the (general-only, no-subject) AuthContext and
# is a correct cache hit, not a leak. The AuthContext-keyed idempotency binding (principal, scopes,
# token_subject) is unit-covered in test_answer_cache.py; token-subject differentiation at the HTTP
# layer is covered by test_router_auth_context.py. The "history" case remains meaningful here.
_IDEMPOTENCY_REPLAY_CASES = {
    "history": (
        {"history": [{"role": "user", "content": "How do I request access?"}]},
        {"history": [{"role": "user", "content": "A completely different question?"}]},
    ),
}


@pytest.mark.parametrize(
    ("request_a", "request_b"),
    _IDEMPOTENCY_REPLAY_CASES.values(),
    ids=list(_IDEMPOTENCY_REPLAY_CASES.keys()),
)
def test_idempotency_key_replay_with_different_field_is_not_the_first_callers_answer(
    request_a: dict, request_b: dict, gateway, settings: Settings
) -> None:
    """PLAN 4.6.3 fix (extended PLAN 10.5 for `knowledge_scope`): the idempotency cache used to key
    only on the raw `Idempotency-Key` header, so a replay with a different principal/history/
    knowledge_scope silently returned the first caller's cached Answer — a cross-tenant/cross-scope
    leak. Binding the key to (principal, history, knowledge_scope) means a mismatch is treated as a
    fresh request (a distinct trace id), not a replay."""
    _index_corpus(gateway, settings)
    chat_settings = _chat_settings(settings)
    service = _grounded_service(gateway, chat_settings)
    client = _client_with_service(chat_settings, service)

    headers = {**_auth(), "idempotency-key": "shared-key"}

    first = _parse_sse(client.post("/chat", json=request_a, headers=headers).text)
    second = _parse_sse(client.post("/chat", json=request_b, headers=headers).text)

    assert first[-1]["traceId"] != second[-1]["traceId"]


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


def test_r1_limits_rate_limit_keyed_on_token_subject_when_tokened(
    gateway, settings: Settings
) -> None:
    """panel r1-limits, check (a): rate limiting is keyed on the verified token subject, not the
    client IP, once a request carries a token — two different token subjects hitting the same
    client each get their own bucket, and a subject that reuses its own bucket gets rate-limited."""
    chat_settings = _chat_settings(settings, chat_rate_limit_per_minute=1)
    service = _grounded_service(gateway, chat_settings)
    app = create_app(settings=chat_settings, start_scheduler=False)
    app.state.answer_service = service
    app.state.token_verifier = _StubTokenVerifier()  # default: subject == the header value
    client = TestClient(app)

    body = {"history": [{"role": "user", "content": "hi"}]}
    headers = _auth()
    first_alice = client.post("/chat", json=body, headers={**headers, "x-obi-token": "alice"})
    second_alice = client.post("/chat", json=body, headers={**headers, "x-obi-token": "alice"})
    first_bob = client.post("/chat", json=body, headers={**headers, "x-obi-token": "bob"})

    assert first_alice.status_code == 200
    assert second_alice.status_code == 429
    assert first_bob.status_code == 200


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
    """panel r5-stream · substep p0-s0_5-reg-retrieval-stage-5
    Events/format: a grounded turn streams `start`, at least one `token`, `citations`, then
    `done`, each as its own `data: {json}` block followed by a blank line (`_parse_sse` enforces
    the `data: ` prefix and blank-line separation on every block it parses) — and the
    reassembled `token` deltas equal `done.answer` verbatim.
    """
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


def test_r5_stream_tokens_are_paced_at_the_configured_chunk_size_and_interval(
    gateway, settings: Settings, monkeypatch
) -> None:
    """panel r5-stream · substep p0-s0_5-reg-retrieval-stage-5
    Events: `token` deltas are exactly `chat_token_chunk_chars` characters (the panel's "40 chars"
    default) except possibly the last, and each token event is paced by one
    `asyncio.sleep(chat_stream_interval_ms / 1000)` call (the panel's "every 15 ms") — proven
    without a real wall-clock wait by recording `asyncio.sleep` calls instead of awaiting them.
    Deliberately does NOT use `_chat_settings` (which overrides both knobs for test speed): this
    test pins the panel's actual defaults, not the fast-test override every other test here uses.
    """
    _index_corpus(gateway, settings)
    chat_settings = settings.model_copy(
        update={"chat_api_key": _API_KEY, "chat_rate_limit_per_minute": 100}
    )
    assert chat_settings.chat_token_chunk_chars == 40
    assert chat_settings.chat_stream_interval_ms == 15
    sleep_calls: list[float] = []

    async def _fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    monkeypatch.setattr(chat_router_module.asyncio, "sleep", _fake_sleep)
    client = _client_with_service(chat_settings, _grounded_service(gateway, chat_settings))

    resp = client.post(
        "/chat",
        json={"history": [{"role": "user", "content": "How do I request access to core systems?"}]},
        headers=_auth(),
    )

    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    token_events = [e for e in events if e["type"] == "token"]
    done = next(e for e in events if e["type"] == "done")
    # this corpus/generator combination produces an answer longer than one chunk — otherwise the
    # chunk-size assertion below would pass trivially on a single, short chunk.
    assert len(token_events) >= 2
    for event in token_events[:-1]:
        assert len(event["delta"]) == 40
    assert len(token_events[-1]["delta"]) <= 40
    assert "".join(e["delta"] for e in token_events) == done["answer"]
    # one sleep call per emitted token event, each for the configured interval
    assert sleep_calls == [0.015] * len(token_events)


def test_r5_stream_generation_failure_after_200_emits_sse_error_not_a_5xx(
    gateway, settings: Settings
) -> None:
    """panel r5-stream · substep p0-s0_5-reg-retrieval-stage-5
    Error after 200: the response has already committed to a 200 status (StreamingResponse starts
    sending as soon as the generator yields its first `start` event) by the time an unexpected
    failure inside `service.answer` can happen, so that failure must surface as an SSE `type:
    error` event on the still-200 stream, never an HTTP 5xx."""
    chat_settings = _chat_settings(settings)

    class _RaisingService:
        def answer(self, history, auth: AuthContext) -> Answer:
            raise RuntimeError("boom")

    client = _client_with_service(chat_settings, _RaisingService())

    resp = client.post(
        "/chat",
        json={"history": [{"role": "user", "content": "How do I request access?"}]},
        headers=_auth(),
    )

    assert resp.status_code == 200  # not a 5xx
    events = _parse_sse(resp.text)
    assert events[0]["type"] == "start"
    assert events[-1]["type"] == "error"
    assert events[-1]["error"]


class _CitingGeneratorFullProtocol(_CitingGenerator):
    """`_CitingGenerator` (test_answer_workflow.py) predates `generate_identity` being added to
    the `AnswerGenerator` protocol, so pyright flags every existing call site — a pre-existing
    gap out of scope here. Rather than adding one more instance of that same error, this local
    subclass completes the protocol for this file's one new use (never called: no test turn here
    is an identity question)."""

    def generate_identity(self, query: str, facts) -> str:
        raise AssertionError(
            "generate_identity must not be called: no test turn is an identity question"
        )


def test_r5_stream_trace_row_records_raw_query_candidates_scores_scopes_latency_answer_citations(
    gateway, settings: Settings
) -> None:
    """panel r5-stream · substep p0-s0_5-reg-retrieval-stage-5
    Trace: one `query_trace` row on the writer engine carries raw/rewritten query, retrieved
    candidates (page ids + chunk ids), rerank scores, allowed sources, allowed knowledge scopes,
    latency, the final answer, and citations — the full column set the panel names, not just the
    answer/rewritten_query/citations subset `test_answer_workflow.py` already checks.

    `allowed_knowledge_scopes` is only ever non-null when the PLAN 10.4 rollout flag
    (`enable_knowledge_scope_filtering`) is on (off by default, see `Settings` and
    `test_retrieval_knowledge_scope.py`), so this builds its own retriever with the flag enabled
    rather than reusing `_build_retriever`/`_grounded_service`, which leave it at the off
    default."""
    _index_corpus(gateway, settings)
    chat_settings = _chat_settings(settings)
    retriever = HybridRetriever(
        get_reader_sessionmaker(),
        build_embedding_provider(chat_settings),
        _build_policy(gateway),
        build_reranker(chat_settings),
        enable_knowledge_scope_filtering=True,
        trace_sessionmaker=get_sessionmaker(),
    )
    service = AnswerService(
        retriever, _EchoRewriter(), _CitingGeneratorFullProtocol(), get_sessionmaker()
    )
    client = _client_with_service(chat_settings, service)
    question = "How do I request access to core systems?"

    resp = client.post(
        "/chat",
        json={"history": [{"role": "user", "content": question}]},
        headers=_auth(),
    )
    assert resp.status_code == 200
    done = _parse_sse(resp.text)[-1]
    trace_id = int(done["traceId"])

    with get_sessionmaker()() as s:
        row = s.execute(
            text(
                "SELECT raw_query, rewritten_query, retrieved_page_ids, retrieved_chunk_ids, "
                "rerank_scores, allowed_sources, allowed_knowledge_scopes, latency_ms, answer, "
                "citations FROM query_trace WHERE id = :id"
            ),
            {"id": trace_id},
        ).one()

    assert row.raw_query == question  # _EchoRewriter echoes verbatim, so raw == rewritten here
    assert row.rewritten_query == question
    assert row.retrieved_page_ids  # candidates
    assert row.retrieved_chunk_ids
    assert row.rerank_scores  # scores
    assert row.allowed_sources == ["confluence:default"]
    assert row.allowed_knowledge_scopes == ["obi-general-test"]
    assert isinstance(row.latency_ms, int) and row.latency_ms >= 0
    assert row.answer == done["answer"]
    assert row.citations["markers"]


def test_s_audit_query_trace_persists_every_named_field_plus_subject_and_feedback(
    gateway, settings: Settings
) -> None:
    """panel s-audit · substep p0-s0_5-reg-security (Protect)
    Duplicates, under this panel's own name, the full per-query column set already proven by
    `test_r5_stream_...` (allowed_sources, allowed_knowledge_scopes, candidates, scores, answer,
    citations) plus `test_subject_hash_persisted_is_the_hash_not_the_raw_subject`'s subject-hash
    proof (test_answer_service.py) and `test_feedback_updates_trace_row`'s feedback proof — one
    end-to-end request through the real `/chat` and `PATCH /chat/{id}/feedback` endpoints, so the
    audit trail's own panel has a single test covering every field it names (decision excluded:
    the panel's own `today` line says that column stays target-only until it is built)."""
    from app.shared.hashing import sha256_text

    _index_corpus(gateway, settings)
    chat_settings = _chat_settings(settings)
    retriever = HybridRetriever(
        get_reader_sessionmaker(),
        build_embedding_provider(chat_settings),
        _build_policy(gateway),
        build_reranker(chat_settings),
        enable_knowledge_scope_filtering=True,
        trace_sessionmaker=get_sessionmaker(),
    )
    service = AnswerService(
        retriever, _EchoRewriter(), _CitingGeneratorFullProtocol(), get_sessionmaker()
    )
    app = create_app(settings=chat_settings, start_scheduler=False)
    app.state.answer_service = service
    app.state.token_verifier = _StubTokenVerifier()  # default: subject == the header value
    client = TestClient(app)
    question = "How do I request access to core systems?"

    resp = client.post(
        "/chat",
        json={"history": [{"role": "user", "content": question}]},
        headers={**_auth(), "x-obi-token": "user-s-audit"},
    )
    assert resp.status_code == 200
    done = _parse_sse(resp.text)[-1]
    trace_id = int(done["traceId"])

    patch_resp = client.patch(
        f"/chat/{trace_id}/feedback",
        json={"feedback": 1},
        headers={**_auth(), "x-obi-token": "user-s-audit"},
    )
    assert patch_resp.status_code == 200

    with get_sessionmaker()() as s:
        row = s.execute(
            text(
                "SELECT retrieved_page_ids, retrieved_chunk_ids, rerank_scores, allowed_sources, "
                "allowed_knowledge_scopes, answer, citations, feedback, subject_hash "
                "FROM query_trace WHERE id = :id"
            ),
            {"id": trace_id},
        ).one()

    assert row.retrieved_page_ids  # candidates
    assert row.retrieved_chunk_ids
    assert row.rerank_scores  # scores
    assert row.allowed_sources == ["confluence:default"]
    assert row.allowed_knowledge_scopes == ["obi-general-test"]
    assert row.answer == done["answer"]
    assert row.citations["markers"]
    assert row.feedback == 1
    # Gap CIP-4: the audit fingerprint is the hash of the ISSUER-NAMESPACED identity key
    # (`f"{issuer}\x00{subject}"`), not the raw `sub` — so identical `sub` from two trusted
    # issuers never collide in the trace. `_StubTokenVerifier` signs `issuer="test-iss"`, subject
    # = the header value "user-s-audit".
    assert row.subject_hash == sha256_text("test-iss\x00user-s-audit").hex()
    assert row.subject_hash != sha256_text("user-s-audit").hex()  # NOT the raw-subject hash
    assert row.subject_hash != "user-s-audit"


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


def test_r1_idem_header_is_optional(gateway, settings: Settings) -> None:
    """panel r1-idem, check (a): the `Idempotency-Key` header is optional — a request that omits
    it entirely still gets a normal, successful response."""
    _index_corpus(gateway, settings)
    chat_settings = _chat_settings(settings)
    client = _client_with_service(chat_settings, _grounded_service(gateway, chat_settings))
    body = {"history": [{"role": "user", "content": "How do I request access?"}]}

    resp = client.post("/chat", json=body, headers=_auth())

    assert resp.status_code == 200


def test_r1_idem_cache_entries_are_bounded(gateway, settings: Settings) -> None:
    """panel r1-idem, check (c): entries are bounded — once `max_entries` is exceeded, the oldest
    key stops being a cache hit rather than growing the cache forever."""
    _index_corpus(gateway, settings)
    chat_settings = _chat_settings(settings, chat_idempotency_cache_max_entries=2)
    client = _client_with_service(chat_settings, _grounded_service(gateway, chat_settings))
    body = {"history": [{"role": "user", "content": "How do I request access?"}]}

    first = _parse_sse(
        client.post("/chat", json=body, headers={**_auth(), "idempotency-key": "k1"}).text
    )
    client.post("/chat", json=body, headers={**_auth(), "idempotency-key": "k2"})
    client.post("/chat", json=body, headers={**_auth(), "idempotency-key": "k3"})  # evicts k1

    replay = _parse_sse(
        client.post("/chat", json=body, headers={**_auth(), "idempotency-key": "k1"}).text
    )
    assert first[-1]["traceId"] != replay[-1]["traceId"]  # k1 was evicted, not replayed


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


def test_r1_idem_cache_key_is_scoped_to_token_subject_not_body_principal(
    gateway, settings: Settings
) -> None:
    """panel r1-idem, check (b):
    Cache key: sha256(key | history | principal | knowledge_scope), target: token subject instead
    of body principal. `_idempotency_cache_key` (router.py) binds the `Idempotency-Key` header to
    the verified `AuthContext.token_subject`, not any body-supplied principal. This is the HTTP-
    level proof the audit found missing: `test_answer_cache_does_not_cross_token_subject_boundary`
    only exercises the OTHER cache (`CachingAnswerService`/`answer_cache._cache_key`) with no
    Idempotency-Key header at all, so it proves nothing about this path. Two different token
    subjects sending the identical Idempotency-Key header, same history, must never share a
    cached answer."""
    _index_corpus(gateway, settings)
    chat_settings = _chat_settings(settings)
    service = _grounded_service(gateway, chat_settings)
    app = create_app(settings=chat_settings, start_scheduler=False)
    app.state.answer_service = service
    app.state.token_verifier = _StubTokenVerifier()  # default: subject == the header value
    client = TestClient(app)

    body = {"history": [{"role": "user", "content": "How do I request access?"}]}
    headers = {**_auth(), "idempotency-key": "shared-key"}

    user_a = _parse_sse(
        client.post("/chat", json=body, headers={**headers, "x-obi-token": "user-a"}).text
    )
    user_b = _parse_sse(
        client.post("/chat", json=body, headers={**headers, "x-obi-token": "user-b"}).text
    )

    assert user_a[-1]["traceId"] != user_b[-1]["traceId"]


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


def test_answer_cache_does_not_cross_token_subject_boundary(gateway, settings: Settings) -> None:
    """PLAN 11.1c (ADR-0014): the answer cache is keyed off the verified AuthContext, so two
    different token subjects never share a cached answer. (Body `principal` is ignored now — the
    pre-11.1c body-principal variant of this test was removed; identity comes from the token.)"""
    _index_corpus(gateway, settings)
    chat_settings = _chat_settings(settings)
    cached_service = CachingAnswerService(
        _grounded_service(gateway, chat_settings), ttl_seconds=60.0
    )
    app = create_app(settings=chat_settings, start_scheduler=False)
    app.state.answer_service = cached_service
    app.state.token_verifier = _StubTokenVerifier()  # default: subject == the header value
    client = TestClient(app)

    body = {"history": [{"role": "user", "content": "How do I request access?"}]}
    user_a = _parse_sse(
        client.post("/chat", json=body, headers={**_auth(), "x-obi-token": "user-a"}).text
    )
    user_b = _parse_sse(
        client.post("/chat", json=body, headers={**_auth(), "x-obi-token": "user-b"}).text
    )

    assert user_a[-1]["traceId"] != user_b[-1]["traceId"]


def test_create_app_wires_the_answer_cache_by_default(settings: Settings) -> None:
    """`main.create_app` wraps the real `AnswerService` in `CachingAnswerService` (PLAN 5) —
    constructing the app makes no network call (same guarantee `build_answer_service` documents),
    so this asserts the wiring directly rather than through a live request."""
    app = create_app(settings=_chat_settings(settings), start_scheduler=False)
    assert isinstance(app.state.answer_service, CachingAnswerService)


def test_feedback_updates_trace_row(gateway, settings: Settings) -> None:
    """panel r5-feedback · substep p0-s0_5-reg-retrieval-stage-5
    `PATCH /chat/{trace_id}/feedback` with `feedback: 1` writes `query_trace.feedback` on the
    writer engine."""
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
    """panel r5-feedback · substep p0-s0_5-reg-retrieval-stage-5
    Auth same as /chat: a request with no `Authorization` header at all is rejected."""
    chat_settings = _chat_settings(settings)
    client = _client_with_service(chat_settings, _grounded_service(gateway, chat_settings))
    resp = client.patch("/chat/1/feedback", json={"feedback": 1})
    assert resp.status_code == 401


def test_r5_feedback_wrong_api_key_is_rejected(gateway, settings: Settings) -> None:
    """panel r5-feedback · substep p0-s0_5-reg-retrieval-stage-5
    Auth same as /chat: a *present but wrong* bearer token is rejected too — the pre-existing
    `test_feedback_requires_auth` only proves a *missing* header 401s, which is a distinct branch
    through `_verify_api_key` (empty token) from a wrong-but-well-formed one (mirrors `/chat`'s
    own `test_key_outside_current_and_previous_is_rejected`, proving the same auth check both
    endpoints share actually rejects a wrong key, not just an absent one)."""
    chat_settings = _chat_settings(settings)
    client = _client_with_service(chat_settings, _grounded_service(gateway, chat_settings))
    resp = client.patch(
        "/chat/1/feedback",
        json={"feedback": 1},
        headers={"authorization": "Bearer some-other-key"},
    )
    assert resp.status_code == 401


def test_feedback_rejects_invalid_value(gateway, settings: Settings) -> None:
    """panel r5-feedback · substep p0-s0_5-reg-retrieval-stage-5
    Body `feedback` is restricted to `1 | -1`: any other value is a 422."""
    chat_settings = _chat_settings(settings)
    client = _client_with_service(chat_settings, _grounded_service(gateway, chat_settings))
    resp = client.patch("/chat/1/feedback", json={"feedback": 2}, headers=_auth())
    assert resp.status_code == 422


def _query_trace_row_count() -> int:
    with get_sessionmaker()() as s:
        return s.execute(text("SELECT COUNT(*) FROM query_trace")).scalar_one()


def test_r1_short_small_talk_writes_no_query_trace_row(gateway, settings: Settings) -> None:
    """panel r1-short · substep 0.5.3
    A short reply without search: small talk never writes a query_trace row (scenario 3 of the
    panel — scenarios 1/2 are already covered by test_small_talk.py and test_clarification.py)."""
    chat_settings = _chat_settings(settings)
    client = _client_with_service(chat_settings, _grounded_service(gateway, chat_settings))
    before = _query_trace_row_count()

    resp = client.post(
        "/chat", json={"history": [{"role": "user", "content": "hi"}]}, headers=_auth()
    )

    assert resp.status_code == 200
    done = _parse_sse(resp.text)[-1]
    assert done["type"] == "done"
    assert done["refused"] is False
    assert done["citations"] == []  # a greeting reply, not a search-backed answer
    assert done["traceId"] is None
    assert _query_trace_row_count() == before  # no new query_trace row


def test_r1_short_vague_question_writes_no_query_trace_row(gateway, settings: Settings) -> None:
    """panel r1-short · substep 0.5.3
    A short reply without search: a too-vague question never writes a query_trace row (scenario 3
    of the panel — scenarios 1/2 are already covered by test_small_talk.py and
    test_clarification.py)."""
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
    before = _query_trace_row_count()

    resp = client.post(
        "/chat",
        json={"history": [{"role": "user", "content": "what are the limits?"}]},
        headers=_auth(),
    )

    assert resp.status_code == 200
    done = _parse_sse(resp.text)[-1]
    assert done["type"] == "done"
    assert done["needsClarification"] is True  # a clarifying question, not a search-backed answer
    assert done["refused"] is False
    assert done["citations"] == []
    assert done["traceId"] is None
    assert _query_trace_row_count() == before  # no new query_trace row


# --- customer-isolation + body-inertness regression tests -------------------------------------


def _set_chunk_tags(page_id: int, tags: list[str]) -> None:
    """Stamp a page's chunk knowledge-scope tags directly (the label->tag pipeline is proven
    elsewhere, e.g. test_scope_tagging_*; here we only need the retrieval-side boundary)."""
    with get_sessionmaker()() as s:
        s.execute(
            text("UPDATE chunk SET tags = :tags WHERE page_id = :pid"),
            {"tags": tags, "pid": page_id},
        )
        s.commit()


def _trace_page_and_chunk_ids(trace_id: int) -> tuple[list[int], list[int]]:
    with get_sessionmaker()() as s:
        row = s.execute(
            text("SELECT retrieved_page_ids, retrieved_chunk_ids FROM query_trace WHERE id = :id"),
            {"id": trace_id},
        ).one()
    return list(row.retrieved_page_ids or []), list(row.retrieved_chunk_ids or [])


def _active_child_chunk_ids(page_id: int) -> set[int]:
    with get_sessionmaker()() as s:
        return {
            int(r[0])
            for r in s.execute(
                text("SELECT id FROM chunk WHERE page_id = :p AND kind = 1 AND is_active"),
                {"p": page_id},
            )
        }


def test_auth6_chat_isolates_a_toast_page_from_a_mews_token_end_to_end(
    gateway, settings: Settings
) -> None:
    """gap AUTH-6 · ADR-0014 customer-isolation backstop (panels s-source / r3-deny).

    End-to-end proof through the real `POST /chat` surface (token -> AuthContext -> AnswerService
    -> reader-role retrieval -> query_trace + citations), not just the retriever unit: a Mews-token
    request must never surface a Toast-tagged page's id or chunk id in its trace or citations, while
    the Mews-authorized page IS returned and cited. The Toast control below proves the Toast page is
    genuinely retrievable for that query — so the Mews-side absence is real isolation, not an empty
    corpus or an unfindable page (this test cannot pass by returning nothing)."""
    index_page(gateway, settings, 3002, 1)  # "Mews PMS Sync Setup"
    index_page(gateway, settings, 3004, 1)  # "Toast POS Menu Sync"
    _set_chunk_tags(3002, ["obi-mews-test"])
    _set_chunk_tags(3004, ["obi-toast-test"])

    chat_settings = _chat_settings(settings)
    app = create_app(settings=chat_settings, start_scheduler=False)
    app.state.answer_service = _grounded_service(gateway, chat_settings)
    app.state.token_verifier = _StubTokenVerifier(
        {
            "mews-jwt": VerifiedClaims(
                issuer="https://app.mews.com",
                subject="u-mews",
                company_id="c1",
                company_name="Hotel",
                integration="mews",
            ),
            "toast-jwt": VerifiedClaims(
                issuer="https://pos.toasttab.com",
                subject="u-toast",
                company_id="c2",
                company_name="Diner",
                integration="toast",
            ),
        }
    )
    client = TestClient(app)
    question = "How does the sync work and what happens when it fails?"
    toast_chunk_ids = _active_child_chunk_ids(3004)
    assert toast_chunk_ids  # the toast page really produced searchable child chunks

    # Control: a Toast-authorized caller DOES retrieve and cite the Toast page for this query.
    toast_done = _parse_sse(
        client.post(
            "/chat",
            json={"history": [{"role": "user", "content": question}]},
            headers={**_auth(), "x-obi-token": "toast-jwt"},
        ).text
    )[-1]
    toast_pages, _ = _trace_page_and_chunk_ids(int(toast_done["traceId"]))
    assert 3004 in toast_pages
    assert any(str(c["pageId"]) == "3004" for c in toast_done["citations"])

    # The Mews caller: the Toast page id/chunk ids never appear in the trace or citations, while the
    # Mews-authorized page IS present and cited (allowed content returned -> not passing by empty).
    resp = client.post(
        "/chat",
        json={"history": [{"role": "user", "content": question}]},
        headers={**_auth(), "x-obi-token": "mews-jwt"},
    )
    assert resp.status_code == 200
    done = _parse_sse(resp.text)[-1]
    page_ids, chunk_ids = _trace_page_and_chunk_ids(int(done["traceId"]))

    assert 3004 not in page_ids  # toast page id never retrieved for a mews token
    assert not (set(chunk_ids) & toast_chunk_ids)  # nor any toast chunk id
    assert 3002 in page_ids  # the mews page IS retrieved
    assert done["refused"] is False
    assert done["citations"]  # grounded, non-empty
    assert all(str(c["pageId"]) != "3004" for c in done["citations"])
    assert any(str(c["pageId"]) == "3002" for c in done["citations"])


def test_cip1_forwarded_body_principal_is_inert_scope_and_principal_unchanged(
    gateway, settings: Settings
) -> None:
    """gap CIP-1 · ADR-0014, ADR-0004 default-deny. A body-supplied `principal` (a well-shaped,
    non-numeric garbage value the shape validator accepts) is inert: it never reaches the
    AuthContext the read path runs under. The served scope stays exactly the verified token's
    scopes and the recorded auth `principal` is None (v1 embedded users are always principal-less).
    Proven by capturing the AuthContext `/chat` forwards into the service."""
    chat_settings = _chat_settings(settings)
    spy = _SpyAnswerService()
    app = create_app(settings=chat_settings, start_scheduler=False)
    app.state.answer_service = spy
    app.state.token_verifier = _StubTokenVerifier(
        {
            "mews-jwt": VerifiedClaims(
                issuer="https://app.mews.com",
                subject="u-mews",
                company_id="c1",
                company_name="Hotel",
                integration="mews",
            )
        }
    )
    client = TestClient(app)

    resp = client.post(
        "/chat",
        json={
            "history": [{"role": "user", "content": "hi"}],
            "principal": "acct-injected-evil",  # accepted by shape validation, must be ignored
        },
        headers={**_auth(), "x-obi-token": "mews-jwt"},
    )

    assert resp.status_code == 200
    assert len(spy.calls) == 1
    served = spy.calls[0]
    assert served.principal is None  # body principal never became the read-path principal
    # scope is exactly the verified mews token's scopes (general + mews), unmoved by the body value
    assert served.allowed_scopes == ("obi-general-test", "obi-mews-test")


def test_authrt4_body_principal_cannot_split_the_token_subject_rate_limit_bucket(
    gateway, settings: Settings
) -> None:
    """gap AUTHRT-4 · C2 (securing-http-and-llm-endpoints). The rate-limit bucket derives from the
    verified `token_subject`, never the body `principal`. Two requests carrying the SAME token but
    DIFFERENT body principals share one bucket — so the second is limited (429). If the body
    principal could influence the key, a caller would dodge the limit by rotating it per request."""
    chat_settings = _chat_settings(settings, chat_rate_limit_per_minute=1)
    app = create_app(settings=chat_settings, start_scheduler=False)
    app.state.answer_service = _grounded_service(gateway, chat_settings)
    app.state.token_verifier = _StubTokenVerifier()  # default: subject == the x-obi-token value
    client = TestClient(app)

    body_a = {"history": [{"role": "user", "content": "hi"}], "principal": "acct-alpha"}
    body_b = {"history": [{"role": "user", "content": "hi"}], "principal": "acct-beta"}
    same_token = {**_auth(), "x-obi-token": "alice"}

    first = client.post("/chat", json=body_a, headers=same_token)
    second = client.post("/chat", json=body_b, headers=same_token)

    assert first.status_code == 200
    assert second.status_code == 429  # same token subject -> same bucket, body principal ignored
