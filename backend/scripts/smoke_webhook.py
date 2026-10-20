"""Live smoke test: prove the webhook -> ingestion path lands chunks in the DB.

This is the go-live canary for the deployed backend. It does NOT touch Confluence and it writes
nothing — it is the *polling + assertion* half of the smoke test. The operator supplies the event
(the half a script cannot fake convincingly):

    1. In Confluence, add a recognized routing label (e.g. ``toast-general``, ADR-routing-labels-sole-content-axis) to a known
       published page (or edit its body).
       Confluence delivers a webhook to the deployed ``POST /confluence/events``; the endpoint
       enqueues a job; the in-process worker drains it and (re)ingests the page.
    2. Run this script pointed at the SAME database the deployed backend writes to. It polls the
       page's state via the owner session (like ``page_state.py``) until active chunks appear, then
       prints how long it took and exits 0. If nothing lands inside ``--timeout`` it exits non-zero.

Because it reads as the DB owner via ``session_scope()``, RLS does not filter the read — it sees the
same rows the ingestion worker just wrote.

Usage (from ``backend``, DATABASE_URL pointed at the store the deployed backend writes to):

    DATABASE_URL=postgresql+psycopg://...supabase... \
        uv run python scripts/smoke_webhook.py 28934165

    # require a specific routing label and a marker word from an edit (MT-6 style edit proof):
    uv run python scripts/smoke_webhook.py 28934165 \
        --require-tag toast-general --marker "camcorder" --timeout 180

Exit codes: 0 = active chunks (and any required tag/marker) observed within the window; 2 = timed
out with no active chunks; 3 = active chunks present but a required tag/marker never appeared.
"""

from __future__ import annotations

import argparse
import time

from sqlalchemy import func, select

from schema.engine import session_scope
from schema.models import KIND_CHILD, Chunk, PageSource


def _snapshot(page_id: int, marker: str | None) -> tuple[int, set[str], int]:
    """Return (active_chunk_count, active_chunk_tags, active_child_marker_hits) for one page.

    Uses the owner session so inactive/edge rows are visible — same access pattern as page_state.py.
    """
    with session_scope() as session:
        ps = session.get(PageSource, page_id)
        if ps is None:
            return (0, set(), 0)

        active_count = session.scalar(
            select(func.count())
            .select_from(Chunk)
            .where(Chunk.page_id == page_id, Chunk.is_active.is_(True))
        )

        tag_rows = session.execute(
            select(Chunk.tags).where(Chunk.page_id == page_id, Chunk.is_active.is_(True))
        ).all()
        tags: set[str] = set()
        for (chunk_tags,) in tag_rows:
            tags.update(chunk_tags or [])

        marker_hits = 0
        if marker is not None:
            like = f"%{marker}%"
            content_match = Chunk.display_content.ilike(like) | Chunk.retrieval_content.ilike(like)
            marker_hits = session.scalar(
                select(func.count())
                .select_from(Chunk)
                .where(
                    Chunk.page_id == page_id,
                    Chunk.is_active.is_(True),
                    Chunk.kind == KIND_CHILD,
                    content_match,
                )
            )

        return (int(active_count or 0), tags, int(marker_hits or 0))


def _poll(
    page_id: int,
    *,
    timeout: float,
    interval: float,
    require_tag: str | None,
    marker: str | None,
) -> int:
    start = time.monotonic()
    deadline = start + timeout
    saw_active = False

    while True:
        active_count, tags, marker_hits = _snapshot(page_id, marker)
        elapsed = time.monotonic() - start

        if active_count > 0:
            saw_active = True
            tag_ok = require_tag is None or require_tag in tags
            marker_ok = marker is None or marker_hits > 0
            if tag_ok and marker_ok:
                detail = ""
                if require_tag:
                    detail += f", tag '{require_tag}' present"
                if marker:
                    detail += f", marker '{marker}' in {marker_hits} active child chunk(s)"
                print(
                    f"PASS: page {page_id} has {active_count} active chunk(s) "
                    f"after {elapsed:.1f}s{detail}"
                )
                return 0

        if time.monotonic() >= deadline:
            if not saw_active:
                print(
                    f"FAIL: page {page_id} still has 0 active chunks after {elapsed:.1f}s "
                    f"(timeout {timeout:.0f}s). Webhook/worker did not ingest the page."
                )
                return 2
            missing = []
            if require_tag is not None and require_tag not in tags:
                missing.append(f"tag '{require_tag}' (saw {sorted(tags)})")
            if marker is not None and marker_hits == 0:
                missing.append(f"marker '{marker}'")
            print(
                f"FAIL: page {page_id} has active chunks but never showed {', '.join(missing)} "
                f"within {timeout:.0f}s."
            )
            return 3

        remaining = deadline - time.monotonic()
        print(f"  ...{elapsed:.1f}s: {active_count} active chunk(s); retrying in {interval:.0f}s")
        time.sleep(min(interval, max(remaining, 0.0)))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Poll the RAG DB until a Confluence page's chunks land (webhook smoke test)."
    )
    parser.add_argument("page_id", type=int, help="The Confluence page id to watch.")
    parser.add_argument(
        "--timeout", type=float, default=120.0, help="Seconds to wait for chunks (default 120)."
    )
    parser.add_argument(
        "--interval", type=float, default=3.0, help="Seconds between polls (default 3)."
    )
    parser.add_argument(
        "--require-tag",
        default=None,
        help="Optional routing label that must appear on the active chunks (e.g. toast-general).",
    )
    parser.add_argument(
        "--marker",
        default=None,
        help="Optional word that must appear in an active child chunk (proves an edit landed).",
    )
    args = parser.parse_args(argv)
    return _poll(
        args.page_id,
        timeout=args.timeout,
        interval=args.interval,
        require_tag=args.require_tag,
        marker=args.marker,
    )


if __name__ == "__main__":
    raise SystemExit(main())
