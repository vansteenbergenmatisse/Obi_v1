"""Task 5 (panel mi-gate / mi-contract): the HTTP surface of the target-enablement visibility
gate — `router._resolve_auth_context`'s 403 mapping and the read-only `GET /chat/visibility`
probe (`router._visibility_payload`).

A verified directed token whose TARGET is not in the catalog's `enabled_targets` is refused on
`POST /chat` with a 403 whose body is the fixed `{error, reason}` pair — distinct from the 400
fail-closed family (unknown value) and the 401 renew family (bad token / vend violation) — and
NEVER names the product id (never-bend rule 10). The visibility probe turns that same refusal
into `{"visible": false, "reason": "target_not_enabled"}` so the widget can hide Obi before any
chat, while a 400/401 hard failure still propagates as today.

App- and DB-free: `_resolve_auth_context` / `_visibility_payload` read only `settings.platform_
registry` and the injected verifier, so a synthetic registry (like test_mi_gate_directed.py) and
a fake verifier returning VerifiedClaims verbatim exercise the full gate with the shipped
catalog as its default (enabled_targets = mews/toast/opera-cloud; xero deliberately disabled)."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import cast

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.features.rag_agent.server.router import (
    _resolve_auth_context,
    _visibility_payload,
)
from app.features.rag_agent.server.token_verifier import TokenVerifier, VerifiedClaims
from app.platform.config import Settings
from app.platform.config.platforms import load_platform_registry

_RECOGNIZED = frozenset({"obi-general-test", "obi-mews-test", "obi-toast-test"})
_HUB_ISS = "https://hub.example.com"


def _registry(tmp_path, allowed_integrations):
    p = tmp_path / "platforms.json"
    p.write_text(
        json.dumps(
            {
                "platforms": {
                    "hub": {
                        "issuer": _HUB_ISS,
                        "jwks_url": f"{_HUB_ISS}/j",
                        "domains": [],
                        "lifetime_minutes": 60,
                        "algs": ["RS256"],
                        "active": True,
                        "allowed_integrations": allowed_integrations,
                    }
                },
                "integrations": {"mews": [], "toast": [], "opera-cloud": [], "xero": []},
            }
        )
    )
    return load_platform_registry(p, _RECOGNIZED, allow_empty=False)


def _directed(*, source, target):
    return VerifiedClaims(
        issuer=_HUB_ISS,
        subject="u1",
        company_id=None,
        company_name=None,
        integration=None,
        source_system=source,
        target_system=target,
        business_id="B-9",
    )


class _FakeVerifier(TokenVerifier):
    """Returns the directed claims verbatim — the token string is never parsed here; the point
    of these tests is the gate + router mapping, not JWT verification (that is test_token_
    verifier.py). Subclasses TokenVerifier (without its registry wiring) only so the helper type
    checks; `verify` is fully overridden."""

    def __init__(self, claims: VerifiedClaims) -> None:
        self._claims = claims

    def verify(self, _raw: str) -> VerifiedClaims:
        return self._claims


def _request_with_token(token: str = "t") -> Request:
    headers = [(b"x-obi-token", token.encode("latin-1"))]
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/chat/visibility",
            "headers": headers,
            "query_string": b"",
            "client": ("203.0.113.9", 1234),
            "server": ("testserver", 80),
            "scheme": "http",
        }
    )


def _settings(reg) -> Settings:
    # `_resolve_auth_context` only reads `settings.platform_registry`; a namespace carrying that
    # one attribute is all the gate needs (a synthetic registry no real Settings would build).
    return cast(Settings, SimpleNamespace(platform_registry=reg))


def test_mi_gate_disabled_target_maps_to_403_with_reason_and_no_product_id(tmp_path):
    """panel mi-gate · Task 5
    `_resolve_auth_context` maps TargetNotEnabledError to a 403 whose body is exactly
    {"error": "integration not available", "reason": "target_not_enabled"} — a 403 (not 401:
    off the renew path; not 400: distinct from the fail-closed family) — and the body never
    names the disabled product id (rule 10)."""
    reg = _registry(tmp_path, ["mews", "xero"])  # vends both → vend rights pass, enablement bites
    verifier = _FakeVerifier(_directed(source="mews", target="xero"))

    with pytest.raises(HTTPException) as exc:
        _resolve_auth_context(_request_with_token(), _settings(reg), verifier)

    assert exc.value.status_code == 403
    assert exc.value.detail == {
        "error": "integration not available",
        "reason": "target_not_enabled",
    }
    assert "xero" not in json.dumps(exc.value.detail)  # rule 10: no product id leaks


def test_mi_gate_visibility_probe_reports_hidden_for_disabled_target(tmp_path):
    """panel mi-contract · Task 5
    The visibility probe reports the company as hidden — {"visible": false, "reason":
    "target_not_enabled"} — when the verified directed target is not enabled, so the frontend
    can hide Obi before any chat round-trip."""
    reg = _registry(tmp_path, ["mews", "xero"])
    verifier = _FakeVerifier(_directed(source="mews", target="xero"))

    payload = _visibility_payload(_request_with_token(), _settings(reg), verifier)

    assert payload == {"visible": False, "reason": "target_not_enabled"}


def test_mi_gate_visibility_probe_reports_visible_for_enabled_target(tmp_path):
    """panel mi-contract · Task 5
    An enabled target (mews, in the shipped enabled_targets) reports visible — the probe never
    adds a reason on the happy path."""
    reg = _registry(tmp_path, ["toast", "mews"])
    verifier = _FakeVerifier(_directed(source="toast", target="mews"))

    payload = _visibility_payload(_request_with_token(), _settings(reg), verifier)

    assert payload == {"visible": True}


def test_mi_gate_visibility_probe_propagates_400_unknown_target(tmp_path):
    """panel mi-contract · Task 5
    A 400/401 hard failure is NOT swallowed into visible:false — an unknown target still
    propagates as the 400 fail-closed family, so the probe never masks a malformed connection
    as merely hidden."""
    reg = _registry(tmp_path, ["mews", "xero"])
    verifier = _FakeVerifier(_directed(source="mews", target="no-such-system"))

    with pytest.raises(HTTPException) as exc:
        _visibility_payload(_request_with_token(), _settings(reg), verifier)

    assert exc.value.status_code == 400


def test_mi_gate_403_body_is_rendered_top_level_not_wrapped_in_detail():
    """panel mi-contract · Task 5
    The wired exception handler renders the 403 body TOP-LEVEL — {"error": ..., "reason": ...} —
    NOT FastAPI's default {"detail": ...}. This is the exact wire contract the frontend proxy
    forwards verbatim and the widget reads as `reason`; a regression to `detail` would silently
    break that read. Proven on a minimal app that registers the real handler + raises the real
    exception, so no signed JWT is needed."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.features.rag_agent.server.router import (
        TargetNotEnabledHTTPError,
        render_target_not_enabled,
    )

    app = FastAPI()
    app.add_exception_handler(TargetNotEnabledHTTPError, render_target_not_enabled)

    @app.get("/boom")
    def _boom() -> dict:
        raise TargetNotEnabledHTTPError()

    resp = TestClient(app, raise_server_exceptions=False).get("/boom")

    assert resp.status_code == 403
    assert resp.json() == {"error": "integration not available", "reason": "target_not_enabled"}
    assert "detail" not in resp.json()
