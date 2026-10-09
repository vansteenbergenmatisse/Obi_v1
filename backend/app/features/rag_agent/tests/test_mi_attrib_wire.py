"""panel mi-attrib · substep 8.3.4 — attribution on the /chat wire (unit level).

`_wire_citations` is the single place a `Citation` DTO becomes the SSE/`done` wire shape the
widget consumes. These tests pin that the assembled attribution reaches the wire when present,
and that a citation with no attribution serializes byte-identically to today (the key is simply
absent), so the no-context / label-only path is unchanged and the OpenAPI drift test's "optional"
contract holds in practice.
"""

from __future__ import annotations

from app.features.rag_agent.schemas import Citation
from app.features.rag_agent.server.router import _wire_citations


def test_widget_attribution_is_serialized_on_the_wire_when_present() -> None:
    """panel mi-attrib · substep 8.3.4
    A citation the backend attributed carries its attribution enum on the wire."""
    wire = _wire_citations(
        [Citation(marker=1, page_id="p1", title="Toast + Mews", url="u/1", attribution="pair")]
    )
    assert wire == [
        {"id": "1", "pageId": "p1", "title": "Toast + Mews", "url": "u/1", "attribution": "pair"}
    ]


def test_widget_attribution_key_absent_when_no_attribution() -> None:
    """panel mi-attrib · substep 8.3.4
    A label-only / no-context citation omits the attribution key entirely — byte-compatible
    with the pre-8.3.4 wire shape (the widget renders exactly as before)."""
    wire = _wire_citations([Citation(marker=1, page_id="p1", title="Runbook", url="u/1")])
    assert wire == [{"id": "1", "pageId": "p1", "title": "Runbook", "url": "u/1"}]
    assert "attribution" not in wire[0]
