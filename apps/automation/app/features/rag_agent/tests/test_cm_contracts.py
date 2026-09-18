"""Regression tests for design panel `cm-contracts` (packages/contracts).

Substep p0-s0_5-reg-code-map (Protect: Code map). The `packages/contracts`
package is the shared shape of a chat request and answer so the widget and the
backend agree; these tests pin what is true on disk today, one test per panel
check, named after the panel id.

The contracts package lives OUTSIDE apps/automation, so the repo root is located
from this file's path (parents[6]): tests -> rag_agent -> features -> app ->
automation -> apps -> <repo root>.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[6]
_CONTRACTS_SRC = _REPO_ROOT / "packages" / "contracts" / "src"
_CHAT_YAML = _CONTRACTS_SRC / "openapi" / "chat.yaml"
_TOKEN_CLAIMS = _CONTRACTS_SRC / "token-claims.json"
_IFRAME_MESSAGES = _CONTRACTS_SRC / "iframe-messages.ts"

# The six chat types the panel names as the contract's schema surface.
_NAMED_CHAT_TYPES = (
    "ChatRequest",
    "ChatTurn",
    "ImageAttachment",
    "ChatStreamEvent",
    "Citation",
    "FeedbackRequest",
)


def _chat_document() -> dict:
    return yaml.safe_load(_CHAT_YAML.read_text())


def test_data_cm_contracts_openapi_chat_yaml_is_the_source_of_truth() -> None:
    """panel cm-contracts · substep p0-s0_5-reg-code-map
    Source of truth: packages/contracts/src/openapi/chat.yaml exists and parses
    as an OpenAPI document (an `openapi` version, an `info` block, and `paths`)."""
    assert _CHAT_YAML.is_file(), f"missing OpenAPI source of truth: {_CHAT_YAML}"
    doc = _chat_document()
    assert isinstance(doc, dict), "chat.yaml did not parse to a mapping"
    assert str(doc.get("openapi", "")).startswith("3."), (
        f"chat.yaml is not an OpenAPI 3.x document: openapi={doc.get('openapi')!r}"
    )
    assert "info" in doc and "paths" in doc, "chat.yaml lacks the OpenAPI info/paths sections"
    assert "/chat" in doc["paths"], "the chat contract does not define the /chat path"


def test_data_cm_contracts_defines_the_six_named_chat_types() -> None:
    """panel cm-contracts · substep p0-s0_5-reg-code-map
    Types: ChatRequest, ChatTurn, ImageAttachment, ChatStreamEvent, Citation and
    FeedbackRequest are each defined as schemas in the chat contract."""
    doc = _chat_document()
    schemas = doc.get("components", {}).get("schemas", {})
    for name in _NAMED_CHAT_TYPES:
        assert name in schemas, f"chat.yaml does not define schema {name!r}"
        assert isinstance(schemas[name], dict), f"schema {name!r} is not a mapping"


def test_data_cm_contracts_note_artifacts_are_present_and_carry_their_fields() -> None:
    """panel cm-contracts · substep p0-s0_5-reg-code-map
    The panel's "Planned" artifacts are present on disk today (panel Today line:
    already exist and are wired, not planned): token-claims.json carries the
    note's claim fields, and iframe-messages.ts carries obi:open/obi:token/obi:clear."""
    # token-claims.json: present, and carries the note's claim fields.
    assert _TOKEN_CLAIMS.is_file(), f"expected present token-claims schema: {_TOKEN_CLAIMS}"
    claims = json.loads(_TOKEN_CLAIMS.read_text())
    properties = claims.get("properties", {})
    for field in ("iss", "aud", "sub", "iat", "exp", "company_id", "company_name", "integration"):
        assert field in properties, f"token-claims.json is missing the note field {field!r}"

    # iframe-messages.ts: present, and carries exactly the three message-type literals.
    assert _IFRAME_MESSAGES.is_file(), f"expected present iframe-messages: {_IFRAME_MESSAGES}"
    iframe_text = _IFRAME_MESSAGES.read_text()
    for message in ("obi:open", "obi:token", "obi:clear"):
        assert f'"{message}"' in iframe_text, f"iframe-messages.ts is missing message {message!r}"
