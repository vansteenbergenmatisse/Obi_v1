"""Live staging runner for the eight sync rules (MT-1..MT-7).

Proves, against a **real Confluence + a real Postgres**, that a Confluence change makes the vector
store do what the eight sync rules require — the live leg the automated fixture-gateway tests
(``test_sync_rules_*.py``, all green) mirror offline. Same ownership pattern as
``verify_knowledge_scope_live.py`` / ``run_reconciliation_once.py``: a one-off operator tool, NOT
part of pytest (it needs real network + real credentials + it mutates live Confluence).

    ┌─────────────────────────────────────────────────────────────────────────────────────────┐
    │  STAGING ONLY.  This mutates live Confluence (adds/removes labels, and asks you to trash / │
    │  restore / edit a page). NEVER run it against production — run it against staging with the │
    │  owner's dedicated test page. You must pass --yes to proceed.                              │
    └─────────────────────────────────────────────────────────────────────────────────────────┘

What it drives on ONE already-synced page you name with ``--page-id`` (carrying exactly one
recognized ROUTING label to start, e.g. ``mews-general``). Under ADR-0021 Path B "recognized label"
means a routing label (``obi-general`` / ``{slug}-general`` / ``{slug}-to-{kind}``); the knowledge-
scope ``-test`` axis is retired. Membership = published + >=1 recognized routing label.

  * Rule 4 — add a second recognized label -> shared, same version id, no re-embed.       [auto]
  * Rule 3 — remove one of the two -> the other stays, same version id, no re-embed.       [auto]
  * Rule 2 — remove the last recognized label -> the page is purged (zero rows).           [auto]
  * Rule 5 — re-add the first recognized label to the now-untagged page -> full rebuild.   [auto]
  * Rule 7 — add the reserved ``classified`` label -> the page is purged (zero rows).      [auto]
  * Rule 1 — trash the page -> purged; restore it -> full rebuild.                       [manual]
  * Rule 6 — edit the body, then rename the title -> a new version each time, every child  [manual]
             re-embedded (no vector reuse).
  * Rule 8 — observed as a side-check: a second page you name with ``--other-page-id`` is
             read before and after and must be byte-identical throughout.

The label-driven rules run automatically via the Confluence v1 label API (the read gateway is
read-only, so writes use a small dedicated client, exactly like ``verify_knowledge_scope_live.py``).
The physical actions no API here can perform — trash, restore, body edit, rename — pause and prompt
you to do them in the Confluence UI, then continue on Enter.

Assertions are **outcomes, never code paths**: chunk/version/page_source row counts, the tag set on
active chunks, and whether ``active_doc_version_id`` changed (the live "did it re-embed?" signal — a
rebuild mints a new doc version, a metadata-only label change keeps the same id). The exact "reused
no vector" guarantee is proven at the database level (``test_in3_*``); live, the observable proxy is
"new version id + the active chunk-id set fully replaced".

REFUSES the offline fixture gateway (no Confluence configured). Restores the page's original label
set in a ``finally`` so a verification run leaves no residue in live Confluence.

Usage (from ``backend``, DB reachable + Confluence configured):

    uv run python scripts/verify_sync_rules.py --page-id 28934165 --yes
    uv run python scripts/verify_sync_rules.py --page-id 28934165 --other-page-id 28934166 \
        --scope-a mews-general --scope-b toast-general --yes

Add ``--no-manual`` to skip the two manual rules (1, 6) and run only the label-driven checks.
Exits 0 iff every check that ran passed and the original labels were restored.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from dataclasses import dataclass

import httpx
from sqlalchemy import select

from app.features.confluence_sync import drain, reap
from app.platform.clients import HttpConfluenceClient
from app.platform.config import Settings, get_settings
from app.platform.jobs import enqueue_job
from schema.engine import session_scope
from schema.models import Chunk, DocumentVersion, PageSource

_OWNER = "verify-sync-rules"
_CLASSIFIED_LABEL = "classified"


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
    """A small client for the v1 content-label write API (the read gateway is read-only).

    Same BasicAuth(email, token) as ``HttpConfluenceClient``; the label add/remove endpoints live on
    the v1 REST surface (``/rest/api/content/{id}/label``). Finite timeout inherited from settings.
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
            total = len(chunk_rows) + n_version_rows  # should be 0 on a clean purge
            return PageState(False, (), None, (), tuple(sorted(active_ids)), total)

        total = 1 + n_version_rows + len(chunk_rows)
        return PageState(
            exists=True,
            tags=tuple(sorted(ps.tags or [])),
            active_doc_version_id=ps.active_doc_version_id,
            active_chunk_tags=tuple(sorted(active_tags)),
            active_chunk_ids=tuple(sorted(active_ids)),
            total_rows=total,
        )


