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
    # 1001-2003: the original ENG/HR corpus. 3001-3010: the substep 0.5.1 additions
    # (one page per knowledge-scope tag, two-label, classified, unlabeled, attachment,
    # group-restricted, empty) — see this directory's README.md page-mapping table.
    assert ids == {
        "1001",
        "1002",
        "1003",
        "2001",
        "2002",
        "2003",
        "3001",
        "3002",
        "3003",
        "3004",
        "3005",
        "3006",
        "3007",
        "3008",
        "3009",
        "3010",
    }


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
    account_ids = {u["accountId"] for u in restrictions["restrictions"]["user"]["results"]}
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


def test_tag_fixture_pages_carry_exactly_one_recognized_scope_label() -> None:
    """panel n/a · substep 0.5.1
    One fixture page per config/knowledge_scopes.json entry, each carrying exactly that
    scope's label — loaded through loader.py, not read from disk directly."""
    loader = _loader()
    by_tag = {
        "3001": "obi-general-test",
        "3002": "obi-mews-test",
        "3003": "obi-operacloud-test",
        "3004": "obi-toast-test",
    }
    for page_id, tag in by_tag.items():
        page = loader.load_page(page_id)
        assert page["id"] == page_id
        labels = loader.load_labels(page_id)
        assert labels is not None
        assert {lbl["name"] for lbl in labels["results"]} == {tag}


def test_two_label_fixture_page_carries_two_ordinary_labels() -> None:
    """panel n/a · substep 0.5.1
    The two-label fixture page carries two ordinary Confluence labels, neither a
    knowledge-scope tag (the two-tag case is a documented conflict, tested elsewhere)."""
    loader = _loader()
    labels = loader.load_labels("3005")
    assert labels is not None
    names = {lbl["name"] for lbl in labels["results"]}
    assert names == {"changelog", "internal"}
    recognized = {"obi-general-test", "obi-mews-test", "obi-operacloud-test", "obi-toast-test"}
    assert names.isdisjoint(recognized)


def test_classified_fixture_page_carries_the_reserved_label() -> None:
    """panel n/a · substep 0.5.1
    The classified fixture page carries exactly the reserved 'classified' label."""
    loader = _loader()
    labels = loader.load_labels("3006")
    assert labels is not None
    assert {lbl["name"] for lbl in labels["results"]} == {"classified"}


def test_unlabeled_fixture_page_has_no_labels() -> None:
    """panel n/a · substep 0.5.1
    The unlabeled fixture page carries zero labels."""
    loader = _loader()
    assert loader.load_labels("3007") is None


def test_attachment_fixture_page_has_one_real_parseable_attachment() -> None:
    """panel n/a · substep 0.5.1
    The attachment fixture page has exactly one attachment, resolvable to a real,
    non-empty file on disk."""
    loader = _loader()
    attachments = loader.load_attachments("3008")
    assert attachments is not None
    assert len(attachments["results"]) == 1
    file_name = attachments["results"][0]["file"]
    path = loader.attachment_path(file_name)
    assert path.is_file()
    assert path.read_text(encoding="utf-8").strip() != ""


def test_group_restricted_fixture_page_has_no_named_users() -> None:
    """panel n/a · substep 0.5.1
    The group-restricted fixture page names a group and zero individual users on its
    read restriction — the one category the original 1001-2003 corpus never covered."""
    loader = _loader()
    restrictions = loader.load_restrictions("3009")
    assert restrictions is not None
    restriction = restrictions["restrictions"]
    assert restriction["user"]["results"] == []
    assert len(restriction["group"]["results"]) == 1
    assert restriction["group"]["results"][0]["name"] == "security"


def test_empty_fixture_page_has_no_body_labels_restrictions_or_attachments() -> None:
    """panel n/a · substep 0.5.1
    The empty fixture page has an empty body, no labels, no restrictions, no attachments."""
    loader = _loader()
    page = loader.load_page("3010")
    assert page["body"]["storage"]["value"] == ""
    assert loader.load_labels("3010") is None
    assert loader.load_restrictions("3010") is None
    assert loader.load_attachments("3010") is None
