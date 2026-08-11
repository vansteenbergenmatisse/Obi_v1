# 0009 — Vision-Grounded Image Analysis

Status: Accepted
Date: 2026-08-11
Governs: apps/automation (rag_agent), apps/web (chat feature), packages/contracts — extends ADR-0005

## Context

Phase 4.7 (Obi widget) added image attachments (file-picker/clipboard-paste) and a real page
screenshot capture (`html-to-image`), plus click-to-zoom preview (4.7.8). Both are client-side
only: on send, images are dropped with an inline notice (`composer.tsx`'s "not analyzed yet"
copy) — no image ever reaches `apps/automation`. `docs/future-ideas/IDEAS.md` #3 raised this gap
in the abstract ("screenshot-grounded guidance"); this ADR is the design pass that gap required
before any code, per this repo's own process.

The existing answer pipeline (ADR-0005) is text-in/text-out: `ChatRequest`/`ChatTurn`
(`packages/contracts`) carry no image field; `AnthropicMessagesClient.create_message`
(`platform/clients/anthropic_client.py`) builds a single `{"type": "text", ...}` content block per
call; `redact_pii` (`rag_agent/domain/pii.py`) is a text regex pass that cannot inspect image
bytes; citation enforcement (`rag_agent/domain/citations.py::enforce_citations`) strips any
sentence not tied to a numbered evidence marker — content it was never designed to see, since
nothing upstream of it has ever produced non-text-evidence-grounded content before now.

Both configured models (`routing_model=claude-haiku-4-5-20251001`,
`answer_model=claude-sonnet-5`) are already vision-capable — no model change is needed, only
wiring.

## Decision

1. **Inline base64, not a separate upload endpoint.** `ChatTurn` gains an optional
   `images: ImageAttachment[]` array (new `ImageAttachment { mediaType: string; data: string }`
   type, `data` base64-encoded) alongside `content`. Rejected a separate upload endpoint that
   returns a reference: this system has no server-side conversation or blob store (`AnswerService`
   is stateless per request, ADR/PLAN 4.4 decision 2, unchanged by this ADR) — an upload endpoint
   would require inventing persistent storage, a reference lifecycle, and its own
   `security_baseline` classification for a requirement no one has confirmed. Inline base64 needs
   zero new persistent state and matches the existing "caller resends the whole history" shape
   exactly.

2. **Images travel only on the newest turn, not replayed on every resend.** Because `history` is
   fully resent on every call (ADR/PLAN 4.4 decision 2), replaying base64 image bytes on every
   turn would multiply request size and Anthropic input-token cost by the conversation length for
   no benefit — a prior turn's image was already analyzed once, when it was current. The web
   client drops `images` from every turn except the last when re-sending history (older turns keep
   `content` text only); the backend does not require or validate this client behavior structurally
   (a caller-supplied `images` on an older turn is simply passed through, not treated as an error),
   but the composer never produces it.

