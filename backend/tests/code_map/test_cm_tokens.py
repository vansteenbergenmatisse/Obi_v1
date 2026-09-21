"""Regression tests for the design-panel `cm-tokens` (packages/design-tokens).

Protect-only, unit level, no network: reads the TypeScript token sources as
text and asserts the real values so `make test-unit` locks the panel's checks.
The repo root is located from this file's path so the test is CWD-independent.
"""

from __future__ import annotations

import re
from pathlib import Path

# backend/tests/code_map/test_cm_tokens.py -> parents[4] == repo root.
REPO_ROOT = Path(__file__).resolve().parents[3]
TOKENS_DIR = REPO_ROOT / "packages" / "design-tokens" / "src"
TOKENS_TS = TOKENS_DIR / "tokens.ts"
TAILWIND_TS = TOKENS_DIR / "tailwind-theme.ts"


def _luminance(hex_color: str) -> float:
    """Perceived luminance in [0, 1] from a #rrggbb string (Rec. 601 weights)."""
    value = hex_color.lstrip("#")
    r, g, b = (int(value[i : i + 2], 16) for i in (0, 2, 4))
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255.0


def _named_hex(source: str, key: str) -> str:
    """Return the #rrggbb value of a top-level `<key>: "#..."` entry."""
    match = re.search(rf'(?m)^\s*{re.escape(key)}:\s*"(#[0-9a-fA-F]{{6}})"', source)
    assert match is not None, f'no `{key}: "#..."` entry in tokens.ts'
    return match.group(1).lower()


def test_cm_tokens_holds_colors_type_and_tailwind_theme_mapping() -> None:
    """panel cm-tokens · substep p0-s0_5-reg-code-map
    Holds: the widget's colors, type, and the Tailwind theme mapping."""
    tokens_src = TOKENS_TS.read_text(encoding="utf-8")
    tailwind_src = TAILWIND_TS.read_text(encoding="utf-8")

    # Colors and type (fonts) are defined and aggregated in tokens.ts.
    assert "export const color = {" in tokens_src
    assert "export const font = {" in tokens_src
    assert re.search(r"export const tokens = \{[^}]*\bcolor\b", tokens_src)
    assert re.search(r"export const tokens = \{[^}]*\bfont\b", tokens_src)

    # The Tailwind theme mapping reads those tokens and exposes colors + fonts.
    assert 'from "./tokens"' in tailwind_src
    assert "export const tailwindTheme = {" in tailwind_src
    assert "colors: {" in tailwind_src
    assert "fontFamily: {" in tailwind_src
    # The mapping wires token values through (not literals): e.g. accent -> color.accent.
    assert "accent: color.accent" in tailwind_src
    assert "sans: font.sans" in tailwind_src


def test_cm_tokens_style_is_light_theme_indigo_accent_inter() -> None:
    """panel cm-tokens · substep p0-s0_5-reg-code-map
    Style: light theme, indigo accent, Inter."""
    tokens_src = TOKENS_TS.read_text(encoding="utf-8")

    # Indigo accent: the accent token is #635bff — a blue-dominant indigo/blurple.
    # ("indigo" is named in the tokens.ts header comment; the value below is the fact.)
    accent = _named_hex(tokens_src, "accent")
    assert accent == "#635bff"
    r, g, b = (int(accent[i : i + 2], 16) for i in (1, 3, 5))
    assert b > r and b > g, "accent must be blue-dominant (indigo), not warm"

    # Inter typography: the sans font stack names Inter.
    assert re.search(r"sans:\s*\"[^\"]*\bInter\b", tokens_src), "Inter missing from font.sans"

    # Light theme: the app background (surface) is near-white and text is dark,
    # i.e. dark text on a light ground. surface=#f6f8fa, text=#30313d.
    surface = _named_hex(tokens_src, "surface")
    text = _named_hex(tokens_src, "text")
    assert surface == "#f6f8fa"
    assert text == "#30313d"
    assert _luminance(surface) > 0.85, "surface should be a light background"
    assert _luminance(text) < 0.35, "text should be dark on the light ground"
    assert _luminance(surface) > _luminance(text)
