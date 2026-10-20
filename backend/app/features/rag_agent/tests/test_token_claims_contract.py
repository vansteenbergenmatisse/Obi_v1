"""Task C1 (PLAN 11.1c): keep packages/contracts/src/token-claims.json in lockstep with the
security-authoritative verifier (server/token_verifier.py).

The verifier is the source of truth (it decides what a valid token is); this test fails if the
published JSON Schema drifts from it — same `required` set, same `aud` constant, same
all-three-or-none business-claims rule."""

from __future__ import annotations

import json
from pathlib import Path

from app.features.rag_agent.server import token_verifier

_TOKEN_CLAIMS_SCHEMA = (
    Path(__file__).resolve().parents[5] / "packages" / "contracts" / "src" / "token-claims.json"
)


def _schema() -> dict:
    return json.loads(_TOKEN_CLAIMS_SCHEMA.read_text())


def test_required_claims_match_the_verifier() -> None:
    schema = _schema()
    assert set(schema["required"]) == set(token_verifier.REQUIRED_CLAIMS)


def test_audience_constant_matches_the_verifier() -> None:
    schema = _schema()
    assert schema["properties"]["aud"]["const"] == token_verifier._AUD


def test_business_claims_are_all_three_or_none() -> None:
    """Mirrors the verifier's `partial business claims` rejection: any one of company_id /
    company_name / integration present requires the other two.

    Since substep 8.1.2 (panel mi-contract) the rule is scoped to the LEGACY form — it lives
    under the conditional that fires only when a token carries NEITHER the structured context nor
    (substep 9.3.1) the directed source/target form. A structured-context or directed token keeps
    its own shape; a context-less, connection-less token keeps today's trio verifier behavior."""
    schema = _schema()
    assert schema["if"] == {
        "not": {"anyOf": [{"required": ["context"]}, {"required": ["source_system"]}]}
    }
    dep = schema["then"]["dependentRequired"]
    business = {"company_id", "company_name", "integration"}
    for key in business:
        assert set(dep[key]) == business - {key}


def test_directed_connection_form_is_published_and_optional() -> None:
    """panel mi-contract · substep 9.3.1
    The directed source → target form (ADR-directed-source-target-routing-labels) is published in the contract: source_system,
    target_system and business_id are declared properties, none added to the REQUIRED registered
    claims (they are an OPTIONAL third business-claim form, like `context`)."""
    schema = _schema()
    props = schema["properties"]
    for field in ("source_system", "target_system", "business_id"):
        assert field in props, f"{field} must be a published token claim"
    assert props["source_system"]["type"] == "string"
    assert props["target_system"]["type"] == "string"
    # substep 8.5.3: Base signs business_id as a number; the verifier normalizes it to a string.
    assert props["business_id"]["type"] == ["string", "integer"]
    # optional: never promoted into the security-authoritative REQUIRED set.
    assert not ({"source_system", "target_system", "business_id"} & set(schema["required"]))
