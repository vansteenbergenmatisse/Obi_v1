"""AUTHRT-REGISTRY-RELOAD · panel cm-config — the platform-registry process cache's contract.

``Settings.platform_registry`` serves a parsed + validated ``PlatformRegistry`` from the keyed
process cache ``_PLATFORM_REGISTRY_CACHE`` (settings.py), keyed on the exact load inputs
``(path, offline, allow_empty, frozenset(recognized scopes))``. These tests pin the three
operationally-visible consequences of that design so a refactor cannot silently change them:

1. an on-disk edit to platforms.json is NOT picked up while the key is unchanged — a registry
   change requires a process restart;
2. the recognized-scope set IS part of the key (and ``knowledge_scope_set`` is an uncached
   per-access re-read), so a scopes-file change forces a revalidating reload that fails LOUDLY,
   naming the scope, when platforms.json maps a scope that vanished;
3. the same key always returns the same registry instance, including across ``model_copy``.

Every test runs against a fresh, empty cache (the ``_fresh_cache`` fixture swaps the module-level
dict) so nothing leaks into — or is masked by — the process-global cache other tests share.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.platform.config import Settings
from app.platform.config import settings as settings_module
from app.platform.config.knowledge_scopes import load_recognized_knowledge_scopes
from app.platform.config.platforms import load_platform_registry

_MEWS_ISS = "https://app.mews.com"


def _write_platforms(path: Path, *, mews_active: bool = True) -> Path:
    path.write_text(
        json.dumps(
            {
                "platforms": {
                    "mews": {
                        "issuer": _MEWS_ISS,
                        "jwks_url": f"{_MEWS_ISS}/j",
                        "domains": ["app.mews.com"],
                        "lifetime_minutes": 60,
                        "algs": ["RS256"],
                        "active": mews_active,
                    }
                },
                "integrations": {"mews": ["obi-mews-test"]},
            }
        )
    )
    return path


def _write_scopes(path: Path, names: list[str]) -> Path:
    """A temp scopes file from a plain name list — never edits the real committed file
    (same helper shape as test_knowledge_scopes.py)."""
    path.write_text(json.dumps({"scopes": [{"name": n, "description": ""} for n in names]}))
    return path


@pytest.fixture
def _fresh_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Swap the process-global registry cache for an empty per-test dict. The property resolves
    ``_PLATFORM_REGISTRY_CACHE`` through the settings module at call time, so this both isolates
    these tests from entries other tests created and keeps the temp-file entries created here out
    of the shared process cache."""
    monkeypatch.setattr(settings_module, "_PLATFORM_REGISTRY_CACHE", {})


def _settings(platforms_path: Path) -> Settings:
    """A Settings whose cache key is fully pinned by the test: env="test" (offline) and an explicit
    allow_empty_platforms=False, so neither the suite-level ALLOW_EMPTY_PLATFORMS env var nor a
    developer's .env can move the (path, offline, allow_empty, scopes) key between accesses."""
    return Settings(env="test", allow_empty_platforms=False, platforms_path=str(platforms_path))


def test_tags_platforms_file_edit_served_stale_until_cache_key_changes(
    tmp_path: Path, _fresh_cache: None
) -> None:
    """AUTHRT-REGISTRY-RELOAD · panel cm-config — platforms.json edits require a RESTART.

    The registry cache is keyed on (path, offline, allow_empty, scopes) — the file's CONTENT is
    not in the key. An operator who edits platforms.json on disk (here: deactivating the only
    platform) is therefore served the OLD registry on every subsequent access with identical key
    inputs: same object, and the deactivated platform still reads as active. This documents the
    operational contract: a platforms.json change only takes effect on process restart. The final
    direct re-load proves the on-disk edit is real (a fresh parse DOES see the deactivation), so
    the staleness asserted above is the cache's doing, not a failed file write."""
    p = _write_platforms(tmp_path / "platforms.json", mews_active=True)
    s = _settings(p)
    first = s.platform_registry
    assert first.platform_for(_MEWS_ISS) is not None  # active, as the file said at first load

    _write_platforms(p, mews_active=False)  # the operator's on-disk edit

    second = s.platform_registry  # identical key inputs -> cache hit
    assert second is first  # the OLD registry object is still served
    assert second.platform_for(_MEWS_ISS) is not None  # stale: still active despite the edit

    # Control: a direct re-load of the edited file sees the deactivation — the edit really landed
    # on disk, so the stale serve above is the cache contract, not a broken fixture.
    fresh = load_platform_registry(p, s.knowledge_scope_set, allow_empty=True, offline=True)
    assert fresh.platform_for(_MEWS_ISS) is None


