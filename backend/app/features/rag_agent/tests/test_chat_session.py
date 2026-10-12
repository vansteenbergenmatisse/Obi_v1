"""Database tests for chat-start / the session store (panel mi-session, substep 9.2.1).

Chat-start resolves a directed connection once and stores it on a ``chat_session`` row keyed on the
verified ``token_subject`` + ``company_id`` (never the caller conversation id — mirrors
``router._idempotency_cache_key``). Later questions reuse the stored row without a catalog lookup.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.features.rag_agent.application.auth_context import AuthContext
from app.features.rag_agent.application.chat_session import (
    load_chat_session,
    start_chat_session,
)
from app.platform.config.product_catalog import Product, ProductCatalog, load_product_catalog
from schema.models import ChatSession

pytestmark = pytest.mark.db


class _SpyCatalog:
    """Wraps the real catalog and counts the routing lookups chat-start performs, so a test can
    prove the per-question load path never touches the catalog again (never-bend rule 8)."""

    def __init__(self, inner: ProductCatalog) -> None:
        self._inner = inner
        self.calls = 0

    def resolve_system(self, name: str) -> Product | None:
        self.calls += 1
        return self._inner.resolve_system(name)

    def build_labels(self, source: str, target: str) -> list[str]:
        self.calls += 1
        return self._inner.build_labels(source, target)


def _auth(subject: str, company_id: str = "c1") -> AuthContext:
    return AuthContext(
        company_id=company_id,
        company_name=None,
        integration=None,
        allowed_scopes=("obi-general-test",),
        allowed_sources=("confluence:default",),
        principal=None,
        token_subject=subject,
    )


def test_rt1_second_question_does_not_call_catalog(session: Session) -> None:
    """panel mi-session · substep 9.2.1
    Chat-start resolves via the catalog once; a later question loads the stored row without any
    catalog lookup."""
    spy = _SpyCatalog(load_product_catalog())
    auth = _auth("iss\x00u1")
    start_chat_session(
        session, auth, source_system="Toast", target_system="Mews", business_id="B-1", catalog=spy
    )
    session.commit()
    assert spy.calls > 0
    before = spy.calls

    loaded = load_chat_session(session, auth)
    assert loaded is not None
    assert loaded.labels == ["obi-general", "toast-general", "mews-general", "toast-to-pms"]
    assert spy.calls == before  # the second question made no catalog call


def test_rt1_session_is_bound_to_its_subject(session: Session) -> None:
    """panel mi-session · substep 9.2.1
    A session row is bound to its verified subject: another subject can neither read nor mutate
    it."""
    catalog = load_product_catalog()
    auth_a = _auth("iss\x00alice")
    auth_b = _auth("iss\x00bob")
    start_chat_session(
        session,
        auth_a,
        source_system="Toast",
        target_system="Mews",
        business_id="B-A",
        catalog=catalog,
    )
    session.commit()

    # another subject cannot read Alice's session
    assert load_chat_session(session, auth_b) is None

    # another subject's start writes only its own row; Alice's row is untouched
    start_chat_session(
        session,
        auth_b,
        source_system="Mews",
        target_system="Toast",
        business_id="B-B",
        catalog=catalog,
    )
    session.commit()

    alice = load_chat_session(session, auth_a)
    assert alice is not None
    assert alice.business_id == "B-A"
    assert alice.labels == ["obi-general", "toast-general", "mews-general", "toast-to-pms"]

    bob = load_chat_session(session, auth_b)
    assert bob is not None
    assert bob.business_id == "B-B"
    assert bob.labels == ["obi-general", "mews-general", "toast-general", "mews-to-pos"]


def test_rt1_partner_switch_refires_and_replaces(session: Session) -> None:
    """panel mi-session · substep 9.2.1
    A different source/target refires chat-start and replaces the block and labels (D7)."""
    catalog = load_product_catalog()
    auth = _auth("iss\x00u1")
    first = start_chat_session(
        session,
        auth,
        source_system="Toast",
        target_system="Mews",
        business_id="B-1",
        catalog=catalog,
    )
    session.commit()
    first_labels = list(first.labels)
    first_block = first.connection_block

    second = start_chat_session(
        session,
        auth,
        source_system="Mews",
        target_system="Toast",
        business_id="B-1",
        catalog=catalog,
    )
    session.commit()
    assert second.labels == ["obi-general", "mews-general", "toast-general", "mews-to-pos"]
    assert second.labels != first_labels
    assert second.connection_block != first_block

    # exactly one row for this subject — the switch replaced in place, never appended
    rows = session.scalars(select(ChatSession)).all()
    assert len(rows) == 1
