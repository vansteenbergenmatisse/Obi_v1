# Future ideas — not scheduled

Backlog of product ideas raised in conversation, captured here so they aren't lost. **None of
these are scoped, designed, or scheduled** — they are not part of `docs/rag/PLAN.md` and carry no
commitment. Before any of these becomes real work: run it through `docs/rag/PLAN.md`'s own
process (design first, an ADR if it's a durable architecture decision, then a phase with
acceptance criteria) rather than building ad hoc.

Each idea below is written as raised, plus a short note on how it would connect to what already
exists — not a spec.

---

## 1. Clarify before searching, on an underspecified question

If the incoming question is too vague or irrelevant to search well, ask the user a clarifying
follow-up **before** running retrieval, instead of firing a low-quality query at the RAG database
and either hallucinating or refusing.

**Relation to current architecture.** Today, an underspecified query just falls through the
existing pipeline (rewrite → retrieve → rerank → refuse if the top score is weak) and comes out
the other end as a refusal ("not in the docs — routed to a human") — see `refusal_min_rerank_score`
and `AnswerService` in PLAN Phase 4.2. This idea adds a stage *before* retrieval: a cheap
classification/rewrite-model call that decides "is this answerable as asked, or do I need one more
detail from the user first" — closer to a conversational disambiguation turn than a retrieval
change. Would need: a way to detect "too vague" (heuristic or a routing-model call), and a new SSE
event type (or reuse of `refused`) so the UI can render "I need a bit more detail" distinctly from
a hard refusal.

## 2. Account/tier/integration awareness

Integrate with the surrounding system so the bot knows things about the asker: what pricing tier
they're on, what integrations they have enabled, what systems/products they use. Answers (and
retrieval scope) could then be tailored to what's actually relevant to *that* customer instead of
the whole corpus.

**Relation to current architecture.** There's no tenant/account model in this repo today —
`principal` on `POST /chat` is just a caller-self-reported string used for page-level ACL
(`PrincipalPermissionPolicy`, PLAN 4.3), not a customer/account record with tier or integration
data. This would need a new data source (likely an existing internal system-of-record, reached via
a new `platform/clients` integration) and a way to fold that context into retrieval scope
(`source_id`/`tags` filtering, see idea 4) and/or into the generation prompt.

## 3. Screenshot-grounded guidance

Take a screenshot of the user's current page/screen and tell them exactly what to do next based on
what's actually visible there, instead of a generic text answer.

**Relation to current architecture.** This is a new modality (vision input) the current pipeline
doesn't have at all — `AnswerService` is text-in/text-out. Would need: a way for the client to
capture and send a screenshot (privacy/consent implications — this is genuinely sensitive input,
review under `securing-http-and-llm-endpoints` before building), a vision-capable model call, and
probably a way to ground the screenshot against known UI states/docs rather than freeform
description.

## 4. Segment the RAG corpus by product/integration

Split the corpus so retrieval doesn't search everything indiscriminately: separate
Muse-related vs. Toast-related vs. other-integration-related content, and further split *within*
an integration by which system it connects to (e.g. "Muse → QuickBooks" content should only be
searched when that's the relevant integration pairing) — as opposed to full-corpus retrieval, which
is what happens today.

**Relation to current architecture.** This one is the closest to already-existing scaffolding.
`page_source`/`chunk` already carry `source_type`, `source_id`, and a free-form `tags` array
(ADR-0004, PLAN 3.5.3), and `source_scope` (PLAN 3.5.6) already resolves which Confluence
roots/spaces feed which tags. Extending tags to encode integration pairs (e.g. `muse:quickbooks`)
and then filtering `HybridRetriever` by tag in addition to `source_id` is plausibly a small
extension of the existing seam rather than new architecture — but confirm that against the real
tag taxonomy before assuming it's just a config change.

---

## Later: visualize the target system

Once any of the above gets real shape, draw the target pipeline (probably a Mermaid diagram in a
markdown file here or in `docs/rag/DESIGN.md`) showing how clarification, account context,
screenshots, and corpus segmentation compose with the existing
`rewrite → retrieve → rerank → ground → refuse → CRAG` pipeline. Not needed until one of these
ideas is actually being designed.
