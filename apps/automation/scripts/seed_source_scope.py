"""One-off CLI to add/update a Confluence sync root in ``source_scope`` (PLAN 3.5.6).

Ownership is deliberately one-off (no CRUD API yet, per the approved design spec): you run this
once per root you want tracked. A ``space`` root reproduces today's whole-space sync; a ``page``
root narrows reconciliation to that page + its live descendants. Idempotent — re-running with the
same ``--root-type``/``--root-id`` updates the existing row (tags, label, is_active) in place.

Usage (from ``apps/automation``):

    uv run python scripts/seed_source_scope.py --root-type space --root-id 100 --label "Engineering"
    uv run python scripts/seed_source_scope.py --root-type page --root-id 1002 --tags eng,runbook
    uv run python scripts/seed_source_scope.py --root-type page --root-id 1002 --deactivate

Once a root is deactivated (or deleted with ``--delete``), the next reconciliation sweep purges
every page that root covered and no other active root still covers.
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.platform.db.engine import session_scope
from app.platform.db.models import SourceScope

_ROOT_TYPES = ("space", "page")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--root-type", required=True, choices=_ROOT_TYPES)
    p.add_argument("--root-id", required=True, help="the space id or page id")
    p.add_argument("--source-type", default="confluence")
    p.add_argument("--tags", default="", help="comma-separated tags for bot scoping")
    p.add_argument("--label", default=None, help="human-readable name, informational only")
    p.add_argument(
        "--deactivate", action="store_true", help="soft-disable this root (is_active=false)"
    )
    p.add_argument(
        "--delete", action="store_true", help="remove the row entirely instead of upserting"
    )
    return p.parse_args(argv)


def seed(
    *,
    root_type: str,
    root_id: str,
    source_type: str = "confluence",
    tags: list[str] | None = None,
    label: str | None = None,
    is_active: bool = True,
) -> int:
    """Insert or update one source_scope row. Returns its id."""
    with session_scope() as session:
        stmt = (
            pg_insert(SourceScope)
            .values(
                root_type=root_type,
                root_id=root_id,
                source_type=source_type,
                tags=list(tags or []),
                label=label,
                is_active=is_active,
            )
            .on_conflict_do_update(
                index_elements=["root_type", "root_id"],
                set_={
                    "source_type": source_type,
                    "tags": list(tags or []),
                    "label": label,
                    "is_active": is_active,
                    "updated_at": func.now(),
                },
            )
            .returning(SourceScope.id)
        )
        return session.execute(stmt).scalar_one()


def deactivate(*, root_type: str, root_id: str) -> bool:
    with session_scope() as session:
        exists = session.execute(
            select(SourceScope.id).where(
                SourceScope.root_type == root_type, SourceScope.root_id == root_id
            )
        ).scalar_one_or_none()
        if exists is None:
            return False
        session.execute(
            update(SourceScope)
            .where(SourceScope.root_type == root_type, SourceScope.root_id == root_id)
            .values(is_active=False, updated_at=func.now())
        )
        return True


def remove(*, root_type: str, root_id: str) -> bool:
    with session_scope() as session:
        result = session.execute(
            delete(SourceScope).where(
                SourceScope.root_type == root_type, SourceScope.root_id == root_id
            )
        )
        return result.rowcount > 0


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    if args.delete:
        removed = remove(root_type=args.root_type, root_id=args.root_id)
        print(f"deleted={removed} root_type={args.root_type} root_id={args.root_id}")
        return 0
    if args.deactivate:
        found = deactivate(root_type=args.root_type, root_id=args.root_id)
        if not found:
            print(f"no existing row for root_type={args.root_type} root_id={args.root_id}")
            return 1
        print(f"deactivated root_type={args.root_type} root_id={args.root_id}")
        return 0

    tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    row_id = seed(
        root_type=args.root_type,
        root_id=args.root_id,
        source_type=args.source_type,
        tags=tags,
        label=args.label,
    )
    print(f"source_scope.id={row_id} root_type={args.root_type} root_id={args.root_id} tags={tags}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
