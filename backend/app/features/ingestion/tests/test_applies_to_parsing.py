"""panel mi-applies · substep 8.2.2 — parsing "Applies to" tables out of a storage body.

Unit tests for the parse point: the standard "Applies to" table (the 8.2.1 authoring
decision) is lifted out of the storage-format body into raw field/value rule mappings,
and the remaining body — what normalize/chunk/hash see — no longer contains the table,
so a table-only edit never changes the content hash. Malformed table shapes fail loudly
with a named reason, never a silently dropped row. No network, no database.
"""

from __future__ import annotations

import pytest

from app.features.ingestion.domain import normalization as norm
from app.features.ingestion.domain.applicability import ApplicabilityValidationError
from app.features.ingestion.domain.applies_to_parsing import extract_applies_to

_CONTENT = (
    "<h1>Mews to QuickBooks Mapping</h1>"
    "<p>How nightly revenue postings map from Mews to QuickBooks Online journals.</p>"
    "<h2>Account Mapping</h2><p>Map each Mews accounting category to one ledger account.</p>"
)

_SOFTWARE_TABLE = (
    "<table><tbody><tr><th>Applies to</th><th>value</th></tr>"
    "<tr><td>level</td><td>software</td></tr>"
    "<tr><td>product</td><td>mews</td></tr></tbody></table>"
)

_CONNECTION_TABLE = (
    "<table><tbody><tr><th>Applies to</th><th>value</th></tr>"
    "<tr><td>level</td><td>connection</td></tr>"
    "<tr><td>connection</td><td>pms-accounting</td></tr>"
    "<tr><td>pms</td><td>mews</td></tr>"
    "<tr><td>accounting</td><td>quickbooks-online</td></tr>"
    "<tr><td>directions</td><td>pms_to_accounting</td></tr></tbody></table>"
)

_CONTENT_TABLE = (
    "<table><tbody><tr><th>Role</th><th>Name</th></tr>"
    "<tr><td>Manager</td><td>Alice</td></tr></tbody></table>"
)


def _reason(html: str) -> str:
    with pytest.raises(ApplicabilityValidationError) as exc:
        extract_applies_to(html)
    return exc.value.reason


def test_in2_applies_parse_extracts_rules_and_strips_table() -> None:
    """panel mi-applies · substep 8.2.2
    An Applies-to table parses into one field/value rule mapping, and the remaining body —
    what normalize/chunk/hash see — hashes identically to the body without the table, so a
    table-only edit is a metadata edit, never a content change."""
    extraction = extract_applies_to(_CONTENT + _SOFTWARE_TABLE)
    assert extraction.rules == [{"level": "software", "product": "mews"}]
    assert "applies to" not in extraction.body_storage.lower()
    with_table = norm.content_hash(norm.normalize_body(extraction.body_storage))
    without_table = norm.content_hash(norm.normalize_body(_CONTENT))
    assert with_table == without_table


def test_in2_applies_parse_leaves_content_tables_alone() -> None:
    """panel mi-applies · substep 8.2.2
    A normal content table (header is not 'Applies to') is no rule and stays in the body."""
    extraction = extract_applies_to(_CONTENT + _CONTENT_TABLE)
    assert extraction.rules == []
    blocks = norm.normalize_body(extraction.body_storage)
    assert norm.content_hash(blocks) == norm.content_hash(
        norm.normalize_body(_CONTENT + _CONTENT_TABLE)
    )


def test_in2_applies_parse_no_table_returns_body_unchanged() -> None:
    """panel mi-applies · substep 8.2.2
    A body with no Applies-to table at all yields zero rules — the label-only default."""
    extraction = extract_applies_to(_CONTENT)
    assert extraction.rules == []
    assert extraction.body_storage == _CONTENT


def test_in2_applies_parse_two_tables_in_page_order() -> None:
    """panel mi-applies · substep 8.2.2
    Several Applies-to tables OR together (§D.4): each is one complete rule, in page order."""
    extraction = extract_applies_to(_SOFTWARE_TABLE + _CONTENT + _CONNECTION_TABLE)
    assert extraction.rules == [
        {"level": "software", "product": "mews"},
        {
            "level": "connection",
            "connection": "pms-accounting",
            "pms": "mews",
            "accounting": "quickbooks-online",
            "directions": "pms_to_accounting",
        },
    ]
    assert "applies to" not in extraction.body_storage.lower()


def test_in2_applies_parse_header_and_fields_normalize_case_and_whitespace() -> None:
    """panel mi-applies · substep 8.2.2
    The editor capitalizes: 'APPLIES TO' still marks the table and ' Level '/' MEWS ' rows
    normalize to lowercase trimmed field/value pairs — a near-miss header silently treated
    as content would silently drop the whole rule."""
    html = (
        "<table><tbody><tr><th>APPLIES TO</th><th>value</th></tr>"
        "<tr><td> Level </td><td>Software</td></tr>"
        "<tr><td>Product</td><td> MEWS </td></tr></tbody></table>"
    )
    extraction = extract_applies_to(html)
    assert extraction.rules == [{"level": "software", "product": "mews"}]


def test_in2_applies_parse_duplicate_field_fails_loudly() -> None:
    """panel mi-applies · substep 8.2.2
    The same field twice in one table fails with a named reason — a silent last-one-wins
    would silently drop the first condition."""
    html = (
        "<table><tbody><tr><th>Applies to</th><th>value</th></tr>"
        "<tr><td>level</td><td>software</td></tr>"
        "<tr><td>product</td><td>mews</td></tr>"
        "<tr><td>product</td><td>toast</td></tr></tbody></table>"
    )
    assert _reason(html) == "duplicate-field"


def test_in2_applies_parse_row_without_value_cell_fails_loudly() -> None:
    """panel mi-applies · substep 8.2.2
    A data row with no value cell is a malformed table, named — never a dropped row."""
    html = (
        "<table><tbody><tr><th>Applies to</th><th>value</th></tr>"
        "<tr><td>level</td></tr></tbody></table>"
    )
    assert _reason(html) == "malformed-table"
