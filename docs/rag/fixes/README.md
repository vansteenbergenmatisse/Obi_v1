# Fixes — cross-phase audit index

Six independent agents audited Phases 0, 1, 2, 3, 3.5 (all sub-steps), and 4 on 2026-08-10, each
re-running tests/boundaries/ruff/pyright live and reading code directly rather than trusting
`PLAN.md`'s self-reported ledger. Phase 5 was deliberately excluded (not yet done). Full detail,
file:line citations, and "confirmed correct" sections are in the per-phase files; this is the
cross-phase triage index, ranked by severity.

| # | Severity | Phase | Finding | File |
|---|---|---|---|---|
| 1 | **CRITICAL** | 1 | Confluence **group** restrictions silently dropped — a page restricted only by group syncs as unrestricted | [phase-1.md](./phase-1.md#security) |
| 2 | **HIGH** | 4 | `Idempotency-Key` cache not bound to `principal`/`history` — a replayed key can leak another caller's cached answer + citations | [phase-4.md](./phase-4.md#security) |
| 3 | **MEDIUM-HIGH** | 4 | Rate limiter keys on the untrusted, caller-supplied `principal` field — trivially bypassed by rotating it | [phase-4.md](./phase-4.md#security) |
| 4 | **MEDIUM-HIGH** | 2 | `rollback_to` doesn't restore `PageSource`'s cached hashes — a rollback can leave the corpus silently pinned to a stale version on the next sync | [phase-2.md](./phase-2.md#plan--design-deviations-docs-vs-code-disagree-or-an-acceptance-criterion-isnt-actually-met) |
| 5 | MEDIUM | 3, 0 | `permission.py`'s `allowed()` overloads one untyped `scope` string for two trust levels (space-wide vs. principal) — the root cause of the 5.3 bypass, still unguarded at the domain layer | [phase-3.md](./phase-3.md#security) |
| 6 | MEDIUM | 4 | Rate limiter has no bucket eviction → unbounded memory growth, compounds #3 | [phase-4.md](./phase-4.md#security) |
| 7 | MEDIUM | 4 | Idempotency cache has no `max_entries` bound (unlike its Phase-5 sibling) | [phase-4.md](./phase-4.md#security) |
| 8 | MEDIUM | 3.5 | Migration-built vs. `create_all`-built schemas silently diverge (duplicate `CHECK` constraint, naming-convention bug) — contradicts the docs' "byte-for-byte identical" claim | [phase-3.5.md](./phase-3.5.md#plan--design-deviations-docs-vs-code-disagree-or-an-acceptance-criterion-isnt-actually-met) |
| 9 | MEDIUM | 1 | Confluence client: no circuit breaker; retry predicate excludes 5xx, contradicting `how_this_works.md` | [phase-1.md](./phase-1.md#security) |
| 10 | MEDIUM | 0 | Pyright baseline crept 31→34 errors across Phase 4, reported "unchanged" session-over-session but never reconciled against ADR-0003's actual fixed number — a governance-gate miss, not just a doc issue | [phase-0.md](./phase-0.md#plan--design-deviations-docs-vs-code-disagree-or-an-adr-decision-wasnt-actually-followed) |
| 11 | LOW | 3.5 | RLS is a no-op in the actual dev environment (`DATABASE_READER_URL` unset → silent fallback to the bypassing superuser) — proven correct only inside the test harness | [phase-3.5.md](./phase-3.5.md#security) |
| 12 | LOW | 1 | Event dedup only keys on `payload_hash`; a same-`delivery_id`/different-hash redelivery raises an uncaught 500 instead of deduping | [phase-1.md](./phase-1.md#security) |
| 13 | LOW | 4 | `Answer.refusal_reason` is computed and tested but never reaches any log, DB column, or API contract | [phase-4.md](./phase-4.md#security) |
| 14 | INFO | 1 | Confluence client's own logger is assigned but never called — no audit logging on that outbound surface | [phase-1.md](./phase-1.md#security) |

## Dead code (all phases)

- **`ingestion/domain/attachment_extraction.py`** — a fully-built PDF/DOCX/XLSX/CSV/HTML extractor with zero call sites; attachment *content* is not searchable despite the code existing. [phase-2.md](./phase-2.md#dead-code--unused)
- `JobStatus.leased` / `JobStatus.cancelled` enum values — declared, never assigned/consumed anywhere. [phase-1.md](./phase-1.md#dead-code--unused)
- `confluence_client.py`'s `log` — assigned, never called. [phase-1.md](./phase-1.md#dead-code--unused)
- `AnswerProvider`/`QueryRewriter`/`AnswerGenerator`'s `@runtime_checkable` — decorator present, zero `isinstance` call sites anywhere. [phase-4.md](./phase-4.md#dead-code--unused)
- `evaluation/metrics/latency_metrics.py` — fully tested, not wired into any runnable path yet (its intended Phase-5 landing spot). [phase-3.md](./phase-3.md#dead-code--unused)
- Stale docstring: `QueryTrace.rerank_scores` still says "reserved for Phase 4" — it's been populated since 4.2. [phase-3.5.md](./phase-3.5.md#dead-code--unused)

## Documentation drift (all phases)

- **`docs/rag/how_this_works.md` is badly stale** — still describes the pre-3.5 system in §§1-9 (only §§10/12 were updated), wrongly claims principal ACL is still fixture-only, undercounts the table list (9 vs. actual 10, missing `page_restriction`), and has a dead in-doc TOC anchor. [phase-0.md](./phase-0.md#plan--design-deviations-docs-vs-code-disagree-or-an-adr-decision-wasnt-actually-followed)
- `DESIGN.md` §1's "Confirmed gaps" paragraph contradicts its own banner (lists reranker/chat/tracing as absent; they've shipped since Phase 3.5/4). [phase-0.md](./phase-0.md#plan--design-deviations-docs-vs-code-disagree-or-an-adr-decision-wasnt-actually-followed)
- `evaluation/README.md` names a `"security"` eval kind that doesn't exist in `EvalKind`; `FEATURES.md`'s evaluation export list is missing the 3.5.5 rerank-lift exports. [phase-3.md](./phase-3.md#plan--design-deviations-docs-vs-code-disagree-or-an-acceptance-criterion-isnt-actually-met)
- Root `CLAUDE.md`'s stated ruff/pyright baseline (2/25, 31/1) is stale — actual is 2/17/34. [phase-2.md](./phase-2.md)

## What's confirmed genuinely correct (so silence elsewhere isn't assumed)

Independently re-verified, by direct code inspection (not docstrings), across multiple agents:
RLS is `FORCE`d with a bound-parameter `set_config` (no injection surface); the reader role has no
`BYPASSRLS`/superuser; the permission-filter-before-rerank ordering holds (checked independently by
three different agents — Phase 0, 3, and 3.5 — all landing on the same line numbers); RRF fusion is
textbook-correct; citation enforcement can't be bypassed by construction; the refusal/CRAG call
order matches ADR-0005 exactly; PII redaction runs on the fully assembled prompt at both LLM call
sites; the web chat proxy never leaks the backend secret or base URL to the browser; and the SSE
stream is a true byte passthrough. See each phase file's own "Confirmed correct" section.

## Per-phase reports

- [phase-0.md](./phase-0.md) — Design docs & ADRs
- [phase-1.md](./phase-1.md) — Confluence sync
- [phase-2.md](./phase-2.md) — Ingestion
- [phase-3.md](./phase-3.md) — Retrieval core
- [phase-3.5.md](./phase-3.5.md) — Accuracy + tagging spine (3.5.1–3.5.6)
- [phase-4.md](./phase-4.md) — Answer runtime & chat

Phase 5 (5.1–5.3 shipped, 5.4+ not yet built) was excluded from this audit round by design.
