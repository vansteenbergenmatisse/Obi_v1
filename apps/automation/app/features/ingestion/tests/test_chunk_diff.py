"""3-pass chunk diff → embedding reuse / re-embed / delete sets."""

from __future__ import annotations

from dataclasses import dataclass

from app.features.ingestion.domain.chunk_diff import diff_chunks


@dataclass
class K:
    stable_key: bytes
    positional_key: bytes
    content_key: bytes


def k(pos: bytes, content: bytes) -> K:
    return K(stable_key=pos + b"|" + content, positional_key=pos, content_key=content)


def test_identical_reuses_everything() -> None:
    old = [k(b"p0", b"a"), k(b"p1", b"b")]
    new = [k(b"p0", b"a"), k(b"p1", b"b")]
    d = diff_chunks(old, new)
    assert len(d.reuse) == 2
    assert all(m.reason == "exact" for m in d.reuse)
    assert d.reembed_indexes == []
    assert d.delete_old_indexes == []


def test_edited_in_slot_reembeds_only_that_chunk() -> None:
    old = [k(b"p0", b"a"), k(b"p1", b"b")]
    new = [k(b"p0", b"a"), k(b"p1", b"b2")]  # slot p1 content changed
    d = diff_chunks(old, new)
    reused_new = {m.new_index for m in d.reuse}
    assert reused_new == {0}
    assert d.reembed_indexes == [1]
    assert d.delete_old_indexes == []  # old p1 was consumed as an edit, not deleted


def test_moved_content_reuses_embedding() -> None:
    # same content "b" moves from position p1 to p2; p1 now holds new content
    old = [k(b"p0", b"a"), k(b"p1", b"b")]
    new = [k(b"p0", b"a"), k(b"p2", b"b"), k(b"p1", b"c")]
    d = diff_chunks(old, new)
    reasons = {(m.new_index, m.reason) for m in d.reuse}
    assert (0, "exact") in reasons
    assert (1, "moved") in reasons  # content "b" reused at new position
    assert d.reembed_indexes == [2]  # new content "c" in slot p1
    assert d.delete_old_indexes == []


def test_added_and_removed() -> None:
    old = [k(b"p0", b"a"), k(b"p1", b"b")]
    new = [k(b"p0", b"a"), k(b"p2", b"c")]  # p1/b removed, p2/c added
    d = diff_chunks(old, new)
    assert {m.new_index for m in d.reuse} == {0}
    assert d.reembed_indexes == [1]
    assert d.delete_old_indexes == [1]  # old "b" deleted


def test_reuse_count_helper() -> None:
    old = [k(b"p0", b"a"), k(b"p1", b"b"), k(b"p2", b"c")]
    new = [k(b"p0", b"a"), k(b"p1", b"b"), k(b"p2", b"c2")]
    d = diff_chunks(old, new)
    assert d.reuse_count == 2
    assert d.reembed_count == 1
