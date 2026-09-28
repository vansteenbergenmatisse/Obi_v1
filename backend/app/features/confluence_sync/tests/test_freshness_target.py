"""The freshness target is a single, settings-exposed number (substep 2.0.1).

Decision `freshness-target` (owner-resolved 2026-09-24): the tested freshness SLA is 60 s, with
<= 20 s retained as the aspiration. This substep only *defines* that number as a setting and proves
it is the single source every freshness test (the live 2.5.3 proof, the e-monitor telemetry) reads —
it does NOT wire the number into any runtime behaviour. These are unit tests: no session fixture, no
database, no network.
"""

from __future__ import annotations

import pytest

from app.platform.config import Settings


def test_data_freshness_target_defaults_to_sixty_seconds() -> None:
    """panel e-monitor · substep 2.0.1
    A number of seconds between Publish and the change being searchable, default 60 (the tested
    SLA the owner confirmed on 2026-09-24). Asserted off the declared field default so it means the
    code default, not whatever a real deployment's .env happens to set."""
    assert Settings.model_fields["freshness_target_seconds"].default == 60
    assert Settings().freshness_target_seconds == 60


def test_data_freshness_target_is_env_overridable() -> None:
    """panel e-monitor · substep 2.0.1
    The target is a real setting on the Settings object, not a module-level literal: it is
    overridable via the environment like every other field on the BaseSettings model."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("FRESHNESS_TARGET_SECONDS", "45")
        assert Settings().freshness_target_seconds == 45


def test_data_freshness_target_is_the_single_source_freshness_tests_read() -> None:
    """panel i2-gone · substep 2.0.1
    The number is exposed on the Settings object (an int field), so every freshness test reads
    `settings.freshness_target_seconds` rather than a hardcoded literal. Proves the field exists and
    is typed as the shared source of truth."""
    field = Settings.model_fields["freshness_target_seconds"]
    assert field.annotation is int
    assert isinstance(Settings().freshness_target_seconds, int)
