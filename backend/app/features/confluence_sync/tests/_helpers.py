"""Shared helpers for confluence_sync DB tests (not collected: filename is not test_*)."""

from __future__ import annotations

from sqlalchemy import func, select

from app.features.confluence_sync.application.worker import drain, run_once
from app.platform.clients import ConfluenceGateway
from app.platform.clients.fixture_confluence_client import FixtureConfluenceGateway
from app.platform.config import Settings
from app.platform.jobs import enqueue_job
from schema.engine import get_sessionmaker, session_scope
from schema.enums import DocState
from schema.models import (
    KIND_CHILD,
    Chunk,
    Document,
    DocumentVersion,
    PageRestriction,
    PageSource,
)


def enqueue_sync(page_id: int, cf_version: int | None, key: str) -> int | None:
    with session_scope() as s:
        return enqueue_job(
            s,
            job_type="sync_page",
            idempotency_key=key,
            payload={"event_type": "test"},
            page_id=page_id,
            cf_version=cf_version,
        )


def enqueue_delete(page_id: int, status: str, key: str) -> int | None:
    with session_scope() as s:
        return enqueue_job(
            s,
            job_type="delete_page",
            idempotency_key=key,
            payload={"status": status},
            page_id=page_id,
        )


def index_page(
    gateway: FixtureConfluenceGateway, settings: Settings, page_id: int, version: int
) -> None:
    """Seed a page into the index at a given version by running the real sync path.

    Label-gated membership (ADR-routing-labels-sole-content-axis): a page indexes only if it carries
    a recognized ROUTING
    label (``obi-general`` / ``{slug}-general`` / ``{slug}-to-{kind}``). Most generic fixtures
    (1001/1002/2002 …) carry only unrelated labels, so — unless the page already has a recognized
    routing label (or one the test set itself) — stamp the base ``obi-general`` routing label on it
    first, persistently, so tests that exercise versioning / chunks / gc / restrictions (and don't
    care about routing) can still seed a page. Tests that assert on labels override them explicitly
    after seeding, so the injected base label is invisible to them; routing/membership tests set a
    recognized label up front and are left untouched. Decided from the gateway's live labels (not
    the on-disk fixture) so a test's own ``set_labels`` wins.
    """
    recognized = settings.product_catalog.all_routing_labels()
    current = [str(label) for label in gateway.get_labels(page_id)]
    if not ({label.strip().lower() for label in current} & recognized):
        gateway.set_labels(page_id, [*current, "obi-general"])
    gateway.set_version(page_id, version)
    enqueue_sync(page_id, version, key=f"seed:{page_id}:{version}")
    run_once(gateway, settings, owner="seed")


def run_worker(gateway: ConfluenceGateway, settings: Settings, owner: str = "test") -> list:
    return drain(gateway, settings, owner=owner, max_jobs=50)


def read():
    """A fresh read-only session (identity map isolated from writers)."""
    return get_sessionmaker()()


def active_version(page_id: int) -> DocumentVersion | None:
    with read() as s:
        ps = s.get(PageSource, page_id)
        if ps is None or ps.active_doc_version_id is None:
            return None
        return s.get(DocumentVersion, ps.active_doc_version_id)


def active_versions_count(page_id: int) -> int:
    with read() as s:
        doc_ids = (
            s.execute(
                select(DocumentVersion.id).where(
                    DocumentVersion.page_id == page_id, DocumentVersion.state == DocState.active
                )
            )
            .scalars()
            .all()
        )
        return len(doc_ids)


def active_child_chunks(page_id: int) -> list[Chunk]:
    with read() as s:
        return list(
            s.execute(
                select(Chunk).where(
                    Chunk.page_id == page_id,
                    Chunk.is_active.is_(True),
                    Chunk.kind == KIND_CHILD,
                )
            )
            .scalars()
            .all()
        )


def child_chunks_for_version(doc_version_id: int) -> list[Chunk]:
    """Every child chunk row for one document_version, regardless of is_active. With retain 0
    (sync rule 6 / D1) a superseded version and its chunks are deleted in the swap transaction, so
    this returns [] for any version other than the current active one."""
    with read() as s:
        return list(
            s.execute(
                select(Chunk).where(
                    Chunk.doc_version_id == doc_version_id, Chunk.kind == KIND_CHILD
                )
            )
            .scalars()
            .all()
        )


def restricted_principals(page_id: int) -> set[str]:
    """The persisted ACL for a page (PLAN 4.3); empty means unrestricted."""
    with read() as s:
        rows = (
            s.execute(select(PageRestriction.principal).where(PageRestriction.page_id == page_id))
            .scalars()
            .all()
        )
        return set(rows)


def count_versions(page_id: int) -> int:
    with read() as s:
        return s.execute(
            select(func.count(DocumentVersion.id)).where(DocumentVersion.page_id == page_id)
        ).scalar_one()


def page_row_counts(page_id: int) -> dict[str, int]:
    """Every stored row a page owns, by table — the outcome a purge drives to all-zero (sync rule
    1/2/7). page_source and page_restriction included so 'the page is gone', not merely inactive,
    is provable in one read."""
    with read() as s:
        return {
            "chunk": s.execute(
                select(func.count()).select_from(Chunk).where(Chunk.page_id == page_id)
            ).scalar_one(),
            "document_version": s.execute(
                select(func.count())
                .select_from(DocumentVersion)
                .where(DocumentVersion.page_id == page_id)
            ).scalar_one(),
            "document": s.execute(
                select(func.count()).select_from(Document).where(Document.page_id == page_id)
            ).scalar_one(),
            "page_source": s.execute(
                select(func.count()).select_from(PageSource).where(PageSource.page_id == page_id)
            ).scalar_one(),
            "page_restriction": s.execute(
                select(func.count())
                .select_from(PageRestriction)
                .where(PageRestriction.page_id == page_id)
            ).scalar_one(),
        }


class CountingEmbedder:
    """Wraps the deterministic Fake embedder and counts work, so a test can assert 'every child was
    re-embedded' (``texts`` == child count) or 'no re-embed' (``calls`` == 0). Reused by the sync
    rules that turn on embedding cost (rules 1b/3/4/5/6). Install with
    :func:`install_counting_embedder`."""

    def __init__(self, inner) -> None:
        self.inner = inner
        self.model = inner.model
        self.dim = inner.dim
        self.calls = 0  # embed() invocations
        self.texts = 0  # total texts embedded == children (re)embedded

    def embed(self, texts):
        self.calls += 1
        self.texts += len(texts)
        return self.inner.embed(texts)


def install_counting_embedder(monkeypatch, settings) -> CountingEmbedder:
    """Swap the ingestion services' embedder for a counting one so a test can assert re-embed work.

    Patches at ingestion's own seam — ``build_ingestion_services`` as imported into the
    ``ingestion.application.command_handler`` module namespace (where ``apply_sync_command`` now
    calls it). Tests are exempt from the forbidden trigger->ingestion edge, so importing the
    handler module here is fine. Wraps whatever embedder the real builder produced (the Fake
    provider under the test env) with the counter, leaving every other service untouched."""
    from dataclasses import replace

    import app.features.ingestion.application.command_handler as handler_mod
    from app.platform.clients.embeddings_client import FakeEmbeddingProvider

    real_build = handler_mod.build_ingestion_services
    counter = CountingEmbedder(
        FakeEmbeddingProvider(settings.embedding_dim, settings.embedding_model or "fake")
    )
    monkeypatch.setattr(
        handler_mod,
        "build_ingestion_services",
        lambda s: replace(real_build(s), embedder=counter),
    )
    return counter
