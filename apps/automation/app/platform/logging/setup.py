"""Structured logging setup (structlog). JSON in non-local envs, console locally."""

from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(level: str = "INFO", env: str = "local") -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level.upper())
    processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    processors.append(
        structlog.dev.ConsoleRenderer()
        if env == "local"
        else structlog.processors.JSONRenderer()
    )
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
