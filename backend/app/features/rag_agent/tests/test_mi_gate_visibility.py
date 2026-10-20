"""ADR-source-system-decides-widget-eligibility (panel mi-gate / mi-contract): the HTTP surface of
the source-enablement visibility
gate — `router._resolve_auth_context`'s 403 mapping and the read-only `GET /chat/visibility`
probe (`router._visibility_payload`).

A verified directed token whose SOURCE is unknown or not in the catalog's `enabled_sources` is
refused on `POST /chat` with a 403 whose body is the fixed `{error, reason}` pair — distinct from
the 401 renew family (bad token / vend violation) — and NEVER names the product (never-bend rule
10). The visibility probe turns that same refusal into `{"visible": false, "reason":
"source_not_enabled"}` so the widget hides Obi before any chat. The target is never checked: any
target, known or not, is visible when the source is supported.

App- and DB-free: `_resolve_auth_context` / `_visibility_payload` read only `settings.platform_
registry` and the injected verifier, so a synthetic registry (like test_mi_gate_directed.py) and
a fake verifier returning VerifiedClaims verbatim exercise the full gate with the shipped
catalog as its default (enabled_sources = mews/toast/opera-cloud; xero deliberately disabled)."""

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


def test_mi_gate_disabled_source_maps_to_403_with_reason_and_no_product_id(tmp_path):
    """panel mi-gate · ADR-source-system-decides-widget-eligibility
    `_resolve_auth_context` maps SourceNotEnabledError to a 403 whose body is exactly
    {"error": "integration not available", "reason": "source_not_enabled"} — a 403 (not 401: off
    the renew path) — and the body never names the refused product (rule 10)."""
    reg = _registry(tmp_path, ["mews", "xero"])  # vends both → vend rights pass, enablement bites
    verifier = _FakeVerifier(_directed(source="xero", target="mews"))

    with pytest.raises(HTTPException) as exc:
        _resolve_auth_context(_request_with_token(), _settings(reg), verifier)

    assert exc.value.status_code == 403
    assert exc.value.detail == {
        "error": "integration not available",
        "reason": "source_not_enabled",
    }
    assert "xero" not in json.dumps(exc.value.detail)  # rule 10: no product id leaks


def test_mi_gate_visibility_probe_reports_hidden_for_disabled_source(tmp_path):
    """panel mi-contract · ADR-source-system-decides-widget-eligibility
    A known source that is not enabled (xero) reports {"visible": false, "reason":
    "source_not_enabled"}, so the frontend hides Obi before any chat round-trip."""
    reg = _registry(tmp_path, ["mews", "xero"])
    verifier = _FakeVerifier(_directed(source="xero", target="mews"))

    payload = _visibility_payload(_request_with_token(), _settings(reg), verifier)

    assert payload == {"visible": False, "reason": "source_not_enabled"}


def test_mi_gate_visibility_probe_hides_an_unknown_source(tmp_path):
    """panel mi-contract · ADR-source-system-decides-widget-eligibility
    A source the catalog does not know (Base's "PEP PMS") is not supported, so Obi is hidden —
    {"visible": false} — instead of the old 400 error that left the widget showing a failure."""
    reg = _registry(tmp_path, ["mews", "xero"])
    verifier = _FakeVerifier(_directed(source="PEP PMS", target="NetSuite"))

    payload = _visibility_payload(_request_with_token(), _settings(reg), verifier)

    assert payload == {"visible": False, "reason": "source_not_enabled"}


def test_mi_gate_visibility_probe_reports_visible_for_any_target(tmp_path):
    """panel mi-contract · ADR-source-system-decides-widget-eligibility
    An enabled source is visible whatever its target: a known enabled target (mews), a known
    target that is not enabled (xero), and a target the catalog does not know (NetSuite)."""
    reg = _registry(tmp_path, ["toast", "mews"])
    for target in ("mews", "xero", "NetSuite"):
        verifier = _FakeVerifier(_directed(source="toast", target=target))
        payload = _visibility_payload(_request_with_token(), _settings(reg), verifier)
        assert payload == {"visible": True}, target


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
        SourceNotEnabledHTTPError,
        render_source_not_enabled,
    )

    app = FastAPI()
    app.add_exception_handler(SourceNotEnabledHTTPError, render_source_not_enabled)

    @app.get("/boom")
    def _boom() -> dict:
        raise SourceNotEnabledHTTPError()

    resp = TestClient(app, raise_server_exceptions=False).get("/boom")

    assert resp.status_code == 403
    assert resp.json() == {"error": "integration not available", "reason": "source_not_enabled"}
    assert "detail" not in resp.json()
