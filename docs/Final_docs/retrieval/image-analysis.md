# Image analysis (the screenshot drives retrieval)

- **Workflow:** retrieval (stage 2/5, owned by `rag_agent`, with a small assist from `retrieval`)
- **Owning code:**
  `backend/app/features/rag_agent/application/answer_service.py`
  (`AnswerService.answer` — transcribes the newest turn's image first, folds the transcription
  into the one search query, threads it to generation as context, and keeps it off every
  persistence/log path; `_fold_search_query`; `_apply_crag_retry`);
  `backend/app/features/rag_agent/domain/prompt.py`
  (`IMAGE_ANALYSIS_SYSTEM_PROMPT` — the transcription-grade extraction prompt; and
  `build_image_context_block` — the uncached answer-context block);
  `backend/app/features/rag_agent/infrastructure/llm_client.py`
  (`AnthropicAnswerGenerator.generate_image_analysis` — the second, independent Anthropic vision
  call; `generate(..., image_analysis=...)` — attaches the transcription as context);
  `backend/app/features/rag_agent/server/router.py`
  (`_validate_history` + `_ALLOWED_IMAGE_MEDIA_TYPES` — the per-turn count/byte caps and the C3
  media-type allowlist, all enforced with a 400 before any LLM call);
  `backend/app/features/retrieval/application/retriever.py`
  (`HybridRetriever.retrieve_with_context` — the `trace_query` parameter that lets the search run
  on the folded query while the trace row records only the text-only query);
  `backend/app/platform/config/settings.py` (`chat_max_images_per_turn` = 10,
  `chat_max_image_bytes` = 3 MB).
- **Design panel:** `r5-image` (with `r2-embed`, `w-composer`, `r1-limits`)
- **Status:** Implemented (unit + database proven; the image path has no eval gold coverage —
  see below).

## What it does

When the newest conversation turn carries one or more images, `AnswerService.answer` makes a
second, independent Anthropic vision call (`generate_image_analysis`) that transcribes the image:
the verbatim on-screen text plus a short description of the UI. This runs FIRST, before every
short-circuit, and the transcription is then put to work three ways:

1. It folds into the one standalone search query (`_fold_search_query`: the rewritten question and
   the transcription joined), so an attached screenshot drives retrieval. A text-empty, image-only
   turn now searches on the transcription alone instead of building an empty result.
2. It rides to grounded generation as an uncached context block (`build_image_context_block`,
   passed via `generate(..., image_analysis=...)`). It is never folded into the numbered evidence
   block, so it can never gain a citation marker and never passes citation enforcement — every
   answer sentence still cites a real retrieved chunk.
3. It rides back to the widget on `Answer.image_analysis`, delivered on the SSE `done` event,
   kept separate from the answer text.

The image is no longer silently dropped on a small-talk, identity, or clarification turn: those
paths still short-circuit, but the transcription rides back on `Answer.image_analysis`.

Input limits are enforced at the `/chat` gate before any LLM call: at most 10 images per turn,
each ≤ 3 MB, on every turn (not just the newest), and a media type outside
{image/png, image/jpeg, image/webp, image/gif} is rejected with a 400.

## Why it does it

A screenshot is often the whole question — a user pastes an error dialog or a settings screen and
asks "why?". Transcribing it and folding that text into the search is what lets retrieval find the
right page; without it the search sees only the (often empty) typed text. The transcription must
never become a citable source (never-bend rule 7): the corpus is the only thing Obi cites, so the
transcription is deliberately kept out of the numbered evidence and out of citation enforcement.
It is treated as screenshot PII — memory-only (never-bend rule 10, ADR-0009 C6): it is never
logged, never written to the `query_trace` row (the retriever traces only the text-only
`trace_query`), and never persisted. The whole flow still obeys the two-read cap (never-bend rule
8): the vision call is not a retrieval read, so there is still exactly one search plus the single
CRAG retry. The cap rose 3→10 (decision w-composer-images, 2026-10-07): 10 × 3 MB base64 = 30 MB
stays under Anthropic's documented 32 MB Messages-API request ceiling and far under its
100-images-per-request limit, and the frontend proxy body ceiling rose to 40 MB to fit 10 images
plus history. The media-type allowlist (C3) keeps an unsupported type from ever reaching the
vision call.

## How we know it works

Unit (`backend/app/features/rag_agent/tests/test_answer_service.py`, panels r2-embed/r5-image):

- `test_rt2_image_transcription_folds_into_the_search_query` — the one search runs on both the
  rewritten question and the transcription.
- `test_rt2_image_only_turn_now_retrieves_on_the_transcription` — an image-only turn searches on
  the transcription (not an empty result) and cites the real retrieved chunk.
- `test_r5_small_talk_turn_with_an_image_still_analyzes_it` /
  `test_r5_clarification_turn_with_an_image_still_analyzes_it` — the image is not dropped on those
  short-circuit turns.
- `test_r5_image_transcription_is_passed_as_context_but_never_a_citable_source` — the transcription
  reaches generation only as its own context argument, never the evidence block, never a citation.
- `test_r5_two_read_cap_holds_with_an_image` — one search + one CRAG retry, the vision call runs
  once and adds no read.
- `test_sec_image_transcription_is_never_written_to_the_trace_query` (C6) — the retriever's trace
  query stays the text-only question; the transcription is never the traced value.
- `test_image_only_turn_with_no_text_and_no_transcription_skips_retrieval` — the embedder is never
  reached with an empty query string.

Unit (`test_llm_client.py`, panel r5-image): `test_generate_image_analysis_prompt_is_transcription_grade`
(verbatim on-screen text + UI description) and
`test_generate_image_analysis_uses_the_raised_transcription_token_budget` (cap raised above 500).

Database (`backend/app/features/confluence_sync/tests/test_chat_endpoint.py`, panel r1-limits):
`test_r1_limits_unsupported_image_media_type_is_rejected_400`,
`test_r1_limits_each_allowed_image_media_type_is_accepted`,
`test_r1_limits_tenth_image_accepted_eleventh_rejected`, plus the existing per-turn count/byte
cap tests and `test_image_within_caps_is_accepted_and_analysis_reaches_the_done_event`.

Gap: `make eval` has no image gold case — the bundled runner carries no image, so the image-driven
retrieval path has no eval coverage (documented, same honesty as the 8.3.x substeps). The text
gold set is byte-identical before and after this change (the text-only path is unchanged), proving
no text-retrieval regression. The live adversarial pass for image-borne prompt injection remains
tracked separately (PLAN 7.6), not solved here.
