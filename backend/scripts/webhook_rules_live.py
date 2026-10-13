"""Live WEBHOOK-PATH runner for the eight sync rules — the "does it really work" button.

Permanent home of the 2026-09-30 session runner (ledger: "Step 3 · Confluence webhook go-live").
Where ``verify_sync_rules.py`` enqueues + drains jobs **in-process** (bypassing delivery), this
script drives ONLY real Confluence REST mutations and then **waits**: every change must travel the
full production path — Confluence → Forge app → ``POST /confluence/events`` on the deployed backend
→ event_ledger row → job → worker → vector store — before a check can pass. The script itself never
enqueues a job and never writes to the RAG database; it reads state (like ``page_state.py``) and
polls until the deployed worker has done the work.

    ┌───────────────────────────────────────────────────────────────────────────────────────────┐
    │  STAGING ONLY.  This mutates live Confluence: labels, a body edit, and a trash/restore on  │
    │  the page you name. NEVER point it at a production content page — use the owner's          │
    │  dedicated test page. You must pass --yes to proceed.                                      │
    └───────────────────────────────────────────────────────────────────────────────────────────┘

Preconditions (the script checks what it can and refuses otherwise):
  * ``DATABASE_URL`` points at the SAME database the deployed backend writes to.
  * Confluence is configured (``CONFLUENCE_BASE_URL`` / ``_EMAIL`` / ``_API_TOKEN``) — the offline
    fixture gateway is refused outright.
  * The deployed backend is up with ``ENABLE_BACKGROUND_JOBS=true`` and the Forge app installed
    (this script cannot verify Railway directly; a leg timing out is the failure signal).
  * ``--page-id`` is already indexed and carries exactly the ``--scope-a`` label.

The legs, in the 2026-09-30 order (each asserts DB **outcomes**, never code paths, and reports the
new ``origin=0`` event_ledger rows as proof the webhook — not this process — delivered the change):

  rule 2 — remove the last recognized label  → the page purges to zero rows.
  rule 5 — re-add the first recognized label → full rebuild (fresh doc version, chunks embedded).
  rule 4 — add a second recognized label     → tags union, SAME doc version + chunk ids.
  rule 3 — remove one of the two             → survivor stays, SAME doc version + chunk ids.
  rule 6 — edit the body (marker appended)   → new doc version, chunk-id set fully replaced,
            marker present in the re-embedded child chunks.           [--skip-edit to skip]
  rule 7 — add ``classified``                → purge despite the recognized label; removing it
            re-indexes with a FRESH doc version.
  rule 1 — trash the page, then restore it   → purge, then full rebuild.  [--skip-trash to skip]
  rule 8 — the witness page (``--other-page-id``) is byte-fingerprinted (page_source +
            document_version + chunk rows, embeddings included) before and after the whole run and
            must be identical.

Cleanup runs in a ``finally`` and leaves no residue: the original label set AND the original body
are restored (each restore travels the webhook path too, and the script waits for the final
re-index). Output is pasteable into the PR per the CLAUDE.md live-level rule.

Usage (from ``backend``; typically ~20 s per leg, minutes if Forge delivery is slow):

    uv run python scripts/webhook_rules_live.py --page-id 1670873122 --other-page-id 1670971395 \
        --scope-a toast-general --scope-b mews-general --yes

``--scope-a`` / ``--scope-b`` are recognized ROUTING labels (ADR-0021 Path B — the knowledge-scope
``-test`` axis is retired; membership = published + >=1 recognized routing label).

Exits 0 iff every check that ran passed and the original labels + body were restored.
"""

from __future__ import annotations

import argparse
import sys
import time
import uuid
from dataclasses import dataclass

import httpx
from sqlalchemy import func, select, text

from app.platform.clients import HttpConfluenceClient
from app.platform.config import Settings, get_settings
from schema.engine import session_scope
from schema.models import KIND_CHILD, Chunk, DocumentVersion, EventLedger, PageSource

_CLASSIFIED_LABEL = "classified"
_DEFAULT_LEG_TIMEOUT = 420.0  # observed live: ~20 s per leg post-fix, up to ~5.7 min before it
_POLL_INTERVAL = 5.0


# --------------------------------------------------------------------------- refusals


