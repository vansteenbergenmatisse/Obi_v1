"""The ``app.allowed_labels`` GUC + RESTRICTIVE ``chunk_labels_read`` policy (substep 9.1.2, D1).

ADR-0020 D1 puts the directed-connection routing filter on the RLS/GUC layer (not SQL text alone),
mirroring ``chunk_scope_read``. This stage lands the policy but the retrieval path that SETS the
GUC is a later substep (9.4.1 / Stage 6). So the policy here is deliberately a **no-op until the
GUC is set**: it opts out when ``app.allowed_labels`` is unset and on the explicit ``'*'`` sentinel,
and only overlaps when a real connection-label list is set. This is sound because labels are the
*routing/relevance* axis, not the access boundary — source isolation (ADR-0004
``chunk_source_read``, lock 1) and customer-scope isolation (ADR-0014 ``chunk_scope_read``, lock 2)
remain the fail-closed enforcement fence and are unchanged.

These tests read ``chunk`` directly as the non-owner ``rag_reader`` (RLS-subject) with no app
predicate, so they prove the DB policy's own behaviour. Mirrors
``test_customer_isolation_backstop.py``.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.platform.config import Settings
from schema.engine import get_reader_sessionmaker, get_sessionmaker

from ._helpers import index_page

pytestmark = pytest.mark.db

_PAGE = 1001  # space 100, unrestricted
_SCOPE = "obi-mews-test"
_BOX = "toast-to-pms"  # a directed-connection routing label (Stage 6 will set the GUC to these)
_OTHER_BOX = "mews-to-pos"


def _stamp(page_id: int, *, tags: list[str], labels: list[str]) -> None:
    with get_sessionmaker()() as s:
        s.execute(
            text("UPDATE chunk SET tags = :tags, labels = :labels WHERE page_id = :pid"),
            {"tags": tags, "labels": labels, "pid": page_id},
        )
        s.commit()


def _count(session, page_id: int) -> int:
    return session.execute(
        text("SELECT count(*) FROM chunk WHERE page_id = :p"), {"p": page_id}
    ).scalar_one()


def _set_gucs(session, *, scope: str, labels: str | None) -> None:
    """Set the reader's source + scope GUCs (always) and the labels GUC (only when given)."""
    session.execute(text("SET LOCAL app.allowed_sources = 'confluence:default'"))
    session.execute(
        text("SELECT set_config('app.allowed_knowledge_scopes', :v, true)"), {"v": scope}
    )
    if labels is not None:
        session.execute(text("SELECT set_config('app.allowed_labels', :v, true)"), {"v": labels})


def test_sec_labels_policy_is_noop_when_guc_unset(gateway, settings: Settings) -> None:
    """panel mi-labels · substep 9.1.2 (D1)
    With ``app.allowed_labels`` unset (today's retrieval path), the RESTRICTIVE labels policy is a
    no-op: a chunk visible under source + scope stays visible, so the existing isolation backstop is
    unchanged. Red today: the policy does not exist to assert a no-op posture on."""
    index_page(gateway, settings, _PAGE, 3)
    _stamp(_PAGE, tags=[_SCOPE], labels=[_BOX])

    with get_reader_sessionmaker()() as s:
        _set_gucs(s, scope=_SCOPE, labels=None)  # deliberately DO NOT set app.allowed_labels
        rows = _count(s, _PAGE)

    assert rows > 0, "unset app.allowed_labels hid rows -> the labels policy is not a no-op yet"


def test_sec_labels_policy_overlaps_when_guc_set(gateway, settings: Settings) -> None:
    """panel mi-labels · substep 9.1.2 (D1)
    When ``app.allowed_labels`` is set (what 9.4.1 will do), the policy keeps only chunks whose
    ``labels`` overlap it; a non-overlapping connection is denied even though source + scope match;
    the ``'*'`` sentinel opts out. Red today: no policy to overlap on."""
    index_page(gateway, settings, _PAGE, 3)
    _stamp(_PAGE, tags=[_SCOPE], labels=[_BOX])

    reader = get_reader_sessionmaker()
    with reader() as s:
        _set_gucs(s, scope=_SCOPE, labels=_BOX)
        overlapping = _count(s, _PAGE)
    with reader() as s:
        _set_gucs(s, scope=_SCOPE, labels=_OTHER_BOX)
        non_overlapping = _count(s, _PAGE)
    with reader() as s:
        _set_gucs(s, scope=_SCOPE, labels="*")
        wildcard = _count(s, _PAGE)

    assert overlapping > 0, "an overlapping connection label was wrongly filtered out"
    assert non_overlapping == 0, "a non-overlapping connection label leaked -> policy not enforcing"
    assert wildcard > 0, "the '*' sentinel did not opt out of the labels filter"
