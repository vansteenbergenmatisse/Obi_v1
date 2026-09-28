"""The trigger layer's dependency-inversion seam onto ingestion.

The trigger layer never imports ``app.features.ingestion`` (a forbidden edge in
``tools/check_feature_boundaries.py``). Instead it owns the *interface* it needs
— :class:`IngestionSink` — and receives a concrete implementation at wiring time
(``app/main.py`` binds ``ingestion.apply_sync_command``; tests bind it in a
conftest fixture). Ingestion satisfies the Protocol **structurally** and never
imports it.

The binding is a module-level singleton set once at startup (D6: the job queue
stays the trigger→ingestion mediation, and the sink runs inside the worker's
handle+complete transaction). ``get_ingestion_sink`` raises if the sink was
never bound, so a mis-wired process fails loudly rather than silently dropping
ingestion work.
"""

from __future__ import annotations

from typing import Protocol

from sqlalchemy.orm import Session

from app.platform.clients import ConfluenceGateway
from app.platform.config import Settings
from app.shared.sync_command import SyncCommand, SyncOutcome


class IngestionSink(Protocol):
    """A callable that applies one decided :class:`SyncCommand` to the store.

    Ingestion's ``apply_sync_command(session, cmd, gateway, settings)`` matches
    this signature structurally — a plain function is a valid ``IngestionSink``.
    """

    def __call__(
        self,
        session: Session,
        cmd: SyncCommand,
        gateway: ConfluenceGateway,
        settings: Settings,
    ) -> SyncOutcome: ...


_sink: IngestionSink | None = None


def set_ingestion_sink(sink: IngestionSink) -> None:
    """Bind the concrete ingestion implementation (called once at wiring time)."""
    global _sink
    _sink = sink


def get_ingestion_sink() -> IngestionSink:
    """Return the bound sink, or raise if the process never wired one."""
    if _sink is None:
        raise RuntimeError(
            "ingestion sink not bound — call set_ingestion_sink(apply_sync_command) "
            "at startup (app/main.py) or in the test conftest before draining jobs"
        )
    return _sink
