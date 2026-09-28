"""Read-only page dump: everything the sync-rules manual tests (MT-1..MT-7) need to observe.

This is the observation tool every manual case in ``docs/Final_docs/sync-rules/manual-tests.md``
reads from. It dumps a single Confluence page's state in the RAG DB and prints it — no writes, no
network. Run it before and after a Confluence action to see whether the vector store did what the
eight sync rules require (page purged, tags updated, a fresh version minted, chunks re-embedded).

For one ``page_id`` it prints:
  * whether the page has a ``page_source`` row, its ``page_status``, ``current_cf_version`` and
    ``active_doc_version_id`` (the "is this page live" summary — this *replaces* the retired
    ``scope_state`` the original plan asked for; ``scope_state`` no longer exists, D4/§7);
  * ``page_source.tags`` (the page-level scope tags);
  * active vs inactive chunk counts (parent/child split);
  * the distinct ``tags`` carried on the page's *active* chunks (what RLS actually filters on);
  * every ``document_version`` row for the page with its ``state`` and ``cf_version``;
  * with the optional ``marker`` argument, how many of the page's chunks (all, and the
    active-child subset) contain that word in ``display_content`` or ``retrieval_content`` — the
    MT-6 way to prove an edit's new text actually landed in the re-embedded chunks.

Runs as the DB owner via ``session_scope()`` (like every other operator script), so RLS does not
filter the read — you see inactive chunks and empty-tags chunks an ``rag_reader`` never would, which
is exactly what an observation tool wants.

Usage (from ``backend``, with a reachable DB — local pgvector or the target store):

    uv run python scripts/page_state.py 28934165
    uv run python scripts/page_state.py 28934165 widget      # count chunks containing "widget"

    # point at the local pgvector store instead of the root .env DATABASE_URL:
    DATABASE_URL=postgresql+psycopg://rag:rag@localhost:5434/omniboost_rag \
        uv run python scripts/page_state.py 28934165

Exit 0 if the page has a ``page_source`` row, 1 if it does not (nothing indexed for that id) — so a
"zero rows" purge result is a clean, scriptable signal.
"""

from __future__ import annotations

import argparse

from sqlalchemy import func, select

from schema.engine import session_scope
from schema.models import KIND_CHILD, KIND_PARENT, Chunk, DocumentVersion, PageSource


def _enum_value(value: object) -> str:
    """Render an Enum column as its ``.value`` (fall back to ``str`` for a plain value)."""
    return str(getattr(value, "value", value))


def _dump(page_id: int, marker: str | None) -> int:
    with session_scope() as session:
        ps = session.get(PageSource, page_id)
        if ps is None:
            print(f"page {page_id}: NO page_source row — nothing is indexed for this page.")
            return 1

        # --- page_source summary --------------------------------------------------------------
        print(f"page {page_id}")
        print(f"  page_status          : {_enum_value(ps.page_status)}")
        print(f"  current_cf_version   : {ps.current_cf_version}")
        print(f"  active_doc_version_id: {ps.active_doc_version_id}")
        print(f"  page_source.tags     : {sorted(ps.tags or [])}")

        # --- chunk counts (active/inactive, parent/child) -------------------------------------
        counts = session.execute(
            select(Chunk.is_active, Chunk.kind, func.count())
            .where(Chunk.page_id == page_id)
            .group_by(Chunk.is_active, Chunk.kind)
        ).all()
        totals = {
            (True, KIND_PARENT): 0,
            (True, KIND_CHILD): 0,
            (False, KIND_PARENT): 0,
            (False, KIND_CHILD): 0,
        }
        for is_active, kind, n in counts:
            totals[(bool(is_active), int(kind))] = n
        active = totals[(True, KIND_PARENT)] + totals[(True, KIND_CHILD)]
        inactive = totals[(False, KIND_PARENT)] + totals[(False, KIND_CHILD)]
        print(
            f"  chunks active        : {active} "
            f"(parent={totals[(True, KIND_PARENT)]}, child={totals[(True, KIND_CHILD)]})"
        )
        print(
            f"  chunks inactive      : {inactive} "
            f"(parent={totals[(False, KIND_PARENT)]}, child={totals[(False, KIND_CHILD)]})"
        )

        # --- distinct tags on active chunks (what RLS filters on) -----------------------------
        active_tag_rows = session.execute(
            select(Chunk.tags).where(Chunk.page_id == page_id, Chunk.is_active.is_(True))
        ).all()
        active_tags: set[str] = set()
        for (tags,) in active_tag_rows:
            active_tags.update(tags or [])
        print(f"  active chunk tags    : {sorted(active_tags)}")

        # --- every document_version row -------------------------------------------------------
        versions = session.execute(
            select(DocumentVersion.id, DocumentVersion.state, DocumentVersion.cf_version)
            .where(DocumentVersion.page_id == page_id)
            .order_by(DocumentVersion.id)
        ).all()
        print(f"  document_version rows: {len(versions)}")
        for vid, state, cf_version in versions:
            active_flag = " (active)" if vid == ps.active_doc_version_id else ""
            print(f"    - id={vid} state={_enum_value(state)} cf_version={cf_version}{active_flag}")

        # --- optional marker-word count -------------------------------------------------------
        if marker is not None:
            like = f"%{marker}%"
            content_match = Chunk.display_content.ilike(like) | Chunk.retrieval_content.ilike(like)
            total_hits = session.scalar(
                select(func.count())
                .select_from(Chunk)
                .where(Chunk.page_id == page_id, content_match)
            )
            active_child_hits = session.scalar(
                select(func.count())
                .select_from(Chunk)
                .where(
                    Chunk.page_id == page_id,
                    Chunk.is_active.is_(True),
                    Chunk.kind == KIND_CHILD,
                    content_match,
                )
            )
            print(
                f"  marker '{marker}'      : {total_hits} chunk(s) contain it "
                f"({active_child_hits} active child chunk(s))"
            )

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only dump of one Confluence page's state in the RAG DB (sync-rules tool)."
    )
    parser.add_argument("page_id", type=int, help="The Confluence page id to dump.")
    parser.add_argument(
        "marker",
        nargs="?",
        default=None,
        help="Optional word: count the page's chunks whose content contains it (MT-6 edit proof).",
    )
    args = parser.parse_args(argv)
    return _dump(args.page_id, args.marker)


if __name__ == "__main__":
    raise SystemExit(main())
