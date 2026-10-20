"""Live isolation check for Option A directed-connection routing (substep 9.6.1, ADR-directed-source-target-routing-labels).

Read-only. Proves, against a REAL store (a local pgvector after a reingest, or Supabase), that a
directed ``source -> target`` chat can read ONLY the chunks whose routing labels overlap its four
boxes, and never another connection's pages. It reproduces the gate+retriever session EXACTLY:

  * the NON-OWNER ``rag_reader`` role (so the RLS policies actually bite — the writer/owner bypasses
    RLS, ADR-source-id-row-security-with-reader-writer-roles / ADR-supabase-postgres-store-without-force-rls), via ``get_reader_sessionmaker``;
  * ``app.allowed_sources   = 'confluence:default'`` (the directed gate's _DEFAULT_SOURCES);
  * ``app.allowed_knowledge_scopes = ''`` (empty — the directed gate sets ``allowed_scopes=()``).
    The knowledge-scope axis is RETIRED (ADR-routing-labels-sole-content-axis Path B): migration 0018 dropped
    ``chunk_scope_read``, so this GUC is now a dead no-op; it is still set, empty, to mirror the
    real gate exactly.
  * ``app.allowed_labels = build_labels(source, target)`` (the four routing boxes, the live axis).

Then a plain ``SELECT ... FROM chunk WHERE is_active`` — whatever comes back is exactly what a
Toast->Mews (etc.) chat could retrieve, because the three RLS policies (source, customer-scope,
routing-label) have already filtered it. No Confluence, no writes, no vectors, no ranking — pure
visibility. It is NOT part of pytest (it needs a real DB + the reader role), the same ownership
pattern as ``verify_knowledge_scope_live.py`` / ``page_state.py``.

For the proof to be real the reader must run as the non-owner role: ``DATABASE_READER_URL`` must be
set to the ``rag_reader`` DSN (production is; the local compose sets it too). If the reader resolves
to the owner role, RLS is bypassed and the check FAILS loudly rather than reporting a false pass.

Usage (from ``backend``, DB reachable):

    uv run python scripts/verify_directed_routing_live.py --source toast --target mews
    uv run python scripts/verify_directed_routing_live.py --source toast --target mews --mirror
    uv run python scripts/verify_directed_routing_live.py --source toast --target mews --json

Exit code: 0 = PASS, 1 = FAIL (leak or RLS bypassed), 2 = nothing to check (empty corpus
or unknown system). PASS means: every active page's visibility matches the box-overlap rule
exactly, AND the corpus actually contained at least one other-connection page that was correctly
hidden (non-vacuous).
"""

from __future__ import annotations

import argparse
import json
import sys

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.platform.config.product_catalog import ProductCatalog, load_product_catalog
from schema.engine import get_reader_sessionmaker, get_sessionmaker

# The directed gate's fixed outputs (auth_context._DEFAULT_SOURCES and the knowledge-scope set).
# Hard-coded here, not imported, because a script lives outside the feature boundary and the gate
# resolves these from a verified token; the values are config-stable. Post-ADR-routing-labels-sole-content-axis the gate sets
# ``allowed_scopes=()`` (the scope axis is retired, migration 0018 dropped chunk_scope_read), so the
# scope GUC is empty and inert — routing happens entirely on ``app.allowed_labels``.
GATE_SOURCES = ("confluence:default",)
GATE_SCOPE: tuple[str, ...] = ()
_READER_ROLE = "rag_reader"


def _set_session_gucs(
    session: Session,
    sources: tuple[str, ...],
    scopes: tuple[str, ...],
    labels: list[str],
) -> None:
    """Set the three transaction-local GUCs exactly as the retriever does (bound set_config,
    is_local=true). Must run in the same transaction as the SELECT that follows."""
    for guc, values in (
        ("app.allowed_sources", list(sources)),
        ("app.allowed_knowledge_scopes", list(scopes)),
        ("app.allowed_labels", labels),
    ):
        session.execute(
            text("SELECT set_config(:g, :v, true)"),
            {"g": guc, "v": ",".join(values)},
        )


def _corpus_pages(owner_sm: sessionmaker[Session]) -> dict[int, list[str]]:
    """Every active page's routing labels, read as the OWNER (RLS bypassed) — the ground truth of
    what is indexed, used to show what the connection correctly excludes."""
    with owner_sm() as s:
        rows = s.execute(
            text(
                "SELECT page_id, (array_agg(DISTINCT l))::text[] AS labels "
                "FROM chunk, LATERAL unnest(CASE WHEN labels = '{}' THEN ARRAY[NULL]::text[] "
                "ELSE labels END) AS l "
                "WHERE is_active GROUP BY page_id ORDER BY page_id"
            )
        ).all()
    return {int(r[0]): [x for x in (r[1] or []) if x is not None] for r in rows}


