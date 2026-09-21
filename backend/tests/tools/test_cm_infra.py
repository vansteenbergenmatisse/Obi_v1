"""Regression tests for design panel ``cm-infra`` — "knowledge-base/local: local Postgres".

Batch: substep ``p0-s0_5-reg-code-map`` (Protect: Code map). These are protect-only
tests: they pin what the repo does *today* and must be green on unchanged code.

Panel cm-infra has two checks:
  1. docker-compose: pgvector image pinned to 0.8.x.
  2. Use: local development and the test database; production is Supabase.

Hermetic and unit-level: no network, no sleep, no clock. The compose file lives at the
repository root (outside ``backend/``), so the repo root is located by walking up
from this test file's path — the same ``Path(__file__).resolve().parents[N]`` pattern the
sibling tooling tests use. No ``db`` marker, so ``make test-unit`` collects it.

Two honest disclosures are baked into the assertions below (see each docstring):
  * The image is pinned by **digest** (``@sha256:...``); its literal tag is ``pg16``, not a
    ``0.8.x`` string. The pgvector 0.8.x version is declared in the compose comment and
    frozen by the digest — it is not readable from the tag, and cannot be resolved from the
    digest offline. So the "0.8.x" fact is asserted at the comment + digest level.
  * "production is Supabase" is **documented prose** (CLAUDE.md), not a fact provable from
    this compose file — the compose defines only the local/test database. That half is also
    flagged open/unconfirmed by decisions.md row ``live-0.5.3-cm-infra``.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

# backend/tests/tools/test_cm_infra.py -> parents[4] is the repository root.
REPO_ROOT = Path(__file__).resolve().parents[3]
COMPOSE_PATH = REPO_ROOT / "knowledge-base" / "local" / "docker-compose.yml"
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"

_DIGEST_RE = re.compile(r"@sha256:[0-9a-f]{64}$")
_TAG_RE = re.compile(r"^(?P<repo>[^:@]+):(?P<tag>[^@]+)(?:@sha256:[0-9a-f]{64})?$")


def _postgres_image() -> str:
    """Parse the compose YAML and return the postgres service's image reference."""
    data = yaml.safe_load(COMPOSE_PATH.read_text())
    return data["services"]["postgres"]["image"]


def test_cm_infra_pgvector_image_pinned_to_0_8_x() -> None:
    """panel cm-infra · substep p0-s0_5-reg-code-map
    docker-compose: the pgvector image is pinned to 0.8.x.

    DISCLOSURE — the panel says "pinned to 0.8.x", but the literal image tag is ``pg16``,
    not a ``0.8.x`` string. Reproducibility is achieved by a **digest pin** (``@sha256:``),
    and the exact pgvector 0.8.x version is stated in the compose comment ("pgvector 0.8.5",
    "Digest verified = 0.8.5"). The digest cannot be resolved to a version offline, so this
    test asserts (a) the image is the pgvector image, (b) it is digest-pinned for
    reproducibility, and (c) the 0.8.x version is declared in the file's comment. It does
    NOT claim the tag literally contains "0.8.x", because it does not.
    """
    image = _postgres_image()

    match = _TAG_RE.match(image)
    assert match is not None, f"unparseable image reference: {image!r}"

    # (a) It is the pgvector image.
    assert match.group("repo") == "pgvector/pgvector", (
        f"expected pgvector/pgvector, got {match.group('repo')!r}"
    )

    # Real tag disclosure: the moving tag is pg16, NOT a 0.8.x literal.
    assert match.group("tag") == "pg16", (
        f"expected the actual tag 'pg16', got {match.group('tag')!r}"
    )

    # (b) It is digest-pinned (reproducible) rather than floating on the rolling tag.
    assert _DIGEST_RE.search(image) is not None, (
        f"image is not digest-pinned (@sha256:<64 hex>): {image!r}"
    )

    # (c) The pgvector 0.8.x version is declared in the compose comment and frozen by the
    #     digest. Read the raw file for the comment (safe_load drops comments).
    raw = COMPOSE_PATH.read_text()
    assert re.search(r"pgvector\s+0\.8\.\d", raw), (
        "compose does not document a pgvector 0.8.x version in a comment"
    )
    assert re.search(r"[Dd]igest verified\s*=\s*0\.8\.\d", raw), (
        "compose does not document the digest-verified 0.8.x version"
    )


def test_cm_infra_compose_defines_local_and_test_db_not_production() -> None:
    """panel cm-infra · substep p0-s0_5-reg-code-map
    Use: the compose file is the local development / test database, not a production definition.

    Assertable from the compose itself: local dev-default credentials, a local named volume,
    a host-side port remap, and the RLS init mount — and the ABSENCE of any Supabase / cloud /
    production reference. That is exactly what a laptop + test database looks like.
    """
    data = yaml.safe_load(COMPOSE_PATH.read_text())
    postgres = data["services"]["postgres"]
    env = postgres["environment"]

    # Local dev defaults, not managed-cloud secrets.
    assert env["POSTGRES_USER"] == "rag"
    assert env["POSTGRES_PASSWORD"] == "rag"
    assert env["POSTGRES_DB"] == "omniboost_rag"

    # Host-side port remap (5434 -> 5432) is a laptop convenience, not a production topology.
    assert "5434:5432" in postgres["ports"]

    # A local named volume and the RLS-role init mount — a self-contained local instance.
    assert "rag_pg_data" in data["volumes"]
    assert any("docker-entrypoint-initdb.d" in v for v in postgres["volumes"])

    # It is NOT a production/Supabase definition: no cloud host, no supabase, no external URL.
    raw = COMPOSE_PATH.read_text().lower()
    assert "supabase" not in raw, "local compose must not reference Supabase (production)"
    assert "amazonaws" not in raw and "rds." not in raw, (
        "local compose must not reference a managed cloud host"
    )


def test_cm_infra_production_is_supabase_is_a_doc_level_claim() -> None:
    """panel cm-infra · substep p0-s0_5-reg-code-map
    "production is Supabase" is a documented prose claim, not a fact provable from infra.

    DISCLOSURE — the compose file (asserted above) defines only the local/test database and
    has no production/Supabase reference. The "production is Supabase" half of the panel lives
    as prose in CLAUDE.md; this test pins that documented source. It further records that
    decisions.md row ``live-0.5.3-cm-infra`` currently flags this claim as open/unconfirmed
    (it could not be verified from staging alone). So this asserts *where the claim is written*,
    never that production actually runs on Supabase.
    """
    claude = CLAUDE_MD.read_text()
    assert re.search(r"Postgres on Supabase", claude), (
        "CLAUDE.md no longer documents 'One Postgres on Supabase' — the panel's "
        "'production is Supabase' claim has lost its documented source"
    )

    # The claim is a known-open finding, not a settled infra fact.
    decisions = (REPO_ROOT / "docs" / "plan" / "decisions.md").read_text()
    assert "live-0.5.3-cm-infra" in decisions, (
        "decisions.md no longer carries the open 'is production actually on Supabase?' finding"
    )
