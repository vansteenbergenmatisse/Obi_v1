"""PLAN 10.7 exit-gate check: is the live corpus ready to flip
``enable_knowledge_scope_filtering`` on?

Read-only. Counts every ``is_active`` chunk whose tags overlap none of the recognized knowledge
scopes (loaded from ``config/knowledge_scopes.json`` — ``general``/``mews``/``opera-cloud``/
``toast``). Such a chunk would silently vanish from every scoped result once the flag is on
(ADR-0011 Decision 1), so this must report **ready** — zero untagged live chunks — before the flag
is set ``true`` in any environment with real content.

Exit status is the gate: ``0`` when ready, ``1`` when one or more live chunks still lack a
recognized scope label (with the offending ``page_id``s printed so an operator knows which
Confluence pages still need a label added).

Usage (from ``apps/automation``, with the DB reachable):

    uv run python scripts/verify_knowledge_scope_backfill.py
    uv run python scripts/verify_knowledge_scope_backfill.py --json

This never flips the flag itself — that is a deliberate, operator-owned ``.env`` change
(``enable_knowledge_scope_filtering=true``) made only after this check passes.
"""

from __future__ import annotations

import argparse
import json
import sys

from app.features.confluence_sync import verify_knowledge_scope_coverage
from app.platform.config.knowledge_scopes import load_recognized_knowledge_scopes
from app.platform.db.engine import session_scope


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    p.add_argument(
        "--json", action="store_true", help="emit the coverage result as a single JSON object"
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    recognized = load_recognized_knowledge_scopes()

    with session_scope() as session:
        cov = verify_knowledge_scope_coverage(session, recognized_scopes=recognized)

    if args.json:
        print(
            json.dumps(
                {
                    "ready": cov.is_ready,
                    "recognized_scopes": cov.recognized_scopes,
                    "total_active_chunks": cov.total_active_chunks,
                    "untagged_active_chunks": cov.untagged_active_chunks,
                    "untagged_page_ids": cov.untagged_page_ids,
                }
            )
        )
    else:
        print(f"recognized knowledge scopes: {', '.join(cov.recognized_scopes)}")
        print(f"active chunks: {cov.total_active_chunks}")
        print(f"untagged active chunks: {cov.untagged_active_chunks}")
        if cov.is_ready:
            print("READY — every live chunk carries a recognized knowledge-scope tag.")
            print("Safe to set enable_knowledge_scope_filtering=true.")
        else:
            print("NOT READY — add a recognized Confluence label to these page ids, then re-sync:")
            print(f"  {', '.join(str(pid) for pid in cov.untagged_page_ids)}")

    return 0 if cov.is_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
