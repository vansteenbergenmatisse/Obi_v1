"""ADR-knowledge-scope-tagging-and-filtering — the reserved 'classified' scope is never selectable at the /chat HTTP edge.

`classified` must exist in knowledge_scopes.json but is never recognized/offerable: the loader
returns ``seen - {RESERVED_CLASSIFIED_SCOPE}`` (knowledge_scopes.py:76), so today the ONLY thing
standing between a body ``knowledge_scope: "classified"`` and the retrieval layer is that
set-exclusion — the router's membership check (`_validate_body_knowledge_scope`) simply treats it
as any other unknown scope. This file pins that HTTP-edge behavior: the literal is a 400 "unknown
knowledge scope" BEFORE any search runs, tokened or tokenless.

Same harness as test_router_auth_context.py: a recorder `AnswerProvider` (captures whether the
service was ever reached), the `_StubTokenVerifier` from test_chat_endpoint, and a purpose-built
temp registry wired via the `platforms_path` setting, so no real JWT signing or JWKS fetch is
needed."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.features.rag_agent import Answer, AuthContext, VerifiedClaims
from app.main import create_app
from app.platform.config import Settings

from .test_chat_endpoint import _auth, _chat_settings, _StubTokenVerifier

pytestmark = (
    pytest.mark.db
)  # substep 0.5.1: real local Postgres via this dir's session-scoped conftest

_MEWS_ISS = "https://app.mews.com"


def _registry_file(tmp_path):
    """A registry with one self-serving active mews platform — enough for a validly-tokened
    request to pass the auth gate so the classified rejection is proven on an otherwise-good
    request, not masked by a 401."""
    p = tmp_path / "platforms.json"
    p.write_text(
        json.dumps(
            {
                "platforms": {
                    "mews": {
                        "issuer": _MEWS_ISS,
                        "jwks_url": f"{_MEWS_ISS}/j",
                        "domains": [],
                        "lifetime_minutes": 60,
                        "algs": ["RS256"],
                        "active": True,
                        "allowed_integrations": ["mews"],
                    }
                },
                "integrations": {"mews": []},
            }
        )
    )
    return p


class _Recorder:
    """Captures the AuthContext /chat forwarded. `last_auth` stays None if the service is never
    reached (a request rejected at auth/validation before streaming)."""

    def __init__(self) -> None:
        self.last_auth: AuthContext | None = None

    def answer(self, history, auth: AuthContext) -> Answer:
        self.last_auth = auth
        return Answer(text="ok", refused=False, trace_id="1")


@pytest.fixture
def client_and_recorder(settings: Settings, tmp_path):
    recorder = _Recorder()
    verifier = _StubTokenVerifier({"MEWS": VerifiedClaims(_MEWS_ISS, "u1", "c1", "Co", "mews")})
    chat_settings = _chat_settings(settings, platforms_path=str(_registry_file(tmp_path)))
    app = create_app(settings=chat_settings, start_scheduler=False)
    app.state.answer_service = recorder
    app.state.token_verifier = verifier
    return TestClient(app), recorder


def _post(client: TestClient, *, token: str | None = None, **body_extra):
    headers = dict(_auth())
    if token is not None:
        headers["x-obi-token"] = token
    body = {"history": [{"role": "user", "content": "hi"}], **body_extra}
    return client.post("/chat", json=body, headers=headers)


def test_rag_knowledge_scope_classified_literal_is_never_selectable(client_and_recorder) -> None:
    """ADR-routing-labels-sole-content-axis — `classified` is reserved and can never be selected as a scope by any caller. The
    knowledge-scope axis is retired, so a body `knowledge_scope` is always logged and IGNORED (never
    a 400, never used): the reserved `classified` value therefore reaches retrieval no differently
    from any other — it is dropped on the floor. It never appears in the served `allowed_scopes`
    (which is empty), and the reserved label's real effect — removing a page from the index — lives
    on the ingestion/label axis, not here. A control request proves the client is not broken."""
    client, recorder = client_and_recorder

    resp = _post(client, token="MEWS", knowledge_scope="classified")
    assert resp.status_code == 200  # ignored, not a 400 — the token drives the request
    assert recorder.last_auth is not None
    assert "classified" not in recorder.last_auth.allowed_scopes  # never selected
    assert recorder.last_auth.allowed_scopes == ()  # ADR-routing-labels-sole-content-axis: no scope is selectable at all

    # tokenless path too: the reserved value is equally inert there
    resp_tokenless = _post(client, knowledge_scope="classified")
    assert resp_tokenless.status_code == 200

    # control: the identical request WITHOUT the body scope is served (fixture not broken)
    control = _post(client, token="MEWS")
    assert control.status_code == 200
    assert recorder.last_auth is not None
    assert "classified" not in recorder.last_auth.allowed_scopes
