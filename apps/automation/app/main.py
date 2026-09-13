"""FastAPI application entrypoint: webhook ingress, health, and (optional) background jobs.

Wiring only — all behavior lives in the features. The app selects a Confluence gateway (live
HTTP client when credentials are configured, otherwise the offline fixture gateway), exposes the
webhook receiver and a health probe, and — when ``enable_background_jobs`` is set — runs the
reconciliation crons and an in-process queue worker via APScheduler.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI

from app import __version__
from app.features.confluence_sync import (
    KIND_COMPLETE,
    KIND_LIGHTWEIGHT,
    drain,
    reap,
    run_reconciliation,
)
from app.features.confluence_sync import router as confluence_router
from app.features.rag_agent import (
    AnswerService,
    AnthropicAmbiguityClassifier,
    AnthropicAnswerGenerator,
    AnthropicQueryRewriter,
    CachingAnswerService,
    TokenVerifier,
)
from app.features.rag_agent import router as chat_router
from app.features.retrieval import HybridRetriever, PrincipalPermissionPolicy
from app.platform.clients import (
    AnthropicMessagesClient,
    ConfluenceGateway,
    FixtureConfluenceGateway,
    HttpConfluenceClient,
    build_embedding_provider,
    build_reranker,
)
from app.platform.config import Settings, get_settings
from app.platform.db.engine import get_reader_sessionmaker, get_sessionmaker, session_scope
from app.platform.logging import configure_logging, get_logger
from app.shared.rate_limiter import SlidingWindowRateLimiter

log = get_logger("main")

_WORKER_OWNER = "in-process-worker"


def build_gateway(settings: Settings) -> ConfluenceGateway:
    """Live client when Confluence is configured; offline fixture gateway otherwise."""
    if settings.confluence_base_url and settings.confluence_api_token:
        return HttpConfluenceClient(settings)
    log.info("gateway_offline", reason="confluence not configured — using fixture corpus")
    return FixtureConfluenceGateway()


def build_answer_service(settings: Settings) -> AnswerService:
    """The `rag_agent` answer runtime (PLAN 4.4), composed from settings.

    Reads run against the non-owner `rag_reader` engine (RLS actually enforced, ADR-0004); the
    policy is constructed empty — PLAN 4.3 made its injected data unused for the `allowed()`
    decision, which is now built fresh per search from live `page_source`/`page_restriction` data
    (see `retriever.py`). Merely constructing this (including the `AnthropicMessagesClient`) makes
    no network call — `build_reranker`/`build_embedding_provider` already fall back to
    deterministic offline providers when unconfigured, so this is safe to call unconditionally at
    app startup, mirroring `build_gateway` above. Returns the raw `AnswerService` — the caller
    (`create_app`, below) wraps it in `CachingAnswerService` (PLAN 5); kept separate so tests can
    still construct an uncached `AnswerService` directly, as `test_chat_endpoint.py` already does.
    """
    retriever = HybridRetriever(
        get_reader_sessionmaker(),
        build_embedding_provider(settings),
        PrincipalPermissionPolicy(),
        build_reranker(settings),
        candidate_k=settings.rerank_candidate_k,
        rerank_depth=settings.rerank_depth,
        hnsw_ef_search=settings.hnsw_ef_search,
        hnsw_iterative_scan=settings.hnsw_iterative_scan,
        trace_sessionmaker=get_sessionmaker(),
        enable_knowledge_scope_filtering=settings.enable_knowledge_scope_filtering,
    )
    client = AnthropicMessagesClient(
        api_key=settings.anthropic_api_key,
        timeout=settings.answer_timeout_seconds,
        max_retries=settings.answer_max_retries,
        breaker_threshold=settings.answer_breaker_threshold,
        max_input_chars=settings.answer_max_input_chars,
    )
    return AnswerService(
        retriever,
        AnthropicQueryRewriter(client, settings.routing_model),
        AnthropicAnswerGenerator(
            client, settings.answer_model, identity_static_facts=settings.obi_identity_text
        ),
        get_sessionmaker(),
        rewrite_enabled=settings.rewrite_enabled,
        refusal_min_rerank_score=settings.refusal_min_rerank_score,
        offtopic_max_rerank_score=settings.offtopic_max_rerank_score,
        crag_max_retries=settings.crag_max_retries,
        retrieve_k=settings.rerank_top_k,
        clarification_classifier=AnthropicAmbiguityClassifier(client, settings.routing_model),
        enable_clarification_branch=settings.enable_clarification_branch,
        recognized_knowledge_scopes=settings.knowledge_scope_set,
        default_knowledge_scope=settings.default_knowledge_scope or None,
        reader_sessionmaker=get_reader_sessionmaker(),
        curated_knowledge_max_entries=settings.curated_knowledge_max_entries,
    )


# -- scheduled tasks -------------------------------------------------------------------


def scheduled_lightweight_reconcile(gateway: ConfluenceGateway, settings: Settings) -> None:
    with session_scope() as session:
        run_reconciliation(session, gateway=gateway, settings=settings, kind=KIND_LIGHTWEIGHT)


def scheduled_complete_reconcile(gateway: ConfluenceGateway, settings: Settings) -> None:
    with session_scope() as session:
        run_reconciliation(session, gateway=gateway, settings=settings, kind=KIND_COMPLETE)


def worker_tick(gateway: ConfluenceGateway, settings: Settings) -> None:
    reap()
    drain(gateway, settings, owner=_WORKER_OWNER, max_jobs=50)


def _build_scheduler(gateway: ConfluenceGateway, settings: Settings) -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        scheduled_lightweight_reconcile,
        CronTrigger.from_crontab(settings.lightweight_recon_cron, timezone="UTC"),
        args=[gateway, settings],
        id="lightweight_reconcile",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        scheduled_complete_reconcile,
        IntervalTrigger(days=settings.complete_recon_interval_days, timezone="UTC"),
        args=[gateway, settings],
        id="complete_reconcile",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        worker_tick,
        IntervalTrigger(seconds=settings.worker_tick_seconds, timezone="UTC"),
        args=[gateway, settings],
        id="worker_tick",
        max_instances=1,
        coalesce=True,
    )
    # Optional DEV-only fast lightweight-reconcile poll (PLAN item A): when set, run the SAME
    # scheduled_lightweight_reconcile as the daily cron above, just on a short interval, so a live
    # page edit is enqueued within N seconds and drained by worker_tick into a new document_version
    # — instead of waiting for lightweight_recon_cron. This is IN ADDITION to the daily cron and
    # adds no new gateway/network surface; None (prod default) leaves the scheduler unchanged.
    if settings.dev_reconcile_interval_seconds and settings.dev_reconcile_interval_seconds > 0:
        scheduler.add_job(
            scheduled_lightweight_reconcile,
            IntervalTrigger(seconds=settings.dev_reconcile_interval_seconds, timezone="UTC"),
            args=[gateway, settings],
            id="dev_lightweight_reconcile",
            max_instances=1,
            coalesce=True,
        )
    return scheduler


def create_app(*, settings: Settings | None = None, start_scheduler: bool | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.env)
    gateway = build_gateway(settings)
    should_start = settings.enable_background_jobs if start_scheduler is None else start_scheduler

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        scheduler: BackgroundScheduler | None = None
        if should_start:
            scheduler = _build_scheduler(gateway, settings)
            scheduler.start()
            log.info("scheduler_started", jobs=[j.id for j in scheduler.get_jobs()])
        try:
            yield
        finally:
            if scheduler is not None:
                scheduler.shutdown(wait=False)

    app = FastAPI(title="omniboost-rag automation", version=__version__, lifespan=lifespan)
    app.state.settings = settings
    app.state.gateway = gateway
    app.state.rate_limiter = SlidingWindowRateLimiter(settings.webhook_rate_limit_per_minute)
    app.state.answer_service = CachingAnswerService(
        build_answer_service(settings),
        ttl_seconds=settings.chat_answer_cache_ttl_seconds,
        max_entries=settings.chat_answer_cache_max_entries,
    )
    # PLAN 11.1c (ADR-0014): the /chat token verifier, built once from the platform registry.
    # Touching settings.platform_registry here is also the fail-fast startup check (bad
    # platforms.json -> boot fails, never fails open to an unverified caller).
    app.state.token_verifier = TokenVerifier(settings.platform_registry)
    app.include_router(confluence_router)
    app.include_router(chat_router)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "env": settings.env}

    return app


app = create_app()
