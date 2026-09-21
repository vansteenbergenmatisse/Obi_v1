"""Live self-test: a real Confluence label change propagates into the RAG DB with no manual step
(PLAN 10.8).

10.1-10.7 build and unit-test the knowledge-scope mechanism; this proves it against the *real*
Confluence API and a *real* Postgres, the way the rest of the ledger insists ("verified live, not
just asserted"). It is a one-off verification tool, NOT part of pytest (it needs real network + real
credentials + it mutates live Confluence), same ownership pattern as ``seed_source_scope.py`` /
``run_reconciliation_once.py``.

What it does, against ONE page you name with ``--page-id`` (pick an already-synced page):

  1. Record the page's current labels + DB state (``page_source.tags`` / ``chunk.tags`` /
     ``labels_hash`` / ``active_doc_version_id`` / ``last_indexed_at``).
  2. ADD a recognized label (default ``obi-mews-test``) via the real Confluence REST label API, then
     drive a sync as a ``label_added`` webhook would (``sync_page`` job -> ``handle_sync_page``).
     Assert: ``tags`` now include the scope; ``labels_hash`` changed; the sync was ``metadata_only``
     with the SAME ``active_doc_version_id`` (the real "no re-embed" proof — a rebuild mints a new
     doc version, a label-only change does not).
  3. SWAP the label (default ``obi-mews-test`` -> ``obi-operacloud-test``). Assert the old scope is
     gone, the new one present, no stale double-tag.
  4. REMOVE the added label. Assert the added scope tag is gone (the page falls back to whatever it
     originally carried — e.g. ``obi-general-test`` — by design, ADR-0011 Decision 1).
  5. RESTORE the page's original label set exactly (a verification run must leave no residue in live
     Confluence). Runs in a ``finally`` so an early failure still cleans up.
  6. It also drives one real ``ingest_event(EventEnvelope("label_added", ...))`` and asserts the
     webhook-receipt entrypoint accepts it and enqueues a ``sync_page`` job — proving the receipt
     path itself, not only the downstream handler.

NOT covered here (blocked, see PLAN 10.8): the network delivery leg — Confluence Cloud POSTing to a
public ``POST /confluence/events``. The backend runs on localhost; that needs the operator's
deployed public URL. Until then updates ride the reconciliation sweep, and this script drives the
job in-process (the same ``sync_page`` job a delivered webhook enqueues).

NOTE on ``_apply_metadata_only``: it DOES bump ``last_indexed_at`` (it stamps ``now`` on every
metadata write). An earlier plan draft claimed ``last_indexed_at`` stays unchanged on a label-only
change — that is wrong against the code. The signal that a label change did NOT re-embed is the
unchanged ``active_doc_version_id`` (+ ``action == "metadata_only"``), which is what this asserts.

REFUSES the offline fixture gateway: a live check must hit real Confluence, not the fixture corpus.

Usage (from ``backend``, DB reachable + Confluence configured):

    uv run python scripts/verify_knowledge_scope_live.py --page-id 28934165
    uv run python scripts/verify_knowledge_scope_live.py --page-id 28934165 \
        --scope-a obi-mews-test --scope-b obi-operacloud-test

Exits 0 iff every assertion passed and the original labels were restored.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from dataclasses import dataclass

import httpx
from sqlalchemy import select

from app.features.confluence_sync import (
    EventEnvelope,
    drain,
    ingest_event,
    reap,
)
from app.platform.clients import HttpConfluenceClient
from app.platform.config import Settings, get_settings
from app.platform.jobs import enqueue_job
from schema.engine import session_scope
from schema.models import Chunk, PageSource

_OWNER = "verify-knowledge-scope-live"


# --------------------------------------------------------------------------- gateway / labels


def _require_live_gateway(settings: Settings) -> HttpConfluenceClient:
    """Build the live Confluence client, or refuse — never the offline fixture corpus."""
    if not (settings.confluence_base_url and settings.confluence_api_token):
        print(
            "REFUSING: Confluence is not configured (confluence_base_url / confluence_api_token "
            "missing). A live verification must not run against the offline fixture gateway.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return HttpConfluenceClient(settings)


def _label_client(settings: Settings) -> httpx.Client:
    """A small client for the v1 content-label write API (the read client is read-only).

    Same BasicAuth(email, token) as ``HttpConfluenceClient``; the label add/remove endpoints live
    on the v1 REST surface (``/rest/api/content/{id}/label``), not v2.
    """
    return httpx.Client(
        base_url=settings.confluence_base_url.rstrip("/"),
        auth=httpx.BasicAuth(settings.confluence_email, settings.confluence_api_token),
        timeout=settings.provider_timeout_seconds,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
    )


def _add_label(client: httpx.Client, page_id: int, name: str) -> None:
    resp = client.post(
        f"/rest/api/content/{page_id}/label", json=[{"prefix": "global", "name": name}]
    )
    resp.raise_for_status()


def _remove_label(client: httpx.Client, page_id: int, name: str) -> None:
    resp = client.delete(f"/rest/api/content/{page_id}/label", params={"name": name})
    # 204 = removed; 404 = it wasn't there (already the desired end-state) — both fine.
    if resp.status_code not in (204, 404):
        resp.raise_for_status()


# --------------------------------------------------------------------------- DB state snapshot


@dataclass(frozen=True)
class PageState:
    exists: bool
    tags: tuple[str, ...]
    labels_hash: str
    active_doc_version_id: int | None
    last_indexed_at: str
    active_chunk_tags: tuple[str, ...]
    active_chunk_ids: tuple[int, ...]


def _read_state(page_id: int) -> PageState:
    with session_scope() as session:
        ps = session.get(PageSource, page_id)
        if ps is None:
            return PageState(False, (), "", None, "", (), ())
        chunk_rows = session.execute(
            select(Chunk.id, Chunk.tags)
            .where(Chunk.page_id == page_id, Chunk.is_active.is_(True))
            .order_by(Chunk.id)
        ).all()
        chunk_tags: set[str] = set()
        chunk_ids: list[int] = []
        for cid, tags in chunk_rows:
            chunk_ids.append(cid)
            chunk_tags.update(tags or [])
        return PageState(
            exists=True,
            tags=tuple(sorted(ps.tags or [])),
            labels_hash=(ps.labels_hash or b"").hex(),
            active_doc_version_id=ps.active_doc_version_id,
            last_indexed_at=str(ps.last_indexed_at),
            active_chunk_tags=tuple(sorted(chunk_tags)),
            active_chunk_ids=tuple(chunk_ids),
        )


# --------------------------------------------------------------------------- sync drivers


def _drive_sync(gateway: HttpConfluenceClient, settings: Settings, page_id: int, note: str) -> str:
    """Enqueue + drain the ``sync_page`` job a label webhook enqueues; return the page's action.

    Uses a unique idempotency key per call (a webhook edit doesn't bump ``cf_version``, so reusing
    the auto key would collide via ON CONFLICT DO NOTHING). This exercises the real
    ``handle_sync_page`` re-fetch/classify/re-stamp path — the thing being verified.
    """
    key = f"verify-live:{page_id}:{note}:{uuid.uuid4()}"
    with session_scope() as session:
        enqueue_job(
            session,
            job_type="sync_page",
            idempotency_key=key,
            payload={"event_type": note},
            page_id=page_id,
        )
    reap()
    results = drain(gateway, settings, owner=_OWNER, max_jobs=50)
    for r in results:
        if r.status == "succeeded" and getattr(r.outcome, "page_id", None) == page_id:
            return str(getattr(r.outcome, "action", "unknown"))
        if r.status != "succeeded":
            print(f"  ! job {r.job_id} ({r.job_type}) failed: {r.error}", file=sys.stderr)
    return "no-op"


def _prove_receipt_entrypoint(
    gateway: HttpConfluenceClient, settings: Settings, page_id: int
) -> bool:
    """Drive one real ``ingest_event(label_added)`` and confirm it accepts + enqueues a job."""
    version = None
    meta = gateway.get_page_meta(page_id)
    if meta is not None:
        version = meta.version_number
    with session_scope() as session:
        result = ingest_event(
            session,
            EventEnvelope(
                event_type="label_added",
                page_id=page_id,
                cf_version=version,
                delivery_id=f"verify-live-{uuid.uuid4()}",
            ),
            settings,
        )
    ok = bool(result.accepted and not result.ignored and result.job_id is not None)
    reap()
    drain(gateway, settings, owner=_OWNER, max_jobs=50)  # clear the job it enqueued
    return ok


# --------------------------------------------------------------------------- checks


class Checks:
    def __init__(self) -> None:
        self.failures: list[str] = []

    def ok(self, condition: bool, label: str) -> None:
        mark = "PASS" if condition else "FAIL"
        print(f"  [{mark}] {label}")
        if not condition:
            self.failures.append(label)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Live knowledge-scope label->RAG-DB propagation self-test."
    )
    parser.add_argument(
        "--page-id", type=int, required=True, help="An already-synced Confluence page id."
    )
    parser.add_argument(
        "--scope-a",
        default="obi-mews-test",
        help="First recognized scope to add (default: obi-mews-test).",
    )
    parser.add_argument(
        "--scope-b",
        default="obi-operacloud-test",
        help="Scope to swap to (default: obi-operacloud-test).",
    )
    args = parser.parse_args(argv)
    page_id: int = args.page_id
    scope_a: str = args.scope_a
    scope_b: str = args.scope_b

    settings = get_settings()
    gateway = _require_live_gateway(settings)
    checks = Checks()

    original_labels = list(gateway.get_labels(page_id))
    baseline = _read_state(page_id)
    if not baseline.exists:
        print(
            f"REFUSING: page {page_id} is not in the index (no page_source row). Pick an "
            "already-synced page.",
            file=sys.stderr,
        )
        return 2
    print(f"page {page_id}: original labels={original_labels} tags={list(baseline.tags)}")

    label_client = _label_client(settings)
    try:
        # 0. Receipt entrypoint.
        print("\n[0] webhook-receipt entrypoint (ingest_event)")
        checks.ok(
            _prove_receipt_entrypoint(gateway, settings, page_id),
            "ingest_event(label_added) accepted and enqueued a sync_page job",
        )

        # 2. ADD scope_a.
        print(f"\n[2] add label '{scope_a}'")
        _add_label(label_client, page_id, scope_a)
        checks.ok(
            scope_a in gateway.get_labels(page_id), f"Confluence now reports label '{scope_a}'"
        )
        action = _drive_sync(gateway, settings, page_id, "label_added")
        after_add = _read_state(page_id)
        checks.ok(scope_a in after_add.tags, f"page_source.tags include '{scope_a}'")
        checks.ok(scope_a in after_add.active_chunk_tags, f"active chunk.tags include '{scope_a}'")
        checks.ok(after_add.labels_hash != baseline.labels_hash, "labels_hash changed")
        checks.ok(action == "metadata_only", f"sync action is metadata_only (was '{action}')")
        checks.ok(
            after_add.active_doc_version_id == baseline.active_doc_version_id,
            "active_doc_version_id unchanged (no re-embed)",
        )
        checks.ok(
            after_add.active_chunk_ids == baseline.active_chunk_ids,
            "active chunk ids unchanged (rows re-stamped, not rebuilt)",
        )

        # 3. SWAP scope_a -> scope_b.
        print(f"\n[3] swap label '{scope_a}' -> '{scope_b}'")
        _remove_label(label_client, page_id, scope_a)
        _add_label(label_client, page_id, scope_b)
        _drive_sync(gateway, settings, page_id, "label_swapped")
        after_swap = _read_state(page_id)
        checks.ok(scope_b in after_swap.tags, f"page_source.tags include '{scope_b}'")
        checks.ok(
            scope_a not in after_swap.tags,
            f"page_source.tags no longer include '{scope_a}' (no stale double-tag)",
        )
        checks.ok(scope_b in after_swap.active_chunk_tags, f"active chunk.tags include '{scope_b}'")
        checks.ok(
            scope_a not in after_swap.active_chunk_tags,
            f"active chunk.tags no longer include '{scope_a}'",
        )

        # 4. REMOVE scope_b.
        print(f"\n[4] remove label '{scope_b}'")
        _remove_label(label_client, page_id, scope_b)
        _drive_sync(gateway, settings, page_id, "label_deleted")
        after_remove = _read_state(page_id)
        checks.ok(
            scope_b not in after_remove.tags, f"page_source.tags no longer include '{scope_b}'"
        )
        checks.ok(
            scope_b not in after_remove.active_chunk_tags,
            f"active chunk.tags no longer include '{scope_b}'",
        )

    finally:
        # 5. RESTORE original labels exactly — remove anything we may have added, re-add originals.
        print("\n[5] restore original labels")
        try:
            current = set(gateway.get_labels(page_id))
            for extra in current - set(original_labels):
                _remove_label(label_client, page_id, extra)
            for missing in set(original_labels) - set(gateway.get_labels(page_id)):
                _add_label(label_client, page_id, missing)
            restored = sorted(gateway.get_labels(page_id))
            checks.ok(
                restored == sorted(original_labels), f"labels restored to {sorted(original_labels)}"
            )
            # Re-stamp the DB back to the original tag set so no residue is left in Postgres either.
            _drive_sync(gateway, settings, page_id, "restore")
        except Exception as exc:  # noqa: BLE001 — best-effort cleanup, report and continue
            print(f"  ! restore step raised: {exc}", file=sys.stderr)
            checks.failures.append("restore original labels")
        finally:
            label_client.close()
            gateway.close()

    print()
    if checks.failures:
        print(f"FAILED — {len(checks.failures)} check(s) failed:", file=sys.stderr)
        for f in checks.failures:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print("OK — every check passed and original labels were restored.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
