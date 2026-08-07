"""Engine + session management. Connection pooling is reused across the process."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.platform.config import get_settings


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
    run as this reader so the source-isolation policy bites. Falls back to ``database_url`` when
    ``database_reader_url`` is unset (RLS is then a no-op — acceptable for local/dev without roles).
    """
    settings = get_settings()
    url = settings.database_reader_url or settings.database_url
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
