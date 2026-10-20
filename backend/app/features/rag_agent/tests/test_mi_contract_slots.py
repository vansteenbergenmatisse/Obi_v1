"""Contract tests for panels `mi-contract` and `mi-attrib` (substep 8.1.2).

packages/contracts gains the structured integration context (company_id + the three
POS/PMS/Accounting slots) alongside the never-dropped legacy `integration` claim, the
Citation attribution field ("which slot let it in"), and the OpenAPI documentation of
the 400-before-search and the out-of-allowlist refusal. These tests keep the contracts
package in lockstep with the backend: the slot names and the attribution vocabulary are
asserted against the catalog loader's `VALID_PRODUCT_ROLES` (substep 8.1.1), the one
backend definition of the three slot roles.

The contracts package lives OUTSIDE backend; the repo root is parents[5] of this file
(tests -> rag_agent -> features -> app -> backend -> <repo root>).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from app.platform.config.product_catalog import VALID_PRODUCT_ROLES

_REPO_ROOT = Path(__file__).resolve().parents[5]
_CONTRACTS_SRC = _REPO_ROOT / "packages" / "contracts" / "src"
_TOKEN_CLAIMS = _CONTRACTS_SRC / "token-claims.json"
_CHAT_YAML = _CONTRACTS_SRC / "openapi" / "chat.yaml"
_INDEX_TS = _CONTRACTS_SRC / "index.ts"

# The attribution vocabulary (§D.13 keuze 3 + substep 9.3.1): general, a named slot, a pair, or
# `connection` — the directed source → target box of Option A routing
# (ADR-directed-source-target-routing-labels).
_ATTRIBUTION_VALUES = frozenset({"general", "pair", "connection"}) | VALID_PRODUCT_ROLES


def _claims_schema() -> dict:
    return json.loads(_TOKEN_CLAIMS.read_text())


def _chat_document() -> dict:
    return yaml.safe_load(_CHAT_YAML.read_text())


def test_data_mi_contract_schema_documents_both_token_forms() -> None:
    """panel mi-contract · substep 8.1.2
    token-claims.json documents both forms — the legacy single `integration` claim and
    the structured `context.slots` — and the legacy form is never dropped."""
    properties = _claims_schema()["properties"]
    # Legacy form intact: the single-string integration claim is still documented.
    assert "integration" in properties, "legacy `integration` claim was dropped"
    assert properties["integration"]["type"] == "string"
    # Structured form present: context.slots with one nullable string per slot.
    assert "context" in properties, "token-claims.json lacks the structured `context` claim"
    context = properties["context"]
    assert context["required"] == ["slots"], "`context` must require `slots`"
    slots = context["properties"]["slots"]["properties"]
    for slot in sorted(VALID_PRODUCT_ROLES):
        assert slot in slots, f"slots lacks {slot!r}"
        assert slots[slot]["type"] == ["string", "null"], (
            f"slot {slot!r} must be one canonical catalog id or null (empty)"
        )


def test_data_mi_contract_slot_names_match_backend_catalog_roles() -> None:
    """panel mi-contract · substep 8.1.2
    Drift: the schema's slot names are exactly the backend catalog's three product roles
    (product_catalog.VALID_PRODUCT_ROLES) — contracts and backend stay in lockstep."""
    slots = _claims_schema()["properties"]["context"]["properties"]["slots"]
    assert set(slots["properties"]) == set(VALID_PRODUCT_ROLES)
    # No fourth slot can sneak in silently.
    assert slots["additionalProperties"] is False


def test_data_mi_contract_structured_form_is_company_id_only() -> None:
    """panel mi-contract · substep 8.1.2
    The structured form carries company_id only — no company name (§D.13 item 2):
    `context` requires `company_id`, and the legacy all-three-or-none rule is scoped to
    tokens WITHOUT `context`, so legacy tokens still carrying company_name stay valid."""
    schema = _claims_schema()
    assert schema["dependentRequired"] == {"context": ["company_id"]}
    # The all-three-or-none rule lives under the conditional that fires only when a token carries
    # NEITHER the structured context NOR (substep 9.3.1) the directed source/target form.
    assert schema["if"] == {
        "not": {"anyOf": [{"required": ["context"]}, {"required": ["source_system"]}]}
    }
    legacy_rule = schema["then"]["dependentRequired"]
    business = {"company_id", "company_name", "integration"}
    for key in business:
        assert set(legacy_rule[key]) == business - {key}
    # The structured context itself never carries a company name.
    context = schema["properties"]["context"]
    assert "company_name" not in json.dumps(context)
    assert context["additionalProperties"] is False


def test_data_mi_contract_openapi_documents_fail_closed_and_allowlist() -> None:
    """panel mi-contract · substep 8.1.2
    The OpenAPI documents the 400-before-search for an unknown slot value and the
    out-of-allowlist refusal (enforced at the gate, substep 8.1.3)."""
    post = _chat_document()["paths"]["/chat"]["post"]
    desc_400 = post["responses"]["400"]["description"]
    assert "400 before any search" in desc_400, (
        "the /chat 400 must document the unknown-slot fail-closed: 400 before any search"
    )
    description = post["description"]
    assert "allowlist" in description, "the /chat description must name the launch allowlist"
    assert "refused" in description, (
        "the /chat description must document the out-of-allowlist refusal"
    )


def test_data_mi_attrib_citation_schema_carries_attribution() -> None:
    """panel mi-attrib · substep 8.1.2
    Citation carries the attribution field ("which slot let it in") as an optional enum
    — optional because the backend assembles it in substep 8.3.4, not here."""
    citation = _chat_document()["components"]["schemas"]["Citation"]
    assert "attribution" in citation["properties"], "Citation lacks the attribution field"
    attribution = citation["properties"]["attribution"]
    assert attribution["type"] == "string"
    assert set(attribution["enum"]) == _ATTRIBUTION_VALUES
    assert "attribution" not in citation["required"], (
        "attribution must stay optional until 8.3.4 populates it"
    )


def test_data_mi_attrib_attribution_values_match_backend_roles() -> None:
    """panel mi-attrib · substep 8.1.2 / 9.3.1
    Drift: the attribution vocabulary is exactly general + the backend catalog's three slot roles
    + pair (§D.13 keuze 3) + the directed `connection` box (substep 9.3.1,
    ADR-directed-source-target-routing-labels) — no invented
    value on either side."""
    attribution = _chat_document()["components"]["schemas"]["Citation"]["properties"]["attribution"]
    assert set(attribution["enum"]) == (
        frozenset({"general", "pair", "connection"}) | VALID_PRODUCT_ROLES
    )


def test_data_mi_attrib_ts_citation_carries_attribution() -> None:
    """panel mi-attrib · substep 8.1.2 / 9.3.1
    The hand-written TS mirror (index.ts) carries the same field: a CitationAttribution
    union of the six values, used as Citation's optional `attribution`."""
    text = _INDEX_TS.read_text()
    match = re.search(r"export type CitationAttribution =([^;]+);", text)
    assert match, "index.ts does not export CitationAttribution"
    literals = set(re.findall(r'"([a-z]+)"', match.group(1)))
    assert literals == _ATTRIBUTION_VALUES
    assert "attribution?: CitationAttribution" in text, (
        "Citation must carry the optional attribution field"
    )
