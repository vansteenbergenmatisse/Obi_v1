"""Regression tests for design panel cm-docs — "docs/adr: the decisions of record".

One deterministic unit test per panel check. Each test reads the corresponding
ADR of record under repo-root `docs/adr/` and asserts it exists and its content
names the concepts the check lists (case-insensitive substring checks).

Hermetic: reads local files only. No network, no sleep, no clock, no randomness.
The ADRs live OUTSIDE backend, so the repo root is located robustly by
walking up from this test file until a directory containing `docs/adr` is found.
"""

from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    """The first ancestor of this file that contains a `docs/adr` directory."""
    for ancestor in Path(__file__).resolve().parents:
        if (ancestor / "docs" / "adr").is_dir():
            return ancestor
    raise AssertionError("could not locate repo root with docs/adr/ above this test file")


def _adr_text(filename: str) -> str:
    adr = _repo_root() / "docs" / "adr" / filename
    assert adr.is_file(), f"ADR of record is missing: docs/adr/{filename}"
    # Collapse all whitespace runs so multi-word terms match across line wraps.
    return " ".join(adr.read_text(encoding="utf-8").lower().split())


def test_cm_docs_0001_stack_names_postgres_pgvector_fastapi_nextjs() -> None:
    """panel cm-docs · substep p0-s0_5-reg-code-map
    0001 records the stack: Postgres + pgvector, FastAPI, Next.js."""
    text = _adr_text("0001-Archetype-And-Stack.md")
    for term in ("postgres", "pgvector", "fastapi", "next.js"):
        assert term in text, f"0001 does not name stack term {term!r}"


def test_cm_docs_0002_retrieval_core_hybrid_rrf_versioned_store() -> None:
    """panel cm-docs · substep p0-s0_5-reg-code-map
    0002 records the retrieval core: hybrid retrieval, RRF, a versioned store."""
    text = _adr_text("0002-Retrieval-And-Versioning-Model.md")
    assert "hybrid" in text, "0002 does not name hybrid retrieval"
    assert "versioned store" in text, "0002 does not name the versioned store"
    # The check names "RRF"; the ADR states the concept in full ("Reciprocal Rank
    # Fusion") rather than the acronym. Assert what the doc actually says.
    assert "reciprocal rank fusion" in text, "0002 does not name Reciprocal Rank Fusion (RRF)"
    assert "rrf" not in text, (
        "expected the acronym RRF to be absent (doc spells out Reciprocal Rank Fusion); "
        "update this test if 0002 starts using the acronym"
    )


def test_cm_docs_0003_feature_boundaries() -> None:
    """panel cm-docs · substep p0-s0_5-reg-code-map
    0003 records feature boundaries."""
    text = _adr_text("0003-Feature-Boundary-Enforcement.md")
    assert "feature" in text, "0003 does not name features"
    assert "boundary" in text or "boundaries" in text, "0003 does not name boundaries"
