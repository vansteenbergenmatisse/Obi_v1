#!/usr/bin/env python3
"""Read and update one design panel from the Obi design page.

The design page (`docs/.../obi-rag-system-flow*.html`) embeds every panel as a
single JSON object in `<script type="application/json" id="nodedata">`. That
file is well over a hundred thousand tokens; agents must never open it whole.
This tool prints one panel (a few hundred tokens), lists or greps panel ids,
and rewrites one panel in place — leaving every byte outside the JSON block
untouched.

Usage:
    python tools/panel.py r5-coverage                       # print one panel as markdown
    python tools/panel.py --list                            # id | title | status, one per line
    python tools/panel.py --grep scope_state                # ids whose text mentions the word
    python tools/panel.py r5-coverage --status built --today "One sentence."

Run from apps/automation (same as tools/check_feature_boundaries.py). The design
file is found relative to the repository root, so the working directory does not
matter. Pass --file to point at a specific HTML file.

Panel fields: n=kind, h=title, st=status, simple=plain words, today=today line,
f=settings rows, files=code locations, s=steps, c=code, t=tests, note=note.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

STATUS_WORDS = ("built", "change", "build", "unverified", "discuss")

# The one JSON block the design page hangs everything off of.
NODEDATA_RE = re.compile(r'(<script type="application/json" id="nodedata">)(.*?)(</script>)', re.S)


def repo_root() -> Path:
    """apps/automation/tools/panel.py -> repository root."""
    return Path(__file__).resolve().parents[3]


def find_design_file(root: Path) -> Path:
    """Locate the design flow HTML that carries the nodedata block.

    Prefers the canonical `docs/Final_docs/obi-rag-system-flow.html`; falls
    back to any `*rag-system-flow*.html` under `docs/`.
    """
    canonical = root / "docs" / "Final_docs" / "obi-rag-system-flow.html"
    if canonical.is_file():
        return canonical
    matches = sorted(root.glob("docs/**/*rag-system-flow*.html"))
    for path in matches:
        if 'id="nodedata"' in path.read_text(encoding="utf-8"):
            return path
    raise SystemExit('panel.py: no design flow HTML with an id="nodedata" block found under docs/')


def read_panels(path: Path) -> tuple[str, re.Match[str], dict[str, dict]]:
    """Return (full html, the nodedata match, the parsed panel dict)."""
    html = path.read_text(encoding="utf-8")
    match = NODEDATA_RE.search(html)
    if match is None:
        raise SystemExit(f'panel.py: no id="nodedata" block in {path}')
    return html, match, json.loads(match.group(2))


def write_panels(path: Path, html: str, match: re.Match[str], panels: dict[str, dict]) -> None:
    """Rewrite only the JSON block; every byte outside it stays identical.

    `indent=0, ensure_ascii=False` reproduces the design page's own formatting,
    so an edit of two fields shows up as a two-field diff and nothing else.
    """
    new_json = json.dumps(panels, ensure_ascii=False, indent=0)
    new_html = html[: match.start(2)] + new_json + html[match.end(2) :]
    path.write_text(new_html, encoding="utf-8")


def _cell(value: str) -> str:
    """Make a string safe for one Markdown table cell."""
    return value.replace("|", r"\|").replace("\n", " ").strip()


def render(pid: str, panel: dict) -> str:
    """Render one panel as compact Markdown (a few hundred tokens)."""
    out: list[str] = [f"# {panel.get('h', pid)}"]

    meta: list[str] = []
    if panel.get("st"):
        meta.append(f"**status:** {panel['st']}")
    if panel.get("n"):
        meta.append(f"**kind:** {panel['n']}")
    meta.append(f"`{pid}`")
    out.append("  ·  ".join(meta))

    if panel.get("simple"):
        out += ["", str(panel["simple"])]
    if panel.get("today"):
        out += ["", f"**Today:** {panel['today']}"]

    if panel.get("f"):
        out += ["", "## Settings", "| field | value |", "|---|---|"]
        for row in panel["f"]:
            if isinstance(row, list):
                label = str(row[0]) if row else ""
                value = " ".join(str(x) for x in row[1:])
            else:
                label, value = str(row), ""
            out.append(f"| {_cell(label)} | {_cell(value)} |")

    if panel.get("files"):
        out += ["", "## Code locations"]
        for row in panel["files"]:
            if isinstance(row, list):
                loc = str(row[0]) if row else ""
                sym = " ".join(str(x) for x in row[1:])
                out.append(f"- `{loc}`" + (f" — {sym}" if sym else ""))
            else:
                out.append(f"- {row}")

    if panel.get("s"):
        out += ["", "## Steps"]
        out += [f"{i}. {step}" for i, step in enumerate(panel["s"], 1)]

    if panel.get("c"):
        out += ["", "## Code", "```", str(panel["c"]), "```"]

    if panel.get("t"):
        out += ["", "## Tests"]
        out += [f"- {item}" for item in panel["t"]]

    if panel.get("note"):
        out += ["", "## Note", str(panel["note"])]

    return "\n".join(out)


def _panel_text(panel: dict) -> str:
    """Flatten every string in a panel into one blob for --grep."""
    parts: list[str] = []

    def walk(value: object) -> None:
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, dict):
            for item in value.values():
                walk(item)
        else:
            parts.append(str(value))

    walk(panel)
    return " ".join(parts)


def cmd_list(panels: dict[str, dict]) -> int:
    for pid, panel in panels.items():
        print(f"{pid} | {panel.get('h', '')} | {panel.get('st', '')}")
    return 0


def cmd_grep(panels: dict[str, dict], word: str) -> int:
    needle = word.lower()
    for pid, panel in panels.items():
        if needle in f"{pid} {_panel_text(panel)}".lower():
            print(pid)
    return 0


def cmd_print(panels: dict[str, dict], pid: str) -> int:
    if pid not in panels:
        raise SystemExit(f"panel.py: no panel with id {pid!r}")
    print(render(pid, panels[pid]))
    return 0


def cmd_update(
    path: Path,
    html: str,
    match: re.Match[str],
    panels: dict[str, dict],
    pid: str,
    status: str | None,
    today: str | None,
) -> int:
    if pid not in panels:
        raise SystemExit(f"panel.py: no panel with id {pid!r}")
    panel = panels[pid]
    changes: list[tuple[str, object, object]] = []
    if status is not None:
        changes.append(("st", panel.get("st"), status))
        panel["st"] = status
    if today is not None:
        changes.append(("today", panel.get("today"), today))
        panel["today"] = today
    write_panels(path, html, match, panels)
    for field, old, new in changes:
        print(f"{pid}.{field}: {old!r} -> {new!r}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="panel.py",
        description="Read or update one design panel from the Obi design page.",
    )
    parser.add_argument("pid", nargs="?", help="panel id, e.g. r5-coverage")
    parser.add_argument("--file", help="path to the design HTML (default: auto-discover)")
    parser.add_argument("--list", action="store_true", help="id | title | status per panel")
    parser.add_argument("--grep", metavar="WORD", help="print ids whose text mentions WORD")
    parser.add_argument("--status", choices=STATUS_WORDS, help="set the panel status word")
    parser.add_argument("--today", metavar="TEXT", help="set the panel today line")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    root = repo_root()
    path = Path(args.file) if args.file else find_design_file(root)
    html, match, panels = read_panels(path)

    if args.list:
        return cmd_list(panels)
    if args.grep is not None:
        return cmd_grep(panels, args.grep)
    if args.pid is None:
        parser.error("give a panel id, --list, or --grep")
    if args.status is None and args.today is None:
        return cmd_print(panels, args.pid)
    return cmd_update(path, html, match, panels, args.pid, args.status, args.today)


if __name__ == "__main__":
    sys.exit(main())
