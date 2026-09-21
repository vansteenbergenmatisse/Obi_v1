"""PLAN 4.6.10: DATABASE_READER_URL unset must fail closed outside an offline env.

`get_reader_engine()` previously fell back to the RLS-bypassing writer connection whenever
``database_reader_url`` was unset, in every env — only ever proven correct inside the test
harness, which always sets a real reader URL explicitly. These tests exercise the three cases
directly, without a live DB connection (``create_engine`` does not connect eagerly, so a
syntactically-valid-but-unreachable URL is enough).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from schema import engine as engine_mod
from schema.settings import KbSettings as Settings


def _settings(**overrides) -> Settings:
    return Settings(database_url="postgresql+psycopg://w:w@localhost:1/writer_db", **overrides)


@pytest.fixture(autouse=True)
def _clear_reader_engine_cache() -> Iterator[None]:
    engine_mod.get_reader_engine.cache_clear()
    yield
    engine_mod.get_reader_engine.cache_clear()


@pytest.mark.parametrize("env", ["local", "test", "dev", "ci"])
def test_offline_env_with_unset_reader_url_falls_back_to_writer_engine(monkeypatch, env) -> None:
    settings = _settings(env=env, database_reader_url="")
    monkeypatch.setattr(engine_mod, "get_settings", lambda: settings)

    eng = engine_mod.get_reader_engine()

    assert eng.url.render_as_string(hide_password=False) == settings.database_url


@pytest.mark.parametrize("env", ["production", "staging", "prod"])
def test_non_offline_env_with_unset_reader_url_fails_closed(monkeypatch, env) -> None:
    settings = _settings(env=env, database_reader_url="")
    monkeypatch.setattr(engine_mod, "get_settings", lambda: settings)

    with pytest.raises(engine_mod.ReaderRoleMisconfiguredError):
        engine_mod.get_reader_engine()


@pytest.mark.parametrize("env", ["local", "test", "production"])
def test_reader_url_set_never_fails_regardless_of_env(monkeypatch, env) -> None:
    reader_url = "postgresql+psycopg://r:r@localhost:1/reader_db"
    settings = _settings(env=env, database_reader_url=reader_url)
    monkeypatch.setattr(engine_mod, "get_settings", lambda: settings)

    eng = engine_mod.get_reader_engine()

    assert eng.url.render_as_string(hide_password=False) == reader_url


def test_r3_reader_engine_binds_to_database_reader_url_not_the_writer_url(monkeypatch) -> None:
    """panel r3-reader · substep p0-s0_5-reg-retrieval-stage-3
    get_reader_engine() is bound to DATABASE_READER_URL, not DATABASE_URL, whenever the reader
    URL is configured -- the panel's third check, distinct from the writer engine."""
    reader_url = "postgresql+psycopg://r:r@localhost:1/reader_db"
    settings = _settings(database_reader_url=reader_url)
    writer_url = settings.database_url
    monkeypatch.setattr(engine_mod, "get_settings", lambda: settings)

    eng = engine_mod.get_reader_engine()

    assert eng.url.render_as_string(hide_password=False) == reader_url
    assert eng.url.render_as_string(hide_password=False) != writer_url
