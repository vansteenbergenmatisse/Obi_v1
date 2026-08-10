"""Rotate `CHAT_API_KEY` without an outage (PLAN 5).

`CHAT_API_KEY` is a shared secret between `apps/web`'s server-side proxy and this API
(`app/features/rag_agent/server/router.py:_verify_api_key`). A naive single-key swap causes a
hard outage the instant the two `.env` files briefly disagree — this script implements the
documented overlap-window mechanism instead (`docs/runbooks/chat-api-key-rotation.md`):

1. `--apply` moves the *current* key into `CHAT_API_KEY_PREVIOUS` (still accepted) and writes a
   fresh 64-char hex key as `CHAT_API_KEY`, in both the root `.env` (this API) and
   `apps/web/.env.local` (the proxy) — the proxy only ever sends one key, so it jumps straight to
   the new value; only this API needs to accept both during the overlap.
2. Restart both processes so the new env takes effect.
3. After the overlap window closes (recommended: days, not minutes — see the runbook for why a
   short-lived, never-browser-exposed, server-to-server secret doesn't need weekly rotation),
   run `--finish` to blank `CHAT_API_KEY_PREVIOUS`, closing the window.

Without `--apply`/`--finish` this only prints what it would do — safe to run to preview.

Usage (from `apps/automation`):

    uv run python scripts/rotate_chat_api_key.py --apply
    uv run python scripts/rotate_chat_api_key.py --finish
"""

from __future__ import annotations

import argparse
import re
import secrets
import sys
from pathlib import Path

_ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"
_WEB_ENV = Path(__file__).resolve().parents[2] / "apps" / "web" / ".env.local"


def _new_key() -> str:
    return secrets.token_hex(32)


def _read_var(path: Path, name: str) -> str:
    if not path.exists():
        return ""
    pattern = re.compile(rf"^{re.escape(name)}=(.*)$", re.MULTILINE)
    match = pattern.search(path.read_text())
    return match.group(1).strip() if match else ""


def _set_var(path: Path, name: str, value: str) -> None:
    """Sets `name=value` in `path`, appending the line if the var isn't present yet."""
    text = path.read_text() if path.exists() else ""
    pattern = re.compile(rf"^{re.escape(name)}=.*$", re.MULTILINE)
    line = f"{name}={value}"
    if pattern.search(text):
        text = pattern.sub(line, text, count=1)
    else:
        if text and not text.endswith("\n"):
            text += "\n"
        text += line + "\n"
    path.write_text(text)


def apply_rotation() -> str:
    """Rotates in the new key, preserving the current one as CHAT_API_KEY_PREVIOUS. Returns the
    new key (for the operator's own record — never logged by the running app)."""
    current = _read_var(_ROOT_ENV, "CHAT_API_KEY")
    new_key = _new_key()
    _set_var(_ROOT_ENV, "CHAT_API_KEY_PREVIOUS", current)
    _set_var(_ROOT_ENV, "CHAT_API_KEY", new_key)
    _set_var(_WEB_ENV, "CHAT_API_KEY", new_key)
    return new_key


def finish_rotation() -> None:
    """Closes the overlap window: the old key stops being accepted."""
    _set_var(_ROOT_ENV, "CHAT_API_KEY_PREVIOUS", "")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--apply", action="store_true", help="rotate in a new key, keep the old one accepted"
    )
    group.add_argument("--finish", action="store_true", help="stop accepting the previous key")
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    if args.apply:
        new_key = apply_rotation()
        print(f"CHAT_API_KEY rotated in {_ROOT_ENV} and {_WEB_ENV}.")
        print(f"New key: {new_key}")
        print(
            "The previous key is still accepted (CHAT_API_KEY_PREVIOUS). Restart both "
            "apps/automation and apps/web, confirm the chat UI still works, then run "
            "--finish once every caller has picked up the new key."
        )
        return 0

    finish_rotation()
    print(f"CHAT_API_KEY_PREVIOUS cleared in {_ROOT_ENV}. Rotation complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
