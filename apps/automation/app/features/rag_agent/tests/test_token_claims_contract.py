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
    Path(__file__).resolve().parents[6] / "packages" / "contracts" / "src" / "token-claims.json"
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
    company_name / integration present requires the other two."""
    dep = _schema()["dependentRequired"]
    business = {"company_id", "company_name", "integration"}
    for key in business:
        assert set(dep[key]) == business - {key}