# --------------------------------------------------------------------------- sync driver


def _drive_sync(gateway: HttpConfluenceClient, settings: Settings, page_id: int, note: str) -> str:
    """Enqueue + drain the ``sync_page`` job a webhook enqueues; return the page's outcome action.

    A unique idempotency key per call (a label/edit event may not bump ``cf_version``, so reusing
    the auto key would collide via ON CONFLICT DO NOTHING). Exercises the real ``handle_sync_page``
    re-fetch/classify/re-stamp (or purge) path — the thing being verified.
    """
    key = f"verify-sync-rules:{page_id}:{note}:{uuid.uuid4()}"
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
    action = "no-op"
    for r in results:
        if r.status == "succeeded" and getattr(r.outcome, "page_id", None) == page_id:
            action = str(getattr(r.outcome, "action", "unknown"))
        elif r.status != "succeeded":
            print(f"  ! job {r.job_id} ({r.job_type}) failed: {r.error}", file=sys.stderr)
    return action


# --------------------------------------------------------------------------- checks harness


class Checks:
    def __init__(self) -> None:
        self.failures: list[str] = []

    def ok(self, condition: bool, label: str) -> None:
        mark = "PASS" if condition else "FAIL"
        print(f"  [{mark}] {label}")
        if not condition:
            self.failures.append(label)


def _prompt(message: str) -> None:
    """Pause for a manual Confluence action; wait for the operator to press Enter."""
    try:
        input(f"\n  >> {message}\n  >> Press Enter when done (Ctrl-C to abort)... ")
    except EOFError:
        print("  (no TTY — cannot run manual steps; use --no-manual)", file=sys.stderr)
        raise SystemExit(2) from None


# --------------------------------------------------------------------------- rule checks


def _rule_4_add_second(gw, settings, lc, checks, page_id, scope_a, scope_b, baseline):
    print(f"\n[rule 4] add second recognized label '{scope_b}' (sharing, no re-embed)")
    _add_label(lc, page_id, scope_b)
    _drive_sync(gw, settings, page_id, "label_added")
    st = _read_state(page_id)
    checks.ok(
        scope_a in st.tags and scope_b in st.tags, f"page_source.tags share both {sorted(st.tags)}"
    )
    checks.ok(scope_b in st.active_chunk_tags, f"active chunk.tags include '{scope_b}'")
    checks.ok(
        st.active_doc_version_id == baseline.active_doc_version_id,
        "active_doc_version_id unchanged (no re-embed)",
    )
    return st


def _rule_3_remove_one(gw, settings, lc, checks, page_id, scope_a, scope_b, before):
    print(f"\n[rule 3] remove one label '{scope_b}', '{scope_a}' stays (metadata-only)")
    _remove_label(lc, page_id, scope_b)
    _drive_sync(gw, settings, page_id, "label_deleted")
    st = _read_state(page_id)
    checks.ok(scope_a in st.tags and scope_b not in st.tags, f"tags now {sorted(st.tags)}")
    checks.ok(st.exists, "page still indexed (a recognized tag remains)")
    checks.ok(
        st.active_doc_version_id == before.active_doc_version_id,
        "active_doc_version_id unchanged (no re-embed)",
    )
    return st


