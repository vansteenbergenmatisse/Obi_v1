# 0008 — Ambiguity Clarification and Fallback

Status: Accepted
Date: 2026-08-11
Governs: apps/automation (rag_agent, evaluation), apps/web (chat feature) — extends ADR-0005

## Context

ADR-0005 fixed the answer pipeline as: rewrite → RLS-scoped retrieve → RRF → cross-encoder rerank
→ parent-context expansion → grounded generation with forced citations → refusal threshold → one
CRAG corrective retry. That pipeline handles "the corpus doesn't cover this" (refusal below
`refusal_min_rerank_score`) but has no concept of "the question itself is too vague to search well" —
a genuinely under-specified query (e.g. "What are the limits?" against a corpus with both expense
limits and approval-amount thresholds) runs the full grounded pipeline and comes out as either a
low-confidence guess or the identical refusal string used for "not in the corpus at all," with no
way for the user to supply the missing detail. `docs/future-ideas/IDEAS.md` #1 raised this gap; an
`ambiguity` eval dataset (`evaluation/datasets/ambiguity.json`) already encodes 3 cases expecting
clarifying behavior that the runtime cannot produce today.

Separately, the existing refusal path's "routing this to a human" (`_REFUSAL_TEXT`,
`rag_agent/application/answer_service.py`) is copy only — no hand-off actually happens — and all
three internal refusal causes (no candidates, weak score, no surviving citations) render identical
user-facing text, so the user can't tell "nothing like this exists" from "I need one more word from
you" from "the model's answer got fully stripped by citation enforcement."

This ADR extends ADR-0005 with a pre-retrieval clarification branch and a refusal-reason taxonomy,
without altering any decision ADR-0005 already made about the grounded path itself.

## Decision

1. **A new pre-retrieval short-circuit, structurally identical to the small-talk fix.** New
   `rag_agent/domain/clarification.py::decide_clarification(query, history) -> ClarificationDecision`
   (heuristic first pass; LLM fallback call only when the heuristic is inconclusive — never a
   substring/fuzzy match, so a real question that happens to be short still runs the full grounded
   pipeline). Wired into `AnswerService.answer` at the same insertion point as
   `is_small_talk` — before rewrite/retrieval/CRAG/refusal — and, like small-talk, writes no
   `query_trace` row. This is one more pre-pipeline branch, not a change to the grounded pipeline
   ADR-0005 already fixed.

2. **Feature-flagged, default off.** `enable_clarification_branch` (new setting,
   `app/platform/config/settings.py`), default `false`. It ships dark until tuned against
   `evaluation/datasets/ambiguity.json`, exactly as `rewrite_enabled` and other pipeline toggles are
   gated. The hermetic test fixture may force it on or off per test; production stays off until a
   design review of real trigger behavior.

3. **Contract change: extend `Answer`, do not add a new SSE event.** `Answer` gains
   `needs_clarification: bool = False`, `clarification_question: str | None = None`,
   `clarification_options: list[str] | None = None`. The existing SSE lifecycle
   (`start`/`token`/`citations`/`done`, ADR-0005 §10) is unchanged — a clarification reply streams
   its question text over the existing `token` events (same as a small-talk reply) with
   `citations: []`, and the `done` payload carries the three new fields. This mirrors how
   `refused`/`refusal_reason` were added to `Answer` rather than inventing a parallel event type, and
   keeps `packages/contracts`'s existing shape additive (new optional fields), not restructured.

4. **Refusal-reason taxonomy, three values, not a fourth "ambiguous."**
   `no_candidates | weak_score | no_citations` — set by the existing `decide_refusal` /
   citation-enforcement-degrades-to-refusal paths, now surfaced (not just logged) so `AnswerService`
   can select distinct copy per reason. Clarification is deliberately **not** part of this taxonomy:
   `needs_clarification=True` is a still-open conversation turn, not a refusal, and does not set
   `refused=True`.

   **Amendment (2026-09-12): the taxonomy is now four values — `off_topic` added.** The below-
   threshold `weak_score` refusal is split by a second, lower threshold
   (`settings.offtopic_max_rerank_score`, kept `< refusal_min_rerank_score`): a top rerank score
   at/below it is `off_topic` (a genuinely unrelated question), between it and the refusal bar stays
   `weak_score`. Justified by a live measurement showing a bimodal rerank distribution (unrelated
   probes ≈0.02, supported facts ≥0.076, an empty gap between), so the split is a real signal, not a
   guess — provisional, re-tuned on the Phase-5 gold set. `off_topic` still sets `refused=True` and
   never fabricates; it only changes the *copy and the hand-off* (decision 5). `no_candidates`
   (retrieval returned nothing) stays a hand-off, not a redirect: an empty in-scope result is a real
   coverage gap, not obviously off-topic. `refusalReason` now also rides the `/chat` SSE `done` event
   (was log-only) so the widget can branch on it.

5. **Differentiated refusal copy, still routes to "a human," still no real integration this
   phase.** Each of the reasons gets its own honest, user-facing string (copy drafted under
   `copywriting-rules`/`anti-ai-writing` at implementation time, not fixed by this ADR).

   **Amendment (2026-09-12): `off_topic` does NOT route to a human.** The three hand-off reasons
   (`no_candidates | weak_score | no_citations`) keep the decision-6 human-hand-off affordance and
   emit the `human_handoff` audit record; `off_topic` instead shows a softer "ask me about the
   documentation" redirect with **no** CTA, and emits a distinct `off_topic_redirect` audit record so
   PLAN 9.7 fallback-rate reporting can separate "sent to a human" from "steered back to the docs."

