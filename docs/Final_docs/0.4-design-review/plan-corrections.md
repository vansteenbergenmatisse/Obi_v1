# Plan corrections — substep 0.4.3

One row per substep in `docs/Final_docs/obi-action-plan.html` (187/187), cross-checked against
`docs/Final_docs/0.4-design-review/delta.md`. Mark definitions: **keep** (delta says change:
none, or work is still needed and the substep's own text already describes it correctly —
no HTML edit), **already done** (the synopsis proves the behavior + a test already exist —
no HTML edit), **changed** (delta reveals the substep's own premise is factually wrong in a
way that alters what it must build/prove — HTML rewritten in place), **not needed** (target
already holds and is fully redundant to keep as future work — none found; see hand-back).

`docs/plan/decisions.md` is still the `_pending_` placeholder. Every substep whose refs line
carries a `blocked`-verdict panel (d-source_scope, em-hostbackend) is marked **keep** and
built to the CLAUDE.md default (no forced resolution here); noted per-row below.

## Marks (187/187)

| substep id | title | mark | reason | proof |
|---|---|---|---|---|
| p0-s0_1-1 | 0.1.1 · Freeze the code | keep | No panel ref (process substep: freeze the code). Repo is well past Phase 0 (commits through 59385f4/bf7fece/2ac7e7a); freezing-the-code as a one-time gate has no ongoing artifact to check against delta.md. | n/a — no design-panel ref |
| p0-s0_1-2 | 0.1.2 · Freeze the database shape | keep | No panel ref (process substep: freeze the database shape). No delta.md row applies; description stands. | n/a — no design-panel ref |
| p0-s0_1-3 | 0.1.3 · Freeze the configuration | keep | No panel ref (process substep: freeze the configuration). No delta.md row applies; description stands. | n/a — no design-panel ref |
| p0-s0_1-4 | 0.1.4 · Archive the old docs, create the new docs folders | keep | No panel ref. Repo check: docs/ still holds the pre-Phase-0 prose corpus (OBI-RAG-SYSTEM-A-Z.md, final_design/, rag/, embedding/, runbooks/) at the root, not under a docs/archive/ folder — the 'archive the old docs' half of this substep is not actually done yet. Its own text is still an accurate statement of remaining work, so no HTML edit is needed. | ls docs/ (run 2026-09-16): no archive/ subfolder present; old docs still at docs/ root |
| p0-s0_1-5 | 0.1.5 · Keep the design files next to the code | keep | No panel ref (process substep: keep design files next to the code). No delta.md row applies. | n/a — no design-panel ref |
| p0-s0_1-6 | 0.1.6 · Write the restore note | keep | No panel ref (process substep: write the restore note). find docs -iname '*restore*' returns nothing — likely not written, but no delta.md row exists to correct; description stands as remaining work. | find docs -iname '*restore*' (2026-09-16): no match |
| p0-s0_2-1 | 0.2.1 · CLAUDE.md in place | already done | No panel ref, but directly verifiable: CLAUDE.md is in place at the repo root and is the active source of truth being followed for this very substep. | Read of CLAUDE.md succeeded; its rules are being applied right now |
| p0-s0_2-2 | 0.2.2 · Three subagents | already done | No panel ref, but directly verifiable: .claude/agents/{obi-auditor,obi-implementer,obi-tester}.md all exist (three subagents). | ls .claude/agents → obi-auditor.md, obi-implementer.md, obi-tester.md |
| p0-s0_2-3 | 0.2.3 · The panel reader | already done | No panel ref, but directly verifiable: apps/automation/tools/panel.py exists and is the panel reader used throughout this substep. | ls apps/automation/tools/panel.py; used live in this and prior substeps |
| p0-s0_2-4 | 0.2.4 · Skill: /obi-verify | changed | 0.5.1 moved the targets to the root Makefile — the skill's unit+database row previously ran `make up && make check`; updated to call the four root targets (`make test-unit`, `make test-db`, `make test-ui`, `make eval`) added by substep 0.5.1, split into separate unit/database/browser/eval rows. Lint+types and live rows unchanged. | .claude/skills/obi-verify/SKILL.md edited 2026-09-16 (0.5.1 closeout); ledger.md 0.5.1 entry |
| p0-s0_2-5 | 0.2.5 · Skill: /obi-test-writer | already done | No panel ref, but directly verifiable: .claude/skills/obi-test-writer exists and is invoked by /obi-change step 2. | ls .claude/skills/obi-test-writer |
| p0-s0_2-6 | 0.2.6 · Skill: /obi-change | already done | No panel ref, but directly verifiable: .claude/skills/obi-change exists — this substep is being run through it right now. | ls .claude/skills/obi-change |
| p0-s0_2-7 | 0.2.7 · Skill: /obi-audit | already done | No panel ref, but directly verifiable: .claude/skills/obi-audit exists. | ls .claude/skills/obi-audit |
| p0-s0_2-8 | 0.2.8 &#183; Prove the test writer&#x27;s tests actually catch a broken build | already done | No panel ref. Ledger already carries a finished 0.2.8 entry proving the test writer's tests catch a broken build (revert-cycle proof). | docs/plan/ledger.md entry '0.2.8 · 2026-09-15 · uncommitted · ...' — 4 revert-cycle results recorded |
| p0-s0_3-1 | 0.3.1 · Run the ten auditors in parallel | already done | No panel ref. The ten (thirteen, incl. README/entrypoint additions) synopsis files already exist under docs/Final_docs/0.3-code-vs-design-audit-2026-09-14/, and ledger entry 0.3.1 records the run. | ls docs/Final_docs/0.3-code-vs-design-audit-2026-09-14/ → 13 files; ledger.md 0.3.1 entry |
| p0-s0_3-2 | 0.3.2 · The test inventory | already done | No panel ref. tests.md (the test inventory) exists in the audit folder and ledger entry 0.3.2 records its production (98 test files / 793 test functions, 101 built panels, 35 untested). | docs/Final_docs/0.3-code-vs-design-audit-2026-09-14/tests.md; ledger.md 0.3.2 entry |
| p0-s0_3-3 | 0.3.3 · The infrastructure inventory | already done | No panel ref. packages-config-infra-docs.md (the infrastructure/config inventory) exists in the audit folder, covering packages/, config/, infra/ and docs/ per its own scope line. | docs/Final_docs/0.3-code-vs-design-audit-2026-09-14/packages-config-infra-docs.md |
| p0-s0_4-1 | 0.4.1 · The delta document | already done | No panel ref. delta.md (the delta document) exists at docs/Final_docs/0.4-design-review/delta.md, 192/192 panels rowed, and is the input this very substep (0.4.3) is walking. | docs/Final_docs/0.4-design-review/delta.md — 192 rows, row-count/change-tally footer |
| p0-s0_4-2 | 0.4.2 · Correct the design page | already done | No panel ref. Ledger entry 0.4.2 records the design page correction already run (52 panels' today/status corrected, obi-rag-system-flow.html updated, brief regenerated) — out of scope for 0.4.3 per the task framing. | docs/plan/ledger.md 0.4.2 entry; docs/Final_docs/obi-rag-system-flow.html; docs/Final_docs/obi-system-brief.md |
| p0-s0_4-3 | 0.4.3 · Correct this plan | already done | This is the substep being executed right now. Its own output is docs/Final_docs/0.4-design-review/plan-corrections.md (this file) plus the surgical edits to obi-action-plan.html recorded below. | This document, and the ledger entry appended for 0.4.3 |
| p0-s0_5-1 | 0.5.1 · The test harness | keep | No panel ref (process substep: the test harness). No delta.md row applies; whether make test-unit/make test-db/make eval are fully wired is a code-level fact this docs-only substep cannot verify without running commands outside this task's scope. | n/a — no design-panel ref, not run in this docs-only substep |
| p0-s0_5-2 | 0.5.2 · The regression suite, ingestion | keep | No design-panel ref on this substep's refs line; no delta.md row applies. Description stands as written. | n/a — no design-panel ref |
| p0-s0_5-3 | 0.5.3 · The regression suite, retrieval | keep | No design-panel ref on this substep's refs line; no delta.md row applies. Description stands as written. | n/a — no design-panel ref |
| p0-s0_5-4 | 0.5.4 · The regression suite runs in CI as a gate | keep | No panel ref (process substep: CI gate). No .github/*.yml workflow file found in the repo, so CI wiring is not yet done; description stands as remaining work. | find .github -iname '*.yml' (2026-09-16): no match |
| p0-s0_5-reg-ingestion-stage-1 | Protect: Ingestion, stage 1 — 7 panels | keep | delta.md: i1-checks, i1-ledger, i1-self, i1-claim, i1-reaper, i1-fail, i1-handle all confirmed, change: none — target already holds. | i1-checks, i1-ledger, i1-self, i1-claim, i1-reaper, i1-fail, i1-handle row(s) in delta.md, change column: none |
| p0-s0_5-reg-ingestion-stage-2 | Protect: Ingestion, stage 2 — 5 panels | keep | delta.md: i2-fetch, i2-meta, i2-nochange, i2-tobuild, i2-inplace (change: none/small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | i2-fetch, i2-meta, i2-nochange, i2-tobuild, i2-inplace row(s) in delta.md |
| p0-s0_5-reg-ingestion-stage-3 | Protect: Ingestion, stage 3 — 5 panels | keep | delta.md: i3-blocks, i3-parents, i3-children, i3-context, i3-tsv (change: none/small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | i3-blocks, i3-parents, i3-children, i3-context, i3-tsv row(s) in delta.md |
| p0-s0_5-reg-ingestion-stage-4 | Protect: Ingestion, stage 4 — 7 panels | keep | delta.md: i4-document, i4-chunks, i4-gate, i4-swap, i4-failed, i4-gc, i4-rollback (change: large/none/small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | i4-document, i4-chunks, i4-gate, i4-swap, i4-failed, i4-gc, i4-rollback row(s) in delta.md |
| p0-s0_5-reg-knowledge-scopes | Protect: Knowledge scopes — 5 panels | keep | delta.md: tg-add, tg-change, tg-first, tg-retag, ks-index (change: none/small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | tg-add, tg-change, tg-first, tg-retag, ks-index row(s) in delta.md |
| p0-s0_5-reg-retrieval-stage-1 | Protect: Retrieval, stage 1 — 6 panels | keep | delta.md: r1-proxy, r1-limits, r1-small, r1-clarify, r1-idem, r1-short (change: none/small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | r1-proxy, r1-limits, r1-small, r1-clarify, r1-idem, r1-short row(s) in delta.md |
| p0-s0_5-reg-retrieval-stage-2 | Protect: Retrieval, stage 2 — 5 panels | keep | delta.md: r2-embed, r2-gucs, r2-dense, r2-keyword, r2-indexes — citation/line-number drift only (already corrected on the design page in substep 0.4.2); this plan substep's own text does not cite the stale lines and is unaffected. | r2-embed, r2-gucs, r2-dense, r2-keyword, r2-indexes row(s) in delta.md, target: (doc fix) |
| p0-s0_5-reg-retrieval-stage-3 | Protect: Retrieval, stage 3 — 6 panels | keep | delta.md: r3-reader, r3-source, r3-acl, r3-torerank, r3-deny, r3-groups (change: none/small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | r3-reader, r3-source, r3-acl, r3-torerank, r3-deny, r3-groups row(s) in delta.md |
| p0-s0_5-reg-retrieval-stage-4 | Protect: Retrieval, stage 4 — 3 panels | keep | delta.md: r4-rerank, r4-weak, r4-proceed (change: none/small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | r4-rerank, r4-weak, r4-proceed row(s) in delta.md |
| p0-s0_5-reg-retrieval-stage-5 | Protect: Retrieval, stage 5 — 7 panels | keep | delta.md: r5-evidence, r5-generate, r5-enforce, r5-stream, r5-nocite, r5-image, r5-feedback (change: small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | r5-evidence, r5-generate, r5-enforce, r5-stream, r5-nocite, r5-image, r5-feedback row(s) in delta.md |
| p0-s0_5-reg-the-widget | Protect: The widget — 8 panels | keep | delta.md: w-launcher, w-panel, w-composer, w-scope, w-proxy, w-i18n, w-screenshot, w-render (change: none/small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | w-launcher, w-panel, w-composer, w-scope, w-proxy, w-i18n, w-screenshot, w-render row(s) in delta.md |
| p0-s0_5-reg-the-relational-database | Protect: The relational database — 4 panels | keep | delta.md: d-event_ledger, d-document, d-reconciliation_run, d-page_restriction (change: none/small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | d-event_ledger, d-document, d-reconciliation_run, d-page_restriction row(s) in delta.md |
| p0-s0_5-reg-the-vector-database | Protect: The vector database — 8 panels | keep | delta.md: vd-text, vd-column, vd-hnsw, vd-nearest, vd-rls, vd-question, vd-keyword, vd-swap (change: none/small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | vd-text, vd-column, vd-hnsw, vd-nearest, vd-rls, vd-question, vd-keyword, vd-swap row(s) in delta.md |
| p0-s0_5-reg-security | Protect: Security — 7 panels | keep | delta.md: s-source, s-acl, s-permitted, s-writer, s-reader, s-anon, s-audit (change: none/small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | s-source, s-acl, s-permitted, s-writer, s-reader, s-anon, s-audit row(s) in delta.md |
| p0-s0_5-reg-code-map | Protect: Code map — 5 panels | keep | delta.md: cm-root, cm-docs, cm-contracts, cm-tokens, cm-infra (change: none/small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | cm-root, cm-docs, cm-contracts, cm-tokens, cm-infra row(s) in delta.md |
| p0-s0_5-reg-system-overview | Protect: System overview — 3 panels | keep | delta.md: ov-confluence, ov-corpus, ov-widget (change: none/small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | ov-confluence, ov-corpus, ov-widget row(s) in delta.md |
| p0-s0_6-1 | 0.6.1 · Record the decisions | keep | No panel ref (decide: record the decisions). docs/plan/decisions.md is still the _pending_ placeholder per the task's own caveat — the decision-recording work described by this substep has not happened yet; description stands. | docs/plan/decisions.md — _pending_ placeholder, unchanged |
| p1-s1_1-1 | 1.1.1 · Move the folders | keep | delta.md: sc-frontend, sc-backend, sc-kb, cm-root, cm-platform, cm-alembic, cm-config, cm-scripts, cm-infra, cm-web, cm-contracts (change: large/none/small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | sc-frontend, sc-backend, sc-kb, cm-root, cm-platform, cm-alembic, cm-config, cm-scripts, cm-infra, cm-web, cm-contracts row(s) in delta.md |
| p1-s1_1-2 | 1.1.2 · One dependency direction | keep | delta.md: sc-kb, sc-backend, sc-frontend, cm-docs (change: small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | sc-kb, sc-backend, sc-frontend, cm-docs row(s) in delta.md |
| p1-s1_1-3 | 1.1.3 · CLAUDE.md, the skills, the agents and the design page follow | keep | delta.md: cm-docs, sc-frontend, sc-backend, sc-kb (change: small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | cm-docs, sc-frontend, sc-backend, sc-kb row(s) in delta.md |
| p1-s1_2-1 | 1.2.1 · The tag map | keep | delta.md: tg-config, ks-validate, ks-edit, cm-config (change: small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | tg-config, ks-validate, ks-edit, cm-config row(s) in delta.md |
| p1-s1_2-2 | 1.2.2 · The widget list is generated | keep | delta.md: ks-deploy, ks-widget, cm-config, w-scope (change: small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | ks-deploy, ks-widget, cm-config, w-scope row(s) in delta.md |
| p1-s1_2-3 | 1.2.3 · The platform list | keep | delta.md cm-config/platform.md:143: platforms.json and a PlatformRegistry/PlatformEntry/load_platform_registry loader already exist ('code the design does not mention' list), so the k-add 'New · build and test' badge may overstate the remaining work — but delta.md does not confirm every specific validation rule this substep lists (lowercase/duplicate/lifetime/algs/classified-nowhere/zero-active-outside-local), so 'already done' is not fully provable here. Left as keep; substep text is not factually wrong, just possibly ahead of where the badge implies. | cm-config row (packages-config-infra-docs.md:59-61); platform.md:143 'code the design does not mention' entry |
| p1-s1_3-1 | 1.3.1 · Create or extend the ideas file | keep | delta.md: r1-rewrite, r5-stream, r4-rerank, em-token, cm-agent (change: large/small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | r1-rewrite, r5-stream, r4-rerank, em-token, cm-agent row(s) in delta.md |
| p2-s2_0-1 | 2.0.1 · The freshness target | keep | No design-panel ref on this substep's refs line; no delta.md row applies. Description stands as written. | n/a — no design-panel ref |
| p2-s2_0-2 | 2.0.2 · Real time during development | keep | delta.md: i1-webhook, i1-checks (change: none/small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | i1-webhook, i1-checks row(s) in delta.md |
| p2-s2_0-3 | 2.0.3 · The full re-index job | keep | delta.md: i2-classify, i1-sweep (change: large/small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | i2-classify, i1-sweep row(s) in delta.md |
| p2-s2_1-1 | 2.1.1 · One pending job per page | keep | delta.md: i1-enqueue, d-job (change: large) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | i1-enqueue, d-job row(s) in delta.md |
| p2-s2_1-2 | 2.1.2 · The label sweep | keep | delta.md: i1-sweep, ks-sweep, ks-orphan, d-reconciliation_run (change: large/small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | i1-sweep, ks-sweep, ks-orphan, d-reconciliation_run row(s) in delta.md |
| p2-s2_1-3 | 2.1.3 · Prove the queue on staging | keep | delta.md: i1-reaper, i1-fail, i1-handle, i1-claim all confirmed, change: none — target already holds. | i1-reaper, i1-fail, i1-handle, i1-claim row(s) in delta.md, change column: none |
| p2-s2_2-1 | 2.2.1 · The index fingerprint | keep | delta.md: i2-hash, d-page_source (change: large/small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | i2-hash, d-page_source row(s) in delta.md |
| p2-s2_2-2 | 2.2.2 · Classification without the version guard | keep | delta.md: i2-classify, i2-fetch (change: none/small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | i2-classify, i2-fetch row(s) in delta.md |
| p2-s2_2-3 | 2.2.3 · Labels to scope state | keep | delta.md: i2-labels, tg-state, tg-two, tg-conflict (change: large/none/small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | i2-labels, tg-state, tg-two, tg-conflict row(s) in delta.md |
| p2-s2_2-4 | 2.2.4 · Label-gated membership, unconditional | keep | delta.md: i2-gone, tg-remove, tg-classified, tg-purge, tg-deactivate, ks-index (change: large/none) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | i2-gone, tg-remove, tg-classified, tg-purge, tg-deactivate, ks-index row(s) in delta.md |
| p2-s2_2-5 | 2.2.5 · Metadata-only updates | keep | delta.md: i2-meta, i2-inplace, tg-retag, tg-add, tg-change (change: none/small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | i2-meta, i2-inplace, tg-retag, tg-add, tg-change row(s) in delta.md |
| p2-s2_2-close-i2-labels | Close: Labels to scope state  [Implemented, needs changing] | keep | delta.md: i2-labels (change: small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | i2-labels row(s) in delta.md |
| p2-s2_2-close-i2-hash | Close: One index fingerprint  [Implemented, needs changing] | keep | delta.md: i2-hash (change: small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | i2-hash row(s) in delta.md |
| p2-s2_2-close-i2-classify | Close: Classify the change  [Implemented, needs changing] | keep | delta.md: i2-classify — citation/line-number drift only (already corrected on the design page in substep 0.4.2); this plan substep's own text does not cite the stale lines and is unaffected. | i2-classify row(s) in delta.md, target: (doc fix) |
| p2-s2_2-close-i2-gone | Close: Gone, classified, or unlabeled: deactivate  [Implemented, needs changing] | keep | delta.md: i2-gone (change: large) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | i2-gone row(s) in delta.md |
| p2-s2_2-close-i2-rebuild | Close: Rebuild a new version  [Implemented, needs changing] | keep | delta.md: i2-rebuild (change: small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | i2-rebuild row(s) in delta.md |
| p2-s2_3-1 | 2.3.1 · Every child is embedded on every rebuild | keep | delta.md: i3-embed, i2-rebuild, vd-swap (change: large/none/small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | i3-embed, i2-rebuild, vd-swap row(s) in delta.md |
| p2-s2_3-2 | 2.3.2 · Attachments: fail the build or flag the type | keep | delta.md: i3-attach (change: small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | i3-attach row(s) in delta.md |
| p2-s2_3-3 | 2.3.3 · Chunking, context notes and the keyword index stay as they are | keep | delta.md: i3-blocks, i3-parents, i3-children, i3-context, i3-tsv, vd-text (change: none/small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | i3-blocks, i3-parents, i3-children, i3-context, i3-tsv, vd-text row(s) in delta.md |
| p2-s2_3-close-i3-embed | Close: Embed every child  [Implemented, needs changing] | keep | delta.md: i3-embed (change: large) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | i3-embed row(s) in delta.md |
| p2-s2_3-close-i3-attach | Close: Attachments  [Implemented, needs changing] | keep | delta.md: i3-attach (change: small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | i3-attach row(s) in delta.md |
| p2-s2_4-1 | 2.4.1 · A version is identified by its fingerprint | changed | delta.md i4-staging/d-document_version (large): migration 0012 already widened document_version's uniqueness constraint to 7 columns by a different mechanism than the design's index_fingerprint plan — neither today's 4-column key nor the target's (document_id, index_fingerprint) key describes the live schema. Rewrote the prompt to require reconciling with what 0012 actually shipped instead of assuming a not-yet-built migration 0011 does this. | i4-staging row (platform.md:92-93; alembic-and-scripts.md:89,93); d-document_version row (platform.md:109); HTML diff |
| p2-s2_4-2 | 2.4.2 · State is stamped with the swap | keep | delta.md: i4-stamp, i4-swap (change: small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | i4-stamp, i4-swap row(s) in delta.md |
| p2-s2_4-3 | 2.4.3 · Gate, garbage collection and rollback keep working | keep | delta.md: i4-gate, i4-gc, i4-rollback, i4-failed, i4-document, i4-chunks (change: large/none) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | i4-gate, i4-gc, i4-rollback, i4-failed, i4-document, i4-chunks row(s) in delta.md |
| p2-s2_4-close-i4-staging | Close: Create the version in staging  [Implemented, needs changing] | keep | delta.md: i4-staging (change: large) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | i4-staging row(s) in delta.md |
| p2-s2_4-close-i4-stamp | Close: Stamp source, tags and scope state  [Implemented, needs changing] | keep | delta.md: i4-stamp (change: small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | i4-stamp row(s) in delta.md |
| p2-s2_5-1 | 2.5.1 · Backfill and the readiness gate | keep | delta.md: tg-state, s-classified (change: large) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | tg-state, s-classified row(s) in delta.md |
| p2-s2_5-2 | 2.5.2 · Retire folder roots | keep | delta.md d-source_scope carries verdict 'blocked' — genuinely open owner call ('keep the table until label-gated ingestion is proven live, then drop it', no confirmed timeline), built to the default per CLAUDE.md and docs/plan/decisions.md (still _pending_). ks-remove (large) is the file-edit-only half already confirmed; the page-deactivation half is the real remaining work, which this substep's own text already targets correctly. | d-source_scope row (verdict: blocked); ks-remove row (widget.md:120) |
| p2-s2_5-3 | 2.5.3 · The freshness proof | keep | delta.md: tg-edit, tg-add, tg-change, tg-remove, tg-rebuild, tg-first, e-monitor (change: large/none/small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | tg-edit, tg-add, tg-change, tg-remove, tg-rebuild, tg-first, e-monitor row(s) in delta.md |
| p2-s2_5-close-tg-remove | Close: Remove the last recognized label  [Planned] | keep | delta.md: tg-remove (change: large) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | tg-remove row(s) in delta.md |
| p2-s2_5-close-tg-classified | Close: Add the classified label  [Planned] | keep | delta.md: tg-classified (change: large) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | tg-classified row(s) in delta.md |
| p2-s2_5-close-tg-two | Close: Two provider labels on one page  [Implemented, needs changing] | keep | delta.md: tg-two (change: small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | tg-two row(s) in delta.md |
| p2-s2_5-close-tg-edit | Close: Edit the body of a labeled page  [Implemented, needs changing] | already done | delta.md: tg-edit confirmed, change: none — confirmed (confluence_sync.md:112) | tg-edit row in delta.md (change: none); design panel's own scope needs no further build |
| p2-s2_5-close-tg-deactivate | Close: Deactivate  [Planned] | already done | delta.md: tg-deactivate confirmed, change: none — confirmed — `deactivate_page` exists and is called from i2-gone's triggers (confluence_sync.md:114) | tg-deactivate row in delta.md (change: none); design panel's own scope needs no further build |
| p2-s2_5-close-tg-purge | Close: Deactivate and purge  [Planned] | keep | delta.md: tg-purge (change: large) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | tg-purge row(s) in delta.md |
| p2-s2_5-close-tg-conflict | Close: Excluded as a conflict  [Implemented, needs changing] | already done | delta.md: tg-conflict confirmed, change: none — confirmed (confluence_sync.md:118) | tg-conflict row in delta.md (change: none); design panel's own scope needs no further build |
| p2-s2_5-close-tg-rebuild | Close: Rebuild with tags carried  [Implemented, needs changing] | already done | delta.md: tg-rebuild confirmed, change: none — confirmed (confluence_sync.md:119) | tg-rebuild row in delta.md (change: none); design panel's own scope needs no further build |
| p2-s2_5-close-tg-config | Close: The scope list file  [Implemented, needs changing] | keep | delta.md: tg-config (change: small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | tg-config row(s) in delta.md |
| p2-s2_5-close-tg-state | Close: scope_state  [Planned] | keep | delta.md: tg-state (change: large) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | tg-state row(s) in delta.md |
| p2-s2_5-close-tg-filter | Close: The filter that uses tags  [Implemented, needs changing] | keep | delta.md: tg-filter (change: large) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | tg-filter row(s) in delta.md |
| p2-s2_5-close-ks-edit | Close: Edit knowledge_scopes.json  [Implemented, needs changing] | keep | delta.md: ks-edit (change: small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | ks-edit row(s) in delta.md |
| p2-s2_5-close-ks-validate | Close: Validate the list  [Implemented, needs changing] | keep | delta.md: ks-validate (change: small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | ks-validate row(s) in delta.md |
| p2-s2_5-close-ks-deploy | Close: Deploy  [Implemented, needs changing] | keep | delta.md: ks-deploy (change: small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | ks-deploy row(s) in delta.md |
| p2-s2_5-close-ks-sweep | Close: The label sweep finds tagged pages  [Planned] | keep | delta.md: ks-sweep (change: large) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | ks-sweep row(s) in delta.md |
| p2-s2_5-close-ks-widget | Close: A widget uses the same slug  [Implemented, needs changing] | keep | delta.md: ks-widget (change: small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | ks-widget row(s) in delta.md |
| p2-s2_5-close-ks-remove | Close: A tag is removed from the file  [Implemented, needs changing] | keep | delta.md: ks-remove (change: large) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | ks-remove row(s) in delta.md |
| p2-s2_5-close-ks-orphan | Close: Pages with only that tag go out  [Planned] | keep | delta.md: ks-orphan (change: large) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | ks-orphan row(s) in delta.md |
| p2-s2_5-close-i1-webhook | Close: POST /confluence/events  [Unverified] | keep | delta.md: i1-webhook (change: small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | i1-webhook row(s) in delta.md |
| p2-s2_5-close-i1-enqueue | Close: Enqueue one job per page  [Implemented, needs changing] | keep | delta.md: i1-enqueue (change: large) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | i1-enqueue row(s) in delta.md |
| p2-s2_5-close-i1-sweep | Close: Sweeps: the safety net  [Implemented, needs changing] | keep | delta.md: i1-sweep (change: large) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | i1-sweep row(s) in delta.md |
| p3-s3_0-1 | 3.0.1 · The accuracy contract | keep | No design-panel ref on this substep's refs line; no delta.md row applies. Description stands as written. | n/a — no design-panel ref |
| p3-s3_0-2 | 3.0.2 · The gold set, version 0 | keep | delta.md: e-gold, e-split, e-stage1, e-stage2, e-stage3, e-stage4 (change: large/small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | e-gold, e-split, e-stage1, e-stage2, e-stage3, e-stage4 row(s) in delta.md |
| p3-s3_1-1 | 3.1.1 · Every candidate carries its identity | keep | delta.md: r2-prov, r2-dense, r2-keyword (change: large/small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | r2-prov, r2-dense, r2-keyword row(s) in delta.md |
| p3-s3_1-2 | 3.1.2 · Fusion by piece, not by page | keep | delta.md: r2-rrf (change: large) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | r2-rrf row(s) in delta.md |
| p3-s3_1-3 | 3.1.3 · The scorer reads the piece that matched | keep | delta.md: r4-texts, r4-rerank (change: large/small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | r4-texts, r4-rerank row(s) in delta.md |
| p3-s3_1-4 | 3.1.4 · Parents from the piece, under the same context | keep | delta.md: r5-parents (change: large) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | r5-parents row(s) in delta.md |
| p3-s3_1-5 | 3.1.5 · Curated entries have one identity | keep | delta.md: r2-curated (change: large) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | r2-curated row(s) in delta.md |
| p3-s3_1-6 | 3.1.6 · Before and after | keep | No design-panel ref on this substep's refs line; no delta.md row applies. Description stands as written. | n/a — no design-panel ref |
| p3-s3_2-1 | 3.2.1 · One authorization context | keep | delta.md: r1-ctx, ov-gate (change: large/small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | r1-ctx, ov-gate row(s) in delta.md |
| p3-s3_2-2 | 3.2.2 · The body never decides access | keep | delta.md: ks-widget, w-scope, r1-limits (change: small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | ks-widget, w-scope, r1-limits row(s) in delta.md |
| p3-s3_2-3 | 3.2.3 · Language: translate in, translate out | keep | delta.md: r1-rewrite, r5-stream, w-i18n (change: large/none/small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | r1-rewrite, r5-stream, w-i18n row(s) in delta.md |
| p3-s3_2-4 | 3.2.4 · The rewrite lists the parts and normalizes phrasing | keep | delta.md: r1-rewrite, r4-fallback (change: large/none) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | r1-rewrite, r4-fallback row(s) in delta.md |
| p3-s3_2-5 | 3.2.5 · Host context hints | keep | delta.md: r1-ctx, r5-evidence (change: large/small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | r1-ctx, r5-evidence row(s) in delta.md |
| p3-s3_2-6 | 3.2.6 · Rate limit and idempotency keys | keep | delta.md: r1-limits, r1-idem (change: small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | r1-limits, r1-idem row(s) in delta.md |
| p3-s3_2-7 | 3.2.7 · Remove the answer cache | keep | delta.md: cm-agent, cm-shared (change: none/small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | cm-agent, cm-shared row(s) in delta.md |
| p3-s3_2-close-r1-auth | Close: Verify who is asking  [Implemented, needs changing] | keep | delta.md r1-auth (large): a full per-user RS256 JWT flow is already built and live-proven for test hosts (commit 59385f4), consistent with this close item's own [Implemented, needs changing] label — 'needs changing' still correctly describes the remaining real-platform-key gap. | r1-auth row (rag_agent.md:77) |
| p3-s3_2-close-r1-ctx | Close: Build the authorization context: company, integration, person  [Planned] | keep | delta.md: r1-ctx (change: large) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | r1-ctx row(s) in delta.md |
| p3-s3_2-close-r1-rewrite | Close: Rewrite into one standalone question  [Implemented, needs changing] | keep | delta.md: r1-rewrite (change: large) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | r1-rewrite row(s) in delta.md |
| p3-s3_3-1 | 3.3.1 · Curated entries in the same pool | keep | delta.md: r2-curated, d-curated (change: large) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | r2-curated, d-curated row(s) in delta.md |
| p3-s3_3-2 | 3.3.2 · Page permissions inside the searches | keep | delta.md: r2-aclsql, r3-acl (change: large/small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | r2-aclsql, r3-acl row(s) in delta.md |
| p3-s3_3-3 | 3.3.3 · Thin results: one extra read | already done | delta.md: r3-torerank confirmed (change: none) and r4-fallback logic confirmed to match exactly (change: none) — the thin-results extra-read mechanism this substep targets is already built. | r3-torerank + r4-fallback rows in delta.md, both change: none |
| p3-s3_3-4 | 3.3.4 · Rerank depth | keep | delta.md: r4-rerank — citation/line-number drift only (already corrected on the design page in substep 0.4.2); this plan substep's own text does not cite the stale lines and is unaffected. | r4-rerank row(s) in delta.md, target: (doc fix) |
| p3-s3_3-close-r2-rrf | Close: Reciprocal rank fusion, by chunk id  [Implemented, needs changing] | keep | delta.md: r2-rrf (change: large) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | r2-rrf row(s) in delta.md |
| p3-s3_3-close-r2-prov | Close: Provenance on every candidate  [Planned] | keep | delta.md: r2-prov (change: large) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | r2-prov row(s) in delta.md |
| p3-s3_3-close-r2-curated | Close: Curated entries: found by relevance, in the same pool  [Implemented, needs changing] | keep | delta.md: r2-curated (change: large) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | r2-curated row(s) in delta.md |
| p3-s3_3-close-r2-aclsql | Close: Lock 3 inside the SQL searches  [Planned] | keep | delta.md: r2-aclsql (change: large) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | r2-aclsql row(s) in delta.md |
| p3-s3_4-1 | 3.4.1 · The scope policy reads the state | keep | delta.md: tg-filter, r3-scope, r3-classified, s-scope, s-classified (change: large) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | tg-filter, r3-scope, r3-classified, s-scope, s-classified row(s) in delta.md |
| p3-s3_4-2 | 3.4.2 · Groups proven live | keep | delta.md: r3-groups, r3-acl (change: none/small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | r3-groups, r3-acl row(s) in delta.md |
| p3-s3_4-3 | 3.4.3 · The space rule | keep | delta.md: r3-acl — citation/line-number drift only (already corrected on the design page in substep 0.4.2); this plan substep's own text does not cite the stale lines and is unaffected. | r3-acl row(s) in delta.md, target: (doc fix) |
| p3-s3_4-close-r3-scope | Close: Scope row security  [Unverified] | keep | delta.md: r3-scope (change: large) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | r3-scope row(s) in delta.md |
| p3-s3_4-close-r3-classified | Close: Conflict and classified are never served  [Planned] | keep | delta.md: r3-classified (change: large) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | r3-classified row(s) in delta.md |
| p3-s3_5-1 | 3.5.1 · Rerank the union once | keep | delta.md: r4-union, r4-fallback (change: large/none) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | r4-union, r4-fallback row(s) in delta.md |
| p3-s3_5-2 | 3.5.2 · Refusal reasons by stage | changed | delta.md r4-refuse (small): a fourth refusal reason, off_topic, was added 2026-09-12 with its own threshold and isn't named on this substep's stage-4 list (which only said no_candidates, weak_score). Added off_topic to the stage-4 line. | r4-refuse row (rag_agent.md:88, 103); 'code the design does not mention' entry domain/refusal.py:24-34,42,79-80 (rag_agent.md:103); HTML diff |
| p3-s3_5-3 | 3.5.3 · Calibrate the refusal threshold | changed | delta.md r4-weak (small): refusal_min_rerank_score was already hand-recalibrated in code from 0.10 to 0.05 on 2026-09-12, ahead of and outside this formal calibration substep. Added a note to Must-be-true/prompt so the substep re-derives from that ad-hoc value on the dev-half gold set and records it properly, instead of assuming the threshold is still untouched at 0.10. | r4-weak row (rag_agent.md:86); HTML diff |
| p3-s3_5-close-r4-texts | Close: Fetch the passages to rerank  [Implemented, needs changing] | keep | delta.md: r4-texts (change: large) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | r4-texts row(s) in delta.md |
| p3-s3_5-close-r4-fallback | Close: One bounded fallback search  [Implemented, needs changing] | already done | delta.md: r4-fallback confirmed, change: none — drifted only on cited line numbers; logic matches exactly (rag_agent.md:87) | r4-fallback row in delta.md (change: none); design panel's own scope needs no further build |
| p3-s3_5-close-r4-union | Close: Rerank the union once  [Planned] | keep | delta.md: r4-union (change: large) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | r4-union row(s) in delta.md |
| p3-s3_5-close-r4-refuse | Close: Refuse and hand off  [Implemented, needs changing] | keep | delta.md: r4-refuse (change: small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | r4-refuse row(s) in delta.md |
| p3-s3_6-1 | 3.6.1 · Dedupe and the token budget | keep | delta.md: r5-dedupe, r5-evidence (change: large/small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | r5-dedupe, r5-evidence row(s) in delta.md |
| p3-s3_6-2 | 3.6.2 · The coverage check | keep | delta.md: r5-coverage, r5-partial (change: large) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | r5-coverage, r5-partial row(s) in delta.md |
| p3-s3_6-3 | 3.6.3 · Partial answers on the wire and on screen | keep | delta.md: r5-partial, w-render, cm-contracts (change: large/none/small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | r5-partial, w-render, cm-contracts row(s) in delta.md |
| p3-s3_6-4 | 3.6.4 · Priority 2 · The support check before send | keep | delta.md: r5-ground, r5-nocite, r5-enforce, r5-stream (change: large/small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | r5-ground, r5-nocite, r5-enforce, r5-stream row(s) in delta.md |
| p3-s3_6-5 | 3.6.5 · Example mode for onboarding | keep | delta.md: r5-generate, r5-ground (change: large/small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | r5-generate, r5-ground row(s) in delta.md |
| p3-s3_6-6 | 3.6.6 · The trace records the decision | changed | delta.md s-audit/d-query_trace (small): the prompt said 'add the trace columns from migration 0011,' but subject_hash already shipped via migration 0011 — only candidate_chunk_ids and decision remain absent and need a new migration (0011 is already taken). Rewrote the prompt to reflect this. | s-audit row (platform.md:118); d-query_trace row (platform.md:114); HTML diff |
| p3-s3_6-close-r5-coverage | Close: Coverage check on the final context  [Planned] | keep | delta.md: r5-coverage (change: large) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | r5-coverage row(s) in delta.md |
| p3-s3_6-close-r5-partial | Close: Partial answer  [Planned] | keep | delta.md: r5-partial (change: large) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | r5-partial row(s) in delta.md |
| p3-s3_6-close-r5-parents | Close: Expand children to parents  [Implemented, needs changing] | keep | delta.md: r5-parents (change: large) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | r5-parents row(s) in delta.md |
| p3-s3_6-close-r5-dedupe | Close: Dedupe and trim to the token budget: the final context  [Planned] | keep | delta.md: r5-dedupe (change: large) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | r5-dedupe row(s) in delta.md |
| p3-s3_6-close-r5-ground | Close: Semantic support verification (batched, before send)  [Planned] | keep | delta.md: r5-ground (change: large) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | r5-ground row(s) in delta.md |
| p3-s3_7-1 | 3.7.1 · The daily report | keep | delta.md: e-monitor, s-audit, r4-refuse (change: large/small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | e-monitor, s-audit, r4-refuse row(s) in delta.md |
| p3-s3_7-2 | 3.7.2 · The held-out set runs every day | keep | delta.md: e-monitor (change: large) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | e-monitor row(s) in delta.md |
| p3-s3_7-3 | 3.7.3 · From report to action | keep | No design-panel ref on this substep's refs line; no delta.md row applies. Description stands as written. | n/a — no design-panel ref |
| p4-s4_1-1 | 4.1.1 · The token verifier | already done | delta.md em-backend/em-token: 'rag_agent/server/token_verifier.py ... already exist, fully built and tested' (rag_agent.md:99); a full RS256 JWT flow (iss/aud/sub/iat/exp/company fields) is already built and tested for test-hosts, live-proven per commit 59385f4. The k-add badge ('New · build and test') is misleading — the verifier already exists and is tested; only real-platform key wiring remains (tracked under em-hostbackend, blocked). | delta.md em-backend row (rag_agent.md:99); em-token row (widget.md:128-130); commit 59385f4 |
| p4-s4_1-2 | 4.1.2 · Context from claims | already done | delta.md em-backend: 'auth_context.py already exist, fully built and tested' (rag_agent.md:99). This substep's own claims (company id, integration, subject from the note; allowed scopes from the integration map; unknown integration refused; principal empty for embedded users) are exactly what's already built and tested — the space_id gap flagged on r1-ctx belongs to substep 3.2.1, not this one, since this substep's text never mentions space_id. | delta.md em-backend row (rag_agent.md:99); r1-ctx row confirms space_id is the only missing field, not referenced by this substep's own Must-be-true |
| p4-s4_1-3 | 4.1.3 · The proxy forwards the note | already done | delta.md w-token: pilot invite token mechanism already deleted (widget.md:99,101-102). delta.md r1-proxy: 'x-widget-access-token no longer exists, the target (X-Obi-Token forwarding) is already built' (widget.md:109). This substep's Must-be-true (forward the bearer header unchanged; delete the pilot token path) is exactly what's already confirmed done. | w-token row (widget.md:99-102); r1-proxy row (widget.md:109); w-proxy row confirmed none |
| p4-s4_2-1 | 4.2.1 · The frame page | keep | delta.md: em-button (change: small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | em-button row(s) in delta.md |
| p4-s4_2-2 | 4.2.2 · obi.js | keep | delta.md: em-loader (change: small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | em-loader row(s) in delta.md |
| p4-s4_2-3 | 4.2.3 · The frame bridge | changed | delta.md em-loader: this substep's own Must-be-true/Proof say obi:clear 'blocks sending until a new note arrives' — delta.md confirms this is factually wrong: 'clear() forgets the token and closes the panel; an absent token degrades to general-only rather than blocking' (widget.md:136). Rewrote the blocking claim to the confirmed degrade-to-general-only behavior. | em-loader row (widget.md:136); HTML diff on obi-action-plan.html |
| p4-s4_2-4 | 4.2.4 · Integration chips | keep | delta.md: em-loader, em-token (change: large/small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | em-loader, em-token row(s) in delta.md |
| p4-s4_2-5 | 4.2.5 · Host context hints from the page | keep | delta.md: em-loader, r1-ctx (change: large/small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | em-loader, r1-ctx row(s) in delta.md |
| p4-s4_2-6 | 4.2.6 · Contracts | keep | delta.md: cm-contracts (change: small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | cm-contracts row(s) in delta.md |
| p4-s4_3-1 | 4.3.1 · Five test host pages | keep | delta.md widget.md:142-143: a multi-user test-host page and a 4-entry TEST_HOSTS local RS256 scaffold already exist, so some of this substep's five pages may already be scaffolded — but delta.md does not confirm the exact five (none/mews/toast/mews-2/choose) or their note endpoints against the substep's specific list, and em-hostbackend is itself a blocked Decision-needed panel. Left as keep; still real work remains. | widget.md:142-143 'code the design does not mention' entries; em-hostbackend row (blocked) |
| p4-s4_3-2 | 4.3.2 · The Data Hub pack | keep | delta.md: em-hostbackend (change: blocked) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | em-hostbackend row(s) in delta.md |
| p4-s4_3-3 | 4.3.3 · Mews, Toast and Opera Cloud packs | keep | delta.md: em-hostbackend, em-kb (change: blocked/none) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | em-hostbackend, em-kb row(s) in delta.md |
| p4-s4_3-close-em-token | Close: The signed note (JWT)  [Planned] | keep | delta.md em-token (large): JWT signing/verification is already built and live-proven for test-hosts (commit 59385f4); only real-platform key wiring remains before this panel can close as fully Implemented. Substep's [Planned] status label is stale for the test-host half but the close criterion (production-ready) is still open. | em-token row (widget.md:128-130) |
| p4-s4_3-close-em-hostbackend | Close: The platform&#x27;s note endpoint  [Decision needed] | keep | delta.md: em-hostbackend (change: blocked) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | em-hostbackend row(s) in delta.md |
| p4-s4_3-close-em-backend | Close: Obi checks the note and picks the pages  [Planned] | keep | delta.md em-backend (large): token_verifier.py and auth_context.py already built and tested; only real-platform onboarding remains before this panel closes. Same nuance as em-token. | em-backend row (rag_agent.md:99) |
| p4-s4_3-close-em-kb | Close: Obi picks the pages: the shared knowledge base  [Implemented, needs changing] | already done | delta.md: em-kb confirmed, change: none — not a Claims-table row in any synopsis (only a cross-reference in `shared.md:62`, "owned by platform/db RLS") | em-kb row in delta.md (change: none); design panel's own scope needs no further build |
| p4-s4_3-close-em-button | Close: The frame: the round button and the chat window  [Planned] | keep | delta.md: em-button (change: small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | em-button row(s) in delta.md |
| p4-s4_3-close-em-loader | Close: obi.js: one script tag  [Planned] | keep | delta.md: em-loader (change: small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | em-loader row(s) in delta.md |
| p4-s4_3-close-w-token | Close: The user token  [Planned] | keep | delta.md w-token (large): JWT per user, in-memory, bearer forwarding already built, ahead of the [Planned] label; only per-platform onboarding remains. | w-token row (widget.md:99-102) |
| p4-s4_3-close-sc-kb | Close: One knowledge base  [Implemented, needs changing] | keep | delta.md: sc-kb (change: small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | sc-kb row(s) in delta.md |
| p4-s4_3-close-sc-user | Close: A Mews user  [Planned] | keep | delta.md: sc-user (change: small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | sc-user row(s) in delta.md |
| p5-s5_1-1 | 5.1.1 · Migration 0011 on production | changed | delta.md cm-alembic (large): the target's described single '0011' migration bundling state+fingerprint+pending-job-index+curated-columns+two-policies+trace-columns does not match reality — the two RESTRICTIVE policies already shipped in migration 0010, the real 0011 only adds subject_hash, and scope_state/index_fingerprint/curated columns are absent through 0012. Rewrote Must-be-true/Proof/prompt to check the live alembic_version first and apply whatever remains, instead of assuming one bundled 0011. | cm-alembic row (alembic-and-scripts.md:74); ov-corpus row (alembic-and-scripts.md:70); HTML diff on obi-action-plan.html |
| p5-s5_1-2 | 5.1.2 · Drop the folder-root table | keep | delta.md d-source_scope: same blocked owner decision as 2.5.2, built to the CLAUDE.md default (keep until label-gated ingestion proven live). Substep already correctly frames this as the eventual action once that condition holds. | d-source_scope row (verdict: blocked) |
| p5-s5_1-3 | 5.1.3 · The never-disable guard | keep | delta.md: s-anon, cm-alembic (change: large/none) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | s-anon, cm-alembic row(s) in delta.md |
| p5-s5_2-1 | 5.2.1 · Freshness, recall and support telemetry | keep | delta.md: e-monitor (change: large) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | e-monitor row(s) in delta.md |
| p5-s5_2-2 | 5.2.2 · Latency and cost per question | keep | delta.md: e-ops (change: large) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | e-ops row(s) in delta.md |
| p5-s5_2-3 | 5.2.3 · Key rotation runbooks checked | keep | delta.md: s-edge, r1-auth (change: large) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | s-edge, r1-auth row(s) in delta.md |
| p6-s6_1-1 | 6.1.1 · Grow the gold set | keep | delta.md: e-gold, e-split (change: large) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | e-gold, e-split row(s) in delta.md |
| p6-s6_1-2 | 6.1.2 · Judges checked against people | keep | delta.md: e-judge (change: large) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | e-judge row(s) in delta.md |
| p6-s6_1-3 | 6.1.3 · Recalibrate everything | keep | delta.md: r4-weak, r5-coverage, r5-ground (change: large/small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | r4-weak, r5-coverage, r5-ground row(s) in delta.md |
| p6-s6_1-4 | 6.1.4 · The ledger rule | keep | No design-panel ref on this substep's refs line; no delta.md row applies. Description stands as written. | n/a — no design-panel ref |
| p7-s7_1-1 | 7.1.1 · Environments | keep | delta.md: cm-root, cm-infra (change: none/small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | cm-root, cm-infra row(s) in delta.md |
| p7-s7_1-2 | 7.1.2 · The webhook moves off the tunnel | keep | delta.md: i1-webhook (change: small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | i1-webhook row(s) in delta.md |
| p7-s7_1-3 | 7.1.3 · The frontend and the embed page online | keep | delta.md: em-loader, em-button (change: small) — the gap(s) delta.md found are exactly what this substep's Must-be-true/prompt already target as work still to do; no factual premise in the substep's own text contradicts delta.md's findings. | em-loader, em-button row(s) in delta.md |
| p7-s7_2-1 | 7.2.1 · Smoke and isolation on production | keep | delta.md: s-reader, s-anon all confirmed, change: none — target already holds. | s-reader, s-anon row(s) in delta.md, change column: none |
| p7-s7_2-2 | 7.2.2 · Alerts and runbooks live | keep | No design-panel ref on this substep's refs line; no delta.md row applies. Description stands as written. | n/a — no design-panel ref |
| p7-s7_2-3 | 7.2.3 · Activate the first platform | keep | delta.md em-hostbackend carries verdict 'blocked' — 'the platform signs directly, or an auth service the two teams agree on does' is a genuinely unresolved owner call per the panel's own status. Substep is itself a decide-kind item already deferring to that default. | em-hostbackend row (verdict: blocked, platform.md:131) |

## Added (new substeps)

None. Every substep whose delta.md rows carry a real (non-doc-fix) `small`/`large` change
already targets that exact gap in its own Must-be-true/Proof/prompt (confirmed by reading each
candidate's live HTML text against its delta.md row) — see the "changed" rows above for the six
cases where the substep's own text needed a factual correction, and the "keep" rows for the
remainder, where no factual correction was needed because the substep already correctly frames
the gap as work still to do. No substep's job has evaporated entirely (no "not needed" marks;
see hand-back for the two borderline candidates considered and rejected).

## Code the design does not mention — 60/60 placed (step 4)

Every synopsis-section-8 item from delta.md's "Code the design does not mention" list (60 items,
one per bullet) already has a home in an existing substep by folder/feature match — none needed
a new substep. Where an item is genuinely load-bearing for a substep's own scope (e.g. the
per-user identity short-circuit files, the `off_topic` refusal reason, the two shipped
migrations), that substep's row in the Marks table above already reflects it (either as a
"changed" edit or as delta.md evidence cited in a "keep"/"already done" reason). The rest are
minor implementation detail (internal helpers, test scaffolding, doc stubs, dependency-wiring
bundles) that extend an existing substep's scope without altering what that substep must build.

| folder | synopsis line (delta.md "code the design does not mention") | home substep | why it fits there |
|---|---|---|---|
| confluence_sync | `application/knowledge_scope_backfill.py:1-71` — the PLAN 10.7 pre-flip coverage check, exported at the feature root but no panel names it (confluence_sync.md:132). | p2-s2_5-1 | backfill/readiness-gate substep this pre-flip coverage check literally implements (2.5.1) |
| confluence_sync | `tests/test_scheduler.py:1-43` — tests `app.main._build_scheduler`'s dev-only fast-poll job (confluence_sync.md:133). | p0-s0_5-1 | test harness substep — dev-only scheduler behavior, protect-it scope |
| confluence_sync | `schemas/events.py:59-65,68-111` — `_as_int` and the nested/flattened webhook-payload tolerance (confluence_sync.md:134). | p0-s0_5-reg-ingestion-stage-1 | webhook payload tolerance folds into the i1-checks regression protection |
| ingestion | `domain/tokenization.py` — `TokenCounter`, no panel names it directly (ingestion.md:125). | p0-s0_5-reg-ingestion-stage-3 | child/parent token counting ties to i3-parents/i3-children sizing |
| ingestion | `application/services.py` — `IngestionServices`/`build_ingestion_services`, the dependency-wiring bundle (ingestion.md:126). | p1-s1_1-2 | dependency-wiring bundle is part of the one-dependency-direction move |
| ingestion | `domain/change_detection.py:80-101` — `index_config_changed` (ingestion.md:127). | p2-s2_2-2 | index_config_changed feeds classification-without-version-guard (2.2.2) |
| ingestion | `application/contextualizer.py:34-80,125-129` — meta-refusal detection, real and tested, no panel (ingestion.md:128). | p0-s0_5-reg-ingestion-stage-3 | meta-refusal detection ties to i3-context's contextualizer scope |
| ingestion | `domain/normalization.py:149-170,173-181` — `build_sections`, `content_hash`/`structure_hash` (ingestion.md:129). | p0-s0_5-reg-ingestion-stage-3 | build_sections/content_hash/structure_hash tie to i3-blocks normalization |
| retrieval | `application/retriever.py:222,234` — `retrieve()` vs `retrieve_with_context()` as two distinct public methods (retrieval.md:127). | p3-s3_1-1 | retrieve() vs retrieve_with_context() is the provenance/context-threading work of 3.1.1 |
| retrieval | `application/retriever.py:9-10` — the `RankFn` eval-harness seam (retrieval.md:128). | p3-s3_0-2 | RankFn eval-harness seam feeds the gold-set/eval substep |
| retrieval | `infrastructure/search_repo.py:52-55` — `KNOWLEDGE_SCOPE_WILDCARD = "*"` sentinel (retrieval.md:129). | p2-s2_5-3 | KNOWLEDGE_SCOPE_WILDCARD sentinel is part of the scope-state/label-gated filter work |
| retrieval | `__init__.py:15-16` — the feature-root import-boundary rule (ADR-features-import-only-through-public-root machinery, not a design claim) (retrieval.md:130). | p1-s1_1-2 | feature-root import-boundary rule is the one-dependency-direction machinery |
| retrieval | `infrastructure/search_repo.py:130-131` — `_vector_literal` helper (retrieval.md:131). | p3-s3_1-2 | _vector_literal is dense-search plumbing under the fusion-by-piece substep |
| rag_agent | `domain/identity.py:1-91`, `application/answer_service.py:207-214`, `infrastructure/llm_client.py:97-103,221-241`, `domain/prompt.py:136-186` — the entire per-user identity short-circuit, a third short-circuit alongside small-talk and clarification (rag_agent.md:102). | p1-s1_1-1 | per-user identity short-circuit; the code-map move substep (cm-agent target: add identity.py/auth_context.py/token_verifier.py) already names these files |
| rag_agent | `domain/refusal.py:24-34,42,79-80`, `settings.py:119-127`, `answer_service.py:113-116,296-302` — the `off_topic` refusal reason and its own threshold (rag_agent.md:103). | p3-s3_5-2 | off_topic refusal reason — folded directly into this substep's corrected reason list (see changed-substep edit above) |
| rag_agent | `application/answer_service.py:130-132,289-302` — `_HANDOFF_REASONS`, which refusal reasons log a human-handoff line (rag_agent.md:104). | p3-s3_5-2 | _HANDOFF_REASONS — matches this substep's own 'human hand-off' clause |
| rag_agent | `settings.py:178-186` — `chat_answer_cache_ttl_seconds`/`max_entries` backing `CachingAnswerService` (rag_agent.md:105). | p3-s3_2-7 | answer-cache TTL/max-entries settings are exactly what 'Remove the answer cache' (3.2.7) removes |
| evaluation | `metrics/fallback_metrics.py:18,27` — `fallback_rate`, `citation_grounding_rate`, exported and tested, no panel names them (evaluation.md:78). | p3-s3_0-2 | fallback_rate/citation_grounding_rate are stage-4 grading-harness metrics |
| evaluation | `run_baseline.py:93-157` — Markdown/JSON rendering of the rerank-lift report (evaluation.md:79). | p0-s0_5-reg-code-map | rerank-lift report rendering ties to cm-eval's location-list correction (folder-level, protect-it) |
| evaluation | `README.md:1-85` — feature-local README on the five eval kinds (evaluation.md:80). | p0-s0_5-reg-code-map | feature README is documentation, no build implied |
| platform | `logging/setup.py` — `configure_logging`, `get_logger` (platform.md:134). | p0-s0_5-reg-code-map | logging/ inventory addition (delta.md: cm-platform target 'add logging/ to the inventory') |
| platform | `db/schema.py`'s `ensure_extensions`, `create_enum_types`, `drop_enum_types`, `create_all`, `drop_all`, `drop_chunk_rls`, `drop_chunk_scope_rls`, `drop_curated_scope_rls`, `enable_non_chunk_rls`, `disable_non_chunk_rls`, `apply_reader_rls`, `drop_reader_rls`, `_grant_extensions_access` (platform.md:135). | p0-s0_5-reg-security | schema.py RLS enable/disable/apply helpers are the security-lock machinery s-source/s-acl protect |
| platform | `db/base.py` — `Base`, `NAMING_CONVENTION` (platform.md:136). | p1-s1_1-1 | Base/NAMING_CONVENTION is base ORM wiring covered by the folder move |
| platform | `db/enums.py` — `ChangeClass`, `EventProcStatus`, `ReconStatus`, `PG_ENUMS` (platform.md:137). | p1-s1_1-1 | enum module is base model wiring covered by the folder move |
| platform | `clients/anthropic_client.py`'s `ImageBlock`, `cached_system_block` (platform.md:138). | p0-s0_5-reg-code-map | anthropic_client ImageBlock/cached_system_block ties to r5-generate/r5-image protection |
| platform | `clients/embeddings_client.py`'s `LocalEmbeddingProvider` (platform.md:139). | p0-s0_5-reg-the-vector-database | LocalEmbeddingProvider ties to vd-model's embedding-provider scope |
| platform | `clients/reranker_client.py`'s `LocalReranker` (platform.md:140). | p0-s0_5-reg-retrieval-stage-4 | LocalReranker ties to r4-rerank protection |
| platform | `clients/confluence_client.py`'s `ConfluenceCircuitBreakerOpenError`, `list_space_pages`, `get_page`, `close()` (platform.md:141). | p0-s0_5-reg-ingestion-stage-1 | confluence_client helpers tie to i1-checks/i1-handle protection |
| platform | `config/settings.py`'s chat/idempotency/answer-cache/HNSW/clarification/refusal-threshold settings block, ~lines 104-243 (platform.md:142). | p1-s1_1-1 | settings.py block is exactly what the code-map move inventories |
| platform | `config/platforms.py` (`PlatformRegistry`, `PlatformEntry`, `load_platform_registry`) and `config/platforms.json`/`platforms.local.json` (platform.md:143). | p1-s1_2-3 | platforms.py/platforms.json — this substep (1.2.3) already builds/tests the platform list |
| platform | `config/obi_identity.md` and `Settings.obi_identity_text`/`platform_registry` properties (platform.md:144). | p4-s4_1-2 | obi_identity.md / obi_identity_text / platform_registry feed 'Context from claims' (4.1.2) |
| shared | `hashing.py`'s six functions beyond `hash_json`/`sha256_text`: `sha256_bytes`, `normalize_text`, `canonical_json`, `hash_labels`, `hash_access_scope`, `hash_attachment_manifest` (shared.md:68). | p3-s3_2-7 | extra hashing.py functions are cm-shared scope, referenced by 'Remove the answer cache' (3.2.7) |
| shared | The boundary contract in `__init__.py:4-6` and its enforcement in `tools/check_feature_boundaries.py:46-103` (shared.md:69). | p1-s1_1-2 | boundary contract + check_feature_boundaries.py is exactly the one-dependency-direction substep |
| shared | `TTLCache`'s insertion-order (not LRU) eviction policy, documented only in its own docstring (shared.md:70). | p3-s3_2-7 | TTLCache eviction policy — same cm-shared scope |
| shared | `SlidingWindowRateLimiter`'s `max_tracked_keys` bounded-memory fix, PLAN 4.6.4 (shared.md:71). | p0-s0_5-reg-retrieval-stage-1 | SlidingWindowRateLimiter bounded-memory fix ties to r1-limits protection |
| alembic + scripts | `alembic/versions/0011_query_trace_subject_hash.py` and `0012_widen_document_version_idem.py` — two shipped migrations no panel names individually (alembic-and-scripts.md:105). | p2-s2_4-1 | the two shipped migrations are exactly what the fingerprint-reconciliation edit above (2.4.1) now accounts for |
| alembic + scripts | `alembic/env.py`, `alembic/script.py.mako` — environment wiring and the migration template (alembic-and-scripts.md:106). | p0-s0_5-1 | env.py/script.py.mako are the test-harness/migration-tooling substep's own scope |
| alembic + scripts | `scripts/setup_supabase.py`'s `_pgvector_version`, `_derive_reader_url`, `_check_anon_denied`, `_check_reader_scope_axis` internal helpers (alembic-and-scripts.md:107). | p0-s0_5-reg-security | setup_supabase.py isolation-check helpers are s-anon/s-reader protection |
| alembic + scripts | `scripts/verify_knowledge_scope_live.py:187-209` — `_prove_receipt_entrypoint` (alembic-and-scripts.md:108). | p2-s2_5-3 | _prove_receipt_entrypoint feeds the freshness proof substep (2.5.3) |
| alembic + scripts | `scripts/rotate_chat_api_key.py` in its entirety — no panel references key rotation at all (alembic-and-scripts.md:109). | p5-s5_2-3 | rotate_chat_api_key.py is exactly what 'Key rotation runbooks checked' (5.2.3) rehearses |
| widget | `src/app/test-hosts/multi/page.tsx` + `multi-user-content.tsx` — the multi-user switcher proving per-user identity live, git `59385f4` (widget.md:142). | p4-s4_3-1 | multi-user test-host page is directly relevant scaffolding for 'Five test host pages' (4.3.1) |
| widget | `src/app/api/test-hosts/config.ts` and its four `TEST_HOSTS` entries — local-only RS256 scaffolding (widget.md:143). | p4-s4_3-1 | TEST_HOSTS local RS256 scaffold is directly relevant scaffolding for 4.3.1 |
| widget | `src/features/chat/ui/menu.tsx`, `menu-item.tsx`, `icon-button.tsx`, `language-menu.tsx`, `contour-background.tsx`, `assistant-mark.tsx`, `image-lightbox.tsx`, `typing-indicator.tsx` — UI primitives, individually untested by any panel (widget.md:144). | p1-s1_1-1 | UI primitives are components/ inventory covered by the code-map move |
| widget | `src/components/ui/button.tsx` + `src/components/README.md` — an unused/placeholder-adjacent `components/` root (widget.md:145). | p1-s1_1-1 | unused components/ root — code-map inventory, no build implied |
| widget | `src/platform/README.md` — documentation stub (widget.md:146). | p1-s1_1-1 | platform/ README stub — code-map inventory, no build implied |
| widget | `src/test-stubs/server-only.ts` — Vitest server-only shim (widget.md:147). | p0-s0_5-1 | Vitest server-only shim is test-harness scope |
| widget | `src/app/(site)/dev-preview-backdrop.tsx` — dev-only decorative wrapper (widget.md:148). | p1-s1_1-1 | dev-only decorative wrapper — code-map inventory, no build implied |
| widget | `packages/contracts/src/token-claims.json` — already built (see cm-contracts verdict above) (widget.md:149). | p4-s4_2-6 | token-claims.json — 'Contracts' substep (4.2.6) is exactly where this is verified built |
| packages/config/infra/docs | `packages/contracts/package.json`, `tsconfig.json`; `packages/design-tokens/package.json`, `tsconfig.json` — pnpm-workspace manifests (packages-config-infra-docs.md:80). | p1-s1_1-1 | workspace manifests are code-map/folder-move inventory |
| packages/config/infra/docs | `packages/contracts/src/openapi/chat.yaml:1-389` — the full OpenAPI document, never walked panel-by-panel (packages-config-infra-docs.md:81). | p4-s4_2-6 | the full OpenAPI document is exactly what 'Contracts' (4.2.6) covers |
| packages/config/infra/docs | `config/platforms.local.json:1-72` — local-only override registry for browser testing (packages-config-infra-docs.md:82). | p4-s4_3-1 | platforms.local.json is local override scaffolding for the five test-host pages |
| packages/config/infra/docs | `config/obi_identity.md:1-25` — the static-facts prompt block for the per-user identity path (packages-config-infra-docs.md:83). | p4-s4_1-2 | obi_identity.md static-facts block feeds 'Context from claims' (4.1.2) |
| packages/config/infra/docs | The large `docs/` prose corpus (`OBI-RAG-SYSTEM-A-Z.md`, `docs/final_design/*`, `docs/rag/*`, `docs/embedding/*`, runbooks, `obi-system-brief.md` itself, etc.) — none named by any of the 22 assigned panel ids in that synopsis's scope; per CLAUDE.md, archived and non-authoritative until reviewed (packages-config-infra-docs.md:84). | p0-s0_1-4 | the large docs/ prose corpus is exactly what 'Archive the old docs' (0.1.4) is meant to move |
| packages/config/infra/docs | `docs/adr/0006`, `0007`, `0010`, `0014` — four ADRs beyond `cm-docs`'s nine named ones; supersession chain spot-checked as internally consistent (packages-config-infra-docs.md:85). | p1-s1_1-3 | the four extra ADRs are CLAUDE.md/design-page-follows scope (1.1.3, cm-docs) |
| packages/config/infra/docs | `apps/automation/tools/panel.py`, `tests/tools/test_panel.py`, `test_agent_guard.py` — the audit tooling itself (packages-config-infra-docs.md:86). | p0-s0_2-3 | the audit tooling itself is exactly what 'The panel reader' (0.2.3) built |
| entrypoint | `_WORKER_OWNER = "in-process-worker"` constant (entrypoint.md:80). | p0-s0_5-reg-code-map | _WORKER_OWNER constant is cm-root protect-it scope |
| entrypoint | `dev_lightweight_reconcile` — the DEV-only fast-poll scheduler job, not named on cm-root's step 5 (entrypoint.md:81). | p0-s0_5-reg-code-map | dev_lightweight_reconcile — cm-root's own step-5 scheduler list, protect-it |
| entrypoint | `GET /health` — neither cm-root nor sc-backend's "today" line mentions a health probe (entrypoint.md:82). | p0-s0_5-reg-code-map | GET /health — cm-root/sc-backend inventory gap, protect-it |
| entrypoint | `app.state.rate_limiter` construction (entrypoint.md:83). | p0-s0_5-reg-retrieval-stage-1 | app.state.rate_limiter construction ties to r1-limits protection |
| entrypoint | `app/__init__.py:8` — `__version__ = "0.2.0"` (entrypoint.md:84). | p0-s0_5-reg-code-map | __version__ constant — cm-root inventory, protect-it |

## Needs live — 12/12 already covered by substep 0.5.3 (step 5)

Substep `p0-s0_5-3` ("0.5.3 · The regression suite, retrieval") already names the mechanism
that consumes this whole list by reference, in its own prompt step 2: "Read the ... 'needs live'
list in docs/Final_docs/0.4-design-review/delta.md. Run the live isolation script against staging
... For each 'needs live' row: mark it green ... or red ...". Every one of the 12 items in
delta.md's "Needs live" section (ov-corpus, cm-infra, cm-docs, i3-children, i3-embed/vd-model
family, ov-filter, r3-scope/s-scope/tg-filter, s-writer, sc-user, e-ops, em-hostbackend,
ov-auth-step-5) is read and checked by this one mechanism when 0.5.3 runs — none needed a new
substep, and none needed a name-by-name rewrite of 0.5.3's own prompt, since the prompt already
points at the whole delta.md list rather than enumerating items individually. This is recorded
here rather than as an HTML edit because 0.5.3's text was already correct before this substep.

## Sanity check (step 6)

`grep -c 'data-id="p[0-9]' docs/Final_docs/obi-action-plan.html` → 187 (unchanged from the
187 before this substep — 0 substeps added, matching the empty Added table above).
`grep -c '0.4.3 correction' docs/Final_docs/obi-action-plan.html` → 6 (matching the six
"changed" rows in the Marks table: p5-s5_1-1, p2-s2_4-1, p3-s3_5-2, p3-s3_5-3, p3-s3_6-6,
p4-s4_2-3).

---

## Amendments implemented 2026-09-18 (answers to the 0.5 questions)

The owner amended the action plan (0.1.1, the 0.5.3 widget batch, 0.6.1, 2.4.3, 3.2.6, 7.1.1) and
answered the open questions from the 0.5 regression phase. This section records what was actually
changed in the tree, per substep. Nothing here changed a business rule; every code change either
made the code match the design page (design page wins) or added a test that pins current behavior.

| substep | change made | files |
|---|---|---|
| 0.1.1 (freeze) | Cut annotated tag **and** branch `pre-target-2026-09-14` on the starting commit `bf7fece829e3ce1e9757e1bdb5fa538fbd6456ae` (from the 0.3 audit README), cut late on 2026-09-18. Recorded the test state in a new `docs/snapshot/README.md`. | `docs/snapshot/README.md` (new); git tag+branch (local only, not pushed) |
| 0.5.3 widget batch | Batch is now 7 panels (w-scope removed). Coverage-map widget level relabelled `component (jsdom, not a real browser)` → `jsdom` for the 7 built panels; `make test-ui` run once (1 passed, the mount smoke). | `docs/Final_docs/0.5-regression-tests/coverage-map.md` |
| 0.5.3 / w-scope | Design page wins: w-scope is `change`, not built. Added a **Close item `p3-s3_2-close-w-scope`** to the Phase 3 · Stage 1 · The gate close list (count 3 → 4); it only flips status once 1.2.2 and 3.2.2 build it. Coverage-map w-scope row marked `change (not counted)` with the Close-item reference. | `docs/Final_docs/obi-action-plan.html`, `docs/Final_docs/0.5-regression-tests/coverage-map.md` |
| 0.6.1 (decisions) | Rewrote `docs/plan/decisions.md` as the canonical list: 15 settled calls (2026-09-14) + 4 added 2026-09-18 (i2-fetch, i4-failed, widget-test-level, r1-limits-ipkey) + 4 open lines (freshness-target, latency-budget, rerank-depth, trusted-proxy-hops). Repointed `regression-decisions.md` to it. | `docs/plan/decisions.md`, `docs/Final_docs/0.5-regression-tests/regression-decisions.md` |
| r1-limits (3.2.6/7.1.1 prep) | Corrected the r1-limits panel today-line (and a second panel repeating the claim) to what the code does — keyed on `request.client.host`, no XFF parsing today. Added regression test `test_r1_limits_untokened_key_is_client_host_and_ignores_x_forwarded_for` (a forged XFF changes nothing). The `TRUSTED_PROXY_HOPS` setting + its four tests belong to 3.2.6; 7.1.1 sets the real hop count. | `docs/Final_docs/obi-rag-system-flow.html`, `apps/automation/app/features/rag_agent/tests/test_edge_auth.py`, `docs/Final_docs/0.5-regression-tests/coverage-map.md` |
| r1-small | Design page wins (owner: "could be Haiku, doesn't matter"): `generate_small_talk` now uses `small_talk_model`, wired to `settings.routing_model` (Haiku) in `main.py`; grounded `generate()` keeps `answer_model`. Rewrote the pinning test and added a fallback test. | `apps/automation/app/features/rag_agent/infrastructure/llm_client.py`, `apps/automation/app/main.py`, `apps/automation/app/features/rag_agent/tests/test_llm_client.py`, coverage-map |
| naming rule | Added panel-id docstrings to 4 cited tests that named no panel (i1-checks, i1-ledger, i2-meta, r4-weak). | `test_webhook.py`, `test_worker_sync.py`, `test_refusal.py` |
| future-ideas | Deferred (owner can't answer yet): em-hostbackend agreed auth service, ov-auth real signing key, sc-user per-person identity, cm-docs 4 missing ADRs. Marked the r1-limits drift resolved. | `docs/future-ideas.md` |

Verification: `make boundaries` clean; `make test-unit` 535 passed (was 533, +2 new tests);
`make test-ui` 1 passed; ruff/format/pyright clean on every touched backend file. `make test-db`
not re-run this pass (no db-level change was made — the new tests are unit-level).

### Re-verification of #8 (path drift) — STILL OPEN

The owner believed the `docs/Final_docs/…` vs `docs/Final_docs/…` path drift was corrected. On disk it is
not: `docs/Final_docs/` contains only `0.5-regression-tests/`. The action plan still references
`docs/Final_docs/0.3-synopsis-of-today/` (substeps 0.3.1, 0.3.2) and `docs/design/obi-rag-system-flow.html`
(0.2.3), while the real files live under `docs/Final_docs/0.3-code-vs-design-audit-2026-09-14/`,
`docs/Final_docs/0.3-synopsis-2026-09-16/`, and `docs/Final_docs/obi-rag-system-flow.html`. The
ledger is `docs/Final_docs/ledger.md`, not `docs/plan/ledger.md`. These path references should be
corrected to the real locations in a dedicated pass; left unchanged here to avoid a broad find-replace
across the 450 KB plan without the owner's go-ahead on the exact target paths.

---

## Sync-rules corrections — substep 2.2.4 series (§13 step 1), 2026-09-24

The owner-approved sync-rules plan (`docs/Final_docs/sync-rules/plan.md`, decisions D1–D4) is the
resolution of the `live-0.5.3-cm-docs` "decision needed" in `docs/plan/decisions.md`: fix the code
to match never-bend rule 1/5, and retire `scope_state`. These panel moves land as the §13 series
executes. **Step 1 (delete/classified purge + restore) is done**; the panel `today`/status flips on
`obi-rag-system-flow.html` and `obi-action-plan.html` are batched to the end of the series (§13
step 6), so this pass records the corrections and flips only the panels whose target is fully met.

| panel / substep | mark | reason (what changed vs the design page as written) |
|---|---|---|
| `i2-gone` | changed | Delete/trash/archive and `classified` now **purge** every row (chunk, document_version, document, page_source, page_restriction), not soft-deactivate. Last-recognized-label-removed trigger still pending (§13 step 2). `today` line updated; status stays `change` until the series completes. |
| `tg-classified` | built | Fully met by step 1: the reserved `classified` label detected on raw labels → `purge_page` → zero rows; restore/re-tag re-indexes as a first index. Proven by `test_in2_classified_label_removes_rows`. Status flipped to `built`. |
| `tg-purge` | changed → built | The mechanism (`purge_page`) is built and tested, BUT its design wording ("Keeps `page_source` with state `classified` so the sweep knows to skip it") is **corrected**: purge deletes `page_source` too. That "keep with state" rested on the `scope_state` enum, which D4 retires; restore is now a first index (`page_source` gone → `local is None`). Security outcome (never leaks) is preserved by deleting the rows outright + RLS fail-closed (D3, §13 step 4). |
| `tg-deactivate` | changed | `deactivate_page` (flip `is_active`, leave rows) is **no longer** the delete/classified path — replaced by purge. `deactivate_page` survives only for the reconciliation source-scope-loss sweep (unchanged this substep). The strict-xfail `test_delete_marks_the_active_version_superseded` (decisions row `tg-deactivate-xfail`) is retired: purge deletes the `document_version` row, so there is no superseded state to assert. |

Panels moved by later steps of this series (recorded here for the map, flipped when their step
lands): `tg-remove`/`ks-index` membership (§13 step 2); `tg-two`/`tg-conflict`/`tg-state` +
`scope_state` retirement (§13 step 3, D4); `3.4.1` RLS fail-closed (§13 step 4, D3); `i3-embed`
no-reuse, `i2-rebuild` title, `i4-gc` retain-0 (§13 step 5, D1); `2.4.3` rollback retired (D1).

## Sync-rules corrections — substep 2.2.4 series (§13 step 2: rule 2 + membership gate), 2026-09-24

Label-gated membership is now enforced in `sync_service.handle_sync_page`: a page is in the index
only while it carries at least one recognized knowledge-scope label (from
`knowledge_scopes.json`). Removing the last recognized label purges the page (rule 2); a first-seen
page with no recognized label is never ingested (never-bend rule 5). This resolves the "fix the code
to match rule 5" arm of the `live-0.5.3-cm-docs` decision-needed in `docs/plan/decisions.md`.

| panel / substep | mark | reason (what changed vs the design page as written) |
|---|---|---|
| `tg-remove` | build → **built** | Removing the last recognized label (or leaving only unrelated labels) now **purges** every row — corrected from the panel's original "deactivate" wording, the same `deactivate → purge` correction already applied to `i2-gone`/`tg-purge` in step 1 (D-decisions retire soft-deactivate for tag loss). Proven by `test_sync_rules_membership.py`. |
| `ks-index` | built (today-line updated) | Adds the **negative** half of membership: not just "a tagged page goes in", but "an untagged page never goes in". The gate is unconditional — **no feature flag**. The action-plan 2.2.4 body mentions "a cut-over flag with default on"; this was built **without** any flag, matching 2.2.4's own "Must be true" line ("A page with no tag from the map leaves the index, always, with no feature flag") and never-bend rule 5. Flip recorded as a deliberate simplification. |
| `i2-gone` | changed (today-line updated) | Its "unlabeled" trigger is now live (last-recognized-label-removed → purge), completing the three triggers the panel names (delete, classified, unlabeled). Status stays `change` pending the step-4 RLS fail-closed defense-in-depth and the deferred live proof. |

**Gate discriminator (design clarification):** membership keys on `scope_result.matched_labels`
(recognized labels *present*), **not** the resolved `scope_result.tags`. A page with two conflicting
provider labels resolves to zero tags this sync (the conflict branch, retired in step 3) yet still
carries recognized labels, so it **stays indexed** rather than being purged and immediately
re-indexed when step 3 makes it visible in both scopes. The still-green `test_ingestion_pipeline.py`
conflict tests pin this.

**Source_scope roots coexist with the gate (not retired):** a `source_scope`-root-covered page is
still swept and tagged by reconciliation, but the root no longer *grants membership* — the covered
page must also carry a recognized label to be indexed; the root's tags union on top. This matches
step 1's recorded stance that `deactivate_page`/reconciliation source-scope-loss survives unchanged.
`test_reconciliation.py`'s two root tests were updated to give covered pages a recognized label.

**Test-fixture consequence (disclosed):** the generic DB fixtures (1001/1002/2002/3005/3007/3010)
carry only unrelated labels, so the gate makes them un-indexable. The shared `index_page` helper now
injects the base `obi-general-test` scope **only when a page has no recognized label** (preserving
scope-tagging tests that set their own recognized label), so the ~two dozen versioning/chunk/gc/
worker tests that don't care about tags keep seeding a page. 14 tests across 12 files were adjusted:
either given an explicit recognized label (direct `handle_sync_page`/enqueue paths that bypass
`index_page`), or — for three RLS **source-axis** tests that relied on the empty-tags floor to see
chunks — opened on the orthogonal knowledge-scope axis with the `'*'` wildcard, or — for
`test_scope_tagging_add`/`test_reindex`/`test_verify_isolation_script` whose premise *was* an
"indexed-but-untagged page" — rewritten to the post-gate reality (that state no longer exists;
`test_verify_isolation_script` forces empty tags directly via SQL to still exercise the script's
legacy-untagged branch until the step-4 backfill).

## Sync-rules corrections — substep 2.2.4 series (§13 step 3: drop conflict + retire scope_state), 2026-09-24

Decision D4 is implemented: two or more recognized provider labels on one page is **legitimate
sharing**, not a conflict. `resolve_knowledge_scope_tags` now returns *all* matched recognized tags
(the `conflict` flag and the `provider_tags` branch are gone), and `sync_service.handle_sync_page`
no longer emits the `knowledge_scope_conflict` warning. A shared page (`[mews,toast]`) resolves to
both tags and is visible in each of those scopes by plain overlap (`chunk.tags && allowed_scopes`),
never public; the explicit `general` tag — in every user's scope set — is the only "everywhere".

**`scope_state` is retired.** It never existed in code (no enum, no `chunk`/`page_source` column, no
consumer) — confirmed by grep across `backend/` and `knowledge-base/`; every prior `scope_state`
mention was a test docstring/comment stating "state is the tag set on `tags`", or design/plan prose.
So retirement is a plan/design-level act, not a schema migration: the design targets an unbuilt
`scope_state` enum, and D4 removes the only non-`ok` value that mattered (conflict). State remains
materialized as `tags` (ADR-scope-state-materialized-as-tags).

Mirroring steps 1–2, the design-page **status** flips are batched to §13 step 6; this pass records
the corrections and updates the affected panels' `today` lines only.

| panel / substep | mark | reason (what changed vs the design page as written) |
|---|---|---|
| `tg-two` | changed → built (flip batched to step 6) | Target "two provider labels → hidden from everyone" is **retired**: the page is now visible in each tagged scope (sharing), never public. Proven by `test_sync_rules_visibility.py::test_tags_shared_page_visible_in_both_scopes`. `today` line updated; status flip deferred because the *target text* itself changes under D4 (never edited in place per CLAUDE.md — reconciled on the page in step 6). |
| `tg-conflict` | retired | There is no conflict/hide outcome. Two provider labels share both scopes; no `knowledge_scope_conflict` log line is emitted. The retired `test_s_audit_knowledge_scope_conflict_log_line_emitted_on_conflicting_labels` proved that per-sync log line — the `s-audit` panel's audit trail keeps its `webhook_event` and `reconciliation_run` coverage via their own dedicated tests. |
| `tg-state` / `scope_state` | retired | Never built in code; the conflict state it would have carried is gone (D4). State stays materialized as `tags`. No column, enum, or RLS state-predicate is introduced. |
| `i2-labels` | changed | Resolution is now "every recognized label becomes a tag" (no conflict zeroing), visibility by overlap. The panel's remaining delta — empty-tags = **private** (fail-closed), not the current empty-tags = public RLS floor — is decision D3 and lands in §13 step 4 (migration 0014); `i2-labels` stays `change` until then. |
| `2.2.3` (Labels to scope state) | retired/absorbed | This substep specified the `scope_state` enum + a conflict state written on the page/chunks. Both are retired (D4 + scope_state never built). Its surviving intent — recognized labels → tags on `page_source`/`chunk`, `classified` handled, unlabeled → out — is delivered by 2.2.4 (§13 steps 1–3). No enum work remains. |
| `2.5.1` (Backfill + readiness gate) | changed | The gate's premise ("zero rows outside `ok`") assumed the `scope_state` enum. With scope_state retired, the readiness concern becomes the D3 empty-tags backfill (Q-B): audit active chunks with `tags=[]` before the RLS floor flips fail-closed. Re-scoped into §13 step 4; the enum-state gate is dropped. |

**Membership discriminator unchanged (step-2 note now fully cohered):** the gate still keys on
`scope_result.matched_labels`. After step 3 a shared page's `matched_labels` equals its resolved
`tags` (both providers), so the gate and the visibility are consistent; a shared page is never
purged-and-re-indexed.

**Rule 11 (eval before/after):** the gold-set baseline (`make eval`) is **byte-identical** before
and after the change (only the run label differs). Honest caveat: the bundled baseline ranker is a
trivial fixture ranker that does not route through knowledge-scope resolution, so it cannot move on
this change; the real visibility proof is the db+retrieval tests in `test_sync_rules_visibility.py`.
The number confirms no gold-set regression.

## §13 step 4 — RLS floor fail-closed (D3) + read-path overlap (2026-09-24)

| panel / substep | mark | reason (what changed vs the design page as written) |
|---|---|---|
| `3.4.1` / `r3-scope` | changed → built (DB level; flip batched to step 6) | Migration `0014_chunk_scope_fail_closed.py` drops `OR cardinality(tags) = 0` from `chunk_scope_read` (mirrored in `schema.py::apply_chunk_scope_rls`). An empty-tags active chunk is now visible to **no** scope — "public" is the explicit `general` tag, never empty tags (D3). Proven by `test_sec_empty_tags_visible_to_no_scope` (red today → green) and the reversible migration test `test_0014_*`. The panel's **target predicate** still reads `scope_state = 'ok' AND (…)`; the `scope_state = 'ok'` conjunct is **retired** (D4/§7 — `scope_state` never built) and is *not* added — the target-text reconciliation and status flip are batched to step 6 (never edited in place per CLAUDE.md). |
| `i2-labels` | changed → complete (flip batched to step 6) | The empty-tags = **private** half (the delta left open after step 3) is now delivered by 0014. `i2-labels` no longer has an outstanding code delta; its status flip joins the step-6 batch. |
| `r3-classified` | unchanged | The `scope_state` enum this panel describes stays retired (D4). Not built; not part of step 4. |

**`'*'` opt-out retained (deliberate):** the fail-closed policy keeps `current_setting(_scope_guc) = '*'` as an unrestricted opt-out for the internal/eval path and the already-authorized parent expansion (`retriever.py::fetch_parent_texts`). The public `/chat` path always resolves a real scope list, never `'*'`. Asserted by `test_scope_rls_wildcard_is_an_explicit_opt_out` and the wildcard leg of `test_sec_empty_tags_visible_to_no_scope`.

**Curated policy untouched (D3):** `apply_curated_scope_rls` keeps its `cardinality(tags) = 0` floor — operator-authored curated entries are intentionally global. Confirmed by `test_0014_drops_the_empty_tags_floor` (asserts the curated floor survives) and `test_curated_scope_rls_isolates_tagged_entries_but_keeps_global`.

**Replaced test:** `test_scope_rls_untagged_chunk_is_global_visible_under_any_scope` (which asserted the now-removed floor — "untagged is global") was **rewritten in place** into `test_sec_empty_tags_visible_to_no_scope` (fail-closed). No behaviour is left unasserted; the old assertion contradicted D3.

**Q-A resolved (correcting the step-1 §0 note).** The step-1 discovery claimed "the test env already runs `enable_knowledge_scope_filtering` **True**". That was a **misread**: the code default *and* the test-env default are **False** (`settings.py:281`; `test_settings.py:56-57` asserts the default is False; `backend/conftest.py` never sets it). What is actually True is that individual retrieval tests pass `enable_knowledge_scope_filtering=True` **directly to the `HybridRetriever` constructor** (per-test wiring of the app-layer predicate), not via env/Settings. Decision: **keep the code default False for step 4.** RLS fail-closed (D3) is the security boundary and is **flag-independent** (the policy never reads the flag). The app-layer predicate is redundant defence-in-depth; flipping the default to True is already deferred to PLAN 10.7's operator `.env` (per the note at `test_settings.py:49-51`), not changed here. The `make eval` before/after is byte-identical, so there is no eval basis to accelerate the flip. Q-A closed: no default change.

**Q-B still outstanding (deploy-time, owner-blocked):** before applying 0014 to Supabase, run a one-off audit listing active chunks with `tags = []` and re-tag any legitimately-global page with `general`. Steps 1–3 already guarantee active chunks carry ≥1 recognised tag, so the code change is safe; the backfill is a pre-deploy safety check, reported in the PR, never auto-mutated.

## §13 step 5 — rule 6: no reuse + title rebuild + retain 0 (2026-09-24)

Substep 2.3.1. Design-page **status** flips are batched to §13 step 6 (mirroring steps 1–4); this
pass records the corrections and updates the panels' today-lines.

| panel / substep | mark | reason (what changed vs the design page / action plan as written) |
|---|---|---|
| `i3-embed` | changed → built (flip batched to step 6) | `_resolve_children` no longer consults `diff_chunks`: every child is contextualised and embedded afresh on every rebuild (no `stable_key` reuse). The panel's `Note`/`Reuse` target text ("only changed children are embedded (stable_key reuse)") is now stale and reconciled in step 6. Proven by `test_in3_body_edit_reembeds_every_chunk_no_reuse` + `test_in3_title_change_reembeds_every_chunk`. |
| `i2-rebuild` | changed → built (flip batched to step 6) | A rename now triggers a rebuild — `ChangeClass.title_changed` added to `_REBUILD_CLASSES`. Safe on `uq_document_version_idem` (a title edit bumps `cf_version`). The panel's `Reuse: … target: no reuse` line is now satisfied. |
| `i4-gc` | changed → built (flip batched to step 6) | Retain changed **2 → 0** (`DEFAULT_RETAIN_SUPERSEDED = 0`, D1): the just-superseded version and its chunks are deleted in the swap transaction. The panel's `Keep: the two most recent superseded versions` target is superseded by retain-0 and reconciled in step 6. |
| `vd-swap` | changed → built (flip batched to step 6) | Step 3 of the panel ("Rows are deleted after two more versions") becomes "rows are deleted in the same swap" under retain 0. Target-text reconciliation batched to step 6. |
| `2.4.3` (Gate, GC and **rollback** keep working) | retired (rollback arm) | D1 kills rollback. `rollback_to` and `test_versioning_rollback.py` are removed. The gate arm (i4-failed: a gate-failed version is never GC'd, leaves no version row) is **unchanged and still green** — retain 0 touches only `superseded` rows, never `failed`. |
| `2.4.3` refs `i4-rollback` | retired | `i4-rollback` no longer has code behind it (rollback removed). Its status flip / retirement on the design page is batched to step 6. |

**Deviation — cut-depth (recorded unprompted).** The plan (§5.3) scopes the no-reuse change to
`_resolve_children`. I went one step further and removed the now-dead reuse **wiring** for a clean
end state: `old_children` threading, and the `reusable_active_children` + `_pipeline_config_matches`
helpers (both retired from the ingestion public surface in `__init__.py` and `FEATURES.md`). The
pure `chunk_diff` domain leaf (`domain/chunk_diff.py` + `test_chunk_diff.py`) is **retained** — it is
independently unit-tested and documented as internal (FEATURES.md), so it is left as a now-unused
utility rather than deleting a domain module on my own judgment; its removal is deferred. `rollback_to`
**is** removed (not merely orphaned): retain 0 leaves it no reachable superseded target, and
never-bend rule 11 forbids an exported function with no test once `test_versioning_rollback.py` is
retired. All of this lands uncommitted for owner review per the branch convention.

**Attachment rebuild (D2).** `attachment_changed` stays **out** of `_REBUILD_CLASSES` (a Confluence
attachment edit doesn't bump `cf_version`, so a new version would collide on
`uq_document_version_idem`). The behaviour is captured as a **strict xfail**,
`test_in3_attachment_edit_reembeds_page` (`reason="needs 2.4.1"`), added to the CI xfail allow-list
(`.github/workflows/ci.yml`, test-db step). It flips to a real pass — and, being strict, XPASSes to
force marker removal — when substep 2.4.1 gives version identity a fingerprint dimension.

**Ripple tests (rewritten, not weakened).** `test_versioning_gc.py` (both tests → retain 0),
`test_versioning_swap.py::test_i4_swap_old_version_and_its_chunks_removed` (old rows gone, not
superseded-inactive), `test_worker_sync.py` (the vd-swap test + two `count_versions == 1`
assertions), `test_reindex.py` (`count_versions == 1`), `test_attachment_wiring.py` (docstring/name:
carried-forward-by-content, not vector reuse). Retired: `test_pipeline_reuse.py`,
`test_versioning_rollback.py`, `test_ingestion_pipeline.py::test_reuse_guard_disables_on_config_change`.

**Whole-repo pyright net-decreased** (47 → 44) — removing `rollback_to`/`reusable_active_children`
dropped their Optional-access errors; ADR-features-import-only-through-public-root D1 holds. `make check` green (backend 935 passed +
1 xfailed, kb 43, boundaries 0).

## §13 step 6 — rule 5 positive guard + rule 8 invariant + finalise (2026-09-24)

The last step of the series: the two remaining guard tests, then the batched design-page **status**
flips and the finalisation of the sync-rules docs. No production code changed — the behaviour these
guards protect was delivered by steps 1–5.

**New tests (green-today guards, proven real by the revert step — `test-proof.md`):**
`test_in2_first_relevant_tag_full_build` (panel ks-index, rule 5 positive half — first recognized
label on an untagged page → full build, `counter.texts == child count`) and
`test_in2_change_never_touches_other_pages_rows` (panel vd-swap, rule 8 — editing then deleting page
A leaves neighbour B byte-identical). With these, the eight sync rules each carry ≥1 green database
test.

**Design-page status flips performed this step** (`obi-rag-system-flow.html`, via `panel.py
--status`, batched here per steps 1–5):

| panel | flip | reason |
|---|---|---|
| `i2-gone` | change → **built** | All three triggers live and purge (delete/classified/unlabeled), proven by `test_sync_rules_delete.py` + `test_sync_rules_membership.py`. |
| `tg-purge` | build → **built** | `purge_page` built + tested (`test_sync_rules_delete.py`). |
| `i2-labels` | change → **built** | Overlap visibility + empty-tags-private code delta fully closed (step 3 sharing + step 4 migration 0014). |
| `i3-embed` | change → **built** | No vector reuse; every child re-embedded (`test_sync_rules_rebuild.py`). |
| `i2-rebuild` | change → **built** | A rename rebuilds + re-embeds (body+title). Attachment-only rebuild stays deferred (D2, strict xfail) — noted in the today-line. |
| `tg-two` | change → **built** | Two recognized provider labels = legitimate sharing (`test_sync_rules_visibility.py`). Its original "hidden from everyone" **target** is retired and now stale on the page (see the TARGET-lines note below); the status reflects the new built behaviour, the target reconciliation is tracked here. |

**Panels whose status is deliberately NOT flipped this step (with reason):**

| panel | left at | reason |
|---|---|---|
| `r3-scope` | `unverified` | RLS fail-closed code + migration 0014 are done and DB-tested, but the panel's **live** leg (0014 applied to Supabase after the Q-B empty-tags backfill audit) is owner-blocked. `unverified` (coded, not proven live) is the honest status; do not flip to `built` until the live leg runs. |
| `tg-conflict`, `tg-state` | unchanged | Both are **retired** concepts (D4 dropped conflict; `scope_state` was never built). `panel.py` has no `retired` status word (`STATUS_WORDS = built/change/build/unverified/discuss`), so no status flip represents "retired" faithfully; the retirement is recorded in this doc (step-3 section) and their today-lines note it. Inventing a status would misrepresent. |
| `tg-deactivate` | unchanged | **Not** retired: `deactivate_page` still runs for the reconciliation source-scope-loss sweep (`reconciliation.py:206-216`). Its role narrowed (no longer the delete/classified path) — recorded in the step-1 section; no status flip earned. |

**Design-page TARGET lines NOT edited (workflow constraint).** — ⚠️ **SUPERSEDED 2026-09-25 by
"Design-page TARGET lines RECONCILED" below**: the owner gave explicit go-ahead once D1–D4 were
final, so these target lines have now been edited. The note is kept for history. Several panels'
*target* text is now
stale under D1–D4 — `tg-two` ("hidden from everyone"), `i4-gc` ("keep the two most recent
superseded"), `vd-swap` ("deleted after two more versions"), `i3-embed` ("stable_key reuse"),
`i2-rebuild` (reuse line), `r3-scope`/`3.4.1` (the `scope_state = 'ok'` conjunct). The `/obi-change`
workflow forbids changing a target line on the design page ("Never: … change a target line on the
design page"), and §0 of the sync-rules plan defines step 6 as flipping **statuses**, not targets.
So the stale targets are left in place and their correction is tracked here (this doc is the
standing record of every moved target); reconciling the target text itself needs an explicit owner
go-ahead. This is the honest state, not an omission.

**Action-plan checkboxes (`obi-action-plan.html`) NOT ticked (with reason).** Substeps 2.2.4 and
2.3.1 have their unit+database work complete and green, but each names a **live** proof in its own
Proof line — 2.2.4 "the live label script passes on staging", 2.5.x freshness — that is owner-blocked
(the `verify_sync_rules.py`/`page_state.py` scripts are unwritten, needing staging +
`CONFLUENCE_WEBHOOK_SECRET` + Confluence site-admin). Ticking a substep whose live leg has not run
would overstate completion, so the checkboxes are left unticked and the outstanding live legs stay in
the ledger under "need from you". The database-level completion is fully recorded in `coverage-map.md`
and this doc.

---

## Design-page TARGET lines RECONCILED to D1–D4 (owner go-ahead, 2026-09-25)

**Supersedes the "Design-page TARGET lines NOT edited" note above.** With D1–D4 confirmed final, the
owner gave explicit go-ahead to reconcile the stale *target* text on `obi-rag-system-flow.html` (not
just the `today`/status lines). Edited via a formatting-preserving script on the `nodedata` JSON block
(byte-identical to `panel.py`'s writer); every edit asserted the old value first. 17 field edits across
7 panels:

| panel | field(s) | from (stale target) | to (D1–D4 behaviour) |
|---|---|---|---|
| `tg-two` | simple, steps (×4), tests (×2), today | "a mistake… hidden from everyone"; `scope_state = conflict` flow; "zero results" tests | D4 legitimate sharing: resolves to both tags, retrievable in each scope; steps rewritten (no conflict/no warning); tests = found in mews & toast, not operacloud; today notes the reconciliation |
| `i4-gc` | simple, Keep, Delete | "keeps the last two old versions for rollback"; Keep = "two most recent superseded" | D1 retain 0: deletes the just-superseded version in the swap txn, no rollback window; Keep = "nothing — retain 0" |
| `vd-swap` | step 3 | "Rows are deleted after two more versions" | D1: "deleted in the same swap transaction (retain 0)" |
| `i3-embed` | note | "Today only changed children are embedded (stable_key reuse). Target: all children…" | "Every child… embedded afresh on every rebuild — no stable_key vector reuse (D1 / 2.3.1)" |
| `i2-rebuild` | Reuse row, note | Reuse = "today: keeps its vector when stable_key matches; target: no reuse"; note prefixed "Target:" | Reuse = "none — every child embedded on every rebuild"; note de-"Target"-ed to present tense |
| `r3-scope` | status, simple, Target predicate, today | status `unverified`; "and whose state is ok"; predicate "`scope_state = 'ok' AND …`"; today "not yet applied to Supabase" | status **built** (0014 applied + verified live 2026-09-25); scope_state dropped from simple + predicate (D4); today records the live proof (empty tags → no scope; 2/2/2/2/8) |
| `tg-filter` | today, Target policy, code DDL | today "not yet applied to Supabase"; policy + DDL carry "`scope_state = 'ok' AND`" | floor-less `'*' OR tags && allowed_scopes` (scope_state retired, D4); today notes 0014 live; app-predicate flag stays off (PLAN 10.7). Status left `change` (the app-predicate cutover is still pending). |

**Deliberately still not touched:** `tg-conflict` / `tg-state` panel *bodies* — they document
concepts D4 retired; their `today` lines already record the retirement and `panel.py` has no `retired`
status word, so their bodies are left as the historical record (unchanged decision from step 6).
`r3-scope`/`tg-filter` code-location file paths (e.g. the `0010`/`alembic/versions/` refs) are
pre-existing path drift, out of D1–D4 scope. The brief (`obi-system-brief.md`) was regenerated from the
edited page.

---

## Action-plan checkboxes 2.2.4 / 2.3.1 TICKED (roadmap substep 4.8, 2026-10-05)

**Supersedes the "Action-plan checkboxes NOT ticked" note above.** The live proof both Proof lines
were waiting on exists since 2026-09-30: the full 8-rule run through the REAL webhook path
(Confluence → Forge → Railway → event ledger → job → worker) against the prod test pages, owner-
accepted and recorded in the ledger ("Step 3 · Confluence webhook go-live") — including rule 2's
last-label purge (2.2.4's live label check) and rule 6's body-edit full re-embed with no vector
reuse (2.3.1's live leg). The roadmap (Step 4, substep 4.8) explicitly orders the tick citing that
proof. Implementation note: the plan page stores ticks in browser localStorage only, so the tick is
baked as a `checked` attribute on the two inputs, and the loader line was adjusted
(`||b.defaultChecked`) so a baked tick renders instead of being wiped by an empty localStorage —
a user's own browser ticks are unaffected.

---

## Design page + action plan EXTENDED for Step 5 — the multi-integration stages (§D.12 item 7, 2026-10-05)

**What was added (additive only — no existing panel, target line, status or substep was edited):**

- **Design page (`obi-rag-system-flow.html`):** new section **05.2 · Multi-integration context**
  (section id `integration`, nav link added) between Knowledge scopes (05) and Retrieval (06), with
  **11 new panels**, prefix `mi-`, all status **build** (Planned): `mi-contract` (company + three
  slots), `mi-catalog` (central product catalog), `mi-gate` (slot validation + launch allowlist),
  `mi-applies` ("Applies to" applicability metadata), `mi-match` (deterministic AND/OR matching),
  `mi-filter` (in-database eligibility filtering, ≤75 candidates), `mi-rerank` (context-aware
  reranking), `mi-prompt` (context in the prompt + the two-read cap), `mi-attrib` (per-slot source
  attribution), `mi-presets` (standalone test presets), `mi-validate` (Phase A human validation).
  `WF`/`SEC` maps gained the `mi` prefix. Panel content is authored from the owner's decision
  rounds 1–2 of 2026-10-05 and `docs/Final_docs/5-integration-context/` (the contract, catalog,
  decision memo and research docs). The brief was regenerated: **203 panels** (was 192).
- **Action plan (`obi-action-plan.html`):** new **Phase 8 · Multi-integration context: Base and
  Data Hub** (section id `p8`, nav link added) with 5 step groups / **16 substeps** in execution
  order: 8.1.1 catalog loader · 8.1.2 contracts T1–T6 · 8.1.3 gate slots · 8.2.1 Applies-to schema
  · 8.2.2 chunk applicability migration + restamp · 8.2.3 deterministic matching · 8.3.1 in-DB
  eligibility filtering · 8.3.2 context-aware rerank · 8.3.3 prompt context · 8.3.4 attribution ·
  8.4.1 standalone presets · 8.4.2 widget context shape · 8.4.3 frontend deploy on Railway ·
  8.5.1 the five worked examples · 8.5.2 Phase A (human-run) · 8.5.3 the Jasper reply + platform
  entries (deliberately last). Each substep carries Must-be-true/Proof/prompt/Check-it and a
  `design page:` refs line naming its `mi-` panels; a 4-item phase gate closes it.
- **Why new ids, not edits:** the never-edit-a-target-line rule and the append-only spirit — the
  Step-5 capability is genuinely new, so it gets new panels and a new phase rather than rewording
  built ones. The agent-built automated test expansion that follows Phase A is roadmap Step 6 and
  is deliberately NOT in phase 8 (stated in the phase lede).