def test_tags_scopes_file_change_revalidates_platforms(
    tmp_path: Path, _fresh_cache: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AUTHRT-REGISTRY-RELOAD · panel cm-config — a scopes-file change fails LOUDLY, never silently.

    ``knowledge_scope_set`` is an uncached per-access re-read, and the recognized-scope frozenset
    is part of the registry cache key. So when a scope that platforms.json maps is removed from
    knowledge_scopes.json, the next ``platform_registry`` access is a cache MISS that re-runs the
    full loader validation — and raises a ValueError NAMING the vanished scope, rather than
    serving the stale registry or quietly dropping the mapping. This is the mechanism behind the
    live-edit failure mode: the half-edited config pair stops the next access cold instead of
    answering under wrong scope rules. (The loader is pointed at a temp scopes file via the same
    settings-module monkeypatch test_settings.py already uses; the committed file is never
    touched.)"""
    scopes_path = _write_scopes(
        tmp_path / "knowledge_scopes.json",
        ["obi-general-test", "classified", "obi-mews-test"],
    )
    monkeypatch.setattr(
        settings_module,
        "load_recognized_knowledge_scopes",
        lambda: load_recognized_knowledge_scopes(scopes_path),
    )
    p = _write_platforms(tmp_path / "platforms.json")
    s = _settings(p)
    # loads fine while the scopes file still carries the scope platforms.json maps
    assert s.platform_registry.allowed_scopes_for("mews") == {
        "obi-mews-test",
        "obi-general-test",
    }

    # the live edit: the mapped scope vanishes from the scopes file (general + classified remain,
    # so the scopes file itself still validates — only the platforms mapping is now dangling)
    _write_scopes(scopes_path, ["obi-general-test", "classified"])

    with pytest.raises(ValueError, match="obi-mews-test") as exc:
        _ = s.platform_registry
    message = str(exc.value)
    assert "not in knowledge_scopes.json" in message  # the loud, named failure — never silent
    assert "mews" in message  # and it names the integration carrying the dangling scope


def test_tags_registry_cache_hit_same_inputs_returns_same_object(
    tmp_path: Path, _fresh_cache: None
) -> None:
    """AUTHRT-REGISTRY-RELOAD · panel cm-config — the cache contract itself.

    The same key inputs always return the SAME registry instance: on repeated property access, and
    across ``Settings.model_copy`` (the cache is keyed on resolved inputs precisely so a copy with
    an identical config reuses, while a copy with a different path recomputes — see the
    ``_PLATFORM_REGISTRY_CACHE`` comment in settings.py). A future refactor that silently drops the
    caching, or drops ``platforms_path`` from the key, trips one of these identity assertions."""
    p = _write_platforms(tmp_path / "platforms.json")
    s = _settings(p)
    first = s.platform_registry
    assert s.platform_registry is first  # repeated access on one instance: same object

    # a model_copy with the SAME key inputs (only a non-key field changes) reuses the instance
    copy_same_key = s.model_copy(update={"log_level": "DEBUG"})
    assert copy_same_key.platform_registry is first

    # a model_copy with a DIFFERENT key input (another path) recomputes — not the same object
    p2 = _write_platforms(tmp_path / "platforms2.json")
    copy_other_path = s.model_copy(update={"platforms_path": str(p2)})
    assert copy_other_path.platform_registry is not first
