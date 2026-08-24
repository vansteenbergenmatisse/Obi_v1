"""One-off CLI: run a single COMPLETE reconciliation sweep + drain the resulting jobs (PLAN 10.7).

This is the operator step that re-stamps ``chunk.tags`` after Confluence labels change but the page
body does not — e.g. after adding a recognized knowledge-scope label (``general``/``mews``/
``opera-cloud``/``toast``) to already-indexed pages. A *complete* sweep enqueues a ``sync_page`` job
for every live page; each job's ``handle_sync_page`` re-reads the page's fresh labels, resolves them
to knowledge-scope tags (PLAN 10.2), unions them with the page's ``source_scope`` tags, and writes
the result to ``chunk.tags`` via the **metadata-only path — no re-embedding** (a label change bumps
``labels_hash`` but not the page body, so ``classify`` never routes it to a rebuild).

It is the manual equivalent of the scheduled ``scheduled_complete_reconcile`` + ``worker_tick`` the
in-process worker runs — used here as a deliberate, one-shot backfill instead of waiting for the
next scheduled complete sweep. Idempotent and safe to re-run: every handler is version-guarded, and
a page already carrying the right tags re-stamps to the identical value.

REFUSES to run against the offline fixture gateway: a real backfill must hit the live Confluence
instance, never the deterministic fixture corpus. If Confluence is not configured this exits
non-zero without touching the queue.

Usage (from ``apps/automation``, with the DB reachable and Confluence configured):

    uv run python scripts/run_reconciliation_once.py

After it reports success, run ``scripts/verify_knowledge_scope_backfill.py`` to confirm the corpus
is READY before flipping ``enable_knowledge_scope_filtering=true``. This script never flips it.
"""

from __future__ import annotations

import sys
from collections import Counter

from app.features.confluence_sync import KIND_COMPLETE, drain, reap, run_reconciliation
from app.platform.clients import HttpConfluenceClient
from app.platform.config import Settings, get_settings
from app.platform.db.engine import session_scope

_OWNER = "one-off-backfill"


def _require_live_gateway(settings: Settings) -> HttpConfluenceClient:
    """Build the live Confluence client, or refuse — never fall back to the fixture corpus."""
    if not (settings.confluence_base_url and settings.confluence_api_token):
        print(
            "REFUSING: Confluence is not configured (confluence_base_url / confluence_api_token "
            "missing). A live backfill must not run against the offline fixture gateway.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return HttpConfluenceClient(settings)


def main() -> int:
    settings = get_settings()
    gateway = _require_live_gateway(settings)

    with session_scope() as session:
        run = run_reconciliation(session, gateway=gateway, settings=settings, kind=KIND_COMPLETE)
        pages_scanned = run.pages_scanned
        jobs_enqueued = run.jobs_enqueued
        orphans_deleted = run.orphans_deleted
        errors = run.errors

    print(
        f"complete sweep: pages_scanned={pages_scanned} jobs_enqueued={jobs_enqueued} "
        f"orphans_deleted={orphans_deleted} errors={errors}"
    )

    reap()
    results = drain(gateway, settings, owner=_OWNER, max_jobs=500)

    actions: Counter[str] = Counter()
    failures: list[str] = []
    for r in results:
        if r.status == "succeeded":
            action = getattr(r.outcome, "action", "unknown")
            actions[action] += 1
        else:
            failures.append(f"job {r.job_id} ({r.job_type}): {r.error}")

    print(
        f"drained {len(results)} job(s): "
        + ", ".join(f"{k}={v}" for k, v in sorted(actions.items()))
    )
    if failures:
        print("FAILURES:", file=sys.stderr)
        for f in failures:
            print(f"  {f}", file=sys.stderr)

    ok = not failures and errors == 0
    print("done — now run scripts/verify_knowledge_scope_backfill.py to confirm READY.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
