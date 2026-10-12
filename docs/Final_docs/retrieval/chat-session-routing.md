# Chat-start and the directed-connection session

- **Workflow:** retrieval
- **Owning code:** `backend/app/features/rag_agent/application/chat_session.py` (the store + flow),
  `backend/app/features/rag_agent/domain/prompt.py` (`build_connection_block`),
  `knowledge-base/schema/models.py` (`ChatSession`), `knowledge-base/migrations/versions/0017_chat_session.py`
- **Design panel:** `mi-session` (one connection per chat) — feeds `mi-route` / `mi-hardfilter`
- **Status:** Implemented

## What it does

A chat over Obi is one directed connection: a `source_system → target_system` for one
`business_id`. Chat-start runs once, at the start of a chat: `start_chat_session` resolves both
systems in the product catalog, builds the four routing labels (`build_labels`) and a connection
block for the system prompt (`build_connection_block`), and stores them on a `chat_session` row.
The row is keyed on the verified edge identity — the sha256 of the issuer-namespaced token subject
plus `company_id` — never the caller-supplied conversation id. Every later question calls
`load_chat_session`, which reads that row and reuses the stored `labels` and `connection_block`
without touching the catalog again. A partner switch — a different source/target — refires
`start_chat_session`, which replaces the labels and block on the same row in place (D7). An
unresolved source or target stores `labels = [obi-general]`, leaves `source_slug`/`target_slug`
null, and writes an "unknown connection" block that never names a fabricated system.

The stored columns are `business_id`, `source_slug`, `target_slug`, `labels`, `connection_block`
and `updated_at`. The connection block names both systems, their roles, the direction and the
business id, and tells the model to answer for this connection only. This component owns the
resolution + storage; it decides nothing about access — the label hard-filter (9.4.1) and the
database locks 0–3 enforce what a chat may see.

## Why it does it

Resolving the connection once and reusing it keeps never-bend rule 8 intact: a question costs at
most the thin-results refetch and the weak-score fallback, and chat-start's catalog lookup is not
one of them. Keying the row on the verified `token_subject` + `company_id` (mirroring
`router._idempotency_cache_key` and `query_trace.subject_hash`) is what binds a session to its
subject — a different subject resolves to a different composite primary key and can neither read
nor mutate another's session, so the request body never decides the connection (rules 2–3). The
subject is hashed before storage so no raw subject or secret lands in a row (rule 10). The
directed model, the four boxes, the once-per-chat resolution and the partner-switch refire are
the locked Option A parameters D4/D7 and chat-start steps 3/5 of ADR-0020. The `chat_session`
table has RLS enabled with no policy (migration 0017), so the Supabase public REST roles are
default-denied while the writer (owner) path bypasses it (ADR-0013) — the Phase 13.1 rationale
that fences every non-chunk table (rule 1).

## How we know it works

- `test_rt1_second_question_does_not_call_catalog` (database, panel `mi-session`): a spy catalog
  proves chat-start resolves once and a later `load_chat_session` makes zero catalog calls, and
  that the stored labels are the four ordered boxes.
- `test_rt1_session_is_bound_to_its_subject` (database, panel `mi-session`): a second subject
  cannot read the first subject's session (`load` returns `None`), and its own `start` writes a
  separate row leaving the first subject's `business_id`/`labels` untouched.
- `test_rt1_partner_switch_refires_and_replaces` (database, panel `mi-session`): a different
  source/target replaces the labels and connection block and leaves exactly one row for the
  subject (replaced in place, never appended).
- `test_rt1_connection_block_names_both_systems_and_direction` /
  `test_rt1_connection_block_unknown_system_says_so` (unit, panel `mi-session`): the rendered
  block for a known connection names both systems, their roles, the direction and the business id;
  the unknown-connection block never fabricates a system or a direction.
- Migration 0017 round-trips under the knowledge-base migration suite (the `0007`/`0009`
  downgrade/upgrade round-trip tests pass once `schema.enable/disable_non_chunk_rls` guard on
  table existence, so the chain stays valid for a table added after 0009).

Wired into `POST /chat` (substep 9.4.1): `AnswerService._resolve_directed_routing` loads this
subject's session on every question and, on the first question of a chat or a partner switch
(a different source/target than the stored row), calls `start_chat_session` — the one catalog
lookup — otherwise reuses the stored row with no catalog call (never-bend rule 8). The stored
`labels` become the retrieval hard filter's `session_labels` (fed to `retrieve_with_context` and
the CRAG retry) and the `connection_block` is threaded into the answer prompt
(`AnthropicAnswerGenerator.generate(..., connection_block=...)`). A legacy/slot/tokenless chat is
not directed, so routing resolves to `(None, None)` — the filter is a no-op and the prompt carries
no connection block. The gate's directed path (`source_system`/`target_system`/`business_id`)
landed in 9.3.1; this substep connected that verified identity to the session store and the filter.

- `test_rt1_directed_chat_feeds_session_labels_to_filter_and_block_to_prompt` (unit,
  `rag_agent/tests/test_answer_service.py`, panels `mi-session`/`mi-hardfilter`): a directed
  Toast→Mews chat threads its four routing labels into the retriever and the connection block into
  the generator; chat-start resolves the catalog once and the second question reuses the stored
  session (no further lookup).
- `test_rt1_legacy_chat_routes_no_session_labels_or_connection_block` (unit, same file): a
  general/tokenless chat threads `None` for both and never starts a session row.
