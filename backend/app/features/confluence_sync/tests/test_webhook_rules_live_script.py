"""``scripts/webhook_rules_live.py`` — the safeguards of the live webhook-path runner.

panel i1-webhook · sync-rules live runner (roadmap substep 4.3)

The runner itself needs a real Confluence + the deployed webhook path, so it has no hermetic
happy-path test (same stance as ``verify_sync_rules.py``).
What IS hermetically provable are its refusals — the two gates that keep it from ever mutating
anything by accident: no ``--yes`` → exit 2 before any client is built; Confluence unconfigured
(the offline fixture env, exactly what the test settings provide) → exit 2 before any mutation.
"""

from __future__ import annotations

import pytest

import scripts.webhook_rules_live as webhook_rules_live
from app.platform.config import Settings


def test_webhook_rules_live_refuses_without_yes(capsys) -> None:
    """Without --yes the runner exits 2 and explains itself, touching nothing."""
    rc = webhook_rules_live.main(["--page-id", "1670873122"])
    err = capsys.readouterr().err

    assert rc == 2
    assert "REFUSING" in err
    assert "--yes" in err


def test_webhook_rules_live_refuses_an_unconfigured_confluence(capsys) -> None:
    """With Confluence unconfigured (the offline fixture env) the gate refuses with exit 2.

    Exercised on the gate function directly with an explicitly blank ``Settings`` — calling
    ``main()`` would read the ambient environment, and a safeguards test must never be able to
    reach a live system.
    """
    blank = Settings(confluence_base_url="", confluence_api_token="")

    with pytest.raises(SystemExit) as excinfo:
        webhook_rules_live._require_live_confluence(blank)
    err = capsys.readouterr().err

    assert excinfo.value.code == 2
    assert "REFUSING" in err
    assert "fixture" in err