def _require_live_confluence(settings: Settings) -> HttpConfluenceClient:
    """Build the live Confluence client, or refuse — never the offline fixture corpus."""
    if not (settings.confluence_base_url and settings.confluence_api_token):
        print(
            "REFUSING: Confluence is not configured (confluence_base_url / confluence_api_token "
            "missing). The webhook-path verification must not run against the offline fixture "
            "gateway.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return HttpConfluenceClient(settings)


# --------------------------------------------------------------------------- Confluence v1 writes


def _rest_client(settings: Settings) -> httpx.Client:
    """v1 REST write client (labels, content PUT/DELETE) — the read gateway is read-only.

    Same BasicAuth(email, token) as ``HttpConfluenceClient``; a longer timeout than the provider
    default because content PUTs are slower than reads.
    """
    return httpx.Client(
        base_url=settings.confluence_base_url.rstrip("/"),
        auth=httpx.BasicAuth(settings.confluence_email, settings.confluence_api_token),
        timeout=max(settings.provider_timeout_seconds, 30.0),
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


def _get_content(client: httpx.Client, page_id: int, *, status: str | None = None) -> dict:
    params: dict[str, str] = {"expand": "body.storage,version"}
    if status is not None:
        params["status"] = status
    resp = client.get(f"/rest/api/content/{page_id}", params=params)
    resp.raise_for_status()
    return resp.json()


def _put_body(client: httpx.Client, page_id: int, *, title: str, html: str, version: int) -> None:
    resp = client.put(
        f"/rest/api/content/{page_id}",
        json={
            "id": str(page_id),
            "type": "page",
            "title": title,
            "version": {"number": version},
            "body": {"storage": {"value": html, "representation": "storage"}},
        },
    )
    resp.raise_for_status()


def _trash_page(client: httpx.Client, page_id: int) -> None:
    resp = client.delete(f"/rest/api/content/{page_id}")  # a current page deletes to the trash
    resp.raise_for_status()


def _restore_page(client: httpx.Client, page_id: int) -> None:
    """Restore a trashed page: v1 PUT status trashed → current (the 2026-09-30 proven shape).

    The v1 content GET returns neither ``title`` nor ``version`` for trashed content (observed
    live 2026-10-05 — it crashed the first run's restore leg), so both come from the v2 pages
    API, which does return them for a trashed page.
    """
    meta_resp = client.get(f"/api/v2/pages/{page_id}", params={"status": "trashed"})
    meta_resp.raise_for_status()
    meta = meta_resp.json()
    resp = client.put(
        f"/rest/api/content/{page_id}",
        params={"status": "trashed"},
        json={
            "id": str(page_id),
            "type": "page",
            "status": "current",
            "title": meta["title"],
            "version": {"number": int(meta["version"]["number"]) + 1},
        },
    )
    resp.raise_for_status()


def _page_is_trashed(client: httpx.Client, page_id: int) -> bool:
    resp = client.get(f"/rest/api/content/{page_id}", params={"status": "trashed"})
    return resp.status_code == 200 and resp.json().get("status") == "trashed"


# --------------------------------------------------------------------------- DB observation


@dataclass(frozen=True)
class PageState:
    exists: bool
    tags: tuple[str, ...]
    active_doc_version_id: int | None
    active_chunk_tags: tuple[str, ...]
    active_chunk_ids: tuple[int, ...]
    total_rows: int  # page_source(0/1) + document_version + chunk rows — 0 means fully purged


def _read_state(page_id: int) -> PageState:
    with session_scope() as session:
        ps = session.get(PageSource, page_id)
        chunk_rows = session.execute(
            select(Chunk.id, Chunk.tags, Chunk.is_active).where(Chunk.page_id == page_id)
        ).all()
        n_version_rows = len(
            session.execute(
                select(DocumentVersion.id).where(DocumentVersion.page_id == page_id)
            ).all()
        )

        active_ids: list[int] = []
        active_tags: set[str] = set()
        for cid, tags, is_active in chunk_rows:
            if is_active:
                active_ids.append(cid)
                active_tags.update(tags or [])

        if ps is None:
            return PageState(
                False, (), None, (), tuple(sorted(active_ids)), len(chunk_rows) + n_version_rows
            )
        return PageState(
            exists=True,
            tags=tuple(sorted(ps.tags or [])),
            active_doc_version_id=ps.active_doc_version_id,
            active_chunk_tags=tuple(sorted(active_tags)),
            active_chunk_ids=tuple(sorted(active_ids)),
            total_rows=1 + n_version_rows + len(chunk_rows),
        )


def _marker_hits(page_id: int, marker: str) -> int:
    with session_scope() as session:
        like = f"%{marker}%"
        return int(
            session.scalar(
                select(func.count())
                .select_from(Chunk)
                .where(
                    Chunk.page_id == page_id,
                    Chunk.is_active.is_(True),
                    Chunk.kind == KIND_CHILD,
                    Chunk.display_content.ilike(like) | Chunk.retrieval_content.ilike(like),
                )
            )
            or 0
        )


def _fingerprint(page_id: int) -> str:
    """One md5 over the page's page_source + document_version + chunk rows (embeddings included).

    The rule-8 witness: identical before/after the run ⇔ no row of the other page was touched.
    Row-text aggregates (``t::text``) so every column participates without naming them.
    """
    parts: list[str] = []
    with session_scope() as session:
        for table in ("page_source", "document_version", "chunk"):
            digest = session.scalar(
                text(
                    f"SELECT md5(coalesce(string_agg(t::text, '|' ORDER BY t::text), ''))"  # noqa: S608 — table name from a fixed tuple
                    f" FROM {table} t WHERE page_id = :pid"
                ),
                {"pid": page_id},
            )
            parts.append(str(digest))
    return "|".join(parts)


def _max_event_id() -> int:
    with session_scope() as session:
        return int(session.scalar(select(func.max(EventLedger.id))) or 0)


def _webhook_events_since(page_id: int, after_id: int) -> list[tuple[int, str]]:
    """New ``origin=0`` (webhook) ledger rows for the page — the delivery evidence per leg."""
    with session_scope() as session:
        rows = session.execute(
            select(EventLedger.id, EventLedger.event_type)
            .where(
                EventLedger.page_id == page_id,
                EventLedger.id > after_id,
                EventLedger.origin == 0,
            )
            .order_by(EventLedger.id)
        ).all()
    return [(int(i), str(e)) for i, e in rows]


# --------------------------------------------------------------------------- checks harness


class Checks:
    def __init__(self) -> None:
        self.failures: list[str] = []

    def ok(self, condition: bool, label: str) -> None:
        mark = "PASS" if condition else "FAIL"
        print(f"  [{mark}] {label}")
        if not condition:
            self.failures.append(label)


def _wait_for(
    page_id: int, predicate, label: str, *, timeout: float, interval: float = _POLL_INTERVAL
) -> tuple[PageState, bool]:
    """Poll the DB until ``predicate(state)`` holds or ``timeout`` elapses (webhook latency)."""
    start = time.monotonic()
    deadline = start + timeout
    while True:
        state = _read_state(page_id)
        if predicate(state):
            print(f"  ... {label} after {time.monotonic() - start:.1f}s")
            return state, True
        if time.monotonic() >= deadline:
            print(f"  ... TIMEOUT ({timeout:.0f}s) waiting for: {label}")
            return state, False
        time.sleep(min(interval, max(deadline - time.monotonic(), 0.0)))


def _report_delivery(checks: Checks, page_id: int, before_event_id: int, leg: str) -> None:
    events = _webhook_events_since(page_id, before_event_id)
    listing = ", ".join(f"#{i} {e}" for i, e in events) or "none"
    checks.ok(len(events) > 0, f"{leg}: webhook delivered (new origin=0 ledger rows: {listing})")


# --------------------------------------------------------------------------- legs


def _leg_rule_2_remove_last(rest, checks, page_id, scope_a, timeout):
    print(f"\n[rule 2] remove the last recognized label '{scope_a}' → purge (webhook path)")
    ev0 = _max_event_id()
    _remove_label(rest, page_id, scope_a)
    st, ok = _wait_for(page_id, lambda s: s.total_rows == 0, "purged to zero rows", timeout=timeout)
    checks.ok(ok and st.total_rows == 0, f"zero rows for the page (total_rows={st.total_rows})")
    _report_delivery(checks, page_id, ev0, "rule 2")
    return st


def _leg_rule_5_first_tag(rest, checks, page_id, scope_a, timeout):
    print(f"\n[rule 5] re-add the first recognized label '{scope_a}' → full build (webhook path)")
    ev0 = _max_event_id()
    _add_label(rest, page_id, scope_a)
    st, ok = _wait_for(
        page_id,
        lambda s: s.exists and len(s.active_chunk_ids) > 0,
        "page re-indexed with active chunks",
        timeout=timeout,
    )
    checks.ok(ok and st.exists, "page_source row present again")
    checks.ok(len(st.active_chunk_ids) > 0, f"active chunks embedded ({len(st.active_chunk_ids)})")
    checks.ok(scope_a in st.active_chunk_tags, f"active chunk.tags include '{scope_a}'")
    _report_delivery(checks, page_id, ev0, "rule 5")
    return st


def _leg_rule_4_add_second(rest, checks, page_id, scope_a, scope_b, before, timeout):
    print(f"\n[rule 4] add second recognized label '{scope_b}' → union, no re-embed (webhook path)")
    ev0 = _max_event_id()
    _add_label(rest, page_id, scope_b)
    st, ok = _wait_for(
        page_id,
        lambda s: scope_b in s.tags,
        f"page_source.tags include '{scope_b}'",
        timeout=timeout,
    )
    checks.ok(
        ok and scope_a in st.tags and scope_b in st.tags, f"tags share both: {sorted(st.tags)}"
    )
    checks.ok(scope_b in st.active_chunk_tags, f"active chunk.tags include '{scope_b}'")
    checks.ok(
        st.active_doc_version_id == before.active_doc_version_id,
        "SAME active_doc_version_id (metadata-only, no re-embed)",
    )
    checks.ok(
        st.active_chunk_ids == before.active_chunk_ids,
        "SAME active chunk-id set (no re-embed)",
    )
    _report_delivery(checks, page_id, ev0, "rule 4")
    return st


def _leg_rule_3_remove_one(rest, checks, page_id, scope_a, scope_b, before, timeout):
    print(f"\n[rule 3] remove one of two ('{scope_b}') → '{scope_a}' stays, no re-embed")
    ev0 = _max_event_id()
    _remove_label(rest, page_id, scope_b)
    st, ok = _wait_for(
        page_id,
        lambda s: s.exists and scope_b not in s.tags,
        f"'{scope_b}' gone from page_source.tags",
        timeout=timeout,
    )
    checks.ok(ok and scope_a in st.tags and scope_b not in st.tags, f"tags now {sorted(st.tags)}")
    checks.ok(st.exists, "page still indexed (a recognized tag remains)")
    checks.ok(
        st.active_doc_version_id == before.active_doc_version_id,
        "SAME active_doc_version_id (metadata-only, no re-embed)",
    )
    checks.ok(st.active_chunk_ids == before.active_chunk_ids, "SAME active chunk-id set")
    _report_delivery(checks, page_id, ev0, "rule 3")
    return st


def _leg_rule_6_body_edit(rest, checks, page_id, marker, before, timeout):
    print(f"\n[rule 6] edit the body (append marker '{marker}') → full rebuild, no vector reuse")
    doc = _get_content(rest, page_id)
    original_html = str(doc["body"]["storage"]["value"])
    ev0 = _max_event_id()
    _put_body(
        rest,
        page_id,
        title=str(doc["title"]),
        html=original_html + f"<p>{marker}</p>",
        version=int(doc["version"]["number"]) + 1,
    )
    st, ok = _wait_for(
        page_id,
        lambda s: s.exists and s.active_doc_version_id != before.active_doc_version_id,
        "a fresh document_version is active",
        timeout=timeout,
    )
    checks.ok(ok, "body edit minted a new document_version (rebuild)")
    checks.ok(
        set(st.active_chunk_ids).isdisjoint(before.active_chunk_ids),
        "active chunk-id set fully replaced (no vector reuse)",
    )
    hits = _marker_hits(page_id, marker)
    checks.ok(hits > 0, f"marker '{marker}' present in {hits} re-embedded active child chunk(s)")
    _report_delivery(checks, page_id, ev0, "rule 6")
    return st, original_html


def _leg_rule_7_classified(rest, checks, page_id, scope_a, before, timeout):
    print(f"\n[rule 7] add '{_CLASSIFIED_LABEL}' → purge despite '{scope_a}'; remove → re-index")
    ev0 = _max_event_id()
    _add_label(rest, page_id, _CLASSIFIED_LABEL)
    st, ok = _wait_for(page_id, lambda s: s.total_rows == 0, "purged to zero rows", timeout=timeout)
    checks.ok(ok and st.total_rows == 0, f"classified purge (total_rows={st.total_rows})")
    _report_delivery(checks, page_id, ev0, "rule 7 (add)")

    ev1 = _max_event_id()
    _remove_label(rest, page_id, _CLASSIFIED_LABEL)
    st2, ok2 = _wait_for(
        page_id,
        lambda s: s.exists and len(s.active_chunk_ids) > 0,
        "page re-indexed after declassify",
        timeout=timeout,
    )
    checks.ok(ok2 and st2.exists, "re-indexed once classified is removed (recognized tag remains)")
    checks.ok(
        st2.active_doc_version_id != before.active_doc_version_id,
        "a FRESH document_version was minted (full rebuild, not resurrection)",
    )
    _report_delivery(checks, page_id, ev1, "rule 7 (remove)")
    return st2


def _leg_rule_1_trash_restore(rest, checks, page_id, before, timeout):
    print("\n[rule 1] trash the page → purge; restore it → full rebuild (webhook path)")
    ev0 = _max_event_id()
    _trash_page(rest, page_id)
    st, ok = _wait_for(page_id, lambda s: s.total_rows == 0, "purged to zero rows", timeout=timeout)
    checks.ok(ok and st.total_rows == 0, f"trashed page purged (total_rows={st.total_rows})")
    _report_delivery(checks, page_id, ev0, "rule 1 (trash)")

    ev1 = _max_event_id()
    _restore_page(rest, page_id)
    st2, ok2 = _wait_for(
        page_id,
        lambda s: s.exists and len(s.active_chunk_ids) > 0,
        "restored page re-indexed",
        timeout=timeout,
    )
    checks.ok(ok2 and st2.exists, "restored page re-indexed (page_source row present)")
    checks.ok(len(st2.active_chunk_ids) > 0, "restored page has active chunks (full rebuild)")
    checks.ok(
        st2.active_doc_version_id != before.active_doc_version_id,
        "a fresh document_version was minted on restore",
    )
    _report_delivery(checks, page_id, ev1, "rule 1 (restore)")
    return st2


# --------------------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Webhook-path live runner for the eight sync rules (no in-process jobs)."
    )
    parser.add_argument(
        "--page-id", type=int, required=True, help="An already-synced staging test page."
    )
    parser.add_argument(
        "--other-page-id",
        type=int,
        default=None,
        help="Witness page for rule 8 — byte-fingerprinted before/after, must be identical.",
    )
    parser.add_argument(
        "--scope-a", default="mews-general", help="The page's recognized routing label (ADR-0021)."
    )
    parser.add_argument(
        "--scope-b", default="toast-general", help="Second recognized routing label (ADR-0021)."
    )
    parser.add_argument(
        "--marker",
        default=None,
        help="Word appended in the rule-6 body edit (default: a unique webhookmarker-<hex>).",
    )
    parser.add_argument(
        "--leg-timeout",
        type=float,
        default=_DEFAULT_LEG_TIMEOUT,
        help="Seconds to wait per leg for the webhook→worker round trip "
        f"(default {_DEFAULT_LEG_TIMEOUT:.0f}).",
    )
    parser.add_argument("--skip-edit", action="store_true", help="Skip the rule-6 body-edit leg.")
    parser.add_argument(
        "--skip-trash", action="store_true", help="Skip the rule-1 trash/restore leg."
    )
    parser.add_argument("--yes", action="store_true", help="Confirm this mutates live Confluence.")
    args = parser.parse_args(argv)

    if not args.yes:
        print(
            "REFUSING: this mutates live Confluence (labels, a body edit, a trash/restore). "
            "Re-run with --yes once you have confirmed --page-id is a STAGING/test page (never a "
            "production content page).",
            file=sys.stderr,
        )
        return 2

    page_id: int = args.page_id
    scope_a: str = args.scope_a
    scope_b: str = args.scope_b
    timeout: float = args.leg_timeout
    marker: str = args.marker or f"webhookmarker{uuid.uuid4().hex[:10]}"

    settings = get_settings()
    gateway = _require_live_confluence(settings)
    checks = Checks()

    original_labels = list(gateway.get_labels(page_id))
    baseline = _read_state(page_id)
    if not baseline.exists:
        print(
            f"REFUSING: page {page_id} is not in the index (no page_source row). Pick an "
            "already-synced page carrying one recognized scope label.",
            file=sys.stderr,
        )
        gateway.close()
        return 2
    if scope_a not in original_labels:
        print(
            f"REFUSING: page {page_id} must start carrying '{scope_a}' (its recognized scope). "
            f"Current labels: {original_labels}.",
            file=sys.stderr,
        )
        gateway.close()
        return 2

    witness_before = _fingerprint(args.other_page_id) if args.other_page_id else None
    print(f"page {page_id}: original labels={original_labels} tags={list(baseline.tags)}")
    if args.other_page_id:
        print(f"witness {args.other_page_id}: fingerprint {witness_before}")
    print(f"leg timeout {timeout:.0f}s — every leg rides the real webhook; nothing enqueued here")

    rest = _rest_client(settings)
    original_html: str | None = None
    try:
        _leg_rule_2_remove_last(rest, checks, page_id, scope_a, timeout)
        st = _leg_rule_5_first_tag(rest, checks, page_id, scope_a, timeout)
        st = _leg_rule_4_add_second(rest, checks, page_id, scope_a, scope_b, st, timeout)
        st = _leg_rule_3_remove_one(rest, checks, page_id, scope_a, scope_b, st, timeout)
        if args.skip_edit:
            print("\n[rule 6] skipped (--skip-edit)")
        else:
            st, original_html = _leg_rule_6_body_edit(rest, checks, page_id, marker, st, timeout)
        st = _leg_rule_7_classified(rest, checks, page_id, scope_a, st, timeout)
        if args.skip_trash:
            print("\n[rule 1] skipped (--skip-trash)")
        else:
            st = _leg_rule_1_trash_restore(rest, checks, page_id, st, timeout)
    finally:
        # Leave no residue: page out of the trash, original body back, original labels back —
        # each restore travels the webhook path too, so wait for the final re-index.
        print("\n[cleanup] restore page status, body and labels (no residue)")
        try:
            if _page_is_trashed(rest, page_id):
                _restore_page(rest, page_id)
                _wait_for(
                    page_id, lambda s: s.exists, "page re-indexed after restore", timeout=timeout
                )
            if original_html is not None:
                doc = _get_content(rest, page_id)
                if str(doc["body"]["storage"]["value"]) != original_html:
                    before_restore = _read_state(page_id)
                    _put_body(
                        rest,
                        page_id,
                        title=str(doc["title"]),
                        html=original_html,
                        version=int(doc["version"]["number"]) + 1,
                    )
                    _wait_for(
                        page_id,
                        lambda s: s.active_doc_version_id != before_restore.active_doc_version_id,
                        "body restored and re-indexed",
                        timeout=timeout,
                    )
                    checks.ok(
                        _marker_hits(page_id, marker) == 0,
                        "marker gone from active chunks (body restored)",
                    )
            current = set(gateway.get_labels(page_id))
            for extra in current - set(original_labels):
                _remove_label(rest, page_id, extra)
            for missing in set(original_labels) - set(gateway.get_labels(page_id)):
                _add_label(rest, page_id, missing)
            restored = sorted(gateway.get_labels(page_id))
            checks.ok(
                restored == sorted(original_labels),
                f"labels restored to {sorted(original_labels)}",
            )
            _wait_for(
                page_id,
                lambda s: s.exists and set(s.tags) == set(baseline.tags),
                "page re-indexed with its original tags",
                timeout=timeout,
            )
        except Exception as exc:  # noqa: BLE001 — best-effort cleanup, report and continue
            print(f"  ! cleanup raised: {exc}", file=sys.stderr)
            checks.failures.append("cleanup: restore status/body/labels")
        finally:
            rest.close()
            gateway.close()

    # Rule 8: the witness page never moved, down to the embedding bytes.
    if witness_before is not None:
        print(f"\n[rule 8] witness page {args.other_page_id} untouched throughout")
        witness_after = _fingerprint(args.other_page_id)
        checks.ok(
            witness_after == witness_before,
            "witness fingerprint (page_source + document_version + chunk rows) identical",
        )

    print()
    if checks.failures:
        print(f"FAILED — {len(checks.failures)} check(s) failed:", file=sys.stderr)
        for f in checks.failures:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print(
        "OK — every sync rule that ran was proven through the LIVE webhook path and the page was "
        "left exactly as found."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
