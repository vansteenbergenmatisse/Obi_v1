"""Attachment text extraction + conditional-OCR gating (native-first, degrade gracefully)."""

from __future__ import annotations

import pytest

from app.features.ingestion.domain.attachment_extraction import (
    attachment_to_blocks,
    extract_attachment,
)


def test_plain_text() -> None:
    r = extract_attachment(filename="notes.txt", media_type="text/plain", data=b"hello world")
    assert r.method == "text"
    assert r.text == "hello world"
    assert r.needs_ocr is False


def test_csv_flattened_to_readable_rows() -> None:
    data = b"name,role\nAlice,Eng\nBob,Design\n"
    r = extract_attachment(filename="team.csv", media_type="text/csv", data=data)
    assert r.method == "csv"
    assert "Alice" in r.text and "Design" in r.text
    assert r.needs_ocr is False


def test_html_stripped_to_text() -> None:
    r = extract_attachment(
        filename="p.html", media_type="text/html", data=b"<h1>Title</h1><p>Body text</p>"
    )
    assert r.method == "html"
    assert "Title" in r.text and "Body text" in r.text
    assert "<h1>" not in r.text


def test_markdown_passthrough() -> None:
    r = extract_attachment(filename="r.md", media_type="text/markdown", data=b"# Heading\n\nnotes")
    assert r.method == "markdown"
    assert "Heading" in r.text


def test_pdf_with_good_native_text_does_not_need_ocr() -> None:
    r = extract_attachment(
        filename="doc.pdf",
        media_type="application/pdf",
        data=b"%PDF-fake",
        pdf_text_fn=lambda _: "This is a full page of extracted native text content.",
    )
    assert r.method == "pdf"
    assert r.needs_ocr is False
    assert "native text" in r.text


def test_scanned_pdf_with_empty_native_text_needs_ocr() -> None:
    r = extract_attachment(
        filename="scan.pdf",
        media_type="application/pdf",
        data=b"%PDF-scan" * 100,
        pdf_text_fn=lambda _: "   ",  # scanned page: native extraction yields nothing
    )
    assert r.method == "pdf"
    assert r.needs_ocr is True


def test_image_always_needs_ocr() -> None:
    r = extract_attachment(filename="diagram.png", media_type="image/png", data=b"\x89PNG...")
    assert r.needs_ocr is True
    assert r.text == ""


def test_unsupported_binary_is_skipped_not_crashed() -> None:
    r = extract_attachment(
        filename="a.bin", media_type="application/octet-stream", data=b"\x00\x01"
    )
    assert r.method == "skipped"
    assert r.needs_ocr is False


def test_missing_optional_lib_degrades_to_skipped() -> None:
    # docx path with no python-docx installed and no injected extractor -> skipped, no crash
    r = extract_attachment(
        filename="d.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        data=b"PK\x03\x04",
    )
    assert r.method in ("docx", "skipped")
    assert isinstance(r.text, str)


# -- attachment_to_blocks (fixes/phase-2 wiring) -----------------------------------------


@pytest.mark.parametrize("raw_text", ["Sign the code of conduct", "  Sign the code of conduct  \n"])
def test_attachment_to_blocks_wraps_text_under_title_keyed_heading_path(raw_text: str) -> None:
    """Covers both a plain body and one with surrounding whitespace — the wrapper strips it."""
    blocks = attachment_to_blocks(title="welcome-checklist.txt", text=raw_text)
    assert [b.kind for b in blocks] == ["heading", "paragraph"]
    assert blocks[0].text == "welcome-checklist.txt"
    assert blocks[0].heading_path == ["Attachments", "welcome-checklist.txt"]
    assert blocks[1].heading_path == ["Attachments", "welcome-checklist.txt"]
    assert blocks[1].text == "Sign the code of conduct"


def test_attachment_to_blocks_empty_text_returns_nothing() -> None:
    assert attachment_to_blocks(title="diagram.png", text="") == []
    assert attachment_to_blocks(title="diagram.png", text="   ") == []


def test_attachment_to_blocks_distinct_attachments_get_distinct_heading_paths() -> None:
    a = attachment_to_blocks(title="a.txt", text="content a")
    b = attachment_to_blocks(title="b.txt", text="content b")
    assert a[0].heading_path != b[0].heading_path
