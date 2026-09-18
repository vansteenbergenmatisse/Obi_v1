"""The text that becomes a vector keeps the verbatim child text separately, for citations
(design panel vd-text).

``retrieval_content`` (embedded) and ``display_content`` (cited) are two distinct columns on the
same active child ``Chunk`` row: the composition prefix (title/heading path, plus any context
note) sits ahead of the child's own text, but that child text is never rewritten in either
column — ``retrieval_content`` always ends with the exact ``display_content`` string, so a
citation built from ``display_content`` reproduces precisely what the embedder matched against.
"""

from __future__ import annotations

import pytest

from ._helpers import active_child_chunks, index_page

pytestmark = (
    pytest.mark.db
)  # substep 0.5.3: real local Postgres via this dir's session-scoped conftest


def test_vd_text_child_text_kept_separately_for_citations(gateway, settings):
    """panel vd-text · substep p0-s0_5-reg-the-vector-database
    Kept separately: the verbatim child text, for citations — an active child chunk's
    ``retrieval_content`` (what gets embedded) ends with its ``display_content`` (the verbatim
    text for citations) unaltered, while carrying the title/heading prefix ahead of it in a
    distinct, separately-stored column."""
    index_page(gateway, settings, 3001, version=1)
    children = active_child_chunks(3001)
    assert children, "expected at least one active child chunk"

    for row in children:
        assert row.display_content
        assert row.retrieval_content
        # the verbatim child text is preserved unaltered at the tail of what gets embedded
        assert row.retrieval_content.endswith(row.display_content)
        # something (the title/heading-path prefix) precedes it — the two are not identical
        assert row.retrieval_content != row.display_content