3. **A new pre-refusal, not pre-retrieval, branch — text retrieval still runs.** Unlike
   small-talk/clarification (which skip retrieval entirely), a turn with an image still runs the
   full rewrite → retrieve → rerank → CRAG path, because a query can legitimately need both
   Confluence-grounded evidence and image content ("what does this error mean, and where's the doc
   for it"). What changes is `decide_refusal` (`rag_agent/domain/refusal.py`): it gains a
   `has_image: bool` input and does not refuse on `weak_score`/`no_candidates` alone when
   `has_image=True` — a turn whose text retrieval found nothing can still produce a real, useful
   answer from the image alone. `no_citations` (citation enforcement stripped every claim) is
   unaffected by this change; it's evaluated after generation, independent of the image path.

4. **Vision analysis is a second, independent generation call — not merged into the citation-
   enforced grounded call.** `AnswerGenerator` gains `generate_image_analysis(query, images) ->
   str`, structurally parallel to `generate_small_talk`: a separate Anthropic call carrying the
   image content blocks plus the user's question, no `evidence_block`, no citation markers, fails
   open to a short "I couldn't look at that image right now" notice on `AnthropicError` (same
   fail-open shape `generate_small_talk` already uses — a vision-analysis failure is not a source
   of inaccurate grounded claims, so it degrades gracefully rather than failing the whole turn).
   Its output is appended to the grounded answer (if any) as a clearly labeled, visually distinct
   section — never passed through `enforce_citations`, and never itself carrying a numbered
   citation marker. This keeps `citations.py`/`enforce_citations`, `refusal.py`'s existing
   `no_citations` reason, and every other ADR-0005-governed stage of the grounded call completely
   untouched — the only touched decision point is `decide_refusal`'s `has_image` gate (3).

5. **`Answer` gains `imageAnalysis: str | None`, not a new SSE event.** Same additive-contract
   shape ADR-0008 used for clarification: the vision-analysis text streams over the existing
   `token` events (appended after the grounded answer text, before `done`), and the `done` payload
   carries `imageAnalysis` so the widget can render it in its own labeled block rather than
   indistinguishably merged into `answer`. `packages/contracts`'s `ChatDoneEvent` grows one more
   optional field.

6. **C6 PII redaction does not extend to image bytes — documented gap, not silently ignored.**
   `redact_pii` remains text-only; there is no NER/CV redaction pass in this repo and building one
   is out of scope for this phase (same posture ADR-0008 took on obfuscated-email text redaction).
   The composer's attachment UI must carry an explicit, honest notice that images are sent to the
   model as-is and are not scanned for personal information — copy drafted under
   `copywriting-rules`/`anti-ai-writing` at implementation time. This is a real accepted risk. the
   PII scope note in `pii.py`'s module docstring gets a matching addendum.

7. **New C3/C10 controls on the image input itself: a per-turn image count cap and a per-image
   byte-size cap** (new settings, names TBD to match `chat_max_message_chars`'s convention —
   e.g. `chat_max_images_per_turn`, `chat_max_image_bytes`), enforced at the same request-validation
   point as the existing `chat_max_history_turns`/`chat_max_message_chars` checks
   (`server/router.py`). **Concrete values are explicitly not decided by this ADR** — per the
   Architecture Standard's rule against inventing scaling/cost numbers, real limits need either a
   vision-token cost measurement or an explicit user-supplied ceiling, neither of which exists yet.
   Implementation must record whatever it picks and why, not silently copy a number from nowhere.

8. **Image-borne prompt injection is a new, real threat class this phase introduces — flagged, not
   solved by this ADR.** Text rendered inside an image (a screenshot crafted to look like a system
   message, or containing "ignore the citation rule") reaches the model with no defense beyond
   whatever the model itself resists — the existing citation-enforcement defense (decision 4) means
   an injected instruction inside an image cannot forge a fake grounded citation (the vision call
   never emits citation markers, and its output never enters `enforce_citations`), but it could
   still produce misleading `imageAnalysis` text. A live-model adversarial pass for this class is
   required before shipping (`securing-http-and-llm-endpoints`), tracked as this phase's own
   security sub-step — not run by this ADR, which is design-only.

## Reason

Keeping the vision call structurally separate from the grounded, citation-enforced call means
ADR-0005's core guarantees (every claim in `answer` traces to a numbered, retrieved citation) are
never weakened by a modality that has no citation concept — an image isn't a retrieved,
versioned Confluence page, so it cannot honestly carry a citation marker. Gating only
`decide_refusal`, and only on the `has_image` input, is the smallest change that fixes the real
interaction bug (a text-empty-but-image-answerable turn would otherwise incorrectly refuse) without
touching how refusal behaves for any turn without an image. Inline base64 and single-turn-only
transmission avoid inventing storage and bound the resend-cost problem without a new abstraction.

## Alternatives considered

- **Merge image content into the same grounded generation call, extend citation markers to cover
  image references (e.g. `[Image 1]`).** Rejected: this would require `enforce_citations` to
  distinguish "a valid Confluence citation" from "a valid image reference" inside the same
  enforcement pass, widening ADR-0005's citation domain for a case (visual, not textual, evidence)
  it was never designed to represent, and blurring the "every claim traces to a retrieved page"
  guarantee the whole accuracy-first mandate rests on.
- **A separate upload endpoint returning a reference id.** Rejected: no persistent
  attachment/blob store exists or is justified by a confirmed requirement; would need its own
  `security_baseline` tier, lifecycle, and cleanup semantics for no benefit over inline base64 at
  this traffic scale (no scaling number exists to justify one).
- **Treat an image turn as a full pre-retrieval short-circuit (skip retrieval entirely, like
  small-talk).** Rejected: would prevent answering a query that genuinely needs both Confluence
  evidence and image content in one turn — the actual product goal ("what's on this screenshot"
  *and* "where's the doc for this") requires both paths to run.
- **Resend every turn's images on every call, matching how text history is resent.** Rejected:
  multiplies image-token cost by conversation length for zero benefit — a prior turn's image was
  already analyzed once.

## Consequences

- `AnswerService.answer` gains a third input-shape concern (images), on top of small-talk and
  clarification's pre-pipeline branches — but this one runs *inside* the existing pipeline
  (retrieval still executes), not ahead of it, so it is not a third item in the small-talk/
  clarification tie-break list.
- `decide_refusal`'s signature changes (`has_image: bool` parameter) — every existing call site and
  test needs updating, even though behavior for `has_image=False` is unchanged (this is a real,
  visible signature change, not just an additive optional field, since refusal logic is a pure
  function over its inputs).
- `Answer`/`ChatDoneEvent`/`packages/contracts` grow one more optional field (`imageAnalysis`);
  `apps/web`'s message-rendering logic needs a matching (additive) update to actually send `images`
  on the newest turn and render the labeled analysis block — today `composer.tsx` drops attachments
  before `onSend` entirely, so the send path itself changes, not just the render path.
- A new, real threat class (image-borne injection) is introduced and must clear a live-model
  adversarial pass (mirroring Phase 5.4's text-injection matrix) before this ships to any real
  traffic — tracked as a required sub-step, not optional.
- `redact_pii`'s scope note grows a documented gap (image bytes are never scanned) that a future
  phase would need a real CV/NER pass to close — not invented here.
- No change to `retrieval/**`, the reranker, citation enforcement's marker logic, or any other
  ADR-0005-governed pipeline stage besides `decide_refusal`'s new input.

## Paths governed

`packages/contracts` (`ChatTurn`, `ChatDoneEvent`, `chat.yaml`),
`apps/automation/app/features/rag_agent/domain/refusal.py`,
`apps/automation/app/features/rag_agent/infrastructure/llm_client.py`,
`apps/automation/app/features/rag_agent/application/answer_service.py`,
`apps/automation/app/features/rag_agent/domain/pii.py` (docstring addendum only),
`apps/automation/app/platform/clients/anthropic_client.py` (multimodal content blocks),
`apps/automation/app/platform/config/settings.py` (new image caps),
`apps/automation/app/features/rag_agent/server/router.py` (C3/C10 image validation),
`apps/web/src/features/chat/**` (composer send path, message rendering, image-lightbox reuse),
`docs/future-ideas/IDEAS.md` (#3).
