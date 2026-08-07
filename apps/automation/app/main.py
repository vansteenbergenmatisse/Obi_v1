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
    SlidingWindowRateLimiter,
    drain,
    reap,
    run_reconciliation,
)
from app.features.confluence_sync import router as confluence_router
from app.platform.clients import (
    ConfluenceGateway,
    FixtureConfluenceGateway,
    HttpConfluenceClient,
)
from app.platform.config import Settings, get_settings
from app.platform.db.engine import session_scope
from app.platform.logging import configure_logging, get_logger

log = get_logger("main")

_WORKER_OWNER = "in-process-worker"


def build_gateway(settings: Settings) -> ConfluenceGateway:
    """Live client when Confluence is configured; offline fixture gateway otherwise."""
    if settings.confluence_base_url and settings.confluence_api_token:
        return HttpConfluenceClient(settings)
    log.info("gateway_offline", reason="confluence not configured — using fixture corpus")
    return FixtureConfluenceGateway()


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
    app.include_router(confluence_router)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "env": settings.env}

    return app


app = create_app()
