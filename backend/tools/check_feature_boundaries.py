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

Run from backend:  uv run python tools/check_feature_boundaries.py
Exits 0 when clean, 1 with a report of violations otherwise.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

AUTOMATION_ROOT = Path(__file__).resolve().parent.parent  # backend
EXCLUDED_DIRS = {".venv", "__pycache__", "alembic", "tools", ".git", "node_modules"}

# ---------------------------------------------------------------------------
# Phase-1 one-way rule (substep 1.1.2). The three top folders may only depend in
# one direction: frontend -> backend -> knowledge-base, never back. These rules
# operate at the REPO ROOT (frontend/, backend/, knowledge-base/ are siblings),
# in addition to the four intra-backend feature rules above.
REPO_ROOT = AUTOMATION_ROOT.parent
_FOLDER_SKIP = {".venv", "__pycache__", ".git", "node_modules", ".next"}

# Python folders -> the top-level import names they may NOT import.
# knowledge-base is the bottom layer (its own package is `schema`); backend never
# reaches up into the frontend.
PY_FOLDER_RULES: dict[str, frozenset[str]] = {
    "knowledge-base": frozenset({"app", "features", "platform", "shared"}),
    "backend": frozenset({"frontend"}),
}
_FRONTEND_EXTS = {".ts", ".tsx", ".js", ".jsx"}
# import/from/require/import() specifier; group(1) is the module path string.
_FE_IMPORT = re.compile(r"""(?:\bfrom|\bimport|\brequire\(|\bimport\()\s*['"]([^'"]+)['"]""")


def _py_top_level_imports(tree: ast.AST):
    """(lineno, top-level module name) for every ABSOLUTE import in a module."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # a relative import can't name-cross a top folder
                continue
            if node.module:
                yield node.lineno, node.module.split(".")[0]


def check_folder_boundaries() -> list[str]:
    """The three cross-folder direction rules (1.1.2). Returns formatted failures."""
    failures: list[str] = []
    # Python folders (knowledge-base, backend): forbidden absolute imports.
    for folder, forbidden in PY_FOLDER_RULES.items():
        root = REPO_ROOT / folder
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.py")):
            if set(path.relative_to(root).parts) & _FOLDER_SKIP:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except (SyntaxError, UnicodeDecodeError):
                continue
            for lineno, top in _py_top_level_imports(tree):
                if top in forbidden:
                    rel = path.relative_to(REPO_ROOT)
                    failures.append(
                        f"{rel}:{lineno}: [rule direction] {folder}/ imports `{top}` — "
                        "the arrow only points frontend -> backend -> knowledge-base"
                    )
    # Frontend: no import specifier may reach into backend/ or a .py file.
    fe_root = REPO_ROOT / "frontend"
    if fe_root.is_dir():
        for path in sorted(fe_root.rglob("*")):
            if path.suffix not in _FRONTEND_EXTS:
                continue
            if set(path.relative_to(fe_root).parts) & _FOLDER_SKIP:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for m in _FE_IMPORT.finditer(text):
                spec = m.group(1)
                segs = [s for s in spec.replace("\\", "/").split("/") if s not in ("", ".", "..")]
                if "backend" in segs or spec.endswith(".py"):
                    lineno = text.count("\n", 0, m.start()) + 1
                    rel = path.relative_to(REPO_ROOT)
                    failures.append(
                        f"{rel}:{lineno}: [rule direction] frontend/ imports `{spec}` — "
                        "the frontend never reaches into backend/ or a .py file"
                    )
    return failures


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

    # The three cross-folder direction rules (1.1.2), scanned at the repo root.
    failures.extend(check_folder_boundaries())

    if failures:
        print(f"Boundary violations ({len(failures)}):\n")
        for line in failures:
            print(f"  {line}")
        print("\nSee tools/check_feature_boundaries.py for the feature + direction rules.")
        return 1
    print("Boundaries OK — no cross-feature deep imports and no wrong-way folder imports.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
