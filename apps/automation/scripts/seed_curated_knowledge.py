"""One-off CLI to add/update/deactivate a `curated_knowledge_entry` row (PLAN 10.6, ADR-0011).

Ownership is deliberately one-off (no CRUD API yet), mirroring `seed_source_scope.py`'s ownership
decision. Unlike `source_scope`, `curated_knowledge_entry` has no DB-level unique constraint to
upsert against (`title` is free text, not a natural key, per the 0007 migration) — "upsert by
title" here means: look up an *active* row with that exact title and update it in place; if none
exists, insert a new one. Deactivation always targets `--id`, not `--title`, since a title is not a
stable identifier once more than one entry could plausibly share wording.

Usage (from `apps/automation`):

    uv run python scripts/seed_curated_knowledge.py --title "Password reset" --body "..." \
        --tags mews
    uv run python scripts/seed_curated_knowledge.py --title "Password reset" --body "updated text"
    uv run python scripts/seed_curated_knowledge.py --id 3 --deactivate

Empty (or omitted) `--tags` means the entry applies to every knowledge scope, matching the table's
own "empty tags = always included" semantics (PLAN 10.3).
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import func, select, update

from app.platform.db.engine import session_scope
from app.platform.db.models import CuratedKnowledgeEntry


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    p.add_argument("--id", type=int, default=None, help="target an existing row by id (deactivate)")
    p.add_argument(
        "--title",
        default=None,
        help="upsert target — update the active row with this exact title, or insert a new one",
    )
    p.add_argument(
        "--body", default=None, help="entry body text (required when upserting by title)"
    )
    p.add_argument(
        "--tags", default="", help="comma-separated knowledge-scope tags; empty = every scope"
    )
    p.add_argument(
        "--deactivate",
        action="store_true",
        help="soft-disable the row named by --id (is_active=false)",
    )
    return p.parse_args(argv)


def seed(*, title: str, body: str, tags: list[str] | None = None) -> int:
    """Update the active row with this exact title in place, or insert a new one. Returns its id."""
    with session_scope() as session:
        existing_id = session.execute(
            select(CuratedKnowledgeEntry.id).where(
                CuratedKnowledgeEntry.title == title, CuratedKnowledgeEntry.is_active.is_(True)
            )
        ).scalar_one_or_none()
        if existing_id is not None:
            session.execute(
                update(CuratedKnowledgeEntry)
                .where(CuratedKnowledgeEntry.id == existing_id)
                .values(body=body, tags=list(tags or []), updated_at=func.now())
            )
            return existing_id
        row = CuratedKnowledgeEntry(title=title, body=body, tags=list(tags or []))
        session.add(row)
        session.flush()
        return row.id


def deactivate(*, entry_id: int) -> bool:
    with session_scope() as session:
        exists = session.execute(
            select(CuratedKnowledgeEntry.id).where(CuratedKnowledgeEntry.id == entry_id)
        ).scalar_one_or_none()
        if exists is None:
            return False
        session.execute(
            update(CuratedKnowledgeEntry)
            .where(CuratedKnowledgeEntry.id == entry_id)
            .values(is_active=False, updated_at=func.now())
        )
        return True


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])

    if args.deactivate:
        if args.id is None:
            print("--deactivate requires --id (a title is not a stable identifier)")
            return 1
        found = deactivate(entry_id=args.id)
        if not found:
            print(f"no existing row for id={args.id}")
            return 1
        print(f"deactivated id={args.id}")
        return 0

    if not args.title or not args.body:
        print("--title and --body are required to add/update a curated entry")
        return 1
    tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    row_id = seed(title=args.title, body=args.body, tags=tags)
    print(f"curated_knowledge_entry.id={row_id} title={args.title!r} tags={tags}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