def _rule_2_remove_last(gw, settings, lc, checks, page_id, scope_a):
    print(f"\n[rule 2] remove the last recognized label '{scope_a}' (purge)")
    _remove_label(lc, page_id, scope_a)
    _drive_sync(gw, settings, page_id, "label_deleted")
    st = _read_state(page_id)
    checks.ok(not st.exists, "page_source row is gone")
    checks.ok(st.total_rows == 0, f"zero rows for the page (purged), total_rows={st.total_rows}")


def _rule_5_first_tag(gw, settings, lc, checks, page_id, scope_a):
    print(f"\n[rule 5] add the first recognized label '{scope_a}' to the untagged page (build)")
    _add_label(lc, page_id, scope_a)
    action = _drive_sync(gw, settings, page_id, "label_added")
    st = _read_state(page_id)
    checks.ok(st.exists, "page indexed again (page_source row present)")
    checks.ok(len(st.active_chunk_ids) > 0, f"active chunks embedded ({len(st.active_chunk_ids)})")
    checks.ok(scope_a in st.active_chunk_tags, f"active chunk.tags include '{scope_a}'")
    checks.ok(action != "metadata_only", f"a full build ran (action='{action}', not metadata_only)")
    return st


def _rule_7_classified(gw, settings, lc, checks, page_id, scope_a):
    print(f"\n[rule 7] add the reserved '{_CLASSIFIED_LABEL}' label (purge)")
    _add_label(lc, page_id, _CLASSIFIED_LABEL)
    _drive_sync(gw, settings, page_id, "label_added")
    st = _read_state(page_id)
    checks.ok(not st.exists, "page_source row is gone")
    checks.ok(st.total_rows == 0, f"zero rows (classified purge), total_rows={st.total_rows}")
    # restore: drop classified, re-add the recognized label, rebuild
    _remove_label(lc, page_id, _CLASSIFIED_LABEL)
    _add_label(lc, page_id, scope_a)
    _drive_sync(gw, settings, page_id, "label_deleted")
    st2 = _read_state(page_id)
    checks.ok(st2.exists, "page re-indexed after removing classified + re-adding a recognized tag")
    return st2


def _rule_1_delete_restore(gw, settings, checks, page_id, before):
    print("\n[rule 1] trash the page (purge), then restore it (full rebuild) — MANUAL")
    _prompt(f"TRASH page {page_id} in Confluence (move it to the trash).")
    _drive_sync(gw, settings, page_id, "page_trashed")
    st = _read_state(page_id)
    checks.ok(not st.exists, "trashed page purged: page_source row gone")
    checks.ok(st.total_rows == 0, f"zero rows after trash, total_rows={st.total_rows}")
    _prompt(f"RESTORE page {page_id} from the Confluence trash.")
    _drive_sync(gw, settings, page_id, "page_restored")
    st2 = _read_state(page_id)
    checks.ok(st2.exists, "restored page re-indexed (page_source row present)")
    checks.ok(len(st2.active_chunk_ids) > 0, "restored page has active chunks (full rebuild)")
    checks.ok(
        st2.active_doc_version_id != before.active_doc_version_id,
        "a fresh document_version was minted on restore (not the pre-trash one)",
    )
    return st2


def _rule_6_edit(gw, settings, checks, page_id, marker, before):
    print("\n[rule 6] edit the body, then rename the title (rebuild, re-embed every child) MANUAL")
    _prompt(
        f"EDIT the BODY of page {page_id} (a real content change) and include the word "
        f"'{marker}' somewhere in the body. Save/publish it."
    )
    _drive_sync(gw, settings, page_id, "page_updated")
    st = _read_state(page_id)
    checks.ok(
        st.active_doc_version_id != before.active_doc_version_id,
        "body edit minted a new document_version (rebuild)",
    )
    checks.ok(
        set(st.active_chunk_ids).isdisjoint(before.active_chunk_ids),
        "active chunk-id set fully replaced (no vector reuse — proxy for re-embed-every-child)",
    )
    print(
        f"  (observe: `page_state.py {page_id} {marker}` should show the marker in the active "
        "child chunks)"
    )
    _prompt(f"RENAME the TITLE of page {page_id} (leave the body unchanged). Save/publish it.")
    _drive_sync(gw, settings, page_id, "page_updated")
    st2 = _read_state(page_id)
    checks.ok(
        st2.active_doc_version_id != st.active_doc_version_id,
        "title rename minted a new document_version (rebuild)",
    )
    return st2


