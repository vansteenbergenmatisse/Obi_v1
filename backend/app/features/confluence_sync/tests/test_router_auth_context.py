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

from app.features.rag_agent import (
    Answer,
    AuthContext,
    ContextSlots,
    TokenError,
    VerifiedClaims,
    chat_router_module,
)
from app.main import create_app
from app.platform.config import Settings

from .test_chat_endpoint import _auth, _chat_settings, _LogRecorder, _StubTokenVerifier

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
    that vends mews + toast (and, for the 8.1.3 slot tests, opera-cloud + xero), and an INACTIVE
    toast platform (still indexed for verification). opera-cloud/xero carry no product scope
    mapping of their own here — opera-cloud exists to prove the allowlist refusal, xero the
    inert accounting slot (O4)."""
    p = tmp_path / "platforms.json"
    p.write_text(
        json.dumps(
            {
                "platforms": {
                    "mews": _reg_entry(_MEWS_ISS, active=True, allowed_integrations=["mews"]),
                    "hub": _reg_entry(
                        _HUB_ISS,
                        active=True,
                        allowed_integrations=["mews", "toast", "opera-cloud", "xero"],
                    ),
                    "toast": _reg_entry(_TOAST_ISS, active=False, allowed_integrations=["toast"]),
                },
                "integrations": {
                    "mews": ["obi-mews-test"],
                    "toast": ["obi-toast-test"],
                    "opera-cloud": [],
                    "xero": [],
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


def _slot_claims(issuer: str, **slots) -> VerifiedClaims:
    """A structured (company_id + context.slots) note, substep 8.1.3 — company-ID-only."""
    return VerifiedClaims(issuer, "u1", "c1", None, None, slots=ContextSlots(**slots))


@pytest.fixture
def client_and_recorder(settings: Settings, tmp_path):
    recorder = _Recorder()
    verifier = _StubTokenVerifier(
        {
            "MEWS": _claims(_MEWS_ISS, "mews"),  # self-serving, allowed -> scoped
            "HUB_TOAST": _claims(_HUB_ISS, "toast"),  # hub vends toast -> scoped
            "CROSS": _claims(_MEWS_ISS, "toast"),  # CIP-A1: mews may not assert toast -> 401
            "INACTIVE": _claims(_TOAST_ISS, "toast"),  # CIP-A2: inactive platform -> 401
            # 8.1.3: unknown values are the 400-before-search family (chat.yaml, §D.11)
            "WORDPRESS": _claims(_MEWS_ISS, "wordpress"),  # unknown integration -> 400
            # G9 (substep 4.2): an issuer absent from the registry entirely -> 401
            "UNKNOWN_ISS": _claims("https://unknown.example.com", "mews"),
            "GARBAGE": TokenError("bad"),
            # 8.1.3 (panel mi-gate): structured three-slot notes
            "SLOTS_MEWS_EMPTY_POS": _slot_claims(_HUB_ISS, pms="mews"),  # empty POS -> serves
            "SLOTS_OPERA_PMS": _slot_claims(_HUB_ISS, pms="opera-cloud"),  # allowlist -> 401
            "SLOTS_UNKNOWN": _slot_claims(_HUB_ISS, pos="wordpress"),  # unknown value -> 400
            "SLOTS_INERT_ACCOUNTING": _slot_claims(_HUB_ISS, pms="mews", accounting="xero"),
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


def test_unknown_integration_is_400_before_search(client_and_recorder) -> None:
    """panel mi-gate · substep 8.1.3 (premise rewrite of test_unknown_integration_is_401)
    An unknown legacy integration value is now the 400-before-any-search fail-closed answer —
    the 8.1.2 contract (chat.yaml /chat 400: 'a verified-token slot (or legacy integration)
    value that resolves to no product in the catalog ... is a 400 before any search') and
    §D.11 extend the unknown-body-scope posture to unknown token values. Was a bare 401."""
    client, recorder = client_and_recorder
    resp = _post(client, token="WORDPRESS")
    assert resp.status_code == 400
    assert recorder.last_auth is None  # the answer service (and so any search) never ran


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


# --- substep 4.2 (coverage audit) gap closures: G4, G9 -----------------------------------------


def test_rt1_body_scope_disagreement_fires_the_ignored_log_and_token_scopes_serve(
    client_and_recorder, monkeypatch
) -> None:
    """panel r1-auth · substep 4.2 (coverage gap G4)
    'Valid token, body scope for another integration: the token wins and the mismatch is logged'
    — `test_body_scope_disagreeing_with_token_is_ignored` proves the token wins; this proves the
    `body_knowledge_scope_ignored` log line itself actually fires, exactly once, carrying the
    requested slug and the winning token scopes, while the served scopes stay the token's.
    Captured via a recorder wrapping the module logger — see `_LogRecorder`'s docstring for why
    structlog's `capture_logs()` cannot work this late in the test run."""
    client, recorder = client_and_recorder
    log_recorder = _LogRecorder(chat_router_module.log)
    monkeypatch.setattr(chat_router_module, "log", log_recorder)

    resp = _post(client, token="MEWS", knowledge_scope="obi-toast-test")

    assert resp.status_code == 200
    ignored = [e for e in log_recorder.entries if e["event"] == "body_knowledge_scope_ignored"]
    assert len(ignored) == 1  # the disagreement is logged, once
    assert ignored[0]["requested"] == "obi-toast-test"
    assert ignored[0]["token_scopes"] == ["obi-general-test", "obi-mews-test"]
    assert recorder.last_auth is not None
    # and the served scopes stay exactly the token's — the logged value never leaks into them
    assert recorder.last_auth.allowed_scopes == ("obi-general-test", "obi-mews-test")


def test_sec_chat_401_body_is_byte_identical_across_all_auth_failure_modes(
    client_and_recorder,
) -> None:
    """panel r1-auth · substep 4.2 (coverage gap G9; premise rewritten in 8.1.3)
    'Fail closed: ... 401 on any mismatch' with no detail on the wire: a garbage token, an issuer
    absent from the registry, an inactive platform, a cross-issuer integration claim, and an
    out-of-allowlist filled slot all yield a 401 whose body BYTES are identical — a caller can
    never tell which gate refused it (every mode raises the same bare `HTTPException(401,
    "invalid token")` in `_resolve_auth_context`), and none of them ever reaches the answer
    service. 8.1.3 premise rewrite: the unknown-integration mode (WORDPRESS) left this set —
    the 8.1.2 contract makes unknown values a 400 before any search (chat.yaml, §D.11) — and
    the allowlist refusal (SLOTS_OPERA_PMS) joined it."""
    client, recorder = client_and_recorder

    bodies: dict[str, bytes] = {}
    for token in ("GARBAGE", "UNKNOWN_ISS", "INACTIVE", "CROSS", "SLOTS_OPERA_PMS"):
        resp = _post(client, token=token)
        assert resp.status_code == 401
        bodies[token] = resp.content

    assert len(set(bodies.values())) == 1  # byte-identical across every failure mode
    assert bodies["GARBAGE"] == b'{"detail":"invalid token"}'  # and it is the bare generic body
    assert recorder.last_auth is None  # no failure mode ever reached the service


# --- substep 8.1.3 (panel mi-gate): the gate accepts slots at the /chat surface -----------------


def test_rt1_empty_pos_with_mews_pms_serves_at_chat(client_and_recorder) -> None:
    """panel mi-gate · substep 8.1.3
    An empty slot never refuses: a structured note with POS empty and PMS=mews is served, the
    one AuthContext carrying mews scopes and the filled PMS slot."""
    client, recorder = client_and_recorder
    resp = _post(client, token="SLOTS_MEWS_EMPTY_POS")
    assert resp.status_code == 200
    assert recorder.last_auth is not None
    assert recorder.last_auth.allowed_scopes == ("obi-general-test", "obi-mews-test")
    assert recorder.last_auth.slot_pms == "mews"
    assert recorder.last_auth.slot_pos is None


def test_rt1_pms_opera_cloud_slot_is_refused_at_chat(client_and_recorder) -> None:
    """panel mi-gate · substep 8.1.3
    A FILLED PMS slot outside the launch allowlist (opera-cloud; only Mews is allowed as PMS)
    refuses the session at /chat — the answer service is never reached."""
    client, recorder = client_and_recorder
    resp = _post(client, token="SLOTS_OPERA_PMS")
    assert resp.status_code == 401
    assert recorder.last_auth is None


def test_rt1_unknown_slot_value_is_400_before_search(client_and_recorder) -> None:
    """panel mi-gate · substep 8.1.3
    An unknown slot value (resolves to no catalog product) is a 400 BEFORE any search — the
    fail-closed posture of §D.11 / chat.yaml; the answer service is never reached."""
    client, recorder = client_and_recorder
    resp = _post(client, token="SLOTS_UNKNOWN")
    assert resp.status_code == 400
    assert recorder.last_auth is None


def test_rt1_accounting_slot_outside_support_serves_at_chat(client_and_recorder) -> None:
    """panel mi-gate · substep 8.1.3
    O4: a filled Accounting slot outside support (xero) never refuses — the session serves
    with the supported slots' scopes; the accounting slot rides the context, inert."""
    client, recorder = client_and_recorder
    resp = _post(client, token="SLOTS_INERT_ACCOUNTING")
    assert resp.status_code == 200
    assert recorder.last_auth is not None
    assert recorder.last_auth.allowed_scopes == ("obi-general-test", "obi-mews-test")
    assert recorder.last_auth.slot_accounting == "xero"


def test_rt1_legacy_note_serves_identically_to_one_filled_slot(client_and_recorder) -> None:
    """panel mi-gate · substep 8.1.3
    A legacy single-integration note behaves exactly as one filled slot at the endpoint: the
    legacy mews note and the structured PMS=mews note yield the same scopes and slots."""
    client, recorder = client_and_recorder
    assert _post(client, token="MEWS").status_code == 200
    assert recorder.last_auth is not None
    legacy = recorder.last_auth
    assert _post(client, token="SLOTS_MEWS_EMPTY_POS").status_code == 200
    assert recorder.last_auth is not None
    structured = recorder.last_auth
    assert legacy.allowed_scopes == structured.allowed_scopes
    assert (legacy.slot_pos, legacy.slot_pms, legacy.slot_accounting) == (
        structured.slot_pos,
        structured.slot_pms,
        structured.slot_accounting,
    )
    assert legacy.slot_pms == "mews"


def test_rt1_body_hint_never_overrides_the_note_slots(client_and_recorder, monkeypatch) -> None:
    """panel mi-gate · substep 8.1.3
    The body never decides access under the slot form either: a recognized body scope that
    disagrees with the structured note is ignored and logged once; the served scopes stay the
    note's (never-bend rule 2)."""
    client, recorder = client_and_recorder
    log_recorder = _LogRecorder(chat_router_module.log)
    monkeypatch.setattr(chat_router_module, "log", log_recorder)

    resp = _post(client, token="SLOTS_MEWS_EMPTY_POS", knowledge_scope="obi-toast-test")

    assert resp.status_code == 200
    ignored = [e for e in log_recorder.entries if e["event"] == "body_knowledge_scope_ignored"]
    assert len(ignored) == 1
    assert ignored[0]["requested"] == "obi-toast-test"
    assert recorder.last_auth is not None
    assert recorder.last_auth.allowed_scopes == ("obi-general-test", "obi-mews-test")
