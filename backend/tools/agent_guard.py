#!/usr/bin/env python3
"""PreToolUse guard for the Obi subagents. Standard library only.

Usage (from a hook):  python3 backend/tools/agent_guard.py <profile>
Profiles: auditor | tester | implementer | none

Reads the hook payload from stdin (JSON with tool_name and tool_input).
Exit 0 allows the call. Exit 2 blocks it and the message on stderr is shown to the agent.

auditor:      Bash only for the panel reader, git log and git blame, and a few read-only
              shell commands. Write only under docs/Final_docs/. No Edit.
tester:       Bash only for make, uv run pytest/ruff/pyright, pnpm, docker compose,
              git status/diff/log and the panel reader. No Write, no Edit.
implementer:  Bash unrestricted. Write and Edit only while .obi/active-substep exists
              (written by /obi-change step 1, removed in step 7).
none:         Passthrough. Allows everything. This is the safe default for the
              settings.json fallback so a normal main session (no .obi/agent-profile)
              is never gated. Enforcement there kicks in only once the orchestrator
              writes .obi/agent-profile before spawning an agent.

Set OBI_GUARD_DEBUG=1 to print the payload keys to stderr (does not block).
"""

import json
import os
import re
import sys

READ_ONLY_SHELL = [
    r"^(ls|wc|head|tail|cat|rg|grep|find|tree|cd|pwd|echo)\b",
]

PROFILES = {
    "auditor": {
        "bash": READ_ONLY_SHELL
        + [
            r"^(uv run )?python3? (backend/)?tools/panel\.py\b",
            r"^uv run pytest\b",
            r"^git (log|blame|show)\b",
        ],
        "write": [r"^docs/Final_docs/"],
        "edit": [],
    },
    "tester": {
        "bash": READ_ONLY_SHELL
        + [
            r"^make\b",
            r"^(cd backend && )?uv run (pytest|ruff|pyright)\b",
            r"^(uv run )?python3? (backend/)?tools/panel\.py\b",
            r"^pnpm\b",
            r"^docker compose\b",
            r"^git (status|diff|log)\b",
        ],
        "write": [],
        "edit": [],
    },
    "implementer": {
        "bash": None,
        "write": None,
        "edit": None,
        "gate": ".obi/active-substep",
    },
    "none": {
        "bash": None,
        "write": None,
        "edit": None,
    },
}

EDIT_TOOLS = {"Edit", "MultiEdit", "NotebookEdit"}
WRITE_TOOLS = {"Write"}


def block(msg):
    sys.stderr.write("obi guard: " + msg + "\n")
    sys.exit(2)


def allowed(patterns, value):
    return patterns is None or any(re.search(p, value) for p in patterns)


def project_rel(file_path):
    """Path of file_path relative to the project root, cwd-independent.

    Hooks run with the agent's own working directory, which is not always the
    repo root. Anchor the write/edit allow-list to CLAUDE_PROJECT_DIR (set by
    the harness for every hook) so the check gives the same answer no matter
    where the agent's shell sits. Falls back to cwd when the var is absent
    (e.g. the unit tests, which invoke the guard from the repo).
    """
    root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    fp = file_path or ""
    if not os.path.isabs(fp):
        fp = os.path.join(root, fp)
    return os.path.relpath(os.path.abspath(fp), os.path.abspath(root))


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in PROFILES:
        block("usage: agent_guard.py <auditor|tester|implementer|none>")
    profile = PROFILES[sys.argv[1]]
    try:
        payload = json.load(sys.stdin)
    except Exception:
        block("could not read the hook payload")
    if os.environ.get("OBI_GUARD_DEBUG"):
        sys.stderr.write(f"obi guard payload keys: {sorted(payload.keys())}\n")
    tool = payload.get("tool_name", "")
    inp = payload.get("tool_input", {}) or {}

    gate = profile.get("gate")
    if gate and tool in EDIT_TOOLS | WRITE_TOOLS and not os.path.exists(gate):
        block(f"no active substep. Run /obi-change <substep id> first; it creates {gate}.")

    if tool == "Bash":
        cmd = (inp.get("command") or "").strip()
        # split chained commands and check every part
        parts = re.split(r"\s*(?:&&|\|\||;|\|)\s*", cmd)
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if profile["bash"] is not None and (">" in part or re.search(r"\btee\b", part)):
                block(f"{sys.argv[1]} may not redirect output: {part}")
            if not allowed(profile["bash"], part):
                block(f"{sys.argv[1]} may not run: {part}")
        sys.exit(0)

    if tool in WRITE_TOOLS:
        path = project_rel(inp.get("file_path"))
        if not allowed(profile["write"], path):
            block(f"{sys.argv[1]} may not write {path}")
        sys.exit(0)

    if tool in EDIT_TOOLS:
        path = project_rel(inp.get("file_path"))
        if not allowed(profile["edit"], path):
            block(f"{sys.argv[1]} may not edit {path}")
        sys.exit(0)

    sys.exit(0)


if __name__ == "__main__":
    main()
