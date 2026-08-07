"""Token-aware parent/child chunking invariants."""

from __future__ import annotations

from app.features.ingestion.domain import normalization as norm
from app.features.ingestion.domain.chunking import ChunkConfig, plan_chunks
from app.features.ingestion.domain.tokenization import TokenCounter

TC = TokenCounter()
CFG = ChunkConfig()

SMALL_HTML = """
<h1>Onboarding Guide</h1>
<h2>Getting Access</h2>
<p>Request access to core systems via the IT portal when you join.</p>
<h2>Key Contacts</h2>
<p>Reach the platform team on Slack for help.</p>
"""


def _big_html() -> str:
    paras = "".join(
        f"<p>Paragraph {i}: the deployment runbook describes the production release "
        f"procedure in careful detail, step by step, including rollback.</p>"
        for i in range(60)
    )
    return f"<h1>Deployment Runbook</h1><h2>Procedure</h2>{paras}"


def test_small_section_yields_one_parent_one_child() -> None:
    blocks = norm.normalize_body(SMALL_HTML)
    plan = plan_chunks(page_id=1001, blocks=blocks, config=CFG, counter=TC)
    # 3 non-empty sections (preamble empty): Getting Access, Key Contacts + the H1 preamble
    assert len(plan) >= 2
    for pp in plan:
        assert len(pp.children) == 1
        assert pp.children[0].text == pp.parent.text
        assert pp.parent.tokens <= CFG.parent_max


def test_large_section_splits_into_multiple_children_under_max() -> None:
    blocks = norm.normalize_body(_big_html())
    plan = plan_chunks(page_id=1002, blocks=blocks, config=CFG, counter=TC)
    all_children = [c for pp in plan for c in pp.children]
    assert len(all_children) > 3
    for pp in plan:
        assert pp.parent.tokens <= CFG.parent_max
        for c in pp.children:
            assert c.tokens <= CFG.child_max


def test_children_cover_parent_content() -> None:
    blocks = norm.normalize_body(_big_html())
    plan = plan_chunks(page_id=1002, blocks=blocks, config=CFG, counter=TC)
    for pp in plan:
        parent_words = set(pp.parent.text.split())
        child_words = {w for c in pp.children for w in c.text.split()}
        assert parent_words <= child_words  # no parent content missing from children


def test_stable_keys_are_deterministic() -> None:
    blocks = norm.normalize_body(_big_html())
    a = plan_chunks(page_id=1002, blocks=blocks, config=CFG, counter=TC)
    b = plan_chunks(page_id=1002, blocks=blocks, config=CFG, counter=TC)
    keys_a = [(pp.parent.stable_key, [c.stable_key for c in pp.children]) for pp in a]
    keys_b = [(pp.parent.stable_key, [c.stable_key for c in pp.children]) for pp in b]
    assert keys_a == keys_b


def test_editing_one_section_keeps_other_section_keys_stable() -> None:
    html_v1 = SMALL_HTML
    html_v2 = SMALL_HTML.replace(
        "Reach the platform team on Slack for help.",
        "Reach the platform team on Slack or email for urgent help.",
    )
    p1 = plan_chunks(page_id=1001, blocks=norm.normalize_body(html_v1), config=CFG, counter=TC)
    p2 = plan_chunks(page_id=1001, blocks=norm.normalize_body(html_v2), config=CFG, counter=TC)
    # "Getting Access" section is untouched -> its section_key + child content_key unchanged
    ga1 = next(pp for pp in p1 if pp.parent.heading_path[-1] == "Getting Access")
    ga2 = next(pp for pp in p2 if pp.parent.heading_path[-1] == "Getting Access")
    assert ga1.parent.section_key == ga2.parent.section_key
    assert ga1.children[0].content_key == ga2.children[0].content_key
    # "Key Contacts" body changed -> its child content_key differs
    kc1 = next(pp for pp in p1 if pp.parent.heading_path[-1] == "Key Contacts")
    kc2 = next(pp for pp in p2 if pp.parent.heading_path[-1] == "Key Contacts")
    assert kc1.children[0].content_key != kc2.children[0].content_key


def test_empty_blocks_yield_empty_plan() -> None:
    assert plan_chunks(page_id=1, blocks=[], config=CFG, counter=TC) == []


def test_heading_path_propagates_to_children() -> None:
    blocks = norm.normalize_body(SMALL_HTML)
    plan = plan_chunks(page_id=1001, blocks=blocks, config=CFG, counter=TC)
    for pp in plan:
        for c in pp.children:
            assert c.heading_path == pp.parent.heading_path
