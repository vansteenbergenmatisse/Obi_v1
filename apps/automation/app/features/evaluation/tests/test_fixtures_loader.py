"""The fixture loader lists expected pages and loads page 1001 versions."""

from __future__ import annotations

from app.features.evaluation.fixtures import confluence_fixtures_dir, load_corpus_loader


def _loader():
    return load_corpus_loader()


def test_fixtures_dir_exists() -> None:
    d = confluence_fixtures_dir()
    assert d.is_dir()
    assert (d / "manifest.json").is_file()


def test_list_pages_expected_ids() -> None:
    loader = _loader()
    ids = {p["id"] for p in loader.list_pages()}
    assert ids == {"1001", "1002", "1003", "2001", "2002", "2003"}


def test_status_coverage() -> None:
    loader = _loader()
    by_id = {p["id"]: p for p in loader.list_pages()}
    assert by_id["1003"]["currentStatus"] == "archived"
    assert by_id["2003"]["currentStatus"] == "trashed"
    assert by_id["1001"]["currentStatus"] == "current"


def test_load_page_1001_versions() -> None:
    loader = _loader()
    assert loader.available_versions("1001") == [1, 2, 3]

    v1 = loader.load_page("1001", version=1)
    v2 = loader.load_page("1001", version=2)
    v3 = loader.load_page("1001", version=3)
    current = loader.load_page("1001")

    assert v1["version"]["number"] == 1
    assert v2["version"]["number"] == 2
    assert v3["version"]["number"] == 3

    # change detection: bodies differ across versions
    b1 = v1["body"]["storage"]["value"]
    b2 = v2["body"]["storage"]["value"]
    b3 = v3["body"]["storage"]["value"]
    assert b1 != b2  # v2 edited access SLA + added info panel
    assert b2 != b3  # v3 added Troubleshooting section
    assert "three business days" in b1
    assert "one business day" in b2
    assert "Troubleshooting" in b3
    assert "Troubleshooting" not in b2

    # v3 snapshot equals the current page fixture
    assert b3 == current["body"]["storage"]["value"]


def test_labels_restrictions_attachments() -> None:
    loader = _loader()
    labels = loader.load_labels("1001")
    assert labels is not None
    assert {lbl["name"] for lbl in labels["results"]} >= {"onboarding", "engineering"}

    restrictions = loader.load_restrictions("1002")
    assert restrictions is not None
    account_ids = {
        u["accountId"] for u in restrictions["restrictions"]["user"]["results"]
    }
    assert account_ids == {"acct-alice", "acct-bob"}

    attachments = loader.load_attachments("1001")
    assert attachments is not None
    titles = {a["title"] for a in attachments["results"]}
    assert "welcome-checklist.txt" in titles
    assert "team-roster.csv" in titles

    # page with none of these returns None
    assert loader.load_labels("2001") is None
    assert loader.load_restrictions("2001") is None


def test_attachment_files_present() -> None:
    loader = _loader()
    assert loader.attachment_path("welcome-checklist.txt").is_file()
    assert loader.attachment_path("team-roster.csv").is_file()
    assert loader.attachment_path("rollback-notes.md").is_file()
