"""Regression tests for panel cm-root (`app/main.py: the wiring`).

One deterministic unit test per panel check, no network and no live database
(``create_engine`` does not connect eagerly, so a syntactically-valid-but-unreachable
DSN is enough, and every hosted provider falls back to its offline fake in the test env).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from app import main
from app.platform.config import Settings
from schema import engine as engine_mod


@pytest.fixture
def prod_platforms(tmp_path: Path) -> str:
    """A valid production platform registry (one real https ACTIVE issuer) so a non-offline
    Settings(env="production") can be constructed without tripping the fail-closed platform-trust
    guard (gap CFG-A/CFG-C) — this test exercises the reader-engine wiring, not the registry."""
    p = tmp_path / "platforms.json"
    p.write_text(
        json.dumps(
            {
                "platforms": {
                    "acme": {
                        "issuer": "https://acme.example.com",
                        "jwks_url": "https://acme.example.com/.well-known/jwks.json",
                        "domains": ["app.acme.example.com"],
                        "lifetime_minutes": 60,
                        "algs": ["RS256"],
                        "active": True,
                    }
                },
                "integrations": {},
            }
        )
    )
    return str(p)


@pytest.fixture(autouse=True)
def _clear_reader_engine_caches() -> Iterator[None]:
    # The reader engine/sessionmaker are lru_cached and read the *global* get_settings(); clear
    # both around each test so a monkeypatched settings object is actually observed (mirrors
    # backend/tests/schema/test_engine_reader_role.py) and no cross-test engine leaks in.
    engine_mod.get_reader_engine.cache_clear()
    engine_mod.get_reader_sessionmaker.cache_clear()
    yield
    engine_mod.get_reader_engine.cache_clear()
    engine_mod.get_reader_sessionmaker.cache_clear()


def test_cm_root_reads_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """panel cm-root · substep p0-s0_5-reg-code-map
    Step 1 — the wiring reads settings: create_app() with no explicit settings resolves them
    via get_settings() and stows exactly that object on app.state.settings."""
    resolved = Settings()
    calls: list[int] = []

    def _spy_get_settings() -> Settings:
        calls.append(1)
        return resolved

    monkeypatch.setattr(main, "get_settings", _spy_get_settings)

    app = main.create_app(start_scheduler=False)

    assert calls == [1]
    assert app.state.settings is resolved


def test_cm_root_reader_engine_fails_closed_without_reader_url_outside_local(
    monkeypatch: pytest.MonkeyPatch,
    prod_platforms: str,
) -> None:
    """panel cm-root · substep p0-s0_5-reg-code-map
    Step 2 — building the reader engine through the wiring fails closed: outside an offline env
    with DATABASE_READER_URL unset, build_answer_service raises ReaderRoleMisconfiguredError
    rather than silently reading as the RLS-bypassing writer role."""
    settings = Settings(
        env="production",
        database_reader_url="",
        database_url="postgresql+psycopg://w:w@localhost:1/writer_db",
        platforms_path=prod_platforms,
    )
    # get_reader_engine reads the global get_settings(), not the arg passed to build_answer_service.
    monkeypatch.setattr(engine_mod, "get_settings", lambda: settings)

    with pytest.raises(engine_mod.ReaderRoleMisconfiguredError):
        main.build_answer_service(settings)


def test_cm_root_builds_hybrid_retriever_with_embedder_reranker_and_scope_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """panel cm-root · substep p0-s0_5-reg-code-map
    Step 3 — the wiring builds HybridRetriever with the embedder, the reranker, and the
    knowledge-scope flag: build_answer_service passes build_embedding_provider(settings),
    build_reranker(settings), and settings.enable_knowledge_scope_filtering straight through."""
    settings = Settings(enable_knowledge_scope_filtering=True)
    embedder_sentinel = object()
    reranker_sentinel = object()
    recorded: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def _record_retriever(*args: Any, **kwargs: Any) -> object:
        recorded.append((args, kwargs))
        return object()  # AnswerService only stores the retriever; a stub is enough

    monkeypatch.setattr(main, "build_embedding_provider", lambda _s: embedder_sentinel)
    monkeypatch.setattr(main, "build_reranker", lambda _s: reranker_sentinel)
    monkeypatch.setattr(main, "HybridRetriever", _record_retriever)

    main.build_answer_service(settings)

    assert len(recorded) == 1
    args, kwargs = recorded[0]
    # main.py positional order: (session_factory, embedder, policy, reranker, ...)
    assert args[1] is embedder_sentinel
    assert args[3] is reranker_sentinel
    assert kwargs["enable_knowledge_scope_filtering"] is True
