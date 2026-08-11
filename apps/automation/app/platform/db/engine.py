"""Engine + session management. Connection pooling is reused across the process."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.platform.config import get_settings


class ReaderRoleMisconfiguredError(RuntimeError):
    """DATABASE_READER_URL is unset outside an offline env (PLAN 4.6.10)."""


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        future=True,
    )


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)


@lru_cache
def get_reader_engine() -> Engine:
    """Engine for the non-owner ``rag_reader`` role (ADR-0004): RLS is actually enforced here.

    The writer path (``get_engine``) runs as the owner/superuser and bypasses RLS. Retrieval must
    run as this reader so the source-isolation policy bites. An unset ``database_reader_url``
    falls back to ``database_url`` (RLS becomes a no-op) only inside an offline env — local/dev
    without roles set up, or the test harness, which grants its own `rag_reader` explicitly and
    never hits this fallback. Outside an offline env this fails closed (PLAN 4.6.10): a real
    deployment silently reading as the RLS-bypassing writer is a security regression, not a
    convenience, so it must be a loud startup failure, not a warning buried in logs.
    """
    settings = get_settings()
    url = settings.database_reader_url
    if not url:
        if not settings.is_offline_env():
            raise ReaderRoleMisconfiguredError(
                f"DATABASE_READER_URL is unset outside an offline env (env={settings.env!r}) — "
                "retrieval would silently read as the RLS-bypassing writer role. Set "
                "DATABASE_READER_URL, or ENV to one of local/test/dev/ci for offline use."
            )
        url = settings.database_url  # offline env: acceptable local/dev fallback, no warning
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        future=True,
    )


@lru_cache
def get_reader_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_reader_engine(), expire_on_commit=False, future=True)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope: commit on success, rollback on error, always close."""
    session = get_sessionmaker()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
