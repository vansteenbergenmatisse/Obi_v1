#!/usr/bin/env python3
"""Enforce the feature / platform / shared import architecture.

Four rules that Ruff's isort cannot express (all checked with `ast.walk`, so
function-local and other nested imports are caught too):

  (a) Code OUTSIDE a feature may import a feature at its public root
      (`app.features.<f>`) but never deeper.
  (b) Code INSIDE feature <f> may deep-import its own feature, but may only
      reach OTHER features at their public root.
  (c) Code inside <f> must not import its own root `app.features.<f>`
      (the self-facade trap: re-importing a half-built package raises
      ImportError at init time).
  (d) `platform/**` and `shared/**` must not import features at all; `shared/**`
      must additionally not import `platform/**` (shared is the bottom layer).

Run from apps/automation:  uv run python tools/check_feature_boundaries.py
Exits 0 when clean, 1 with a report of violations otherwise.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

AUTOMATION_ROOT = Path(__file__).resolve().parent.parent  # apps/automation
EXCLUDED_DIRS = {".venv", "__pycache__", "alembic", "tools", ".git", "node_modules"}


def dotted_module(path: Path) -> str:
    """Dotted import path of a file relative to the automation root."""
    rel = path.relative_to(AUTOMATION_ROOT).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def importer_context(rel_parts: tuple[str, ...]) -> tuple[str, str | None]:
    """Classify where an importing file lives: (kind, feature_name)."""
    if rel_parts[:2] == ("app", "features") and len(rel_parts) > 2:
        return ("feature", rel_parts[2])
    if rel_parts[:2] == ("app", "platform"):
        return ("platform", None)
    if rel_parts[:2] == ("app", "shared"):
        return ("shared", None)
    return ("outside", None)


def feature_target(module: str) -> tuple[str, int] | None:
    """(feature_name, depth) for an `app.features.*` module; depth 0 == root."""
    parts = module.split(".")
    if len(parts) >= 3 and parts[0] == "app" and parts[1] == "features":
        return (parts[2], len(parts) - 3)
    return None


def resolve(module: str | None, level: int, importer: str, is_init: bool) -> str | None:
    """Resolve a (possibly relative) import target to an absolute dotted path."""
    if level == 0:
        return module
    pkg = importer.split(".") if is_init else importer.split(".")[:-1]
    base = pkg[: len(pkg) - (level - 1)]
    return ".".join(base + (module.split(".") if module else []))


def targets(node: ast.AST, importer: str, is_init: bool) -> list[str]:
    """Absolute dotted modules referenced by one import statement."""
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if isinstance(node, ast.ImportFrom):
        mod = resolve(node.module, node.level, importer, is_init)
        if mod is None:
            return []
        # `from app.features import <f>` is a root import of feature <f>.
        if mod == "app.features":
            return [f"app.features.{alias.name}" for alias in node.names]
        return [mod]
    return []


def check_file(path: Path) -> list[tuple[int, str, str]]:
    rel_parts = path.relative_to(AUTOMATION_ROOT).with_suffix("").parts
    kind, feat = importer_context(rel_parts)
    importer = dotted_module(path)
    is_init = path.name == "__init__.py"
    tree = ast.parse(path.read_text(), filename=str(path))
    violations: list[tuple[int, str, str]] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for mod in targets(node, importer, is_init):
            if not mod or not mod.startswith("app."):
                continue
            ft = feature_target(mod)

            if kind in ("platform", "shared"):
                if ft is not None:
                    violations.append((node.lineno, "d", f"{kind} imports feature `{mod}`"))
                elif kind == "shared" and mod.startswith("app.platform"):
                    violations.append((node.lineno, "d", f"shared imports platform `{mod}`"))
                continue

            if ft is None:
                continue
            tgt_feat, depth = ft

            root = f"app.features.{tgt_feat}"
            if kind == "feature":
                if tgt_feat == feat:
                    if depth == 0:
                        violations.append(
                            (node.lineno, "c", f"imports own root `{mod}` (self-facade trap)")
                        )
                elif depth > 0:
                    violations.append(
                        (node.lineno, "b", f"deep-imports another feature `{mod}` — use `{root}`")
                    )
            elif kind == "outside" and depth > 0:
                violations.append(
                    (node.lineno, "a", f"imports below a feature root `{mod}` — use `{root}`")
                )

    return violations


def main() -> int:
    failures: list[str] = []
    for path in sorted(AUTOMATION_ROOT.rglob("*.py")):
        if set(path.relative_to(AUTOMATION_ROOT).parts) & EXCLUDED_DIRS:
            continue
        # Only files that could import app.* matter; scan app/ plus test trees.
        rel = path.relative_to(AUTOMATION_ROOT)
        if rel.parts[0] not in ("app", "tests") and path.name != "conftest.py":
            continue
        for lineno, rule, msg in check_file(path):
            failures.append(f"{rel}:{lineno}: [rule {rule}] {msg}")

    if failures:
        print(f"Feature-boundary violations ({len(failures)}):\n")
        for line in failures:
            print(f"  {line}")
        print("\nSee tools/check_feature_boundaries.py for the four rules.")
        return 1
    print("Feature boundaries OK — no cross-feature deep imports.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
