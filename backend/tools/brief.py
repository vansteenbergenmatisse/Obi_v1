#!/usr/bin/env python3
"""Regenerate the markdown brief from the design page. Needs beautifulsoup4.

Usage: uv run python backend/tools/brief.py [design.html] [brief.md]
Defaults: docs/Final_docs/obi-rag-system-flow.html -> docs/Final_docs/obi-system-brief.md
"""

import datetime
import json
import re
import sys

from bs4 import BeautifulSoup, NavigableString, Tag

SRC = sys.argv[1] if len(sys.argv) > 1 else "docs/Final_docs/obi-rag-system-flow.html"
OUT = sys.argv[2] if len(sys.argv) > 2 else "docs/Final_docs/obi-system-brief.md"
h = open(SRC, encoding="utf-8").read()
soup = BeautifulSoup(h, "html.parser")
D = json.loads(soup.find("script", id="nodedata").string)
js = soup.find_all("script")[-1].string
WF = dict(re.findall(r'\b(\w+):"([^"]+)"', re.search(r"var WF = \{(.*?)\};", js, re.S).group(1)))
SEC = dict(re.findall(r'\b(\w+):"([^"]+)"', re.search(r"var SEC = \{(.*?)\};", js, re.S).group(1)))
ST = {
    "built": "Implemented",
    "change": "Implemented, needs changing",
    "build": "Planned",
    "discuss": "Decision needed",
    "unverified": "Unverified",
}


def inline(node):
    """Convert inline HTML to markdown text."""
    if isinstance(node, NavigableString):
        return re.sub(r"\s+", " ", str(node))
    out = []
    for c in node.children:
        if isinstance(c, NavigableString):
            out.append(re.sub(r"\s+", " ", str(c)))
        elif c.name == "code":
            out.append("`" + c.get_text() + "`")
        elif c.name in ("b", "strong"):
            out.append("**" + inline(c).strip() + "**")
        elif c.name == "a":
            href = c.get("href", "")
            t = inline(c).strip()
            out.append(t if href.startswith("#") else f"{t} ({href})")
        elif c.name == "span" and "tag" in c.get("class", []):
            out.append("[" + c.get_text(strip=True) + "]")
        elif c.name == "span" and "ref" in c.get("class", []):
            out.append(" (ref: " + c.get_text(strip=True) + ")")
        elif c.name == "input":
            out.append("[ ] ")
        elif c.name == "br":
            out.append("\n")
        else:
            out.append(inline(c))
    return "".join(out)


def cell(td):
    return inline(td).strip().replace("|", "\\|").replace("\n", " ")


def table_md(t):
    rows = [tr for tr in t.find_all("tr", recursive=False)] or t.find_all("tr")
    lines = []
    first = rows[0]
    if first.find("th"):
        hdr = [cell(x) for x in first.find_all(["th", "td"])]
        body = rows[1:]
    else:
        n = len(first.find_all(["td", "th"]))
        hdr = ["Field", "Value"] if n == 2 else [f"Col {i + 1}" for i in range(n)]
        body = rows
    lines.append("| " + " | ".join(hdr) + " |")
    lines.append("|" + "---|" * len(hdr))
    for tr in body:
        cells = [cell(x) for x in tr.find_all(["td", "th"])]
        cells += [""] * (len(hdr) - len(cells))
        lines.append("| " + " | ".join(cells[: len(hdr)]) + " |")
    return "\n".join(lines)


def svg_md(svg):
    boxes = []
    for g in svg.find_all("g", attrs={"data-n": True}):
        texts = [t.get_text(strip=True) for t in g.find_all("text")]
        cls = g.get("class", [])
        chg = " (changes from today)" if "chg" in cls else ""
        boxes.append(
            f"  - {texts[0] if texts else '?'}"
            + (f" — {' / '.join(texts[1:])}" if len(texts) > 1 else "")
            + f" → panel `{g['data-n']}`{chg}"
        )
    labels = [
        t.get_text(strip=True) for t in svg.find_all("text", class_="lb") if t.parent.name == "svg"
    ]
    out = ["Diagram (" + (svg.get("aria-label") or "no description") + ")"]
    if labels:
        out.append("  - labels: " + "; ".join(labels))
    out += boxes
    return "\n".join(out)