def _visible_pages(
    reader_sm: sessionmaker[Session],
    boxes: list[str],
) -> tuple[str, set[int]]:
    """The active pages a directed chat can actually read, as the rag_reader role with the gate's
    GUCs set. Returns the connected role and the visible page-id set."""
    with reader_sm() as s:
        role = str(s.execute(text("SELECT current_user")).scalar())
        _set_session_gucs(s, GATE_SOURCES, GATE_SCOPE, boxes)
        rows = s.execute(text("SELECT DISTINCT page_id FROM chunk WHERE is_active")).scalars().all()
    return role, {int(p) for p in rows}


def _check_one(
    catalog: ProductCatalog,
    source: str,
    target: str,
    owner_sm: sessionmaker[Session],
    reader_sm: sessionmaker[Session],
) -> dict:
    """Run the isolation check for one directed connection. Returns a structured result dict."""
    src = catalog.resolve_system(source)
    tgt = catalog.resolve_system(target)
    if src is None or tgt is None:
        return {"status": "unknown_system", "source": source, "target": target}

    boxes = catalog.build_labels(source, target)
    corpus = _corpus_pages(owner_sm)
    if not corpus:
        return {"status": "empty_corpus", "boxes": boxes}

    role, visible = _visible_pages(reader_sm, boxes)
    box_set = set(boxes)

    pages = []
    mismatches = []
    hidden_other_connection = 0
    for page_id, labels in corpus.items():
        expected = bool(set(labels) & box_set)  # overlaps a box -> should be visible
        actual = page_id in visible
        pages.append(
            {"page_id": page_id, "labels": labels, "expected": expected, "visible": actual}
        )
        if expected != actual:
            mismatches.append(page_id)
        if not expected and not actual:
            hidden_other_connection += 1

    rls_enforced = role == _READER_ROLE
    non_vacuous = hidden_other_connection > 0
    passed = (not mismatches) and rls_enforced and non_vacuous
    return {
        "status": "pass" if passed else "fail",
        "source": src.id,
        "target": tgt.id,
        "boxes": boxes,
        "role": role,
        "rls_enforced": rls_enforced,
        "non_vacuous": non_vacuous,
        "hidden_other_connection": hidden_other_connection,
        "mismatches": mismatches,
        "pages": pages,
    }


def _print_human(result: dict) -> None:
    src, tgt = result.get("source"), result.get("target")
    print(f"\n=== {src} -> {tgt} ===")
    if result["status"] == "unknown_system":
        print(
            f"  UNKNOWN SYSTEM: {result['source']!r} or {result['target']!r} is not in the catalog."
        )
        return
    print(f"  boxes: {result['boxes']}")
    if result["status"] == "empty_corpus":
        print("  NOTHING TO CHECK: no active chunks indexed. Run the reingest (Gate 2) first.")
        return
    print(f"  reader role: {result['role']}  (RLS enforced: {result['rls_enforced']})")
    if not result["rls_enforced"]:
        print(
            "  !! reader is NOT the rag_reader role — RLS is bypassed, this is NOT a real proof.\n"
            "     Set DATABASE_READER_URL to the rag_reader DSN and re-run."
        )
    print(f"  {'page':>10}  {'visible':>7}  {'expected':>8}  labels")
    for p in result["pages"]:
        mark = "" if p["visible"] == p["expected"] else "  <-- MISMATCH"
        print(
            f"  {p['page_id']:>10}  {str(p['visible']):>7}  {str(p['expected']):>8}  "
            f"{p['labels']}{mark}"
        )
    print(
        f"  other-connection pages correctly hidden: {result['hidden_other_connection']}"
        f"  | mismatches: {result['mismatches'] or 'none'}"
    )
    print(f"  RESULT: {'PASS' if result['status'] == 'pass' else 'FAIL'}")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    p.add_argument("--source", required=True, help="source system (canonical id, alias, or name)")
    p.add_argument("--target", required=True, help="target system (canonical id, alias, or name)")
    p.add_argument(
        "--mirror",
        action="store_true",
        help="also run the reversed connection (target -> source) to prove the direction flip",
    )
    p.add_argument("--json", action="store_true", help="print the structured result as JSON")
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    args = _parse_args(argv)
    catalog = load_product_catalog()
    owner_sm = get_sessionmaker()
    reader_sm = get_reader_sessionmaker()

    results = [_check_one(catalog, args.source, args.target, owner_sm, reader_sm)]
    if args.mirror:
        results.append(_check_one(catalog, args.target, args.source, owner_sm, reader_sm))

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for r in results:
            _print_human(r)

    statuses = {r["status"] for r in results}
    if "fail" in statuses:
        return 1
    if statuses & {"unknown_system", "empty_corpus"}:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
