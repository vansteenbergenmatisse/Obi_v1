"""First-index knowledge-scope tagging: the tag is already resolved on the very first sync."""

from __future__ import annotations

import pytest

from app.platform.db.models import PageSource

from ._helpers import active_child_chunks, index_page, read

pytestmark = pytest.mark.db


def test_tg_first_page_indexed_with_tags_already_resolved(gateway, settings):
    """panel tg-first · substep 0.5.2
    A first build creates document, version, chunks, and activates them with the label tags:
    a brand-new page (never seen before) carrying a Confluence label that maps to a known
    knowledge-scope tag must already carry that resolved tag on `page_source.tags` and on its
    active chunks after the one and only sync — not indexed bare and tagged in a later pass.
    """
    # page 3002 ("Mews PMS Sync Setup") is fresh to this test module and carries the Confluence
    # label "obi-mews-test", which config/knowledge_scopes.json recognizes as a knowledge-scope tag.
    index_page(gateway, settings, 3002, version=1)

    with read() as s:
        page_source = s.get(PageSource, 3002)
        assert page_source is not None
        assert "obi-mews-test" in page_source.tags

    chunks = active_child_chunks(3002)
    assert chunks and all("obi-mews-test" in c.tags for c in chunks)
