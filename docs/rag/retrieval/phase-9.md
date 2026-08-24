# Phase 9 — Unanswerable/vague-query fallback

**Status:** ✅ done, all 9 sub-steps closed (`docs/rag/PLAN.md` lines 3584–3993, 2026-08-11/13 —
deliberately the **last** phase in the plan). Governed by
`docs/adr/0008-Ambiguity-Clarification-Fallback.md` and `docs/rag/DESIGN.md` §11.

## What happened

A genuinely vague/under-specified query now gets a clarifying question with concrete options instead
of silently running the full grounded pipeline into one generic refusal string; refusal reasons became
a distinguishable, closed taxonomy; the "routing this to a human" copy became a real (if minimal)
logged event; and fallback quality became measurable.

**ADR-0008's locked contract shape:**

1. **A new pre-retrieval short-circuit**, structurally identical to the pre-existing small-talk fix —
   `domain/clarification.py::decide_clarification`, checked right after the small-talk check, before
   rewrite/retrieval.
2. **Feature-flagged, default off** (`enable_clarification_branch`).
3. **Extends `Answer`, no new SSE event** — `needs_clarification` / `clarification_question` /
   `clarification_options`, additive on the existing `done` payload.
4. **Refusal-reason taxonomy: three values, not four.** `no_candidates | weak_score | no_citations` —
   "ambiguous" is deliberately not a fourth refusal reason, since `needs_clarification=True` is an
   **open turn**, not a refusal (`refused` stays `False` on that path).
5. **Differentiated refusal copy** per reason — still routes to "a human," still a stub this phase.
6. **Human hand-off is a stub, by explicit user decision** — a structured log line + a static widget
   CTA, no real integration. Salesforce is the noted eventual target.
7. **Evaluation reuses the existing `ambiguity` `EvalKind`** — no new literal.
8. **No MMR/diversity filtering, no new vector store, no agent-loop rewrite** — explicit non-goals.
9. Sequenced dead last, after Phase 7 — no phase in this plan follows Phase 9.

## Sub-steps

- **9.1** — Design doc + ADR-0008. No code.
- **9.2** — `domain/clarification.py::decide_clarification` + `AnthropicAmbiguityClassifier`
  (`llm_client.py`, cheap `routing_model` tier). Heuristic-first: a query ≥12 words is confidently
  self-specifying and skips the LLM call; every shorter query falls through to the classifier
  (never guessed at). Wired right after small-talk — this **is** the tie-break ADR-0008 flagged as
  open ("hi, what's the approval process?" still reaches this branch normally, since `is_small_talk`
  requires the *whole* message to match). Behind the flag, computed and logged
  (`clarification_decision`) but never changes `Answer` yet — the bypass itself is 9.3.
- **9.3** — Clarification response generation + wiring. On an ambiguous verdict,
  `AnswerService.answer` bypasses rewrite/retrieval/CRAG/refusal entirely (same shape as small-talk:
  no `query_trace` row, `refused` stays `False`) and calls
  `AnthropicAnswerGenerator.generate_clarification`, which sends `CLARIFICATION_SYSTEM_PROMPT` asking
  for a fixed `Question: ... / Options: / - ...` shape;
  `domain/clarification.py::parse_clarification_reply` parses it deterministically, returning `None`
  (→ static fallback) on anything unparseable. **Disclosed gap**, same reasoning as small-talk's own:
  an ambiguous query with an attached image gets the clarifying question and the image is silently
  dropped (this bypass returns before Phase 7's image analysis runs).
- **9.4** — Differentiated refusal messaging. `RefusalReason` becomes a closed `Literal`;
  `decide_refusal` returns the category directly instead of a free-text diagnostic with an
  interpolated score (the old string couldn't be a groupby key for 9.7's fallback-rate reporting).
  `answer_service.py`'s `_REFUSAL_COPY: dict[RefusalReason, str]` replaces one identical string with
  three distinct, honest messages.
- **9.5** — Obi widget fallback UX (`apps/web`, out of this folder's scope — quick-reply chips, a
  distinct "clarifying" status, expanded empty-state suggestions). See
  [`../OBI-WIDGET-DESIGN.md`](../OBI-WIDGET-DESIGN.md).
- **9.6** — Human hand-off stub. `answer_service.py`'s two refusal branches each emit one
  `log.info("human_handoff", trace_id=..., raw_query=..., refusal_reason=...)` call —
  `raw_query` is deliberately the user's verbatim text (not `rewritten`), a disclosed exception to
  `router.py`'s own "never log raw query" rule, justified because `query_trace.raw_query` already
  persists the same text keyed by the same `trace_id` (this is a second place it's *read* from, not a
  new place it's *written*). Frontend: a `mailto:` CTA (`apps/web`).
- **9.7** — Fallback-quality evaluation. `evaluation/metrics/fallback_metrics.py` — `fallback_rate`
  and `citation_grounding_rate` (a lightweight, non-LLM-judge faithfulness proxy: fraction of an
  answer's cited ids within a case's labelled-relevant set). A new `out_of_corpus.json` eval dataset
  (one case, empty `relevant_chunk_ids`) proves a genuinely out-of-corpus query refuses
  (`no_candidates`) rather than being mislabelled ambiguous or fabricating an answer.
- **9.8** — Security review, zero findings. Three deterministic red-team regression tests (classifier
  trusts only a *leading* `AMBIGUOUS` token; `parse_clarification_reply` discards text outside its
  expected shape; a clarifying turn's `done` event never leaks `refusalReason` or any internal
  category) plus a **live-model adversarial pass** (system-prompt exfiltration, DAN-style role
  switch, internal-category exfiltration, benign control) against the real classifier +
  clarification calls — zero findings, mirroring 7.6's precedent.
- **9.9** — Exit gate. Zero regressions; ADR-0008 confirmed matching shipped code across all 9
  decisions.

## Files & folders used

- `app/features/rag_agent/domain/clarification.py` — `decide_clarification`,
  `ClarificationDecision`, `parse_clarification_reply`, `ClarificationReply`, `AmbiguityClassifier`
  protocol.
- `app/features/rag_agent/domain/refusal.py` — `RefusalReason` (closed `Literal`).
- `app/features/rag_agent/domain/prompt.py` — `AMBIGUITY_CLASSIFIER_SYSTEM_PROMPT`,
  `CLARIFICATION_SYSTEM_PROMPT`.
- `app/features/rag_agent/infrastructure/llm_client.py` — `AnthropicAmbiguityClassifier`,
  `AnthropicAnswerGenerator.generate_clarification`.
- `app/features/rag_agent/application/answer_service.py` — the clarification-branch wiring, the
  `_REFUSAL_COPY` table, `human_handoff` log calls.
- `app/features/rag_agent/schemas.py` — `Answer.needs_clarification` /
  `.clarification_question` / `.clarification_options`.
- `app/features/rag_agent/server/router.py` — `needsClarification`/`clarificationQuestion`/
  `clarificationOptions` on the `done` SSE payload; `needs_clarification`/`refusal_reason` on the
  `chat_request` audit log line.
- `app/platform/config/settings.py` — `enable_clarification_branch`.
- `app/features/evaluation/metrics/fallback_metrics.py`; `evaluation/datasets/ambiguity.json`,
  `evaluation/datasets/out_of_corpus.json`.
- `docs/adr/0008-Ambiguity-Clarification-Fallback.md`, `docs/rag/DESIGN.md` §11.
