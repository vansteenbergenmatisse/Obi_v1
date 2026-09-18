"""panel s-edge · substep 0.5.3

Direct unit coverage of `router.py`'s `_verify_api_key` and `_rate_limit_key` — the two edge
(Lock 0) checks: the host key (`CHAT_API_KEY`, with `chat_api_key_previous` for rotation
overlap) is checked server-to-server only, and the rate-limit key is the verified token's `sub`
claim (hashed), falling back to the client IP only when there is no token.

Host-key rejection (unconfigured -> 503) and rotation-overlap acceptance (current AND previous
both accepted) already have full end-to-end `TestClient` + DB coverage in
`confluence_sync/tests/test_chat_endpoint.py` (`test_unconfigured_api_key_fails_closed`,
`test_missing_api_key_is_rejected`, `test_previous_api_key_is_accepted_during_rotation_overlap`,
`test_key_outside_current_and_previous_is_rejected`). The tests below add a fast, DB-free
unit-level check of the same `_verify_api_key` function directly (no app, no network), and close
the one real gap: nothing anywhere calls or asserts on `_rate_limit_key` itself."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.features.rag_agent.application.auth_context import AuthContext, general_only_context
from app.features.rag_agent.server.router import _rate_limit_key, _verify_api_key
from app.platform.config import Settings
from app.shared.hashing import sha256_text


def _request(
    headers: dict[str, str] | None = None, client_host: str | None = "203.0.113.5"
) -> Request:
    header_list = [
        (key.lower().encode("latin-1"), value.encode("latin-1"))
        for key, value in (headers or {}).items()
    ]
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/chat",
        "headers": header_list,
        "query_string": b"",
        "client": (client_host, 12345) if client_host else None,
        "server": ("testserver", 80),
        "scheme": "http",
    }
    return Request(scope)


def _auth_header(token: str) -> dict[str, str]:
    return {"authorization": f"Bearer {token}"}


def _auth_context(*, token_subject: str) -> AuthContext:
    return AuthContext(
        company_id=None,
        company_name=None,
        integration=None,
        allowed_scopes=("obi-general-test",),
        allowed_sources=("confluence:default",),
        principal=None,
        token_subject=token_subject,
    )


def test_s_edge_host_key_rejects_unconfigured_and_wrong_key() -> None:
    """panel s-edge · substep 0.5.3
    No host key configured -> the check fails closed with 503; a wrong or missing key when a
    host key IS configured -> 401."""
    unconfigured = Settings(chat_api_key="", chat_api_key_previous="")
    with pytest.raises(HTTPException) as unconfigured_exc:
        _verify_api_key(_request(_auth_header("anything")), unconfigured)
    assert unconfigured_exc.value.status_code == 503

    configured = Settings(chat_api_key="the-real-key", chat_api_key_previous="")
    with pytest.raises(HTTPException) as wrong_key_exc:
        _verify_api_key(_request(_auth_header("wrong-key")), configured)
    assert wrong_key_exc.value.status_code == 401

    with pytest.raises(HTTPException) as missing_key_exc:
        _verify_api_key(_request(), configured)
    assert missing_key_exc.value.status_code == 401


def test_s_edge_host_key_accepts_current_and_previous_during_rotation() -> None:
    """panel s-edge · substep 0.5.3
    During a rotation overlap window (chat_api_key = current, chat_api_key_previous = old), a
    request using EITHER key is accepted."""
    settings = Settings(chat_api_key="key-b-current", chat_api_key_previous="key-a-previous")

    # neither call raises -> both the current and the previous key are accepted
    _verify_api_key(_request(_auth_header("key-a-previous")), settings)
    _verify_api_key(_request(_auth_header("key-b-current")), settings)


def test_s_edge_rate_limit_key_is_subject_hash_not_ip_when_tokened() -> None:
    """panel s-edge · substep 0.5.3
    The rate-limit key is the verified token subject's sha256 hash, not the client IP, so two
    different verified subjects behind the same IP get two different buckets; with no token at
    all, the key falls back to the client IP."""
    same_ip_request = _request(client_host="198.51.100.7")

    key_user_1 = _rate_limit_key(same_ip_request, _auth_context(token_subject="user-1"))
    key_user_2 = _rate_limit_key(same_ip_request, _auth_context(token_subject="user-2"))

    assert key_user_1 == f"sub:{sha256_text('user-1').hex()}"
    assert key_user_2 == f"sub:{sha256_text('user-2').hex()}"
    assert key_user_1 != key_user_2
    assert "198.51.100.7" not in key_user_1
    assert "198.51.100.7" not in key_user_2

    tokenless_key = _rate_limit_key(same_ip_request, general_only_context())
    assert tokenless_key == "ip:198.51.100.7"


def test_r1_limits_untokened_key_is_client_host_and_ignores_x_forwarded_for() -> None:
    """panel r1-limits · substep 0.6.1 decision `r1-limits-ipkey` (2026-09-18).
    The untokened fallback key is `request.client.host`; there is NO X-Forwarded-For parsing today
    (TRUSTED_PROXY_HOPS defaults to 0, set for real in 7.1.1). A forged X-Forwarded-For header must
    therefore change nothing — otherwise the limit would be trivially spoofable. This pins the code
    to the corrected panel today-line so a silent XFF change shows up as a failing test."""
    plain = _request(client_host="198.51.100.7")
    forged = _request(
        headers={"x-forwarded-for": "1.2.3.4, 5.6.7.8"}, client_host="198.51.100.7"
    )

    assert _rate_limit_key(plain, general_only_context()) == "ip:198.51.100.7"
    # a spoofed X-Forwarded-For does not become the key: the bucket is still the real peer address
    assert _rate_limit_key(forged, general_only_context()) == "ip:198.51.100.7"