6. **Human hand-off is a stub, this phase, by explicit user decision.** On any `refused=True`
   answer, emit one structured log record (existing `structlog` convention — `trace_id`, `raw_query`,
   `refusal_reason`, `created_at`) and surface a "connect me to a human" CTA in the widget that
   displays static contact copy. No webhook, ticket, or email integration is built. **Salesforce is
   the noted eventual target** (per `docs/future-ideas/IDEAS.md` #1's update) — deferred until that
   integration is actually prioritized; do not invent a Salesforce credential or endpoint before then.

7. **Evaluation reuses the existing `ambiguity` `EvalKind` — no new literal added.** The closed
   5-way `EvalKind` (`retrieval | answer | ambiguity | latency | permission`,
   `evaluation/schemas.py`) already has an `ambiguity` kind; `ambiguity.json`'s existing cases are
   extended to assert `needs_clarification=True` (not just `expected_answer` text). A genuinely
   out-of-corpus case (no clarification, no match anywhere) is a `retrieval`/`answer`-kind case with
   an empty relevant-chunk set, not a new kind — the existing type stays closed.

8. **No MMR/diversity filtering, no new vector store, no agent-loop rewrite.** Explicit non-goals,
   confirmed with the user: diversity filtering doesn't address unanswerable/vague queries and would
   touch the already-shipped ADR-0005 retrieval pipeline for no benefit here; Postgres+pgvector+
   Cohere remains the stack (ADR-0001/0002); `AnswerService` stays a fixed pipeline, per ADR-0005
   decision 5 — this branch is one more short-circuit, not a planner.

9. **Execution sequencing: after Phase 7, and after Phase 4.8, by explicit user direction — not a
   technical dependency.** Phase 9 shares no files or risk with Phase 7 (vision-grounded image
   analysis) or Phase 4.8 (repo separation); the ordering is a deliberate choice to finish the
   already-in-flight phases first, not because this branch depends on either. This ADR and the
   design-doc section it accompanies may be written now (documentation only); no code under this ADR
   lands before Phase 7 and Phase 4.8 are both done.

## Reason

Reusing the small-talk short-circuit's shape keeps the new branch auditable the same way — a narrow,
flag-gated classifier ahead of the pipeline, not a change inside it — so ADR-0005's fixed-workflow
guarantees (bounded latency, stage-by-stage testability) hold unchanged for every query that isn't
flagged ambiguous. Extending `Answer` rather than adding an SSE event minimizes contract churn for
`packages/contracts` and the web client, which already know how to render `refused`/`citations`.
Keeping the refusal taxonomy at three values (not four) preserves the distinction that clarification
is a conversational turn, not a failure — conflating them would make analytics on "how often do we
actually fail" meaningless. A stub hand-off avoids inventing an integration (and its credentials)
before the business has decided where it should actually go.

## Alternatives considered

- **A new SSE event type for clarification.** Rejected: widens the `/chat` contract for no behavior
  the existing `token`/`done` shape can't already carry once `Answer` gains the three new fields.
- **Folding "ambiguous" into the existing refusal reasons as a fourth value.** Rejected: refusal
  implies the conversation ended in failure; clarification implies it's still open. Conflating them
  breaks fallback-rate/refusal-rate reporting (Phase 9.7).
- **A real Slack/email/Salesforce hand-off this phase.** Rejected per explicit user decision — no
  credential or integration target exists yet; building one now would invent scope. Logged as the
  eventual target in `docs/future-ideas/IDEAS.md` #1 instead.
- **A new `EvalKind` literal for "unanswerable."** Rejected: `ambiguity` already covers the
  clarification-trigger case and `retrieval`/`answer` already cover "no relevant chunk exists";
  widening the closed Literal type isn't justified by a case the existing kinds already express.

## Consequences

- `AnswerService.answer` gains a second pre-pipeline branch (clarification, alongside small-talk);
  both must be checked before rewrite/retrieval, so their relative ordering (e.g. "hi, what's the
  approval process?" — small talk or ambiguous?) needs an explicit tie-break decision at
  implementation time (9.2/9.3), not left to whichever branch happens to run first.
- `Answer` and the `/chat` `done` SSE payload grow three optional fields; `packages/contracts` and
  the web client's message-rendering logic need matching (additive) updates.
- Refusal-reason taxonomy becomes user-visible, not just logged — copy for all three reasons must be
  written and reviewed before `enable_clarification_branch` (or the reason-differentiation change,
  which can ship independently) goes live.
- The human hand-off stays a log line + static CTA until a future phase adds a real integration;
  fallback-rate metrics (9.7) measure how often this CTA fires, giving a real number to justify (or
  not) building the Salesforce integration later.
- No change to `retrieval/**`, the reranker, or any ADR-0005-governed pipeline stage.

## Paths governed

`apps/automation/app/features/rag_agent/domain/clarification.py` (new),
`apps/automation/app/features/rag_agent/application/answer_service.py`,
`apps/automation/app/features/rag_agent/domain/prompt.py`,
`apps/automation/app/features/rag_agent/infrastructure/llm_client.py`,
`apps/automation/app/features/evaluation/datasets/ambiguity.json`,
`apps/automation/app/features/evaluation/metrics/**`,
`apps/automation/app/platform/config/settings.py`,
`apps/web/src/features/chat/**`, `packages/contracts`,
`docs/future-ideas/IDEAS.md` (#1).
