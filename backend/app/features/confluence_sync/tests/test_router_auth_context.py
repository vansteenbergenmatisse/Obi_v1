"""PLAN 11.1c (ADR-0014) — the /chat edge-binding proof: the verified `X-Obi-Token` (NOT the
request body) drives the knowledge scope that reaches the answer service.

This is the security done-when for Task B1, extended with the AUTH-1 / CIP-A1 / CIP-A2 repair:
- AUTH-1 / CIP-A2: a validly-verified token from an INACTIVE platform is denied at /chat (401).
- CIP-A1: the integration claim is bound to the issuing platform's allow-list — a self-serving
  platform may assert only its own integration; a hub may vend the product integrations it lists.

It uses a recorder `AnswerProvider` (captures the `AuthContext` the router built) and the
`_StubTokenVerifier` from test_chat_endpoint (maps a raw header value to claims / a TokenError), so
no real JWT signing or JWKS fetch is needed. Because build_auth_context now gates on the ACTIVE
platform + its allowed_integrations, the app is pointed at a purpose-built temp registry (via the
`platforms_path` setting) rather than the committed platforms.json (whose only active platform is
the placeholder datahub) — the stub verifier still supplies the claims, but the issuer/integration
must line up with a real registry entry for the gate to admit them."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.features.rag_agent import Answer, AuthContext, TokenError, VerifiedClaims
from app.main import create_app
from app.platform.config import Settings

from .test_chat_endpoint import _auth, _chat_settings, _StubTokenVerifier

pytestmark = (
    pytest.mark.db
)  # substep 0.5.1: real local Postgres via this dir's session-scoped conftest

_MEWS_ISS = "https://app.mews.com"
_HUB_ISS = "https://hub.example.com"
_TOAST_ISS = "https://pos.toasttab.com"  # INACTIVE in the temp registry below


def _reg_entry(issuer, *, active, allowed_integrations):
    return {
        "issuer": issuer,
        "jwks_url": f"{issuer}/j",
        "domains": [],
        "lifetime_minutes": 60,
        "algs": ["RS256"],
        "active": active,
        "allowed_integrations": allowed_integrations,
    }


def _registry_file(tmp_path):
    """A registry with: a self-serving active mews platform (allowed only mews), an active hub
    that vends mews + toast, and an INACTIVE toast platform (still indexed for verification)."""
    p = tmp_path / "platforms.json"
    p.write_text(
        json.dumps(
            {
                "platforms": {
                    "mews": _reg_entry(_MEWS_ISS, active=True, allowed_integrations=["mews"]),
                    "hub": _reg_entry(
                        _HUB_ISS, active=True, allowed_integrations=["mews", "toast"]
                    ),
                    "toast": _reg_entry(_TOAST_ISS, active=False, allowed_integrations=["toast"]),
                },
                "integrations": {
                    "mews": ["obi-mews-test"],
                    "toast": ["obi-toast-test"],
                },
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


def _claims(issuer: str, integration: str | None) -> VerifiedClaims:
    if integration is None:
        return VerifiedClaims(issuer, "u1", None, None, None)
    return VerifiedClaims(issuer, "u1", "c1", "Co", integration)


@pytest.fixture
def client_and_recorder(settings: Settings, tmp_path):
    recorder = _Recorder()
    verifier = _StubTokenVerifier(
        {
            "MEWS": _claims(_MEWS_ISS, "mews"),  # self-serving, allowed -> scoped
            "HUB_TOAST": _claims(_HUB_ISS, "toast"),  # hub vends toast -> scoped
            "CROSS": _claims(_MEWS_ISS, "toast"),  # CIP-A1: mews may not assert toast -> 401
            "INACTIVE": _claims(_TOAST_ISS, "toast"),  # CIP-A2: inactive platform -> 401
            "WORDPRESS": _claims(_MEWS_ISS, "wordpress"),  # unknown integration -> 401
            "GARBAGE": TokenError("bad"),
        }
    )
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


def test_hub_vends_product_integration(client_and_recorder) -> None:
    """CIP-A1 hub model: the hub platform legitimately asserts a product integration it lists."""
    client, recorder = client_and_recorder
    resp = _post(client, token="HUB_TOAST")
    assert resp.status_code == 200
    assert recorder.last_auth is not None
    assert recorder.last_auth.allowed_scopes == ("obi-general-test", "obi-toast-test")


def test_cross_issuer_integration_is_401(client_and_recorder) -> None:
    """CIP-A1: a self-serving platform (mews) claiming another platform's integration (toast) is
    rejected at /chat, before the service is reached."""
    client, recorder = client_and_recorder
    resp = _post(client, token="CROSS")
    assert resp.status_code == 401
    assert recorder.last_auth is None


def test_inactive_platform_token_is_401(client_and_recorder) -> None:
    """AUTH-1 / CIP-A2: a validly-verified token from an inactive platform is denied at /chat."""
    client, recorder = client_and_recorder
    resp = _post(client, token="INACTIVE")
    assert resp.status_code == 401
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
