"""Fixture gateway ``list_pages_by_label`` — CQL label discovery, mirrored offline.

The live client issues a CQL ``space.id = <id> AND label in (...)`` query (live-tested); the
fixture reproduces it in memory. These assert the fixture contract the sweep's discovery relies
on: filter by space + label, honor ``set_labels`` overrides and hidden/non-current exclusion,
and return nothing for an empty label list (no query).
"""

from __future__ import annotations

from app.platform.clients.fixture_confluence_client import FixtureConfluenceGateway

SPACE = 100
PAGE = 1001


def test_returns_only_pages_carrying_a_requested_label() -> None:
    g = FixtureConfluenceGateway()
    g.set_labels(PAGE, ["obi-toast-test"])
    assert [m.page_id for m in g.list_pages_by_label(SPACE, ["obi-toast-test"])] == [PAGE]


def test_empty_label_list_returns_nothing() -> None:
    g = FixtureConfluenceGateway()
    g.set_labels(PAGE, ["obi-toast-test"])
    assert g.list_pages_by_label(SPACE, []) == []


def test_unmatched_label_returns_nothing() -> None:
    g = FixtureConfluenceGateway()
    g.set_labels(PAGE, ["obi-toast-test"])
    assert g.list_pages_by_label(SPACE, ["obi-mews-test"]) == []


def test_hidden_page_is_excluded() -> None:
    g = FixtureConfluenceGateway()
    g.set_labels(PAGE, ["obi-toast-test"])
    g.hide(PAGE)
    assert g.list_pages_by_label(SPACE, ["obi-toast-test"]) == []
