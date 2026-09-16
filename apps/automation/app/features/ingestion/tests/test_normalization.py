"""Regression coverage for panel i3-blocks: normalize Confluence HTML into blocks."""

from __future__ import annotations

from app.features.ingestion.domain.attachment_extraction import attachment_to_blocks
from app.features.ingestion.domain.normalization import Block, normalize_body


def test_i3_blocks_input_is_storage_html_plus_attachment_text() -> None:
    """panel i3-blocks · substep 0.5.2
    Input is Confluence storage-format HTML plus extracted attachment text: normalize_body
    handles the former and attachment_to_blocks handles the latter, both producing Blocks."""
    body_blocks = normalize_body("<h1>Title</h1><p>Some body text.</p>")
    attachment_blocks = attachment_to_blocks(title="notes.txt", text="Some attachment text.")

    assert body_blocks and all(isinstance(b, Block) for b in body_blocks)
    assert attachment_blocks and all(isinstance(b, Block) for b in attachment_blocks)


def test_i3_blocks_output_is_flat_block_list_with_heading_path() -> None:
    """panel i3-blocks · substep 0.5.2
    Output is a flat list of blocks with a heading path: a page with heading, paragraph,
    table, code and list produces a flat (non-nested) list whose non-heading blocks carry
    the nearest preceding heading(s) in heading_path."""
    html = """
    <h1>Section One</h1>
    <p>Intro paragraph.</p>
    <h2>Subsection</h2>
    <table><tr><td>Row1Cell1</td><td>Row1Cell2</td></tr></table>
    <ac:structured-macro ac:name="code"><ac:plain-text-body>print(1)</ac:plain-text-body></ac:structured-macro>
    <ul><li>Item A</li><li>Item B</li></ul>
    """

    blocks = normalize_body(html)

    assert [b.kind for b in blocks] == [
        "heading",
        "paragraph",
        "heading",
        "table",
        "code",
        "list",
    ]
    # flat: no nested containers, every element is a top-level Block in one list
    assert all(isinstance(b, Block) for b in blocks)

    by_kind = {b.kind: b for b in blocks if b.kind != "heading"}
    assert blocks[0].heading_path == ["Section One"]
    assert by_kind["paragraph"].heading_path == ["Section One"]
    assert blocks[2].heading_path == ["Section One", "Subsection"]
    assert by_kind["table"].heading_path == ["Section One", "Subsection"]
    assert by_kind["code"].heading_path == ["Section One", "Subsection"]
    assert by_kind["list"].heading_path == ["Section One", "Subsection"]


def test_i3_blocks_kept_whole_table_and_code_never_split() -> None:
    """panel i3-blocks · substep 0.5.2
    Kept whole: a multi-row/multi-cell table and a multi-line code macro each produce
    exactly one block, never one per row/cell/line."""
    html = """
    <table>
      <tr><td>Row1Cell1</td><td>Row1Cell2</td></tr>
      <tr><td>Row2Cell1</td><td>Row2Cell2</td></tr>
      <tr><td>Row3Cell1</td><td>Row3Cell2</td></tr>
    </table>
    <ac:structured-macro ac:name="code"><ac:plain-text-body>line one
line two
line three</ac:plain-text-body></ac:structured-macro>
    """

    blocks = normalize_body(html)

    table_blocks = [b for b in blocks if b.kind == "table"]
    code_blocks = [b for b in blocks if b.kind == "code"]

    assert len(table_blocks) == 1
    assert len(code_blocks) == 1
    assert "Row1Cell1" in table_blocks[0].text
    assert "Row2Cell1" in table_blocks[0].text
    assert "Row3Cell1" in table_blocks[0].text
    assert "line one" in code_blocks[0].text
    assert "line two" in code_blocks[0].text
    assert "line three" in code_blocks[0].text