# --------------------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Live staging runner for the eight sync rules.")
    parser.add_argument(
        "--page-id", type=int, required=True, help="An already-synced staging test page."
    )
    parser.add_argument(
        "--other-page-id",
        type=int,
        default=None,
        help="A second untouched indexed page — rule 8 side-check (must stay byte-identical).",
    )
    parser.add_argument(
        "--scope-a", default="mews-general", help="First recognized routing label (ADR-0021)."
    )
    parser.add_argument(
        "--scope-b", default="toast-general", help="Second recognized routing label (ADR-0021)."
    )
    parser.add_argument(
        "--marker", default="verifymarker", help="Word to add in the rule-6 body edit."
    )
    parser.add_argument(
        "--no-manual", action="store_true", help="Skip rules 1 and 6 (manual steps)."
    )
    parser.add_argument("--yes", action="store_true", help="Confirm this mutates live Confluence.")
    args = parser.parse_args(argv)

    if not args.yes:
        print(
            "REFUSING: this mutates live Confluence. Re-run with --yes once you have confirmed the "
            "--page-id is a STAGING test page (never production).",
            file=sys.stderr,
        )
        return 2

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
            "already-synced page carrying one recognized scope label.",
            file=sys.stderr,
        )
        return 2
    if scope_a not in original_labels:
        print(
            f"REFUSING: page {page_id} must start carrying '{scope_a}' (its recognized scope). "
            f"Current labels: {original_labels}.",
            file=sys.stderr,
        )
        return 2

    other_before = _read_state(args.other_page_id) if args.other_page_id else None
    print(f"page {page_id}: original labels={original_labels} tags={list(baseline.tags)}")

    label_client = _label_client(settings)
    try:
        st = _rule_4_add_second(
            gateway, settings, label_client, checks, page_id, scope_a, scope_b, baseline
        )
        st = _rule_3_remove_one(
            gateway, settings, label_client, checks, page_id, scope_a, scope_b, st
        )
        _rule_2_remove_last(gateway, settings, label_client, checks, page_id, scope_a)
        st = _rule_5_first_tag(gateway, settings, label_client, checks, page_id, scope_a)
        st = _rule_7_classified(gateway, settings, label_client, checks, page_id, scope_a)

        if not args.no_manual:
            st = _rule_1_delete_restore(gateway, settings, checks, page_id, st)
            _rule_6_edit(gateway, settings, checks, page_id, args.marker, st)
        else:
            print("\n[rules 1 + 6] skipped (--no-manual)")

        # Rule 8 side-check: the other page never moved.
        if other_before is not None:
            print(f"\n[rule 8] page {args.other_page_id} untouched throughout")
            other_after = _read_state(args.other_page_id)
            checks.ok(
                other_after == other_before,
                "the other page's version id, chunk ids and tags are byte-identical",
            )

    finally:
        # Restore original labels exactly — a verification run leaves no residue in live Confluence.
        print("\n[restore] original labels")
        try:
            current = set(gateway.get_labels(page_id))
            for extra in current - set(original_labels):
                _remove_label(label_client, page_id, extra)
            for missing in set(original_labels) - set(gateway.get_labels(page_id)):
                _add_label(label_client, page_id, missing)
            restored = sorted(gateway.get_labels(page_id))
            checks.ok(
                restored == sorted(original_labels),
                f"labels restored to {sorted(original_labels)}",
            )
            _drive_sync(gateway, settings, page_id, "restore")  # re-stamp DB to the original set
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
    print("OK — every sync-rule check that ran passed and original labels were restored.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
