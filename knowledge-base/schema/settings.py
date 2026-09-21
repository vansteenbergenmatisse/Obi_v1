"""Knowledge-base DB settings — the schema package's own configuration source.

The schema package is standalone (ADR-0003 / Phase-1 one-way rule: knowledge-base imports
nothing from the backend). It therefore reads the few DB-relevant settings it needs directly,
rather than importing ``app.platform.config``. These fields mirror the backend's ``Settings``
and use the SAME ``env_file`` + env-var names, so both read identical values — there is one
source of truth in practice: the environment (and the local .env for dev). Substep 1.1.1,
owner-approved (decisions.md · kb-import-name / the config-decoupling deviation).
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

# Envs where a missing hosted-provider key or DB role falls back to a safe offline default
# instead of failing (PLAN 4.6.10). Mirrors app.platform.config._OFFLINE_ENVS.
_OFFLINE_ENVS = {"local", "test", "dev", "ci"}


class KbSettings(BaseSettings):
    """DB-connection + embedding-dimension settings for the schema package.

    Reads the same env vars and .env files as the backend's ``Settings`` (env_file resolved
    relative to CWD, which is ``backend/`` for the app, tests and alembic), so values never
    diverge. Defaults copied verbatim from ``backend/app/platform/config/settings.py``.
    """

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    env: str = "local"
    database_url: str = "postgresql+psycopg://rag:rag@localhost:5434/omniboost_rag"
    # non-owner rag_reader DSN for RLS-enforced retrieval reads (PLAN 3.5.3; ADR-0004).
    # Empty -> retrieval falls back to database_url (RLS is a no-op for a superuser/owner).
    database_reader_url: str = ""
    embedding_dim: int = 1024

    def is_offline_env(self) -> bool:
        return self.env.lower() in _OFFLINE_ENVS


def get_kb_settings() -> KbSettings:
    """Read settings fresh from the environment on every call — deliberately NOT lru_cached.

    The DB engine (``schema.engine``) is itself cached, so this is only constructed at engine
    creation (and once for ``models.EMB_DIM`` at import). Staying uncached means the test harness
    only has to clear the engine caches (``get_engine.cache_clear()`` etc.) after redirecting
    ``DATABASE_URL`` to a per-test database — it never has to know about a settings cache here.
    Constructing KbSettings re-reads env vars + the .env files, matching the backend's values.
    """
    return KbSettings()
