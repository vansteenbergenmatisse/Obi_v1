"""The /chat body accepts the dev-only simulated context, then ignores it (panel mi-contract).

Substep 8.4.2 · The widget carries the extended context. The standalone preset selector threads a
simulated integration context (company_id + three §D.13 slots) onto the request so the dev harness
can exercise the real pipeline. The body model accepts the SHAPE so the harness does not 400; the
backend logs and IGNORES it in favour of the verified token/note — the body never decides access
(never-bend rules 2–3; the integration context comes only from the verified token,
legacy-three-slot-context-contract §4). Unit level: pure body-model + helper behavior, no DB, no
network.
"""

from __future__ import annotations

import sys

import pytest
from pydantic import ValidationError

from app.features.rag_agent.server.router import ChatRequestBody, _note_simulated_context_ignored

# The `server` package re-exports the APIRouter instance as `server.router`, shadowing the
# submodule via `import`; reach the real module through sys.modules to monkeypatch its `log`.
chat_router = sys.modules["app.features.rag_agent.server.router"]


def _body(**overrides: object) -> dict:
    base: dict = {"history": [{"role": "user", "content": "hi"}]}
    base.update(overrides)
    return base


def test_widget_chat_body_accepts_a_simulated_context_shape() -> None:
    """panel mi-contract · substep 8.4.2
    A request carrying a well-shaped simulatedContext parses — the dev harness does not 400."""
    body = ChatRequestBody(
        **_body(
            simulated_context={
                "company_id": "preset-pos-to-pms",
                "slots": {"pos": "toast", "pms": "mews", "accounting": None},
            }
        )
    )
    assert body.simulated_context is not None
    assert body.simulated_context.company_id == "preset-pos-to-pms"
    assert body.simulated_context.slots.pos == "toast"
    assert body.simulated_context.slots.accounting is None


def test_widget_chat_body_without_simulated_context_is_unchanged() -> None:
    """panel mi-contract · substep 8.4.2
    A real/legacy session sends no simulatedContext — the field is absent, byte-compatible."""
    body = ChatRequestBody(**_body())
    assert body.simulated_context is None


def test_sec_malformed_simulated_context_is_rejected() -> None:
    """panel mi-contract · substep 8.4.2
    A malformed simulatedContext (slots not an object, extra keys) is rejected at the body shape —
    a hand-rolled body cannot smuggle an unexpected structure through."""
    with pytest.raises(ValidationError):
        ChatRequestBody(**_body(simulated_context={"company_id": "x", "slots": "nope"}))
    with pytest.raises(ValidationError):
        ChatRequestBody(**_body(simulated_context={"company_id": "x", "slots": {}, "extra": 1}))


def test_sec_simulated_context_is_logged_without_leaking_its_values(monkeypatch) -> None:
    """panel mi-contract · substep 8.4.2
    The ignored simulated context is logged as which slot KEYS were filled only — never the
    product ids or the company id (rule 10). The value never widens access: the helper only logs."""
    fake_log = _FakeLog()
    monkeypatch.setattr(chat_router, "log", fake_log)

    body = ChatRequestBody(
        **_body(
            simulated_context={
                "company_id": "preset-secret-co",
                "slots": {"pos": "toast", "pms": "mews", "accounting": None},
            }
        )
    )
    _note_simulated_context_ignored(body)

    assert fake_log.calls == [("simulated_context_ignored", {"filled_slots": ["pos", "pms"]})]
    serialized = repr(fake_log.calls)
    assert "preset-secret-co" not in serialized
    assert "toast" not in serialized
    assert "mews" not in serialized


def test_sec_absent_simulated_context_logs_nothing(monkeypatch) -> None:
    """panel mi-contract · substep 8.4.2
    No simulatedContext on the request → nothing is logged (the common real-session path)."""
    fake_log = _FakeLog()
    monkeypatch.setattr(chat_router, "log", fake_log)

    _note_simulated_context_ignored(ChatRequestBody(**_body()))

    assert fake_log.calls == []


class _FakeLog:
    """Records `log.info(event, **fields)` calls directly (same technique as test_answer_service's
    `_FakeLog`): structlog caches its logger on first use, so a monkeypatched fake is the
    order-independent way to capture a single log line."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def info(self, event: str, **fields: object) -> None:
        self.calls.append((event, fields))
