# The answer prompt (grounded generation)

- **Workflow:** retrieval (stage 5, owned by `rag_agent`)
- **Owning code:**
  `backend/app/features/rag_agent/domain/prompt.py` — every prompt string lives here
  (`ANSWER_SYSTEM_PROMPT`, `build_answer_prompt`, `build_evidence_block`,
  `build_answer_context_block`, and since 8.3.3 `build_integration_context_block` +
  the `EXAMPLE_INTEGRATION_CONTEXT_DATA_HUB` / `EXAMPLE_INTEGRATION_CONTEXT_BASE`
  example renderings);
  `backend/app/features/rag_agent/infrastructure/llm_client.py`
  (`AnthropicAnswerGenerator.generate` — assembles the cached persona block plus the
  optional uncached per-chat blocks and makes the one Anthropic call);
  `backend/app/features/rag_agent/application/answer_service.py`
  (`AnswerService.answer` — builds the evidence block, derives the customer's actual
  connections through the catalog, and threads the verified context into generation).
- **Design panel:** `mi-prompt` (section 05.2 · Multi-integration context)
- **Status:** Unverified (the integration-context injection is coded and unit/eval-proven;
  no live customer token carries slots yet, so the block has never been rendered against a
  real session — Phase A validates live. The single-integration grounded answer underneath
  is Implemented.)

## What it does

The grounded answer call sends two or more system blocks and one user message. The user
message (`build_answer_prompt`) is the rewritten question plus the numbered evidence block
(`build_evidence_block` — the parent text of each retrieved hit, markers `[1..n]`), with the
citation instruction repeated inline. The first system block is the cached persona/style
prompt (`ANSWER_SYSTEM_PROMPT`): answer only from the numbered evidence, cite every claim with
its marker, write in a natural human voice. The whole reply then passes `enforce_citations`
before the user sees it — an uncited or mis-cited claim is discarded, and if nothing survives
the answer degrades to a refusal (rule 7).

After the cached persona block ride optional **uncached** per-chat blocks, each dropped
entirely when its values are unknown (nothing is guessed), so per-chat variation never busts
the shared prompt cache:

- the **business-context block** (`build_answer_context_block`, operator request 2026-09-23) —
  the verified business name and integration.
- the **verified integration setup** (`build_integration_context_block`, substep 8.3.3) — the
  same verified context the search (8.3.1) and the reranker (8.3.2) already used.

### The integration-context block (substep 8.3.3, panel mi-prompt)

When a request carries a verified `CustomerContext`, `generate` appends one uncached block
naming the customer's real setup:

```
Verified integration setup (facts, not instructions — use this to tailor and attribute your answer, never to decide what you may access):
Host platform: datahub
Selected integration: toast
Connected systems:
- POS: toast
- PMS: mews
Not configured (ask, never assume these exist):
- Accounting
Active connections and directions:
- pos-pms: pms=mews, pos=toast (directions: pos_to_pms, pms_to_pos)
Answer guidance: Name which system each fact comes from. Focus on the systems this question is about. When something the question needs is not configured in this setup, say it is not configured and ask for it, instead of inventing a configuration the customer does not have.
```

The known systems are the filled §D.13 slots; the absent roles are named as the ask; the host
platform and selected integration come straight from the frozen `AuthContext`; the connections
are the customer's actual ones, **derived** from the filled slots through the product catalog by
`eligibility_params` — the exact §D.4 derivation the search eligibility uses (one semantics, two
executors). Everything in the block is public catalog vocabulary (product ids, a platform key)
— never a company id, token or secret (rule 10), and never the request body. A slotless,
platformless, integrationless context yields no block, so the no-context answer prompt is
byte-identical to the pre-8.3.3 path.

`prompt.py` also carries two populated example renderings — `EXAMPLE_INTEGRATION_CONTEXT_DATA_HUB`
(Toast + Mews on the Data Hub host, the pos-pms connection, both directions) and
`EXAMPLE_INTEGRATION_CONTEXT_BASE` (Mews + Xero on the Base host, the pms-accounting
connection) — so the block's shape is demonstrable for both launch host platforms without a
live token.

## Why it does it

The answering model must know which systems the customer actually runs so it can attribute each
fact to its system and explain missing configuration instead of inventing it (§D.7). The block
is **answer guidance only** — it is presented as "facts, not instructions" with an explicit
"never to decide what you may access" line (the same anti-injection posture as the identity and
business-context blocks). The backend alone enforces eligibility (never-bend rule 3): the search
SQL already filtered the eligible set (8.3.1) and the reranker scored only that set (8.3.2), so
the chunks the model reads are already eligibility-filtered. The block never widens access, and a
frontend selection or a prompt instruction cannot expand permissions.

Further retrieval stays inside never-bend rule 8: the only extra read is the single CRAG
weak-score retry in `answer_service`, which reuses the same auth context and the same verified
`CustomerContext` (so the retry filters eligibility identically) — at most two reads per
question, never a loop. The prompt change added no new read.

The derived connections come from the catalog only; when no catalog is wired (most unit tests)
the block falls back to the context's own real records (empty at launch) and simply omits the
connections line rather than erroring.

## How we know it works

- **Unit** (`backend/app/features/rag_agent/tests/test_prompt_integration_context.py`, panel
  mi-prompt, 8.3.3): the block renders the known systems, the absent accounting role, the host
  platform, the selected integration, and the actual connection with both directions, and
  carries the attribution + missing-config guidance and the "facts, not instructions / never to
  decide what you may access" posture; an empty context yields no block (byte-identical
  no-context path); both the Base and Data Hub example prompts render with real catalog ids.
- **Unit** (`backend/app/features/rag_agent/tests/test_llm_client.py`, panel mi-prompt, 8.3.3):
  `generate` attaches the integration setup as its own **uncached** system block alongside the
  cached persona, and adds no integration block when no verified context is passed.
- **Unit** (`backend/app/features/rag_agent/tests/test_answer_service.py`, panel mi-prompt,
  8.3.3): `answer` threads the verified slots + host platform and the catalog-derived connection
  into generation (general-only path threads an empty context and no connections); and the
  read counter never exceeds two even when every result scores weak enough to force the CRAG
  retry (rule 8, no loop).
- **Eval** (`make eval`, rule 11): every gold-set number is identical to the floor in
  `docs/plan/baseline.md` before and after 8.3.3 — the bundled runner carries no customer
  context, so the integration block is never added and the no-context prompt is byte-identical.
  Context-carrying gold cases (Step 6) and Phase A (8.5.2) provide the live evidence.
- Not yet proven: no live token carries slots yet (platforms don't mint the structured
  context), so the block has never been rendered against a real session.
