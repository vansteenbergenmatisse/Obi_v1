# Phase 9 security review — the directed-connection surface (substep 9.6.1)

> On-file security review for action-plan substep `9.6.1`, covering every token/endpoint change the
> Option A directed-connection routing introduced across substeps **9.3.1** (directed token form +
> gate + widget) and **9.4.1** (`/chat` session wiring + the `labels && session_labels` hard
> filter). Run with the `securing-http-and-llm-endpoints` skill. The per-substep checklists are in
> the `9.3.1` and `9.4.1` ledger entries; this note is the consolidated Phase-9 record.

## Surfaces in scope

Phase 9 added **no new HTTP route and no new LLM call**. It changed the behaviour of the one
existing authenticated surface, `POST /chat` (and its verifier), so the review re-classifies that
surface and confirms every control still holds under the directed form.

| Surface | Tier | Phase-9 change |
|---|---|---|
| `POST /chat` (answer path) | **LLM-CALL** (+ reads customer-scoped corpus) | Accepts the directed `source_system`+`target_system`+`business_id` token; resolves the connection at the gate; loads/creates the chat session once; hard-filters retrieval on the session's four labels; feeds the connection block to the answer prompt. |
| `TokenVerifier.verify` (feeds the gate) | — (auth input) | Parses the directed form into `VerifiedClaims` (`_parse_directed`); a malformed directed token is a bare `TokenError` (401). |

The directed form routes; the legacy `integration` and structured `context.slots` forms stay
accepted for back-compat but no longer drive routing.

## security_baseline

```yaml
security_baseline:
  applies: true
  surfaces:
    - id: POST /chat (directed-connection form, substeps 9.3.1 + 9.4.1)
      tier: LLM-CALL
      controls:
        C1_auth:
          status: covered
          mechanism: >
            Host API key gates the endpoint FIRST, then the user note is verified
            (TokenVerifier + build_auth_context). The directed connection is read ONLY from the
            verified token: source/target/business_id come from signed claims, never the request
            body (ChatRequestBody has extra="forbid", so a source_system/target_system body key is
            a 422; test_sec_body_can_never_carry_the_connection). business_id becomes company_id —
            the company-isolation axis, never a scope axis by itself (never-bend rules 2-3).
        C2_rate_limit:
          status: covered
          mechanism: "Unchanged — per-client-IP sliding window (chat_rate_limit_per_minute); the directed form adds no new key or bypass."
        C3_input:
          status: covered
          mechanism: >
            Two layers. Structural: _parse_directed requires all three of source_system/
            target_system/business_id to be non-empty strings or it is a bare TokenError (401) —
            no partner-system-without-counterpart, no missing/empty business_id. Semantic: the gate
            resolves source AND target through the catalog's lenient resolver; an unknown system is
            UnknownIntegrationError = 400 BEFORE any search touches the database (§D.11 fail-closed).
            Vend rights bind both endpoints (IntegrationNotAllowedError = 401) — an issuer may assert
            only systems its allowed_integrations resolve to.
        C4_timeout:
          status: covered
          mechanism: "Unchanged — embedder/reranker/answer carry answer_timeout_seconds + max_retries + breaker (PLAN 4.4). The session load is one keyed SELECT; no new fan-out."
        C5_output_rate:
          status: covered
          mechanism: "Unchanged — streaming is capped; the connection block is a fixed, short, catalog-derived system block (uncached), not user-influenced free text."
        C6_redaction:
          status: covered
          mechanism: >
            The session labels and the connection block are PUBLIC catalog vocabulary
            (obi-general / {slug}-general / {slug}-to-{kind} + product display names) — nothing
            customer-secret enters the prompt via routing. business_id is carried as an opaque id,
            never traced raw; the token subject is sha256-hashed before it keys the chat_session row
            (never-bend rule 10). The raw user token lives in widget memory only (no web storage,
            cookie, URL, or log — iframe-bridge sec test).
        C7_idempotency:
          status: covered
          mechanism: "Unchanged — optional Idempotency-Key header with a TTL dedup window; the cache key already binds the verified auth context, so two connections never share a replay."
        C8_concurrency:
          status: opted_out
          justification: >
            The answer path is read-only over the corpus. The one write is the chat_session upsert,
            keyed on (sha256(subject), company_id); chat-start runs once per chat and a partner
            switch replaces the row in place — a benign last-writer-wins on a single owner-written
            row, no shared-resource contention to lock.
        C9_audit:
          status: covered
          mechanism: "Unchanged — the trace row records the request; it carries the English markers/citations, no secret, no raw subject or token."
        C10_abuse:
          status: covered
          mechanism: "Unchanged — the LLM spend cap / kill switch is per the existing /chat baseline; routing adds no new paid call (the catalog is in-memory, resolved once per chat)."
```

## Never-bend rules touched (all upheld)

- **Rules 2-3 (the body never decides access; one authorization context per request).** The
  connection is a verified claim; the body cannot carry it (`extra="forbid"`). Every corpus read in
  the request — hybrid search, rerank-text fetch — runs under the SAME `app.allowed_labels` GUC set
  from the session, alongside the source and scope GUCs. Parent expansion is label-exempt because
  the matched child it expands is already authorized (it passed the filtered search), not because it
  reads under looser rules.
- **Rule 8 (at most two extra reads).** The session load is a keyed lookup, resolved once per chat
  (`load_chat_session` makes no catalog call on later turns); the directed gate adds zero corpus
  reads. The thin-results refetch + weak-score fallback remain the only two extras — unchanged.
- **Rule 10 (no secret in SQL / log / trace / URL / storage).** Labels ride as **bound parameters**
  (`labels && :session_labels`), never interpolated; a label value carrying `,` or `*` is rejected
  before the join (`test_sec_malicious_label_value_never_reaches_sql_text`,
  `test_sec_apply_allowed_labels_uses_bound_param_not_interpolated`). The subject is hashed; the
  token is memory-only in the widget.
- **Rule 1 (row security never disabled).** The RESTRICTIVE `chunk_labels_read` policy (landed
  inert in 9.1.2) becomes live here and **ANDs** with the source (lock 1) and customer-scope
  (lock 2) policies. Labels are fail-OPEN on an unset/empty GUC **by design** — they are the
  relevance/routing axis, not the access fence; source and customer-scope isolation stay
  **fail-closed and unchanged**. No policy was weakened, disabled, or forced; no 0009/0014 downgrade
  was run.

## Verdict

**PASS.** The directed-connection surface tightens what a chat can retrieve (a connection filter on
top of membership + access) and never widens it. Every LLM-CALL-tier control is covered; the single
opt-out (C8) is justified. No critical or high finding.
