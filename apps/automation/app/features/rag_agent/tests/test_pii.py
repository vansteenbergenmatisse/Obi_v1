"""PII redaction: pattern-based scrubbing of text before it reaches an Anthropic call."""

from __future__ import annotations

from app.features.rag_agent.domain.pii import redact_pii


def test_redacts_email() -> None:
    out = redact_pii("contact alice@example.com for access")
    assert "alice@example.com" not in out
    assert "[REDACTED_EMAIL]" in out


def test_redacts_ssn() -> None:
    out = redact_pii("my ssn is 123-45-6789")
    assert "123-45-6789" not in out
    assert "[REDACTED_SSN]" in out


def test_redacts_credit_card() -> None:
    out = redact_pii("card number 4111111111111111 expires soon")
    assert "4111111111111111" not in out
    assert "[REDACTED_CARD]" in out


def test_redacts_phone_number() -> None:
    out = redact_pii("call me at 415-555-0100 tomorrow")
    assert "415-555-0100" not in out
    assert "[REDACTED_PHONE]" in out


def test_leaves_plain_text_untouched() -> None:
    text = "How do I request access to core systems when I join?"
    assert redact_pii(text) == text


def test_redacts_multiple_occurrences() -> None:
    out = redact_pii("email a@b.com or c@d.com")
    assert out.count("[REDACTED_EMAIL]") == 2


def test_obfuscated_email_evades_redaction_documented_known_gap() -> None:
    """Red-team (PLAN 5.3): documents, not fixes, a known limitation already stated in this
    module's docstring ("pattern-based, not NER"). A trivially obfuscated email ('at'/'dot'
    spelled out) does not match `_EMAIL_RE` and passes through unredacted. Recorded as an explicit
    regression marker so a future change to the regex is a deliberate decision, not an accidental
    behavior change caught by surprise; NER-grade detection is out of scope here (see module
    docstring), and a real fix would need a live-model or NER pass, not a regex tweak."""
    out = redact_pii("contact alice [at] example [dot] com for access")
    assert "alice [at] example [dot] com" in out
    assert "[REDACTED_EMAIL]" not in out
