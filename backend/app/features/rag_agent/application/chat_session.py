"""Chat-start + the directed-connection session store (Option A Stage 4, substep 9.2.1).

Panel mi-session (ADR-directed-source-target-routing-labels chat-start step 3/5, D7). A chat is one
directed ``source → target``
connection. ``start_chat_session`` runs ONCE at chat-start: it resolves both systems in the product
catalog, builds the four routing labels and the connection block, and upserts a ``chat_session`` row
keyed on the VERIFIED edge identity (``token_subject`` + ``company_id``, mirroring
``router._idempotency_cache_key`` — never the caller-supplied conversation id). Every later question
calls ``load_chat_session``, which reads the stored row and makes NO catalog lookup (never-bend rule
8: at most two extra reads per question, and chat-start is not one of them). A partner switch — a
different source/target — refires ``start_chat_session`` and replaces the labels + block in place
(D7); the composite key guarantees it only ever touches this subject's own row.

The row's binding to a subject is structural: the primary key is derived from the verified subject
+ company, so a different subject resolves to a different key and can neither read nor mutate
another's session. The subject is hashed (``sha256_text``) exactly as ``query_trace.subject_hash``
is, so the raw subject never lands in a row (rule 10).

This module performs catalog resolution + prompt assembly only; it never decides access — the label
hard-filter (9.4.1) and the database (Locks 0-3) enforce what a chat may see (never-bend rule 3)."""

from __future__ import annotations

import datetime as dt
from typing import Protocol

from sqlalchemy.orm import Session

from app.features.rag_agent.application.auth_context import AuthContext
from app.features.rag_agent.domain.prompt import build_connection_block
from app.platform.config.product_catalog import Product
from app.shared.hashing import sha256_text
from schema.models import ChatSession


class ChatSessionError(ValueError):
    """A chat session cannot be keyed because the verified identity is incomplete — no
    ``token_subject`` or no ``company_id``. A directed-connection chat always rides a verified token
    carrying both (the gate requires ``company_id`` when a connection is asserted); the tokenless
    path (not narrowed to a connection) never starts a session."""


class SystemResolver(Protocol):
    """The slice of ``ProductCatalog`` chat-start needs — resolving an endpoint and building the
    routing labels. A Protocol so a test can supply a counting spy that proves the per-question load
    path performs no catalog lookup, without subclassing the frozen catalog dataclass."""

    def resolve_system(self, name: str) -> Product | None: ...

    def build_labels(self, source: str, target: str) -> list[str]: ...


def _session_key(auth: AuthContext) -> tuple[str, str]:
    """The composite session key: ``(sha256(token_subject), company_id)``. Both must be present —
    the verified edge identity is the only thing that binds a session to a subject."""
    if not auth.token_subject:
        raise ChatSessionError("a chat session requires a verified token subject")
    if not auth.company_id:
        raise ChatSessionError("a chat session requires a verified company_id")
    return sha256_text(auth.token_subject).hex(), auth.company_id


def load_chat_session(session: Session, auth: AuthContext) -> ChatSession | None:
    """Load this subject's stored session (the per-question path). Reads the row by the composite
    key and makes NO catalog lookup — the stored ``labels``/``connection_block`` are reused as-is.
    A different subject resolves to a different key, so it can never read another's session; a
    verified identity with no stored session yet returns ``None``."""
    subject_hash, company_id = _session_key(auth)
    return session.get(ChatSession, (subject_hash, company_id))


def start_chat_session(
    session: Session,
    auth: AuthContext,
    *,
    source_system: str,
    target_system: str,
    business_id: str,
    catalog: SystemResolver,
) -> ChatSession:
    """Chat-start (runs once per chat): resolve the directed connection, build the labels + block,
    and upsert this subject's session row.

    Resolves ``source``/``target`` in the catalog (the ONE catalog lookup per chat), builds the four
    routing labels and the connection block, then writes them under the composite
    ``(subject_hash, company_id)`` key — creating the row on first start, or replacing the labels +
    block in place on a partner switch (D7). It only ever touches this subject's own row, so a
    different subject's start writes a separate row and leaves this one untouched. An unresolved
    source/target yields ``labels = [obi-general]`` and an "unknown" connection block (step 5) with
    ``source_slug``/``target_slug`` left ``None`` — never a fabricated system."""
    subject_hash, company_id = _session_key(auth)
    src = catalog.resolve_system(source_system)
    tgt = catalog.resolve_system(target_system)
    labels = catalog.build_labels(source_system, target_system)
    connection_block = build_connection_block(src, tgt, business_id)
    now = dt.datetime.now(dt.UTC)

    row = session.get(ChatSession, (subject_hash, company_id))
    if row is None:
        row = ChatSession(
            subject_hash=subject_hash,
            company_id=company_id,
            business_id=business_id,
            source_slug=src.id if src is not None else None,
            target_slug=tgt.id if tgt is not None else None,
            labels=labels,
            connection_block=connection_block,
            updated_at=now,
        )
        session.add(row)
    else:
        row.business_id = business_id
        row.source_slug = src.id if src is not None else None
        row.target_slug = tgt.id if tgt is not None else None
        row.labels = labels
        row.connection_block = connection_block
        row.updated_at = now
    session.flush()
    return row
