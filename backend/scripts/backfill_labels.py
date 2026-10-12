"""Operator CLI: backfill the raw-labels column on existing chunks (ADR-0020 D1, substep 9.1.2).

Stamps each indexed page's raw Confluence labels (the unresolved ``get_labels`` output) onto its
``page_source`` row and active chunks, for a corpus indexed before migration 0016 added the column.
This is the backfill ADR-0020 D0 / plan Stage 7 calls after the Confluence relabel; the live
label-change path already stamps the column going forward.

Idempotent — safe to run twice. Reads raw labels through the live Confluence gateway (the same one
sync uses), so it refuses the offline fixture corpus, mirroring ``verify_sync_rules.py``.

Usage (from ``backend``, with the DB and Confluence reachable):

    uv run python scripts/backfill_labels.py
    uv run python scripts/backfill_labels.py --json
"""

from __future__ import annotations

import argparse
import json
import sys

from app.features.ingestion import backfill_labels
from app.platform.clients import HttpConfluenceClient
from app.platform.config import Settings, get_settings


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    p.add_argument(
        "--json", action="store_true", help="emit the backfill report as a single JSON object"
    )
    return p.parse_args(argv)


def _require_live_gateway(settings: Settings) -> HttpConfluenceClient:
    """Build the live Confluence client, or refuse — never the offline fixture corpus."""
    if not (settings.confluence_base_url and settings.confluence_api_token):
        print(
            "REFUSING: Confluence is not configured (confluence_base_url / confluence_api_token "
            "missing). The backfill reads each page's raw labels from the live store, never the "
            "offline fixture gateway.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return HttpConfluenceClient(settings)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    settings = get_settings()
    gateway = _require_live_gateway(settings)
    report = backfill_labels(gateway)
    if args.json:
        print(
            json.dumps(
                {
                    "pages_scanned": report.pages_scanned,
                    "pages_stamped": report.pages_stamped,
                    "chunks_stamped": report.chunks_stamped,
                }
            )
        )
    else:
        print(
            f"pages_scanned={report.pages_scanned} pages_stamped={report.pages_stamped} "
            f"chunks_stamped={report.chunks_stamped}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