def block(node, depth=0):
    """Convert a block-level node to markdown."""
    if isinstance(node, NavigableString):
        s = str(node).strip()
        return s if s else ""
    name = node.name
    cls = node.get("class", [])
    if name == "h2":
        return "### " + node.get_text(strip=True)
    if name == "h3":
        return "#### " + node.get_text(strip=True)
    if name == "p":
        if "hint" in cls:
            return ""
        if "cap" in cls:
            return "_" + inline(node).strip() + "_"
        if "lead" in cls:
            return "**" + inline(node).strip() + "**"
        return inline(node).strip()
    if name in ("ul", "ol"):
        items = []
        for i, li in enumerate(node.find_all("li", recursive=False)):
            b = li.find("b", recursive=False)
            sp = li.find("span", recursive=False)
            if b and sp and not sp.get("class"):
                txt = "**" + inline(b).strip() + "** " + inline(sp).strip()
            else:
                txt = inline(li).strip()
                inner = li.find(["ul", "ol"], recursive=False)
                if inner:
                    txt = txt + "\n" + block(inner, depth + 1)
            bullet = f"{i + 1}." if name == "ol" else "-"
            items.append("  " * depth + f"{bullet} " + txt)
        return "\n".join(items)
    if name == "table":
        return table_md(node)
    if name == "pre":
        return "```\n" + node.get_text() + "\n```"
    if name == "svg":
        return svg_md(node)
    if name == "summary":
        h3 = node.find("h3")
        if h3:
            return "#### " + h3.get_text(strip=True)
        return ""
    if name == "div" and "callout" in cls:
        inner = "\n\n".join(x for x in (block(c, depth) for c in node.children) if x)
        return "\n".join("> " + l for l in inner.split("\n"))
    if name == "div" and "stage-card" in cls:
        return "\n\n".join(x for x in (block(c, depth) for c in node.children) if x)
    if name == "div" and "canvas" in cls:
        return "\n\n".join(x for x in (block(c, depth) for c in node.children) if x)
    if name == "details":
        return "\n\n".join(x for x in (block(c, depth) for c in node.children) if x)
    if name in ("div", "section"):
        return "\n\n".join(x for x in (block(c, depth) for c in node.children) if x)
    return inline(node).strip()


def panel_md(k, p):
    out = [f"##### Panel `{k}` · {p.get('h', '')} · [{ST.get(p.get('st'), p.get('st'))}]"]
    if p.get("n"):
        out.append(f"- Kind: {p['n']}")
    if p.get("simple"):
        out.append(f"- In plain words: {p['simple']}")
    if p.get("today"):
        out.append(f"- Today: {p['today']}")
    if p.get("f"):
        out.append("- Settings and rules:")
        out.append("  | Setting | Value |\n  |---|---|")
        for a, b in p["f"]:
            out.append(f"  | {a.replace('|', '/')} | {str(b).replace('|', '/')} |")
    if p.get("files"):
        out.append("- Where in the code:")
        for a, b in p["files"]:
            out.append(f"  - `{a}` — {b}")
    if p.get("s"):
        out.append("- Steps:")
        for i, s in enumerate(p["s"]):
            out.append(f"  {i + 1}. {s}")
    if p.get("c"):
        out.append("- Code:\n```\n" + p["c"] + "\n```")
    if p.get("t"):
        out.append("- How to test it:")
        for t in p["t"]:
            out.append(f"  - {t}")
    if p.get("note"):
        out.append(f"- Target and notes: {p['note']}")
    return "\n".join(out)


# panels grouped by section, in order of first appearance
order = []
for g in soup.find_all(attrs={"data-n": True}):
    if g["data-n"] not in order:
        order.append(g["data-n"])
for k in D:
    if k not in order:
        order.append(k)
by_sec = {}
for k in order:
    sec = SEC.get(k.split("-")[0])
    by_sec.setdefault(sec, []).append(k)

