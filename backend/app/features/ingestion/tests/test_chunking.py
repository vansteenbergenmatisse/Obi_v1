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


def test_i3_parents_size_target_1200_hard_cap_2000() -> None:
    """panel i3-parents · substep p0-s0_5-reg-ingestion-stage-3
    A parent stays whole up to the 2000-token hard cap; anything larger than the cap
    is split at the 1200-token target, and no resulting parent ever exceeds the cap."""
    under_cap = " ".join("lorem" for _ in range(1800))  # 1801 tokens: > target, <= hard cap
    over_cap = " ".join("ipsum" for _ in range(3000))  # 3001 tokens: > hard cap
    html = f"<h1>Doc</h1><h2>Under Cap</h2><p>{under_cap}</p><h2>Over Cap</h2><p>{over_cap}</p>"
    blocks = norm.normalize_body(html)
    plan = plan_chunks(page_id=2001, blocks=blocks, config=CFG, counter=TC)

    under_cap_parents = [pp for pp in plan if pp.parent.heading_path[-1] == "Under Cap"]
    over_cap_parents = [pp for pp in plan if pp.parent.heading_path[-1] == "Over Cap"]

    # a unit bigger than the target but within the hard cap is kept as one parent
    assert len(under_cap_parents) == 1
    assert CFG.parent_target < under_cap_parents[0].parent.tokens <= CFG.parent_max

    # a unit bigger than the hard cap is split into multiple parents, each at/under target
    assert len(over_cap_parents) > 1
    for pp in over_cap_parents:
        assert pp.parent.tokens <= CFG.parent_target
        assert pp.parent.tokens <= CFG.parent_max


def test_i3_parents_boundary_never_crosses_heading_section() -> None:
    """panel i3-parents · substep p0-s0_5-reg-ingestion-stage-3
    Two small heading sections that would easily fit token-wise into one 1200-token
    parent are never merged: each keeps its own parent, scoped to its own heading."""
    blocks = norm.normalize_body(SMALL_HTML)
    plan = plan_chunks(page_id=1001, blocks=blocks, config=CFG, counter=TC)
    ga = next(pp for pp in plan if pp.parent.heading_path[-1] == "Getting Access")
    kc = next(pp for pp in plan if pp.parent.heading_path[-1] == "Key Contacts")

    assert ga is not kc
    assert ga.parent.heading_path == ["Onboarding Guide", "Getting Access"]
    assert kc.parent.heading_path == ["Onboarding Guide", "Key Contacts"]
    # neither parent's text carries content from the other section
    assert "Slack" not in ga.parent.text
    assert "IT portal" not in kc.parent.text


def test_i3_children_size_target_400_min_150_max_750() -> None:
    """panel i3-children · substep p0-s0_5-reg-ingestion-stage-3
    Children land near the 400-token target; a would-be trailing window under the
    150-token minimum is merged back rather than left short, and none exceeds 750."""
    body = " ".join("lorem" for _ in range(800))
    html = f"<h1>Doc</h1><h2>Sec</h2><p>{body}</p>"
    blocks = norm.normalize_body(html)
    plan = plan_chunks(page_id=3001, blocks=blocks, config=CFG, counter=TC)
    pp = next(pp for pp in plan if pp.parent.heading_path[-1] == "Sec")

    assert len(pp.children) == 2  # the naive 3rd window (51 tokens) merges into the 2nd
    for c in pp.children:
        assert CFG.child_min <= c.tokens <= CFG.child_max


def test_i3_children_overlap_12_percent() -> None:
    """panel i3-children · substep p0-s0_5-reg-ingestion-stage-3
    Consecutive children share ~12% (child_overlap_ratio) of the child target in
    trailing/leading tokens."""
    words = [f"w{i:04d}" for i in range(500)]
    html = f"<h1>Doc</h1><h2>Sec</h2><p>{' '.join(words)}</p>"
    blocks = norm.normalize_body(html)
    plan = plan_chunks(page_id=4001, blocks=blocks, config=CFG, counter=TC)
    pp = next(pp for pp in plan if pp.parent.heading_path[-1] == "Sec")
    assert len(pp.children) > 1

    expected_overlap_tokens = int(CFG.child_target * CFG.child_overlap_ratio)
    for prev, nxt in zip(pp.children, pp.children[1:], strict=False):
        prev_words = prev.text.split()
        next_words = nxt.text.split()
        overlap_len = 0
        for k in range(1, min(len(prev_words), len(next_words)) + 1):
            if prev_words[-k:] == next_words[:k]:
                overlap_len = k
        assert overlap_len > 0
        overlap_text = " ".join(prev_words[-overlap_len:])
        assert TC.count(overlap_text) == expected_overlap_tokens


def test_i3_children_identity_four_keys_present() -> None:
    """panel i3-children · substep p0-s0_5-reg-ingestion-stage-3
    Every child chunk carries all four stable identity keys: section_key, positional_key,
    content_key and stable_key, correctly scoped (shared within a section, unique per chunk)."""
    blocks = norm.normalize_body(_big_html())
    plan = plan_chunks(page_id=1002, blocks=blocks, config=CFG, counter=TC)

    all_stable_keys: list[bytes] = []
    for pp in plan:
        for c in pp.children:
            for key in (c.section_key, c.positional_key, c.content_key, c.stable_key):
                assert isinstance(key, bytes)
                assert len(key) > 0
            # every child in a parent shares that parent's section identity
            assert c.section_key == pp.parent.section_key
            all_stable_keys.append(c.stable_key)
        # children within the same parent are positionally and stably distinct
        positional_keys = [c.positional_key for c in pp.children]
        assert len(positional_keys) == len(set(positional_keys))

    # stable keys are unique across the whole plan
    assert len(all_stable_keys) == len(set(all_stable_keys))
