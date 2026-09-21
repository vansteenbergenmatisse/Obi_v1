"""PLAN 11.1c (ADR-0014) — the /chat edge-binding proof: the verified `X-Obi-Token` (NOT the
request body) drives the knowledge scope that reaches the answer service.

This is the security done-when for Task B1. It uses a recorder `AnswerProvider` (captures the
`AuthContext` the router built) and the `_StubTokenVerifier` from test_chat_endpoint (maps a raw
header value to claims / a TokenError), so no real JWT signing or JWKS fetch is needed. The real
`settings.platform_registry` (knowledge-base/config/platforms.json) maps integration `mews` ->
["obi-general-test", "obi-mews-test"]."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.features.rag_agent import Answer, AuthContext, TokenError, VerifiedClaims
from app.main import create_app
from app.platform.config import Settings

from .test_chat_endpoint import _auth, _chat_settings, _StubTokenVerifier

pytestmark = (
    pytest.mark.db
)  # substep 0.5.1: real local Postgres via this dir's session-scoped conftest


class _Recorder:
    """Captures the AuthContext /chat forwarded. `last_auth` stays None if the service is never
    reached (a request rejected at auth/validation before streaming)."""

    def __init__(self) -> None:
        self.last_auth: AuthContext | None = None

    def answer(self, history, auth: AuthContext) -> Answer:
        self.last_auth = auth
        return Answer(text="ok", refused=False, trace_id="1")


def _claims(integration: str | None) -> VerifiedClaims:
    if integration is None:
        return VerifiedClaims("https://app.mews.com", "u1", None, None, None)
    return VerifiedClaims("https://app.mews.com", "u1", "c1", "Hotel", integration)


@pytest.fixture
def client_and_recorder(settings: Settings):
    recorder = _Recorder()
    verifier = _StubTokenVerifier(
        {
            "MEWS": _claims("mews"),
            "WORDPRESS": _claims("wordpress"),  # unknown integration -> UnknownIntegrationError
            "GARBAGE": TokenError("bad"),
        }
    )
    app = create_app(settings=_chat_settings(settings), start_scheduler=False)
    app.state.answer_service = recorder
    app.state.token_verifier = verifier
    return TestClient(app), recorder


def _post(client: TestClient, *, token: str | None = None, **body_extra):
    headers = dict(_auth())
    if token is not None:
        headers["x-obi-token"] = token
    body = {"history": [{"role": "user", "content": "hi"}], **body_extra}
    return client.post("/chat", json=body, headers=headers)


def test_token_integration_drives_scopes(client_and_recorder) -> None:
    client, recorder = client_and_recorder
    resp = _post(client, token="MEWS")
    assert resp.status_code == 200
    assert recorder.last_auth is not None
    assert recorder.last_auth.allowed_scopes == ("obi-general-test", "obi-mews-test")


def test_body_scope_disagreeing_with_token_is_ignored(client_and_recorder) -> None:
    client, recorder = client_and_recorder
    resp = _post(client, token="MEWS", knowledge_scope="obi-toast-test")
    assert resp.status_code == 200
    # token wins — the recognized-but-disagreeing body scope is logged and ignored, never used
    assert recorder.last_auth is not None
    assert recorder.last_auth.allowed_scopes == ("obi-general-test", "obi-mews-test")


def test_unknown_body_scope_is_400_before_search(client_and_recorder) -> None:
    client, recorder = client_and_recorder
    # well-shaped but not a recognized slug -> 400 before the service is reached
    resp = _post(client, token="MEWS", knowledge_scope="obi-fake-test")
    assert resp.status_code == 400
    assert recorder.last_auth is None


def test_unknown_integration_is_401(client_and_recorder) -> None:
    client, recorder = client_and_recorder
    resp = _post(client, token="WORDPRESS")
    assert resp.status_code == 401
    assert recorder.last_auth is None


def test_tokenless_request_is_general_only(client_and_recorder) -> None:
    client, recorder = client_and_recorder
    resp = _post(client)
    assert resp.status_code == 200
    assert recorder.last_auth is not None
    assert recorder.last_auth.allowed_scopes == ("obi-general-test",)
    assert recorder.last_auth.token_subject is None


def test_bad_token_is_401_before_search(client_and_recorder) -> None:
    client, recorder = client_and_recorder
    resp = _post(client, token="GARBAGE")
    assert resp.status_code == 401
    assert recorder.last_auth is None