md = []
md.append("# Obi, part by part — the complete brief, A to Z")
md.append("")
md.append(
    "Generated on "
    + datetime.date.today().isoformat()
    + " from `"
    + SRC
    + "` (the target design for Obi). This file carries every visible section, every table, every diagram box and every click panel of that page, in the page's order, so a reader who cannot open the HTML has the same information."
)
md.append("")
md.append("## 0 · How to read this brief")
md.append("""
**What Obi is.** A chat widget that answers questions from Omniboost's Confluence pages with citations. Two workflows: **ingestion** (a published Confluence page becomes chunks with vectors in Postgres) and **retrieval** (a question becomes a cited answer from those chunks). One Postgres database (Supabase, pgvector) is both the relational store and the vector store. The backend is Python (FastAPI) under `backend`; the widget is Next.js under `frontend`; contracts and design tokens are packages.

**How the page marks reality.** Every stage, box and panel carries one status:

| Label | Meaning |
|---|---|
| Implemented | deployed and tested on the live store today |
| Implemented, needs changing | runs today, but the target changes it |
| Planned | does not exist in code yet |
| Unverified | coded but not applied or not proven on the live store |
| Decision needed | blocked on a call from the owner (Matisse) |
| Priority 1 / Priority 2 | the two target changes that ship first (section 01, "Ship order") |

Where a panel has both a **Today** line and a **Target and notes** line, the Today line describes the current code and the Target line the design. Both are given so that a reader can compute the delta.

**How this brief is organised.** Sections 01 to 11 follow the page. Each section gives the plain-language lede (written for leadership), then its subsections, tables, callouts and diagrams, then every click panel that belongs to that section (panel id, status, plain words, today, settings, code locations with line numbers where the page has them, steps, code, tests, notes). Panel ids are stable references: `r5-coverage` is the coverage check panel wherever it is mentioned.

**For the agent that will compare this to the codebase and write the implementation plan.**

1. Treat every "Today" line, every "Where in the code" path and every line-number reference as a claim to verify against the repository. Record each claim as confirmed, drifted, or missing.
2. Treat every "Target" line, every "Planned" panel and every "Implemented, needs changing" panel as a delta to implement. The checklist in section 01.1 is the acceptance list: one checkbox per verifiable task with its section and panel references.
3. Group the deltas by the ship order in section 01: Priority 1 (exact chunk through search, rerank and answer; sections 06.2 to 06.5), Priority 2 (batched support check before send; section 06.5), then the rest in section order (ingestion fingerprint and whole-page rebuild, label-gated ingestion, scope_state and the RESTRICTIVE policy, the embedding work in 03.2, the folder move in 01.2).
4. Do not implement anything tagged "Decision needed" without the owner's call. Section 11 lists every open decision; several sections repeat the tag in place. The page proposes a default for each; state the default in the plan and mark it as awaiting confirmation.
5. Every threshold and depth on the page (refusal threshold 0.10, `coverage_min_score`, `coverage_unsure_band`, rerank depth 75 vs 150, the support-check latency budget) is provisional until the gold set in section 10 exists. Plan the gold set early because acceptance for stages 4 and 5 depends on it.
6. Section 08.1 ends with the full DDL of the one target migration (0011). Apply migration 0010 live first; run the backfill and the readiness gate (`verify_knowledge_scope_backfill.py`) before trusting the new policy.
7. Never disable row security on Supabase and never run the 0009 downgrade there: both expose the tables through the public REST roles.
""")

for sec in soup.find_all("section"):
    sid = sec.get("id")
    num = sec.find(class_="sec-num").get_text(strip=True)
    title = sec.find("h2").get_text(strip=True)
    md.append(f"\n---\n\n## {num} · {title}\n")
    md.append(f"_Section id: `{sid}`_\n")
    lede = sec.find("p", class_="lede")
    if lede:
        md.append("**In plain words (the lede):** " + inline(lede).strip() + "\n")
    wrap = sec.find("div", class_="wrap")
    parts = []
    for c in wrap.children:
        if isinstance(c, Tag) and (
            c.get("class") and ("sec-head" in c["class"] or "lede" in c["class"])
        ):
            continue
        x = block(c)
        if x:
            parts.append(x)
    md.append("\n\n".join(parts))
    if by_sec.get(sid):
        md.append(f"\n#### Panels that belong to this section ({len(by_sec[sid])})\n")
        md.append(
            f"_Workflow label shown in the drawer: {WF.get(by_sec[sid][0].split('-')[0], '')}_\n"
        )
        for k in by_sec[sid]:
            md.append(panel_md(k, D[k]) + "\n")

md.append("\n---\n\n## Appendix · Index of every panel\n")
md.append("| Panel id | Section | Title | Status |\n|---|---|---|---|")
for k in order:
    p = D[k]
    sec = SEC.get(k.split("-")[0], "")
    md.append(
        f"| `{k}` | {sec} | {p.get('h', '').replace('|', '/')} | {ST.get(p.get('st'), p.get('st'))} |"
    )

text = "\n".join(md)
text = re.sub(r"\n{3,}", "\n\n", text)
open(OUT, "w", encoding="utf-8").write(text)
print(len(text), "chars", text.count("\n"), "lines", len(order), "panels")
