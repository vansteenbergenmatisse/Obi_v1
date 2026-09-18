# Obi, part by part — the complete brief, A to Z

Generated on 2026-09-18 from `docs/Final_docs/obi-rag-system-flow.html` (the target design for Obi). This file carries every visible section, every table, every diagram box and every click panel of that page, in the page's order, so a reader who cannot open the HTML has the same information.

## 0 · How to read this brief

**What Obi is.** A chat widget that answers questions from Omniboost's Confluence pages with citations. Two workflows: **ingestion** (a published Confluence page becomes chunks with vectors in Postgres) and **retrieval** (a question becomes a cited answer from those chunks). One Postgres database (Supabase, pgvector) is both the relational store and the vector store. The backend is Python (FastAPI) under `apps/automation`; the widget is Next.js under `apps/web`; contracts and design tokens are packages.

**How the page marks reality.** Every stage, box and panel carries one status:

| Label | Meaning |
|---|---|
| Implemented | deployed and tested on the live store today |
| Implemented, needs changing | runs today, but the target changes it |
| Planned | does not exist in code yet |
| Unverified | coded but not applied or not proven on the live store |
| Decision needed | blocked on a call from the owner (Matisse) |
| Priority 1 / Priority 2 | the two target changes that ship first (section 01, "Ship order") |

Where a panel has both a **Today** line and a **Target and notes** line, the Today line describes the current code and the Target line the design. Both are given so that a reader can compute the delta.

**How this brief is organised.** Sections 01 to 11 follow the page. Each section gives the plain-language lede (written for leadership), then its subsections, tables, callouts and diagrams, then every click panel that belongs to that section (panel id, status, plain words, today, settings, code locations with line numbers where the page has them, steps, code, tests, notes). Panel ids are stable references: `r5-coverage` is the coverage check panel wherever it is mentioned.

**For the agent that will compare this to the codebase and write the implementation plan.**

1. Treat every "Today" line, every "Where in the code" path and every line-number reference as a claim to verify against the repository. Record each claim as confirmed, drifted, or missing.
2. Treat every "Target" line, every "Planned" panel and every "Implemented, needs changing" panel as a delta to implement. The checklist in section 01.1 is the acceptance list: one checkbox per verifiable task with its section and panel references.
3. Group the deltas by the ship order in section 01: Priority 1 (exact chunk through search, rerank and answer; sections 06.2 to 06.5), Priority 2 (batched support check before send; section 06.5), then the rest in section order (ingestion fingerprint and whole-page rebuild, label-gated ingestion, scope_state and the RESTRICTIVE policy, the embedding work in 03.2, the folder move in 01.2).
4. Do not implement anything tagged "Decision needed" without the owner's call. Section 11 lists every open decision; several sections repeat the tag in place. The page proposes a default for each; state the default in the plan and mark it as awaiting confirmation.
5. Every threshold and depth on the page (refusal threshold 0.10, `coverage_min_score`, `coverage_unsure_band`, rerank depth 75 vs 150, the support-check latency budget) is provisional until the gold set in section 10 exists. Plan the gold set early because acceptance for stages 4 and 5 depends on it.
6. Section 08.1 ends with the full DDL of the one target migration (0011). Apply migration 0010 live first; run the backfill and the readiness gate (`verify_knowledge_scope_backfill.py`) before trusting the new policy.
7. Never disable row security on Supabase and never run the 0009 downgrade there: both expose the tables through the public REST roles.

---

## 01 · System overview: two workflows, one store

_Section id: `fit`_

**In plain words (the lede):** Obi is a chat window that answers questions from our Confluence pages. Two workflows do all the work. **Ingestion** reads a published page and stores it in pieces. **Retrieval** takes a question and writes a cited answer from those pieces. Both use one Postgres database and nothing else.

Diagram (Top row: Confluence feeds receive, decide, build and activate, which write into the Postgres corpus. Bottom row: the widget goes through gate, search, filter, judge and answer, reading from the same corpus. An auth host feeds the gate. An eval set feeds the judge.)
  - labels: WORKFLOW 1 · INGESTION · runs as the table owner; WORKFLOW 2 · RETRIEVAL · runs as rag_reader, row security enforced
  - Confluence — pages, labels, files → panel `ov-confluence`
  - 1 · Receive — webhook, queue → panel `ov-receive`
  - 2 · Decide — what changed? → panel `ov-decide`
  - 3 · Build — chunk, context, embed → panel `ov-build`
  - 4 · Activate — one atomic swap → panel `ov-activate`
  - Auth host — signs a user token → panel `ov-auth` (changes from today)
  - Postgres corpus — one store, row security always on → panel `ov-corpus`
  - Eval set — gold questions → panel `ov-eval` (changes from today)
  - Obi widget — in Mews, Toast, web → panel `ov-widget`
  - 5 · Gate — who asks, limits → panel `ov-gate`
  - 6 · Search — meaning + keywords → panel `ov-search`
  - 7 · Filter — three locks → panel `ov-filter`
  - 8 · Judge — rerank, anything relevant? → panel `ov-judge`
  - 9 · Answer — enough proof, cite, stream → panel `ov-answer`

_Dashed box borders mark parts that change from what runs today. The dashed line means "feeds numbers into", not a live call._

core step

outside system or tool

a decision or gate

stop, refuse, or fail path

data or state

changes from today

#### Status labels used everywhere

| Label | Meaning | Test |
|---|---|---|
| [Implemented] | The code exists, is deployed, and is covered by a test that runs in CI or was run against the live store. | You can point at the test and at the deploy. |
| [Implemented, needs changing] | Runs today. The target changes how it works. The current behavior and the target are both written down in the box. | Both a "today" and a "target" line exist. |
| [Planned] | Does not exist in code yet. | No file to point at. |
| [Unverified] | Code exists but is not deployed, or is deployed but not tested against the live store. Do not count on it until verified. | Code yes, deploy or live test no. |
| [Decision needed] | Cannot be decided by the code. Needs a call from you. | Listed in the Open chapter. |

Every clickable box carries one of these. Every stage section separates "today" from "target" in its stage card.

#### Eight rules that apply everywhere

- **Accuracy before coverage.** Obi refuses and hands off to a human before it guesses. Three code checks enforce this: every sentence must cite a source, a score below the threshold refuses, and the database itself hides rows the caller may not see: by source today, and by scope once migration 0010 is live.
- **Every read carries one authorization context.** Who is asking, which sources they may see, which scopes they may see, and which pages. The gate builds it once. Every later step uses it. Search, rerank, parent lookup, curated lookup. No step fetches under looser rules.
- **The database denies by default.** If a step forgets to set its scope, Postgres returns zero rows. Never another customer's rows.
- **An index update is all or nothing.** A page is rebuilt in staging and then swapped live in one transaction. The live corpus is never half built. Rollback is instant.
- **Tags in Confluence are the one control surface.** The tag names live in `config/knowledge_scopes.json`. A page is in the index for one reason only: it is published and carries one of those tags. Add the tag and the page goes in. Remove the last tag and the page goes out. Edit the page and the whole page is thrown out and re-uploaded. Add `classified` and the page goes out and stays out.
- **Two workflows, never more.** Ingestion and retrieval. Everything on this page belongs to one of the two, or to the store they share. A new source or a new widget adds a stage to one workflow. It never adds a third workflow.
- **A fixed workflow, never an agent loop.** Each stage is a plain function. Latency is bounded. Every refusal can be audited. At most two extra reads per question: one thin-results refetch in stage 2 under the same auth context, and one weak-score fallback in stage 4 with the person's own words. Never a loop.
- **The same embedder on both sides.** Pages and questions go through the same model. Change the model and the version stamp forces a full re-embed of the whole corpus.

#### Ship order: the two changes that come first

> **Priority 1 · Keep the exact matching chunk all the way through search, reranking and the answer.** [Priority 1] Sections 06.2 to 06.4. Today search can find the answer in section 8 of a page and the reranker receives section 1 of that same page instead. Fusion by chunk id, provenance on every candidate and exact-child reranking fix this. It ships first because it fixes a direct loss of correct evidence.
> 
> **Priority 2 · Check that the sources support the answer before it is sent.** [Priority 2] Section 06.5. Today a sentence passes when its citation number points at a real evidence block, even when that block does not back the claim. A batched support check runs before the replay and cuts or marks unsupported sentences. It costs one extra model call per answer. That is the price of accuracy first.

> **Every box is clickable.** A panel opens. It starts with two or three sentences in plain words, the kind you could read to a five-year-old. Below that: what runs today, the settings and defaults, where the code lives, the steps in order, and how to test that part. Escape or a click outside closes it.

> **Why two workflows with nine stages, and not one pipeline.** Ingestion has four stages. Retrieval has five. Each stage has one job, one owner in the code, and one set of tests. A failure in the middle of one stage is easy to place. You can rerun ingestion for 200 pages or swap the reranker without touching the rest.

#### Panels that belong to this section (14)

_Workflow label shown in the drawer: System overview_

##### Panel `ov-confluence` · Confluence, the source of truth · [Implemented]
- Kind: Outside system
- In plain words: Confluence is where the pages live. Obi reads them and never writes to them.
- Today: Live on one Confluence Cloud site. Four labeled test pages are in the index today. Connection via a Basic Auth API token in the root .env.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | What we read | page meta, body (storage format), labels, read restrictions, attachments |
  | APIs used | v2 pages, spaces and labels; v1 for restrictions, group members, attachment download |
  | Client | HttpConfluenceClient: timeout, retry on 5xx, circuit breaker after 5 failures |
  | Test double | FixtureConfluenceGateway reads tests/fixtures/confluence, so CI never calls the network |
- Where in the code:
  - `platform/clients/confluence_client.py` — the real client
  - `platform/clients/fixture_confluence_client.py` — offline stand-in
  - `platform/config/settings.py` — CONFLUENCE_BASE_URL, EMAIL, API_TOKEN, WEBHOOK_SECRET
- Steps:
  1. An editor saves a page or changes a label in Confluence.
  2. Confluence posts a webhook (once a public URL is registered) or a sweep asks Confluence what changed.
  3. The worker fetches the page facts through the client and ingestion stage 2 decides what to do.
- Target and notes: The restrictions endpoint in v2 is marked under construction by Atlassian. The client uses the v1 endpoint, and a failed fetch fails closed (page treated as restricted to nobody).

##### Panel `ov-receive` · Receive and queue · [Implemented, needs changing]
- Kind: Ingestion stage 1
- In plain words: Hears that a page changed and puts one job on a list. Does nothing else.
- Today: Webhook handler, ledger, queue and worker all run. The webhook has no public URL yet, so changes arrive through sweeps and scripts.
- Steps:
  1. Check the message: rate, size, signature, shape.
  2. Write it to the event ledger once.
  3. Put one job per page on the queue.
  4. A worker claims it under a lease and runs ingestion stage 2.
- Target and notes: Changes in the target: one pending job per page (coalescing) and a label sweep that discovers pages by label.

##### Panel `ov-decide` · Decide what changed · [Implemented, needs changing]
- Kind: Ingestion stage 2
- In plain words: Looks at the changed page and picks one action: rebuild it, update its tags, take it out, or do nothing.
- Today: Classification by hashes works. Two gaps: attachment-only changes never rebuild, and the version guard can skip a label change.
- Steps:
  1. Fetch meta, labels, restrictions, attachment list.
  2. Compute the scope state from the labels.
  3. Hash everything into one index fingerprint.
  4. Route to rebuild, metadata-only, deactivate, or no change.

##### Panel `ov-build` · Build the chunks · [Implemented, needs changing]
- Kind: Ingestion stage 3
- In plain words: Cuts the page into big and small pieces and turns every small piece into a meaning code. The whole page, every time.
- Today: Parent and child chunking, contextual notes, embeddings, keyword index and attachments all run. Embedding reuse checks body text only.
- Steps:
  1. Normalize HTML and attachments into blocks.
  2. Pack parents of about 1200 tokens, split children of about 400.
  3. Prefix each child with title, heading path and a short note.
  4. Embed every child of the page. Index keywords.
- Target and notes: Target: every rebuild embeds the whole page. The vector reuse check (stable_key) is removed.

##### Panel `ov-activate` · Activate · [Implemented, needs changing]
- Kind: Ingestion stage 4
- In plain words: Writes the new pieces to a side room, then flips one switch so the new page replaces the old one in the same instant.
- Today: Staging version, validation gate, atomic pointer swap, GC and rollback all run.
- Steps:
  1. Create the version in staging.
  2. Insert inactive chunks and link them.
  3. Gate: no children means fail.
  4. Swap the pointer in one transaction. Stamp source, tags, scope state.
- Target and notes: Change in the target: the version's uniqueness key becomes the index fingerprint, so a file-only change may build.

##### Panel `ov-auth` · The auth host: the host backend or an agreed auth service · [Implemented]
- Kind: Outside system
- In plain words: Hands each person a signed card that says which company they belong to, which integration they use, and who they are. Today this is the host's own server.
- Today: Built: the host issues a signed per-user JWT (iss, aud, sub, iat, exp, company_id, company_name, integration), verified before any search — live-proven for test hosts (commit 59385f4).
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Issues | a signed JWT per user: iss, aud, sub, iat, exp, company_id, company_name, integration |
  | Verified by | the backend on every /chat call, before any search |
  | Never trusted | principal or knowledge_scope from the request body |
- Steps:
  1. The host backend signs the person in and reads company and integration from its own records.
  2. It issues a short-lived signed JWT for Obi.
  3. The host page loads the Obi iframe and sends the token by postMessage to the exact Obi origin.
  4. The iframe holds the token in memory and sends it as a bearer header through the proxy.
  5. The backend verifies algorithm, signature, issuer, audience and expiry, then builds the auth context.
- How to test it:
  - A forged, modified or expired token is a 401.
  - A body knowledge_scope that disagrees with the token is ignored.
- Target and notes: Open: who signs (the host backend or an agreed service), the key exchange, the permitted host domains, the identity mapping for page permissions. The full design is section 03.2.

##### Panel `ov-corpus` · The Postgres corpus · [Implemented]
- Kind: Data
- In plain words: The one storage box: tables for pages and pieces, plus the meaning codes for search. It hides rows a person may not see.
- Today: Supabase Cloud (AWS eu-west-1), Postgres with pgvector 0.8.2. Alembic head 0012 live.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Engine | PostgreSQL 16 + pgvector + full-text search |
  | Dense index | HNSW over halfvec(3072), cosine, m=16, ef_construction=200 |
  | Keyword index | GIN over tsvector |
  | Isolation | row security on every table; writer exempt by ownership |
  | Fallback host | AWS RDS or Aurora: a connection string swap plus re-applying roles and policies |
- Where in the code:
  - `platform/db/models.py` — all eleven tables
  - `platform/db/schema.py` — roles and policies
  - `platform/db/engine.py` — writer and reader engines
  - `alembic/versions/` — 0001 to 0010
- Target and notes: Never disable row security on any table on Supabase. The public REST roles hold SELECT on everything; the policies are the only fence.

##### Panel `ov-eval` · The evaluation set · [Planned]
- Kind: Evaluation
- In plain words: A list of test questions with known right answers, used to check Obi after every change.
- Today: No gold set exists. make eval runs a synthetic fixture of 6 current pages.
- Steps:
  1. Write 150 to 250 reviewed cases.
  2. Split dev and held-out.
  3. Score each stage separately.
  4. Every threshold and model swap is measured here first.

##### Panel `ov-widget` · The Obi widget · [Implemented]
- Kind: The widget
- In plain words: The chat window inside Mews or Toast where a person types a question and gets a cited answer.
- Today: Built in apps/web. Launcher, teaser, panel, composer, images, screenshot, six locales, dev-only scope switcher. Per-user JWT from the host; the shared pilot invite token is retired.
- Steps:
  1. The widget is embedded in a platform's page with a scope from its config.
  2. The user asks. The widget calls its own proxy route.
  3. The proxy adds the server key and streams the answer back.

##### Panel `ov-gate` · The gate: who are we talking to? · [Implemented, needs changing]
- Kind: Retrieval stage 1
- In plain words: Finds out who is asking: which company, which integration (Mews, Toast, Opera Cloud), which person. Writes that into one note every later step obeys.
- Today: Server key, limits, small talk, clarification flag, rewrite all run. Identity comes from the body.
- Steps:
  1. Verify the host key and, in the target, the user token.
  2. Apply limits.
  3. Build one authorization context.
  4. Short-circuit small talk and vague questions. Rewrite the rest.

##### Panel `ov-search` · Search · [Implemented, needs changing]
- Kind: Retrieval stage 2
- In plain words: Finds pieces that mean the same as the question and pieces that share its words, only among rows this person may see, and merges them into one list.
- Today: Dense and keyword search over children, fused by page id with RRF. Curated entries are prepended by id after the search.
- Steps:
  1. Embed the question.
  2. Set both scope GUCs for the transaction.
  3. Dense and keyword search over active children.
  4. Fuse by chunk id; keep provenance. Curated entries are in the pool.

##### Panel `ov-filter` · Filter: three locks · [Unverified]
- Kind: Retrieval stage 3
- In plain words: Removes anything this person may not see. Two rules run inside the database before rows come out; a third checks Confluence page permissions.
- Today: Source RLS live. Scope RLS coded (migration 0010), not applied live. Page ACL runs before rerank. Empty tags read as public.
- Steps:
  1. Lock 1: source row policy.
  2. Lock 2: scope row policy, RESTRICTIVE.
  3. Lock 3: page restriction rows for the candidate pages.
  4. Only then does text leave the database.

##### Panel `ov-judge` · Rerank and judge · [Implemented, needs changing]
- Kind: Retrieval stage 4
- In plain words: Scores each found piece against the question. Weak scores mean Obi searches once more, then refuses rather than guess.
- Today: Cohere rerank on one child per page. A 0.10 threshold decides. The fallback picks the higher of two runs.
- Steps:
  1. Rerank the matching passages.
  2. If weak, one fallback search and one rerank of the union.
  3. Strong enough: the top passages move on to stage 5. Still weak: refuse.

##### Panel `ov-answer` · Answer · [Implemented, needs changing]
- Kind: Retrieval stage 5
- In plain words: Writes the answer from the found pieces only. Every sentence must point to a source, and a missing part of the question is named as undocumented.
- Today: Parent expansion, generation, citation enforcement, image analysis, SSE replay and query_trace all run. Parents are fetched with the source scope only.
- Steps:
  1. Expand children to parents under the same auth context.
  2. Dedupe and budget the parents.
  3. Coverage check on the final context: full answer, partial answer, or refuse.
  4. Generate with numbered evidence. Cut uncited sentences.
  5. Check that every cited source supports its sentence. Cut what is not.
  6. Stream and trace.

---

## 01.1 · Implementation checklist

_Section id: `checklist`_

**In plain words (the lede):** This is the list of every task on this page that a test can prove. Work that runs today and work that is planned both sit here. Tick a box only when the named test passes on the named deployment. The boxes reset when the page reloads, so copy the list into your tracker. Click a group title to open or close it.

#### Ingestion, stage 1 · Receive and queue

- [ ] Webhook endpoint reachable from Confluence over public HTTPS; a test label event arrives and is logged in event_ledger. (ref: 04.1 · confluence_sync/api/webhook.py · needs the AWS deploy)
- [ ] HMAC check rejects a bad signature with 401 and a missing secret with 503, verified against the deployed URL. (ref: 04.1 · i1-checks)
- [ ] Rate limit 300/min/IP and 512 KiB body cap enforced at the deployed endpoint. (ref: 04.1 · i1-checks)
- [ ] Delivery dedup: the same delivery id twice creates one ledger row and one job. (ref: 04.1 · i1-ledger)
- [ ] Own-write loop guard: an event whose actor is the service account creates no job. (ref: 04.1 · i1-self)
- [ ] Coalescing: two events on one page while a job is pending yield one pending job (partial unique index on job.page_id WHERE status = pending). (ref: 04.1 · i1-enqueue · 08.1 job)
- [ ] New revision: an event arriving while a job is running creates a second job that runs after the first. (ref: 04.1 · i1-enqueue)
- [ ] Worker claim uses FOR UPDATE SKIP LOCKED with a 120 s lease; reaper frees a dead lease. (ref: 04.1 · i1-claim, i1-reaper)
- [ ] Retry with backoff, then dead letter; attempt count survives a rollback. (ref: 04.1 · i1-fail, i1-handle)
- [ ] Daily label sweep: for each slug in knowledge_scopes.json, a Confluence label search across all spaces enqueues every tagged page. (ref: 04.1 · i1-sweep · 05 ks-sweep)
- [ ] Folder-root sweep over source_scope removed; source_scope no longer read anywhere in ingestion. (ref: 04.1 · 08.1 source_scope)
- [ ] Only published pages produce events; a saved draft creates no job (verified with a draft edit). (ref: 03 · 04.1)

#### Ingestion, stage 2 · Decide what changed

- [ ] Labels matched case-insensitively against knowledge_scopes.json; scope_state written as ok / conflict / classified / unlabeled. (ref: 04.2 · i2-labels)
- [ ] Content fingerprint includes body, structure, title, attachment ids and versions, and parser/chunker/contextualizer/embedding configuration. (ref: 04.2 · i2-hash)
- [ ] Metadata fingerprint includes labels and read restrictions; a metadata-only change updates in place with no embedding call. (ref: 04.2 · i2-meta, i2-inplace)
- [ ] Version guard removed for metadata: a label change at an unchanged page version updates the tags column. (ref: 04.2 · i2-classify)
- [ ] attachment_changed and title_changed are rebuild triggers. (ref: 04.2 · change_detection.py → classify, sync_service.py → _REBUILD_CLASSES)
- [ ] Last recognized tag removed → page deactivated within the freshness target. (ref: 04.2 · i2-gone · 05)
- [ ] classified label → page deactivated and chunks deleted; later removal re-indexes from scratch. (ref: 04.2 · i2-gone · 05 tg-classified)
- [ ] Two provider tags → scope_state = conflict, warning logged, page hidden everywhere, heals on fix. (ref: 04.2 · 05 tg-two)
- [ ] Restrictions fetch failure stores the page as readable by nobody (fail closed). (ref: 04.2 · i2-fetch)
- [ ] Acceptance: replace a PDF without editing the body; after sync the new content is searchable and the old attachment chunks are inactive. (ref: 04.2 acceptance check)

#### Ingestion, stage 3 · Build the chunks

- [ ] Normalize keeps tables and code blocks whole; attachment text lands under an Attachments heading. (ref: 04.3 · i3-blocks)
- [ ] Parents ~1200 tokens (cap 2000), children ~400 tokens with 12% overlap, links to parent and neighbors set. (ref: 04.3 · i3-parents, i3-children)
- [ ] Embedding input = title + heading path + Haiku context note + child text; citation text stored separately. (ref: 04.3 · i3-context · worked example)
- [ ] stable_key vector reuse removed: a rebuild embeds every child (test: no chunk id from the old version is active and every new child has a fresh embedding). (ref: 04.3 · i3-embed)
- [ ] Embedding batches of 128 with retry, backoff, circuit breaker; a failed batch fails the build and the old version stays live. (ref: 04.3 · i3-embed)
- [ ] tsvector on every child, GIN indexed. (ref: 04.3 · i3-tsv · 08.2)
- [ ] Unsupported attachment (image, scanned PDF) yields empty text plus a flag; the page still builds. (ref: 04.3 · i3-attach)
- [ ] Attachment download or parser error fails the build; the previous version stays searchable; job retries then dead-letters. (ref: 04.3 · i3-attach)
- [ ] Attachment report (count, extracted, empty, failed) written on document_version and summarized by the daily sweep. (ref: 04.3 · i3-attach · Unverified)
- [ ] Code default embedder matches the deployed .env (OpenAI text-embedding-3-large, 3072) or a bake-off has picked a winner. (ref: 03 settings · 08.2 vd-model)

#### Ingestion, stage 4 · Activate

- [ ] document_version uniqueness is (document_id, index_fingerprint); an attachment-only rebuild at the same page version succeeds. (ref: 04.4 · i4-staging · 08.1)
- [ ] Validation gate: zero children marks the version failed and leaves the live version untouched. (ref: 04.4 · i4-gate)
- [ ] Pointer swap is one transaction; partial unique index allows one active version per document; test: two actives are refused. (ref: 04.4 · i4-swap)
- [ ] Stamp reads tags from labels only (no source_scope union); tags on served rows are never empty. (ref: 04.4 · i4-stamp)
- [ ] GC keeps two superseded versions; older versions and their chunks are deleted. (ref: 04.4 · i4-gc)
- [ ] Rollback repoints to an old version and restores its hashes so the next sync does not report "no change". (ref: 04.4 · i4-rollback)
- [ ] Test: delete, restore, delete ends inactive with no duplicate version. (ref: 11 · change 2 tests)

#### Knowledge scopes

- [ ] knowledge_scopes.json validated at startup: lowercase, unique, classified always present; a bad entry stops startup with a named error. (ref: 05 · ks-validate)
- [ ] Adding a slug and deploying is the only setup for a new tag; GET /health lists it as a valid scope. (ref: 05 · ks-edit, ks-deploy)
- [ ] Removing a slug: pages with only that tag deactivate on the next sweep; pages with another recognized tag stay in. (ref: 05 · ks-orphan)
- [ ] Rename from obi-*-test to general / mews / toast / classified done, or a decision recorded to keep the test names. (ref: 05 · 11 open)
- [ ] opera-cloud kept or dropped: decision recorded. (ref: 05 · 11 open)
- [ ] Widget knowledgeScope validated for shape and membership only; unknown slug returns 400; a known slug that disagrees with the token is ignored and logged; the token decides scope. (ref: 05 · ks-widget · 06.1)

#### Retrieval, stage 1 · The gate

- [ ] A trusted issuer (host backend or agreed auth service) issues a signed token carrying iss, aud, sub, iat, exp, company_id, company_name, integration. (ref: 06.1 · ov-auth · 03.2 · 11 open)
- [ ] Backend verifies host key and user token; company, integration, principal derived from the token; body values ignored (test: a foreign principal in the body is ignored or 401). (ref: 06.1 · r1-auth)
- [ ] Authorization context has company_id, integration, allowed scopes (integration + general), allowed sources, principal, subject; built once, passed to every read. (ref: 06.1 · r1-ctx)
- [ ] Rate limit 20/min, history ≤ 20 turns × 4000 chars, images ≤ 4 × 5 MB enforced. (ref: 06.1 · r1-limits)
- [ ] Small-talk short-circuit matches the whole message only. (ref: 06.1 · r1-small)
- [ ] Rewrite lists the question parts, including multipart first-turn questions; fails open to raw text. (ref: 06.1 · r1-rewrite)
- [ ] CachingAnswerService removed; idempotency replay kept and bound to token + history + scope. (ref: 06.1 · r1-idem)

#### Retrieval, stage 2 · Search

- [ ] [Priority 1] Both searches return chunk_id, parent_chunk_id, page_id, doc_version_id. (ref: 06.2 · search_repo.py)
- [ ] [Priority 1] RRF fuses and dedupes by chunk id; two sections of one page can both survive (acceptance: section 8 reaches Cohere). (ref: 06.2 · fusion.py → reciprocal_rank_fusion)
- [ ] Both GUCs set per transaction as bound parameters; hnsw.ef_search = 100; iterative_scan = relaxed_order. (ref: 06.2 · r2-gucs)
- [ ] Dense query uses the indexed halfvec(3072) expression; EXPLAIN shows the HNSW index. (ref: 06.2 · r2-dense · review item 5)
- [ ] Page-access predicate added to dense and keyword queries before LIMIT 75, next to source and scope predicates. (ref: 06.2 · r2-aclsql)
- [ ] Filtered recall under restrictive permissions measured on the gold set. (ref: 06.2 · 10 evidence table)
- [ ] Bounded extra retrieval when fewer than k permitted children survive; size decided. (ref: 06.2 limits table)
- [ ] Curated entries embedded and tsvector-indexed at seed time; retrieved by relevance in both branches; fused with documents. (ref: 06.2 · r2-curated · seed_curated_knowledge.py)
- [ ] Curated identity is (source_type, item_id); no collision with chunk ids. (ref: 06.2 · curated_knowledge.py → curated_entry_to_hit)
- [ ] "First five entries by id" insertion removed (acceptance: entry 40 is found and cited, entries 1 to 5 are not injected). (ref: 06.2 acceptance check)

#### Retrieval, stage 3 · Filter

- [ ] Migration 0010 applied to Supabase; verify-isolation passes there. (ref: 06.3 · 11 open · Unverified today)
- [ ] Lock 2 predicate is scope_state = ok AND tags && allowed_scopes; empty tags are never public. (ref: 06.3 · r3-scope)
- [ ] Same RESTRICTIVE policy on curated_knowledge_entry; RLS never disabled on any table (Supabase anon check). (ref: 06.3 · 09 s-anon)
- [ ] Negative tests: wrong source id → zero rows; scope GUC unset → zero tagged rows. (ref: 06.3 · r3-deny)
- [ ] App-side page ACL check retained as the second wall after the SQL predicate. (ref: 06.3 · r3-acl)
- [ ] Groups expanded at sync time; unexpandable group gets a sentinel (fail closed). (ref: 06.3 · r3-groups)
- [ ] rag_reader is NOSUPERUSER NOBYPASSRLS, SELECT only; missing reader URL fails startup outside local. (ref: 06.3 · r3-reader)

#### Retrieval, stage 4 · Rerank and judge

- [ ] [Priority 1] fetch_rerank_texts fetches by exact chunk id; DISTINCT ON (page_id) removed; several children per page allowed. (ref: 06.4 · r4-texts)
- [ ] [Priority 1] Cohere receives child passages (title + contextual text, 4000 chars). (ref: 06.4 · r4-rerank)
- [ ] Fallback: union of both candidate sets, dedupe by chunk id, one rerank against one question (no "pick the higher run"). (ref: 06.4 · r4-union)
- [ ] Refusal threshold recalibrated on the gold set; recalibrated again on any reranker model change. (ref: 06.4 · r4-weak · 11 open)
- [ ] Rerank depth, final passage count decided and written into the limits table. (ref: 06.2 limits table)
- [ ] Coverage check removed from this stage (now in stage 5). (ref: 06.4 · r5-coverage)

#### Retrieval, stage 5 · Answer

- [ ] Parent expansion runs inside the same auth context with both GUCs set and page ACL applied; no fresh session. (ref: 06.5 · r5-parents)
- [ ] [Priority 1] Parent expansion uses the parent id carried by each selected child; never a lookup by page (acceptance: the section 8 child expands to the section 8 parent). (ref: 06.5 · r5-parents · 06.2 r2-prov)
- [ ] Dedupe merges neighbors; trimming to the context token budget keeps evidence per question part first. (ref: 06.5 · r5-dedupe)
- [ ] Context token budget decided and written into the limits table. (ref: 06.2 limits table)
- [ ] decide_coverage runs on the final context after trimming; outcomes full / partial / refuse (insufficient_coverage). (ref: 06.5 · coverage.py → decide_coverage)
- [ ] Coverage mapping: each parent in the final context is reranked against each question part (part as query); a part is covered at or above coverage_min_score, unsure inside the band below it, and only unsure parts go to one Haiku call; keyword or embedding similarity alone never certifies a part. (ref: 06.5 · r5-coverage)
- [ ] Partial answer names the undocumented part and offers a human (acceptance: setup + permissions + rollback with no rollback passage). (ref: 06.5 acceptance check)
- [ ] Evidence block numbered [n] title then parent text; company and integration passed as plain facts. (ref: 06.5 · r5-evidence)
- [ ] Valid citation-number checking cuts uncited sentences and strips invented markers; no_citations refusal when nothing survives. (ref: 06.5 · r5-enforce)
- [ ] [Priority 2] Batched support check runs before send over every (sentence, cited passage) pair; unsupported sentences cut, partly supported marked; nothing left refuses with unsupported; verdicts on the trace; latency measured on the gold set. (ref: 06.5 · r5-ground)
- [ ] Support judge failure mode decided (refuse or send marked unverified) and a latency budget set. (ref: 06.5 · 11 open)
- [ ] query_trace gains token_subject (hashed), candidate_chunk_ids, decision. (ref: 06.5 · 08.1 query_trace)
- [ ] Image analysis output never carries a citation marker; an image turn never refuses on weak score. (ref: 06.5 · r5-image)

#### Data and vector store

- [ ] page_source has scope_state and index_fingerprint columns. (ref: 08.1 columns table)
- [ ] chunk has scope_state; served rows never have empty tags. (ref: 08.1 · d-chunk)
- [ ] job has the partial unique index on (page_id) WHERE status = pending. (ref: 08.1 · d-job)
- [ ] curated_knowledge_entry has embedding, tsv, scope_state. (ref: 08.1 · d-curated)
- [ ] HNSW index over embedding::halfvec(3072), m = 16, ef_construction = 200, only active children with a vector. (ref: 08.2 · vd-hnsw)
- [ ] GIN indexes on tsv and on tags; btree on (is_active, source_id) and (is_active, space_id). (ref: 08.1 indexes table)
- [ ] Whole-page swap test: after a rebuild no old vector of that page is returned by the HNSW search. (ref: 08.2 · vd-swap)

#### Embedding and separation of concerns

- [ ] Folder rename approved or declined; if approved, one PR moves apps/web → frontend/, apps/automation → backend/, db + alembic + config + seeds → knowledge-base/, with CI and deploy paths updated and no logic change. (ref: 01.2 · 11 open)
- [ ] obi.js: one script tag draws the round button and the frame from our domain; Obi.init({ tokenUrl }) is the only platform-side call; Obi.clear() on logout. (ref: 03.2 · em-loader)
- [ ] obi.js fetches the note from tokenUrl at the click, hands it to the frame over a checked channel (exact Obi origin, parent window only), renews it silently before expiry and after a long idle stretch. (ref: 03.2 · em-loader · em-token)
- [ ] The note is held in memory only; never in a URL, cookie, web storage, log line or trace row (hash of sub only); the ?access_token= path removed. (ref: 03.2 · em-token · 07 w-token)
- [ ] platforms.json holds one entry per platform (issuer, key URL, domains, lifetime) plus the integration map; every tag in it exists in knowledge_scopes.json; a bad entry stops startup; an unknown integration is refused; no values gives general only. (ref: 03.2 · em-backend)
- [ ] Token verifier: algorithm allow-list, key lookup by kid against the platform's entry, iss, aud, exp with 60 s leeway; 401 on any failure with no detail; 503 on an empty platforms.json outside local. (ref: 03.2 · em-backend)
- [ ] AuthContext carries company_id, company_name, integration, allowed_scopes from the map, allowed_sources, principal, token_subject; every read in one request logs the same scopes. (ref: 03.2 · em-backend · 06.1 r1-ctx)
- [ ] Four test host pages on our domain (no values, Mews, Toast, a second Mews company), each with its own note endpoint; the full flow passes on all four before any platform is involved. (ref: 03.2 step 3)
- [ ] Each platform's domains in platforms.json; CSP frame-ancestors and the message check read the same list. (ref: 03.2 · 07 · 11 open)
- [ ] Obi.clear() drops the note, the thread and the identity; the next question is refused until a new note arrives. (ref: 03.2 done-when 7)
- [ ] Shared contracts: token-claims.json and the obi.js ↔ frame message types in packages/contracts, with a drift test against the backend verifier. (ref: 03.2 · cm-contracts)
- [ ] Done-when 1 to 7 pass in CI and once on a live run with the platform's test company, signed off. (ref: 03.2 done-when 1 to 7)

#### Security, evaluation, operations

- [ ] Lock 0 (host key + user token) live before any public deploy. (ref: 09 · s-edge)
- [ ] Every row of "what happens when a lock is missing" has a passing test. (ref: 09 table)
- [ ] Gold set of 150 to 250 reviewed cases with the fields in section 10; dev and held-out halves. (ref: 10 · e-gold, e-split)
- [ ] Stage scores: recall at k before rerank, precision at 5 and NDCG at 10 after rerank, context assembly, generation. (ref: 10 · e-stage1 to e-stage4)
- [ ] LLM judge validated against human-graded cases before use; different model from the generator. (ref: 10 · e-judge)
- [ ] Freshness target N decided; freshness and recall telemetry in production. (ref: 10 · e-monitor · 11 open)
- [ ] Evidence table kept current: every measured number names its test set, deployment, and permission setting. (ref: 10 evidence table)
- [ ] Each platform's domains in platforms.json; CSP frame-ancestors and the postMessage check read the same list. (ref: 03.2 · 07 · 11 open)
- [ ] Design document 04 updated or deleted where it contradicts 03 and 05. (ref: 11 · found while reading)

---

## 01.2 · Separation of concerns: one frontend, one backend, one knowledge base

_Section id: `concerns`_

**In plain words (the lede):** Obi has three parts. One frontend: the chat window a person types in. One backend: the code that checks who is asking, then searches and writes the answer. One knowledge base: the Postgres database where every page lives with its tags. A person only ever gets pages whose tags match their integration and which they may read.

Diagram (Top row: the frontend, the backend and the knowledge base as three boxes, joined by HTTPS and SQL. Bottom row: a Mews user gets a signed token, the backend builds an authorization context with the scopes mews and general, the scope policy and page permissions filter the rows, and the answer cites only Mews and general pages.)
  - labels: THE THREE PARTS · one folder each in the proposed layout; HTTPS; SQL; EXAMPLE · a Mews user, left to right
  - 1 · Frontend — the chat window and its proxy route / frontend/ (today: apps/web) → panel `sc-frontend`
  - 2 · Backend — verify, ingest, search, rerank, answer / backend/ (today: apps/automation) → panel `sc-backend`
  - 3 · Knowledge base — Postgres: pages, tags, row security / knowledge-base/ (schema, tags, seeds) → panel `sc-kb`
  - Mews user — signed in at the host → panel `sc-user`
  - Signed token — integration = mews → panel `em-token` (changes from today)
  - Auth context — scopes: mews, general → panel `r1-ctx` (changes from today)
  - Scope policy — tags && {mews, general} → panel `r3-scope` (changes from today)
  - Page permissions — lock 3, per person → panel `r3-acl`
  - Cited answer — mews + general only → panel `r5-evidence`

_Top: the three parts and the two channels between them. Bottom: one Mews question, left to right. A page tagged toast is never in the list. A page tagged general is. A Mews page restricted in Confluence to a group the person is not in is dropped by lock 3. Dashed borders mark parts that change from what runs today._

#### What each part owns

| Part | Owns | Belongs in its folder | Never does |
|---|---|---|---|
| Frontend | The chat window. The iframe handshake and the token held in memory. The proxy route that adds the host key. Six locales. Rendering of answers, citations, refusals and clarifying chips. | UI components. The proxy route. Shape checks on the request. The iframe bridge. A scope list generated from `knowledge_scopes.json` at build time for the dev switcher, without `classified`. | Decide who may see what. Hold a signing key. Talk to Postgres. |
| Backend | The webhook and the sweeps. Ingestion. Token verification and the authorization context. Search, rerank, coverage, generation. The citation check and the support check. The audit trail. | The FastAPI app. The five features. The clients for Confluence, OpenAI, Cohere and Claude. The job worker. The eval runner. | Trust a scope or a principal from a request body. Serve a row the database policy hides. Render UI. |
| Knowledge base | The schema. The two roles and the row policies. The migrations. The tag list. The integration-to-tags map. Curated seed data. The local Postgres for a laptop. | Models and DDL. Alembic versions. Config JSON. Seed scripts. docker-compose. | Hold page content in git. The content lives in Postgres and comes from Confluence. Hold application logic. |

#### How the three parts talk

| From | To | Channel | Carries | Status |
|---|---|---|---|---|
| Browser (chat window) | Frontend proxy | HTTPS `POST /api/chat` on the frontend's own origin | history, images, `knowledgeScope`; the user token as a bearer header (target) | [Implemented, needs changing] |
| Frontend proxy | Backend | HTTPS `POST /chat`, SSE back | the body as-is, the host key, the user token (target) | [Implemented, needs changing] |
| Backend | Knowledge base (Postgres) | SQL as `rag_reader` for reads and as the owner for writes | `set_config` for sources and scopes, then the queries | [Implemented] |
| Confluence | Backend | webhook `POST /confluence/events`; daily sweeps | page events; label search results | [Unverified] no public URL yet |
| Knowledge base folder | Postgres | `alembic upgrade head`; seed scripts | schema, roles, policies, curated entries | [Implemented] |
| Knowledge base folder | Frontend and backend | `knowledge_scopes.json` read at build time and at startup | the tag list; the integration map (proposed) | [Implemented, needs changing] |

Two rules hold the parts apart. The frontend never decides access, so a bug in the widget cannot widen what a person sees. The backend never reads a row the database would hide, so a bug in the backend cannot either. The only place a tag is defined is the knowledge base folder. Every filter reads that one list.

#### The folder structure: today and proposed

Today the code sits in one monorepo under `apps/`, `packages/`, `config/` and `infra/`. The proposed layout keeps every file and every feature boundary. It moves them under three parent folders so the folder names say what the part is. [Decision needed] The move is a rename with no logic change. Approve it and it ships as one pull request.

**Today** [Implemented]

```
repo/
├─ apps/
│  ├─ automation/        Python backend
│  │  ├─ app/main.py
│  │  ├─ features/       the five features
│  │  ├─ platform/       db, clients, settings
│  │  ├─ shared/
│  │  ├─ alembic/        versions 0001 to 0010
│  │  └─ scripts/
│  └─ web/               Next.js widget + proxy
├─ packages/
│  ├─ contracts/         chat.yaml, TS types
│  └─ design-tokens/
├─ config/
│  └─ knowledge_scopes.json
├─ infra/foundation/     local Postgres
└─ docs/adr/
```

**Proposed** [Decision needed]

```
repo/
├─ frontend/             was apps/web
│  ├─ src/features/chat/ ui, api, proxy, model
│  ├─ src/features/embed/  obi.js, frame (new)
│  └─ src/app/api/chat/  proxy route entry
├─ backend/              was apps/automation
│  ├─ app/main.py
│  ├─ features/          the same five
│  ├─ platform/          clients, settings, jobs
│  ├─ shared/
│  └─ scripts/
├─ knowledge-base/       new parent folder
│  ├─ schema/            models, roles, policies
│  ├─ migrations/        alembic env + versions
│  ├─ config/
│  │  ├─ knowledge_scopes.json
│  │  └─ platforms.json   (new)
│  ├─ seed/              curated entries
│  └─ local/             docker-compose
├─ packages/contracts/   chat.yaml, claims, msgs
└─ docs/adr/
```

#### What moves where

| Today | Proposed | Why | Status |
|---|---|---|---|
| `apps/web/` | `frontend/` | The name says what it is. Nothing inside changes. | [Decision needed] |
| `apps/automation/` | `backend/` | Same. The five feature folders and the boundary rule stay as they are. | [Decision needed] |
| `apps/automation/platform/db/` | `knowledge-base/schema/` | Models, roles and policies describe the knowledge base. They belong with it. | [Decision needed] |
| `apps/automation/alembic/` | `knowledge-base/migrations/` | A migration changes the knowledge base. Run `alembic` from this folder. | [Decision needed] |
| `config/knowledge_scopes.json` | `knowledge-base/config/knowledge_scopes.json` | The tag list is the one control surface. The frontend and the backend both read it from here. | [Decision needed] |
| rule in code: scopes = integration + general | `knowledge-base/config/platforms.json` | One file says which tags each integration may see. The backend validates a token's integration against it. | [Planned] |
| `scripts/seed_curated_knowledge.py` and the entries | `knowledge-base/seed/` | Seed data is knowledge base data. | [Decision needed] |
| `infra/foundation/` | `knowledge-base/local/` | The compose file only runs a local Postgres. | [Decision needed] |

> **One dependency direction.** The backend imports the models from `knowledge-base/schema/` as a Python package. The knowledge base folder imports nothing from the backend. The frontend imports neither; it reads the tag list as JSON at build time. The boundary checker (ADR-0003) gets one new rule for this. Deploy config changes with the move: CI paths, Dockerfiles and the hosting config point at the new folders. The move is the only change in that pull request.

#### Example: a Mews user asks a question

1. **A person at Hotel Example signs in to Mews and opens Obi.** Their signed token says `company_id = c_8f3a`, `integration = mews`, `sub = user_19f2`. The chat window holds it in memory. [Planned]
2. **The backend verifies the token and builds one authorization context.** Allowed scopes: `mews` and `general`, from the integration map. Allowed sources: `confluence`. Principal: from the trusted identity mapping, or none. [Planned]
3. **The search transaction sets the scope.** `app.allowed_knowledge_scopes = 'mews,general'`. The scope policy shows a piece only when `scope_state = 'ok'` and its tags overlap that set. A page tagged `toast` never comes back. A page tagged `general` does. [Implemented, needs changing]
4. **Lock 3 checks Confluence page permissions.** A Mews page restricted to the finance group is dropped unless the person's principal is in that group. No principal: open pages only. [Implemented]
5. **The answer cites only Mews and general pages.** The exact matching pieces are reranked, expanded to parents and checked for coverage and support. The trace row records `allowed_knowledge_scopes = mews,general` and the token subject. [Implemented, needs changing]

| Page tags | Page restriction in Confluence | A Mews user sees it? | Why |
|---|---|---|---|
| mews | none | yes | tag matches, page is open |
| general | none | yes | every integration gets general |
| mews, general | none | yes | either tag matches |
| toast | none | no | no tag overlap; the database never returns the row |
| mews | finance group only | only members of that group | lock 3 checks the person's principal |
| mews, toast | none | no | `scope_state = conflict`: hidden from everyone until an editor fixes the labels |
| classified | any | no | the page is out of the index and its pieces are deleted |
| none | any | no | a page with no recognized tag is not in the index (target) |

#### Panels that belong to this section (4)

_Workflow label shown in the drawer: Separation of concerns_

##### Panel `sc-frontend` · One frontend · [Implemented]
- Kind: Part
- In plain words: The chat window a person types in, plus the small server route that adds the secret key. It shows answers. It never decides who may see what.
- Today: apps/web: a Next.js app with the widget UI, its proxy route, and a built iframe bridge holding the token in memory. Embedded in a platform page with a scope from its config. A per-user JWT from the host gates it; the shared pilot token is retired.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Owns | the chat UI, six locales, rendering of answers and refusals, the iframe bridge (planned), the token in memory (planned), the proxy route |
  | Talks to | the backend only, over HTTPS POST /chat with SSE back |
  | Reads from the knowledge base folder | the tag list, imported at build time; the widget's scope list is generated from it, without classified |
  | Never | decides access, holds a signing key, opens a database connection |
- Where in the code:
  - `apps/web/src/features/chat/` — ui, api, server (proxy), model
  - `apps/web/src/features/embed/` — iframe bridge and token store (planned)
  - `apps/web/src/app/api/chat/route.ts` — the proxy entry
- Target and notes: Proposed folder: frontend/. A rename with no logic change. See section 01.2 for what moves where.

##### Panel `sc-backend` · One backend · [Implemented]
- Kind: Part
- In plain words: The code that checks who is asking, reads Confluence, builds the index, searches, scores and writes the answer. One backend serves every integration.
- Today: apps/automation: FastAPI, five feature folders (confluence_sync, ingestion, retrieval, rag_agent, evaluation), platform clients, the job worker.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Owns | the webhook and sweeps, ingestion, token verification, the authorization context, search, rerank, coverage, generation, the citation and support checks, the audit trail |
  | Talks to | Postgres as rag_reader for reads and as the owner for writes; Confluence, OpenAI, Cohere and Claude over HTTPS |
  | Reads from the knowledge base folder | the models, the roles and policies, the tag list, the integration map (planned) |
  | Never | trusts a scope or principal from a request body, serves a row the database hides, renders UI |
- Where in the code:
  - `apps/automation/app/main.py` — wires everything
  - `apps/automation/features/` — the five features
  - `apps/automation/platform/` — clients, settings, jobs (and today also db models)
- Target and notes: Proposed folder: backend/. The five features and the boundary rule (ADR-0003) stay exactly as they are.

##### Panel `sc-kb` · One knowledge base · [Implemented, needs changing]
- Kind: Part
- In plain words: One Postgres database holds every page in pieces with its tags. The database itself hides rows a person may not see. The folder next to it holds the schema, the tags and the seed data, never the pages.
- Today: Supabase Postgres with pgvector. Schema and policies in platform/db, migrations in alembic/versions (12 files through 0012), the tag list in config/knowledge_scopes.json, curated seeds in scripts/, a local compose file in infra/foundation.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Holds in Postgres | pages, versions, chunks with vectors, page restrictions, the queue, the audit trail, curated entries |
  | Holds in the folder | models and DDL, roles and row policies, alembic versions, knowledge_scopes.json, platforms.json (planned), seed scripts, docker-compose |
  | Filters by | tags (lock 2), source (lock 1), page restrictions (lock 3); the policies run inside Postgres |
  | Never | holds page content in git, holds application logic |
- Where in the code:
  - `platform/db/models.py, schema.py` — tables, roles, policies
  - `alembic/versions/` — 0001 to 0010
  - `config/knowledge_scopes.json` — the tag list
  - `scripts/seed_curated_knowledge.py` — curated seeds
- Target and notes: Proposed folder: knowledge-base/ with schema/, migrations/, config/, seed/ and local/. The backend imports schema/ as a package. The folder imports nothing back.

##### Panel `sc-user` · A Mews user · [Planned]
- Kind: Example
- In plain words: A person who works at a hotel that runs Mews. They sign in to the host application, and that sign-in is what tells Obi who they are.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Company | Hotel Example Group, company_id c_8f3a |
  | Integration | mews |
  | Person | sub user_19f2; principal only if the identity mapping exists |
  | Gets | pages tagged mews or general that they may read |
- Target and notes: Today no per-person identity reaches the backend. The pilot uses one shared token. See section 03.2.

---

## 02 · Where the code lives

_Section id: `code`_

**In plain words (the lede):** This is the map of the code as it is today. One repository holds everything. The backend is Python under `apps/automation`. The widget is Next.js under `apps/web`. The proposed three-folder layout is in section 01.2 and stays marked as proposed until you approve it.

Diagram (Folder map: the backend features confluence_sync, ingestion, retrieval, rag_agent and evaluation, plus platform, shared, alembic, scripts and the scopes config file. The frontend app, the contracts package, the design tokens and the ADR folder.)
  - labels: apps/automation · the Python backend (FastAPI, SQLAlchemy, Alembic, uv); frontend and shared packages (pnpm)
  - app/main.py — wires everything → panel `cm-root`
  - confluence_sync — receive + sweeps → panel `cm-sync`
  - ingestion — chunk, embed, swap → panel `cm-ingest`
  - retrieval — search, rerank → panel `cm-retrieval`
  - rag_agent — /chat, judge, answer → panel `cm-agent`
  - evaluation — gold set, metrics → panel `cm-eval`
  - platform/ — db, clients, config → panel `cm-platform`
  - shared/ — rate limiter, hashing → panel `cm-shared`
  - alembic/versions — 0001 to 0010 → panel `cm-alembic`
  - scripts/ — operator one-offs → panel `cm-scripts`
  - knowledge_scopes — .json, the scope list → panel `cm-config`
  - docs/adr — 14 decisions → panel `cm-docs`
  - apps/web — the Obi widget → panel `cm-web`
  - packages/contracts — chat.yaml, TS types → panel `cm-contracts`
  - design-tokens — colors, type → panel `cm-tokens`
  - infra/foundation — local Postgres → panel `cm-infra`

_config/knowledge_scopes.json sits at the repo root, next to apps/ and packages/, so both apps read the same file._

#### Who owns which table

| Feature | Writes | Reads | Role |
|---|---|---|---|
| confluence_sync | page_source, page_restriction, event_ledger, job, reconciliation_run | Confluence API | writer (owner) |
| ingestion | document, document_version, chunk | page blocks from confluence_sync | writer (owner) |
| retrieval | query_trace (retrieval half) | chunk, page_source, page_restriction, curated_knowledge_entry | rag_reader |
| rag_agent | query_trace (answer half), curated_knowledge_entry (via seed script) | everything retrieval returns | reader for reads, writer for trace |
| evaluation | eval-reports/ on disk | the whole retrieval workflow | reader |

> **The boundary rule.** `tools/check_feature_boundaries.py` fails the build if one feature imports deep inside another. Cross-feature calls go through each feature's `__init__.py`. `platform/` and `shared/` import no features. This is ADR-0003, and it is why the parts below can be swapped one at a time.

#### Panels that belong to this section (16)

_Workflow label shown in the drawer: Code map_

##### Panel `cm-root` · app/main.py: the wiring · [Implemented]
- Kind: File
- In plain words: Starts the app and plugs every part together.
- Today: Builds the FastAPI app, the retriever, the answer service, the scheduler, and mounts the two routers.
- Where in the code:
  - `apps/automation/app/main.py` — create_app, build_answer_service
  - `apps/automation/app/platform/config/settings.py` — every knob, read from .env
- Steps:
  1. Read settings.
  2. Build the reader engine (fails closed without DATABASE_READER_URL outside local).
  3. Build HybridRetriever with embedder, reranker, and the scope flag.
  4. Build AnswerService with rewriter, generator, and the recognized scopes.
  5. Mount /confluence/events and /chat. Start the sweep scheduler.

##### Panel `cm-sync` · features/confluence_sync · [Implemented]
- Kind: Feature
- In plain words: The code that talks to Confluence: hears events, runs sweeps, turns labels into tags.
- Today: Owns receive, decide, sweeps, and the label-to-tag rule. Writes page_source, page_restriction, event_ledger, job, reconciliation_run.
- Where in the code:
  - `server/webhook.py` — POST /confluence/events
  - `application/event_service.py` — ledger dedup, job keys
  - `infrastructure/event_repo.py` — record_event
  - `application/worker.py` — three-transaction job loop
  - `application/sync_service.py` — handle_sync_page, the decision
  - `domain/change_detection.py` — classify
  - `domain/knowledge_scope.py` — labels to scope tags
  - `application/reconciliation.py` — daily and complete sweeps
  - `domain/scope_resolver.py` — source_scope roots (retiring)

##### Panel `cm-ingest` · features/ingestion · [Implemented]
- Kind: Feature
- In plain words: The code that cuts pages into pieces, makes meaning codes, and swaps the new version live.
- Today: Owns chunking, contextualization, embedding reuse, attachment extraction, and versioning. Writes document, document_version, chunk, page_source.
- Where in the code:
  - `domain/chunking.py` — parents and children
  - `application/contextualizer.py` — title, path, LLM note
  - `domain/chunk_diff.py` — which children can reuse a vector
  - `domain/attachment_extraction.py` — PDF, DOCX, XLSX, CSV to blocks
  - `application/versioning.py` — stage_and_activate, rollback_to, GC

##### Panel `cm-retrieval` · features/retrieval · [Implemented]
- Kind: Feature
- In plain words: The code that searches, merges results, checks page permissions, and calls the reranker.
- Today: Owns search, fusion, the page ACL, rerank wiring, and the retrieval half of query_trace. The rag_reader binding itself lives in platform/db/engine.py; this folder only comments on it.
- Where in the code:
  - `application/retriever.py` — HybridRetriever: the search transaction
  - `infrastructure/search_repo.py` — dense_search, keyword_search, GUCs, rerank texts, parents
  - `domain/fusion.py` — reciprocal_rank_fusion
  - `domain/permission.py` — classify_scope, PrincipalPermissionPolicy
  - `domain/knowledge_scope.py` — resolve_allowed_scopes
  - `infrastructure/trace_repo.py` — write_query_trace

##### Panel `cm-agent` · features/rag_agent · [Implemented]
- Kind: Feature
- In plain words: The code behind the chat endpoint: decides to answer or refuse, and cuts sentences without a source.
- Today: Owns POST /chat, the answer workflow, refusal, citations, prompts, curated knowledge, and the answer cache (to remove).
- Where in the code:
  - `server/router.py` — POST /chat, PATCH feedback, auth, limits, SSE
  - `application/answer_service.py` — the fixed workflow
  - `infrastructure/llm_client.py` — rewrite, generate, small talk, clarification, image
  - `domain/prompt.py` — system prompts and the evidence block
  - `domain/citations.py` — enforce_citations
  - `domain/refusal.py` — decide_refusal
  - `domain/small_talk.py, domain/clarification.py` — the two short-circuits
  - `domain/pii.py` — redact_pii
  - `infrastructure/curated_knowledge_repo.py` — fetch_curated_entries
  - `application/answer_cache.py` — CachingAnswerService (remove)

##### Panel `cm-eval` · features/evaluation · [Planned]
- Kind: Feature
- In plain words: The code that runs the test questions and scores the answers.
- Today: A DB-free baseline runner over synthetic fixtures. Latency helpers exist but are unwired. No gold set.
- Where in the code:
  - `run_baseline.py, runner.py` — make eval
  - `metrics/` — precision, ndcg, rerank lift, fallback rate, latency helpers
  - `datasets/` — retrieval_smoke, permission, ambiguity, out_of_corpus

##### Panel `cm-platform` · platform/: shared technical capabilities · [Implemented]
- Kind: Folder
- In plain words: Shared plumbing: database setup, API clients, settings, the job queue.
- Today: Database models and roles, the four API clients, settings, the job queue. Imports no feature.
- Where in the code:
  - `platform/db/models.py, enums.py, schema.py, engine.py` — tables, enums, roles and policies, engines
  - `platform/clients/confluence_client.py` — Confluence
  - `platform/clients/embeddings_client.py` — OpenAI, Voyage, fake, local
  - `platform/clients/reranker_client.py` — Cohere, fake
  - `platform/clients/anthropic_client.py` — Claude messages with images
  - `platform/config/settings.py, knowledge_scopes.py` — settings and the scope-list loader
  - `platform/jobs/queue.py` — enqueue, claim, complete, fail, reap

##### Panel `cm-shared` · shared/: small generic helpers · [Implemented]
- Kind: Folder
- In plain words: Small helpers used everywhere, like the rate limiter and hashing.
- Where in the code:
  - `shared/rate_limiter.py` — SlidingWindowRateLimiter, used by webhook and chat
  - `shared/ttl_cache.py` — TTLCache, used by idempotency (and the answer cache, to remove)
  - `shared/hashing.py` — hash_json, sha256_text

##### Panel `cm-alembic` · alembic/versions: the migrations · [Unverified]
- Kind: Folder
- In plain words: The numbered history of every database change.
- Today: 0001 core schema, 0002 provider tags and RLS, 0003 query_trace, 0004 source_scope, 0005 page_restriction, 0006 dedupe check constraints, 0007 knowledge scope, 0008 drop FORCE RLS, 0009 reader policies, 0010 scope RLS. Live head on Supabase: 0012.
- Steps:
  1. Every migration has a downgrade.
  2. 0010 must be applied live before any public deploy.
  3. The target adds one migration, 0011: scope_state, index_fingerprint and its uniqueness key, the pending-job index, curated embeddings and indexes, the two RESTRICTIVE policies, and three trace columns. The DDL is written out below and in section 08.1.
- Code:
```
-- 0011_target_schema (one migration, one downgrade)

-- 1. scope_state on chunk and page_source
CREATE TYPE scope_state AS ENUM ('ok','conflict','classified','unlabeled');
ALTER TABLE chunk        ADD COLUMN scope_state scope_state NOT NULL DEFAULT 'unlabeled';
ALTER TABLE page_source  ADD COLUMN scope_state scope_state NOT NULL DEFAULT 'unlabeled';

-- 2. index_fingerprint: the identity of a build
ALTER TABLE page_source      ADD COLUMN index_fingerprint text;
ALTER TABLE document_version ADD COLUMN index_fingerprint text;
ALTER TABLE document_version DROP CONSTRAINT uq_document_version_idem;
ALTER TABLE document_version ADD CONSTRAINT uq_document_version_fingerprint
  UNIQUE (document_id, index_fingerprint);
-- ux_document_version_one_active (one active per document) stays as it is

-- 3. one pending sync_page job per page
CREATE UNIQUE INDEX ux_job_pending_sync_page
  ON job (page_id) WHERE status = 'pending' AND job_type = 'sync_page';

-- 4. curated entries searched like chunks
ALTER TABLE curated_knowledge_entry ADD COLUMN embedding vector(3072);
ALTER TABLE curated_knowledge_entry ADD COLUMN tsv tsvector;
ALTER TABLE curated_knowledge_entry ADD COLUMN scope_state scope_state NOT NULL DEFAULT 'ok';
CREATE INDEX ix_curated_embedding_hnsw ON curated_knowledge_entry
  USING hnsw ((embedding::halfvec(3072)) halfvec_cosine_ops)
  WITH (m = 16, ef_construction = 200) WHERE is_active AND embedding IS NOT NULL;
CREATE INDEX ix_curated_tsv_gin ON curated_knowledge_entry USING gin (tsv) WHERE is_active;

-- 5. the scope policy: state ok and a real tag match, no empty-tags floor
DROP POLICY IF EXISTS chunk_scope_read ON chunk;
CREATE POLICY chunk_scope_read ON chunk AS RESTRICTIVE FOR SELECT
  USING (scope_state = 'ok' AND (
    current_setting('app.allowed_knowledge_scopes', true) = '*'
    OR tags && string_to_array(current_setting('app.allowed_knowledge_scopes', true), ',')));
DROP POLICY IF EXISTS curated_knowledge_entry_scope_read ON curated_knowledge_entry;
CREATE POLICY curated_knowledge_entry_scope_read ON curated_knowledge_entry AS RESTRICTIVE FOR SELECT
  USING (scope_state = 'ok' AND (
    current_setting('app.allowed_knowledge_scopes', true) = '*'
    OR tags && string_to_array(current_setting('app.allowed_knowledge_scopes', true), ',')));

-- 6. trace: what the target adds
ALTER TABLE query_trace ADD COLUMN token_subject_hash text;
ALTER TABLE query_trace ADD COLUMN candidate_chunk_ids integer[];
ALTER TABLE query_trace ADD COLUMN decision text;

-- backfill before the policy is trusted: every active chunk with a recognized tag -> 'ok';
-- verify_knowledge_scope_backfill.py must report zero rows in any other state.
```
- Target and notes: Never run the 0009 downgrade on Supabase. It would expose the tables to the public anon role.

##### Panel `cm-scripts` · scripts/: operator tools · [Implemented]
- Kind: Folder
- In plain words: One-off tools an operator runs by hand.
- Where in the code:
  - `setup_supabase.py` — preflight, provision-reader, verify-isolation
  - `seed_source_scope.py` — folder roots (retiring)
  - `seed_curated_knowledge.py` — upsert curated entries
  - `run_reconciliation_once.py` — one manual sweep
  - `verify_knowledge_scope_backfill.py` — readiness gate: zero untagged chunks
  - `verify_knowledge_scope_live.py` — add, edit, remove a real label and check the DB
  - `rotate_chat_api_key.py` — overlap-window key rotation

##### Panel `cm-config` · config/knowledge_scopes.json: the scope list · [Implemented, needs changing]
- Kind: File
- In plain words: The tag list. A Confluence label in this file is a knowledge scope; add a name to add a tag.
- Today: Holds obi-general-test, obi-mews-test, obi-operacloud-test, obi-toast-test. Loaded at startup; startup fails if the general scope is missing. The widget's scope list is a hand-written copy of this file, guarded by a runtime drift test, not generated at build time.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Target list | general, mews, toast, classified (opera-cloud: confirm) |
  | Read by | the backend loader at startup, and the widget build, which imports the same file and generates its scope list (no hand-written copy, no drift test) |
  | Matching | case-insensitive, exact |
  | Next to it (planned) | platforms.json: one entry per platform (issuer, key URL, domains) plus which tags each integration may see |
- Where in the code:
  - `config/knowledge_scopes.json` — the list
  - `platform/config/knowledge_scopes.py` — load_recognized_knowledge_scopes
  - `apps/web/src/features/chat/model/knowledge-scopes.ts` — generated from the JSON at build time, without classified
- Code:
```
{
  "scopes": ["general", "mews", "toast", "classified"]
}
```

##### Panel `cm-docs` · docs/adr: the decisions of record · [Implemented]
- Kind: Folder
- In plain words: The written record of big decisions and why.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | 0001 | stack: Postgres + pgvector, FastAPI, Next.js |
  | 0002 | retrieval core: hybrid, RRF, versioned store |
  | 0003 | feature boundaries |
  | 0004 | provider tags and source RLS |
  | 0005 | reranking and the answer pipeline |
  | 0008 | clarification fallback |
  | 0009 | image analysis |
  | 0011 | knowledge scopes |
  | 0013 | Supabase on AWS, NO FORCE RLS |
  | 0014 | scope RLS backstop |
- Target and notes: Changing any fixed decision needs a new ADR. The changes on this page need at least one: the fingerprint, scope_state, label-gated ingestion, and the edge token.

##### Panel `cm-web` · apps/web: the widget · [Implemented]
- Kind: App
- In plain words: The chat widget's code.
- Today: server/auth.ts has been deleted; the proxy no longer uses it. The iframe bridge (src/features/embed/) is built and tested, not planned.
- Where in the code:
  - `src/features/chat/ui/` — launcher, teaser, panel, composer, bubbles, menus
  - `src/features/chat/api/chat-client.ts` — SSE parsing
  - `src/features/chat/server/route-handlers.ts, validation.ts, auth.ts` — the proxy
  - `src/features/chat/model/` — messages, i18n, knowledge-scopes
  - `src/app/api/chat/route.ts` — thin route entry
  - `src/features/embed/` — iframe bridge, token store (planned, section 03.2)

##### Panel `cm-contracts` · packages/contracts · [Implemented]
- Kind: Package
- In plain words: The shared shape of a request and an answer, so widget and backend agree.
- Today: token-claims.json and iframe-messages.ts already exist and are wired, not planned.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Source of truth | src/openapi/chat.yaml |
  | Types | ChatRequest, ChatTurn, ImageAttachment, ChatStreamEvent, Citation, FeedbackRequest |
  | Planned | token-claims.json (the note's fields) and iframe-messages.ts (obi:open, obi:token, obi:clear) |
- Target and notes: The backend hand-writes matching Pydantic models. A drift test between the two is a cheap safeguard worth adding.

##### Panel `cm-tokens` · packages/design-tokens · [Implemented]
- Kind: Package
- In plain words: Colors and fonts for the widget.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Holds | the widget's colors, type, and the Tailwind theme mapping |
  | Style | light theme, indigo accent, Inter |

##### Panel `cm-infra` · infra/foundation: local Postgres · [Implemented]
- Kind: Folder
- In plain words: A local Postgres so everything runs on a laptop.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | docker-compose | pgvector image pinned to 0.8.x |
  | Use | local development and the test database; production is Supabase |

---

## 03 · What arrives at the system

_Section id: `arrives`_

**In plain words (the lede):** Three things come into Obi from outside. Confluence sends a message when an editor publishes a page. A person sends a question from the chat window. Settings come from the code and from the deployed `.env` file. Each of the three has a fixed shape that the tables below spell out.

#### Confluence events (webhook or sweep)

| Event group | Events | Job it creates |
|---|---|---|
| SYNC_EVENTS | page created, updated, moved, restored, unarchived; attachment created, updated, removed; label added, deleted; page permissions updated. Only **published** pages fire these. A draft or an unpublished edit never reaches us. | `sync_page`, one per page |
| DELETE_EVENTS | page trashed, archived, removed, deleted | `delete_page`, higher priority |
| SPACE_EVENTS | space updated, space permissions updated | `reconcile_space` |
| everything else | comments, likes, blog posts, and so on | ignored, logged |

Each event carries the page id, the page version, the space id, the actor, a timestamp, and a delivery id. The parser accepts both the nested and the flat webhook shapes. Label and permission events do **not** bump the page version. This matters in ingestion stage 2. Confluence sends an event only when an editor clicks Publish. The Confluence API also returns the published version only. So Obi never sees a half-written page.

#### The chat request

| Field | What it is | Limit |
|---|---|---|
| history | the turns so far, must end on a user turn | 20 turns, 4000 chars each |
| images | base64 images on the newest turn only | 4 per turn, 5 MB each |
| knowledgeScope | which platform the widget sits in, for example `mews` | a lowercase slug, checked for shape and against the list; unknown slug: 400. The token decides the scope. A known slug that disagrees with the token is ignored and logged [Implemented, needs changing] |
| principal | who is asking, for page-level access | derived from the token's `sub` through the identity mapping, never from the body [Implemented, needs changing] |
| Authorization header | one shared server key today; a key per widget host plus a signed user token from the host backend in the target (section 03.2) | fail closed if missing [Planned] |
| Idempotency-Key | optional; a replay of the same request returns the same answer | bound to token, history, scope |

#### Settings that shape behavior

| Setting | Default in code | Deployed value | Where |
|---|---|---|---|
| embedding_provider / model / dim | voyage, voyage-3-large, 1024 | openai, text-embedding-3-large, 3072 | settings.py:61-63, root .env |
| reranker_model | rerank-v3.5 | rerank-v3.5 (v4.0 exists; swap only with a threshold retune) | settings.py:83 |
| answer_model / routing_model | claude-sonnet-5 / claude-haiku-4-5 | same | settings.py:57-58 |
| refusal_min_rerank_score | 0.10 (provisional) | 0.10 | settings.py:99 |
| enable_knowledge_scope_filtering | false | true | .env |
| knowledge scopes | the JSON file | obi-general-test, obi-mews-test, obi-operacloud-test, obi-toast-test | config/knowledge_scopes.json |

> **The .env wins over the code default.** [Decision needed] The code says Voyage at 1024 dims. The deployed .env says OpenAI at 3072 dims. Both paths exist and both are tested. The live index uses the OpenAI 3072 path (a `halfvec` cast). Pick one as the default in code so a fresh deploy with no .env does not build a different index by surprise.

---

## 03.1 · Glossary: the words used everywhere below

_Section id: `glossary`_

**In plain words (the lede):** Nineteen words carry most of the meaning on this page. Each one is used in exactly one sense. Read them once and the stage sections read faster. The last seven belong to the embedding work in the next section.

| Word | Meaning here |
|---|---|
| Ingestion | Workflow 1. Everything between an editor clicking Publish in Confluence and the page sitting in Postgres as active chunks with vectors. |
| Retrieval | Workflow 2. Everything between a question typed in the widget and a cited answer or a refusal. |
| Chunk | One piece of a page stored as one row in the `chunk` table. Two kinds: parent and child. |
| Parent | A big chunk, about 1200 tokens, one section of a page. Not embedded. The answer model reads parents. |
| Child | A small chunk, about 400 tokens, cut from inside one parent. Embedded and indexed. Search matches on children. |
| Embedding | A list of 3072 numbers produced by a model from a piece of text. Texts with similar meaning have similar embeddings. Also called a vector. |
| Hybrid search | Two searches run together: dense (nearest embeddings) and keyword (Postgres full text). Each returns 75 children. |
| RRF | Reciprocal rank fusion. Merges the two ranked lists into one. Score = sum of 1 / (60 + rank). Ranked item: child chunk id (target), page id (today). |
| Reranking | A cross-encoder (Cohere) reads the question and one passage together and returns a relevance score. Runs on the fused candidates. |
| Context | The final set of parent passages handed to the answer model, after expansion, dedupe, and the token budget. The coverage check runs on this. |
| Knowledge scope | A tag. One of the names in `config/knowledge_scopes.json`. Decides which pages a widget may see. |
| Authorization context | The one object stage 1 of retrieval builds: company, integration, allowed scopes, allowed sources, principal. Every read uses it. |
| Company | The tenant: a hotel or restaurant group. Comes from the token as `company_id`. Tags do not know about companies; a company rule is a separate decision. |
| Integration | The system the company runs: `mews`, `toast`, `opera-cloud`. Comes from the token. Maps to the allowed tags through `platforms.json`. |
| Host application | The software that shows Obi inside its screens: Mews, Toast or an Omniboost app. It signs the person in and its backend issues the token. |
| iframe | A window inside a web page that shows another site. Obi runs in one, on its own origin, inside the host's page. |
| JWT | A signed note in JSON. Anyone who holds it can read it. The signature proves nobody changed it. It does not hide the contents. |
| postMessage | The browser's way for two windows on different origins to send each other messages. Both sides must check who sent what. |
| Principal | The identity Confluence page permissions are checked against: an Atlassian account id. Comes from a trusted mapping of the token's `sub`, or is absent. |

---

## 03.2 · Embedding Obi in another application: one script tag, a signed note, and what a person may see

_Section id: `embed`_

**In plain words (the lede):** A platform like Mews or Toast adds one script tag to its page. Our script draws a round Obi button at the top of the screen. Click it and the chat window pops up. At that click the script fetches a short signed note from the platform's own server that says who this is: an id, the company name and the integration. Obi checks the note and answers from the pages that integration may see. No values on the note: general pages only.

> **Status.** [Planned] The script, the frame, the note and its check do not exist yet. Today one shared key and one shared pilot token do this job. Two calls are made on this page: the note is fetched at the button click, and it lives about an hour with silent renewal. Both are settings, so either can change without touching the design.

> **What this protects.** Obi holds verified, shareable knowledge. It keeps Mews content and Toast content apart and honors Confluence page permissions. It is not a vault. Secrets never enter it, and a page labeled `classified` is deleted from the index. The note is readable by anyone who holds it. The signature only proves nobody changed it.

#### Who talks to whom

Diagram (On the platform's page: one script tag loads obi.js from our domain, which draws the button and the frame; at the click it fetches a signed note from the platform's own server; it hands the note to the frame and renews it silently. At Obi: the backend checks the note, picks the pages the integration may see, and answers with citations.)
  - labels: ON THE PLATFORM'S PAGE · Mews, Toast, an Omniboost app; AT OBI
  - 1 · One script tag: obi.js — our script, from our domain / draws the round button and the frame → panel `em-loader` (changes from today)
  - 2 · The platform's server — one endpoint signs a short note / id · company name · integration, or none → panel `em-hostbackend` (changes from today)
  - 3 · obi.js holds the note — fetched at the click, kept in memory / renewed silently, sent with every question → panel `em-token` (changes from today)
  - 4 · Obi checks the note — real, meant for Obi, not expired / bad note: refused, no search → panel `em-backend` (changes from today)
  - 5 · Obi picks the pages — mews → mews + general / no values → general only → panel `em-kb` (changes from today)
  - 6 · Obi answers — cited from those pages only / page permissions still apply → panel `ov-answer`

_Solid borders run today. Dashed borders are the new part. The platform writes no UI and no messaging code. Box 2 is the one thing it builds._

#### The plan, step by step

We build the script and the frame once. We prove the whole flow on our own test pages first. Then every platform gets the same template and follows it with its own values. Our code does not change per platform; one config entry does. Changes to the button or the chat ship from our side, and the platform redeploys nothing.

| Step | We do (Obi) | The platform does (Mews, Toast, the next one) |
|---|---|---|
| 1 | Build the frame page (the round button and the chat window) and `obi.js`, the script that draws the frame, fetches the note, renews it and talks to the frame. |  |
| 2 | Change the backend so it accepts the note: check the signature, read the three values or none, pick the tags. Trusted platforms live in `platforms.json`, one entry each, with the note lifetime per platform. |  |
| 3 | Build four test host pages on our own domain. Each one has its own note endpoint that hands out a different set of values: none; a Mews company; a Toast company; a second Mews company. Run the whole flow on all four: click, note, check, answers, silent renewal after an hour, logout. |  |
| 4 | Hand over the template below: one script tag, one init call, the note structure, the four things we need back, and one of the test pages to copy. | Read it. Name one engineer. |
| 5 |  | Send us four things: the issuer name it will put on the note, the public key URL, the domains the button will live on, and the integration value it will send. |
| 6 | Add the platform's entry to `platforms.json`. Deploy. |  |
| 7 |  | Add the script tag and the init call to the page. |
| 8 |  | Build one endpoint, `/api/obi-token`: signed-in people only; the three values from its own session, or none; signed with its private key; lifetime as agreed. |
| 9 | Run the checks at the bottom against the platform's test company. | Give us a test company per integration and one test user in a restricted Confluence group. |
| 10 | Next platform: repeat 6 and 9. | Next platform: repeat 5, 7, 8 and 9 with its own values. Same template. |

#### The template every platform follows

**A · One script tag and one init call.** The only line the platform edits is the address of its own note endpoint. Two technical notes. First: `obi.js` runs inside the platform's page, so `fetch(tokenUrl)` is a same-origin request and carries the platform's session cookie by itself; no CORS is needed as long as the endpoint lives on the same origin as the page. If the platform serves it from another origin, that endpoint must allow the page's origin with credentials. Second: the frame page `/embed` is served with a `Content-Security-Policy: frame-ancestors` header built at request time from every domain in `platforms.json`; with an empty list outside local the frame returns 403 instead of rendering.

```
<script src="https://obi.omniboost.com/obi.js"></script>
<script>
  Obi.init({ tokenUrl: "/api/obi-token" });   // your endpoint (step 8)

  // on logout or company switch:
  // Obi.clear();
</script>
```

| obi.js does this for the platform | The platform never writes |
|---|---|
| Draws the round button and opens the chat window in a frame from our domain. Fetches the note from `tokenUrl` at the click. Hands it to the frame over a checked channel. Renews it silently before it expires and after a long idle stretch. On `Obi.clear()` forgets the note and the chat. | An iframe tag. Messaging code. Origin checks. Renewal timers. Any UI. |

**B · The note.** The platform's server signs and returns this from `/api/obi-token`, for signed-in people only. The three business fields are optional. Send all three or none.

**Default: no values** → general pages only

```
{
  "iss": "https://app.mews.com",
  "aud": "obi",
  "sub": "the person's id",
  "iat": 1757577600,
  "exp": 1757581200
}
```

**With the three values** → that integration + general

```
{
  "iss": "https://app.mews.com",
  "aud": "obi",
  "sub": "the person's id",
  "iat": 1757577600,
  "exp": 1757581200,
  "company_id": "c_8f3a",
  "company_name": "Hotel Example Group",
  "integration": "mews"
}
```

| Field | Rule |
|---|---|
| iss | the platform's name, the same string it sends us in step 5 |
| aud | always `obi` |
| sub | the person's id at the platform, stable, not an email |
| iat, exp | issued now; expires after the agreed lifetime (default 60 minutes) |
| company_id | the company's stable id; goes on the audit trail |
| company_name | shown in the chat header; never decides access |
| integration | one of the values in our map: `mews`, `toast`; anything else is refused |
| signature | RS256 or ES256, private key on the platform's server, key id in the header |

**C · What we need back, once per platform.**

| Item | Example |
|---|---|
| issuer name | `https://app.mews.com` |
| public key URL | `https://app.mews.com/.well-known/obi-jwks.json` |
| domains | `app.mews.com`, `staging.mews.com` |
| integration value | `mews` |

#### One template, many platforms

Each platform is one entry in our config. Nothing else in our code knows the platform's name. The lifetime sits in the entry, so one platform can run an hour and another fifteen minutes.

```
{
  "platforms": {
    "mews": {
      "issuer":   "https://app.mews.com",
      "jwks_url": "https://app.mews.com/.well-known/obi-jwks.json",
      "domains":  ["app.mews.com"],
      "lifetime_minutes": 60
    },
    "toast": {
      "issuer":   "https://pos.toasttab.com",
      "jwks_url": "https://pos.toasttab.com/.well-known/obi-jwks.json",
      "domains":  ["pos.toasttab.com"],
      "lifetime_minutes": 60
    }
  },
  "integrations": {
    "mews":  ["mews", "general"],
    "toast": ["toast", "general"]
  }
}
```

| Changes per platform | Stays the same |
|---|---|
| the issuer name, the public key, the domains, the lifetime, the integration value, the note endpoint on its side | `obi.js`, the frame, the init call, the note structure, our backend code, the knowledge base |

#### Why the note stays signed

Values typed into the page can be changed by anyone with the browser's developer tools open. A Mews user could set `integration: "toast"` and read Toast documentation. With a signed note that edit breaks the signature and the request is refused. Today that only guards shareable documentation. The moment one company-specific page or one restricted page enters the knowledge base, the signature is what stops anyone from claiming any company. The platform pays for this once, with one small endpoint.

#### Done when

1. All four test host pages pass the checks below before any platform is involved.
2. A Mews note gets Mews and general pages, and never a Toast-only page.
3. A note with no values gets general pages only.
4. A changed, expired or missing note is refused before any search.
5. A message from a domain not in the platform's entry is ignored.
6. After an hour of use the chat still works, and the renewal happened without a click.
7. After `Obi.clear()` the page holds no note and no chat.

Still to decide: which platform goes first, whether embedded users need per-person Confluence page permissions, and the lifetime per platform. They are in section 11.

#### Panels that belong to this section (6)

_Workflow label shown in the drawer: Embedding Obi in another application_

##### Panel `em-token` · The signed note (JWT) · [Implemented]
- Kind: Contract
- In plain words: A short signed note from the platform's server. By default it carries no values. With values it carries an id, the company name and the integration. obi.js fetches it at the click and renews it silently. Obi checks the signature before it reads a word of it.
- Today: Built: a short signed JWT per user carrying company_id, company_name and integration, verified before any search — live-proven for test hosts (commit 59385f4).
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Default | no values: general pages only |
  | Three values | company_id, company_name, integration |
  | Always | iss, aud = obi, sub, iat, exp |
  | Signed with | the platform's private key; key id in the header |
  | Lifetime | per platform, default 60 minutes; renewed silently by obi.js |
  | Readable | yes: base64 JSON; the signature only proves nothing changed |
  | Never in | a URL, a cookie, web storage, a log line |
- Code:
```
{
  "iss": "https://app.mews.com",
  "aud": "obi",
  "sub": "user_19f2",
  "iat": 1757577600,
  "exp": 1757581200,
  "company_id": "c_8f3a",
  "company_name": "Hotel Example Group",
  "integration": "mews"
}
```
- How to test it:
  - Change one character of integration: signature fails, refused.
  - exp in the past: refused.
  - No values: general pages only.
  - A valid mews note and a body scope of toast: scoped to mews.
- Target and notes: The issuer URL, the key id and the sub format are placeholders. Nothing is configured until the decisions in section 11 are made.

##### Panel `em-loader` · obi.js: one script tag · [Implemented]
- Kind: Frontend
- In plain words: One line on the platform's page loads our script. The script draws the round button, opens the chat window in a frame from our domain, fetches the note, renews it and talks to the frame. The platform writes none of that.
- Today: Built and unit-tested: draws the round button, opens the chat window in a frame from our domain, fetches the note and renews it. Obi.clear() forgets the note and closes the panel, degrading to general-only rather than blocking sending, until a new note arrives. Replaces the earlier straight-embed pilot flow that read a shared token from the URL.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Loads from | https://obi.omniboost.com/obi.js, versioned; changes ship from our side |
  | Init | Obi.init({ tokenUrl }); tokenUrl is the platform's note endpoint and the only value it edits |
  | At the click | fetch(tokenUrl) from inside the platform's page: same-origin, so the platform's session cookie goes along by itself and no CORS is needed; an endpoint on another origin must allow the page's origin with credentials |
  | Hands the note | to the frame by postMessage with the exact Obi origin; the frame accepts it from the parent window only |
  | Renewal | a timer fires before exp; after a long idle stretch the next activity fetches a fresh note; no click needed |
  | Obi.clear() | forgets the note, empties the chat, hides the company name, blocks sending until a new note arrives |
  | Never | a note in a URL, a cookie or web storage |
- Where in the code:
  - `apps/web/src/features/embed/loader.ts` — built to public/obi.js (planned)
  - `apps/web/src/features/embed/iframe-bridge.ts` — the frame side of the channel (planned)
  - `apps/web/src/app/embed/page.tsx` — the frame's page (planned)
- How to test it:
  - The platform's page contains one script tag and one init call and nothing else from us.
  - A note is fetched at the first click, not at page load.
  - After 61 minutes of use a question still answers and the log shows one silent renewal.
  - A message from a domain not in the platform's entry: no note stored, one log line.
- Target and notes: This is the piece that makes changes ours to ship. A fix in the handshake never needs the platform to edit its page.

##### Panel `em-hostbackend` · The platform's note endpoint · [Decision needed]
- Kind: Outside system
- In plain words: One endpoint on the platform's own server. It knows who is signed in, which company they belong to and which integration that company runs. It writes those on a short signed note, or writes none.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Route | /api/obi-token (any path; the platform tells obi.js which) |
  | Who may call it | signed-in people only; it uses the platform's own session |
  | Default | no values: iss, aud = obi, sub, iat, exp only |
  | With values | company_id, company_name, integration, from its own records, never from the browser |
  | Signs with | a private key that stays on its server (RS256 or ES256), key id in the header |
  | Lifetime | as agreed per platform, default 60 minutes |
  | Gives Obi once | issuer name, public key URL, domains, integration value |
- How to test it:
  - Two companies never share a company_id.
  - A company that does not run Toast never gets integration = toast.
  - A call without a session gets nothing.
- Target and notes: The one thing the platform builds. Decision needed: the platform signs directly, or an auth service the two teams agree on does.

##### Panel `em-backend` · Obi checks the note and picks the pages · [Implemented]
- Kind: Backend
- In plain words: Obi's server checks the note is real, meant for Obi and not expired. Then it reads the values and writes one note of its own that every later step obeys: which company, which integration, which tags.
- Today: One shared CHAT_API_KEY is compared in constant time, plus per-user JWT verification (issuer, signature, audience, expiry) that builds the AuthContext; principal comes from the token, not the request body — live-proven for test hosts (commit 59385f4).
- Settings and rules:
  | Setting | Value |
  |---|---|
  | platforms.json | one entry per platform: issuer, public key URL, domains, lifetime; plus the integration map |
  | Lifetime check | exp minus iat must not exceed the platform's lifetime_minutes |
  | No values | allowed tags = general |
  | Unknown integration | refused |
  | Empty platforms.json outside local | startup fails |
  | Bad note | 401 with no detail; no search runs |
  | Company identity | the pair (iss, company_id); two platforms may reuse a company id |
- Where in the code:
  - `rag_agent/server/token_verifier.py` — verification (planned)
  - `rag_agent/application/auth_context.py` — context construction (planned)
  - `rag_agent/server/router.py:254-267` — _verify_api_key (today)
  - `config/platforms.json` — one entry per platform: issuer, jwks_url, domains, lifetime_minutes; plus the integration map (planned)
- Steps:
  1. Check the host key.
  2. Read iss from the note; find the platform's entry in platforms.json. No entry: refused.
  3. Reject any signing algorithm not on the allow-list; find the public key by key id; check the signature.
  4. Check aud = obi and exp with 60 s leeway.
  5. Read company_id, company_name, integration. None present: tags = general only.
  6. Look the integration up in the map; unknown: refused.
  7. Build one AuthContext and hand it to every read.
- Code:
```
@dataclass(frozen=True)
class AuthContext:
    company_id: str
    company_name: str            # display only
    integration: str             # mews, toast
    allowed_scopes: tuple[str, ...]   # from platforms.json, always has 'general'
    allowed_sources: tuple[str, ...]
    principal: str | None       # from the identity mapping, or None
    space_id: int | None        # the Confluence space the widget is bound to; lock 3's space rule
    token_subject: str
```
- How to test it:
  - Forged, changed or expired note: 401.
  - No values: only general pages come back.
  - A body knowledge_scope that disagrees with the note is ignored and logged; an unknown slug is a 400 before any search.
  - Every read in one request logs the same tags to query_trace.
- Target and notes: Verification order is fixed: algorithm, signature, issuer, audience, expiry, then the business claims. Never the other way round.

##### Panel `em-kb` · Obi picks the pages: the shared knowledge base · [Implemented, needs changing]
- Kind: Store
- In plain words: One database for every integration. Row security inside it shows a person only pieces whose tags match their integration, plus general, and which they may read.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | mews | mews + general |
  | toast | toast + general |
  | no values | general |
  | Then | source lock, page restrictions per person, company rule once it exists |
  | One database | tags separate the integrations, never separate databases |
- Target and notes: The rows and policies do not change for this work. The note only changes where the tags come from.

##### Panel `em-button` · The frame: the round button and the chat window · [Implemented]
- Kind: Frontend
- In plain words: What obi.js draws: a round button at the top of the screen, and the chat window that pops up when it is clicked. Both come from our domain inside one frame.
- Today: apps/web/src/app/embed/page.tsx is built and unit-tested, not planned.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Comes from | https://obi.omniboost.com/embed |
  | Accepts | the note and the clear message, only from the parent window, only from a domain in the platform's entry |
  | Keeps the note | in memory inside the frame |
  | Sends | the note as a bearer header on every question, through the proxy that adds the host key |
  | CSP | frame-ancestors built at request time from every domain in platforms.json; empty list outside local: 403, the frame does not render |
- Where in the code:
  - `apps/web/src/app/embed/page.tsx` — the frame's page (planned)
  - `apps/web/src/features/chat/` — the chat window (exists)
- How to test it:
  - The frame refuses a message from any other window or domain.
  - The note never appears in the frame's URL, cookies or storage.

---

## 04 · Workflow 1 · Ingestion, from A to Z

_Section id: `ingest`_

**In plain words (the lede):** Ingestion is the road from a published Confluence page to searchable pieces in Postgres. It starts when an editor clicks Publish on a page that carries a knowledge tag. It ends when the whole page sits in the database as active pieces with their vectors. Four stages run in order inside one job. This chapter reads the whole road once and the four sections after it open each stage.

Diagram (Confluence and the knowledge scope tag list feed receive, decide, build and activate, which write into the Postgres corpus.)
  - Confluence — published + tagged → panel `ov-confluence`
  - Stage 1 · Receive — webhook, queue → panel `ov-receive`
  - Stage 2 · Decide — what changed? → panel `ov-decide`
  - Stage 3 · Build — chunk, embed all → panel `ov-build` (changes from today)
  - Stage 4 · Activate — one atomic swap → panel `ov-activate`
  - Postgres — tables + vectors → panel `ov-corpus`
  - Knowledge scopes — the tag list → panel `tg-config`
  - Sweeps — daily safety net → panel `i1-sweep`
  - Runs as writer — table owner → panel `s-writer`

_Dashed arrows are inputs, not live calls. The tag list tells stage 2 which labels count. Sweeps feed stage 1 the same jobs a webhook would._

#### The whole path, step by step

1. **An editor publishes a page in Confluence.** The page carries a tag from the knowledge-scope list, for example `toast`. Drafts do nothing. Only Publish counts.
2. **Confluence posts a webhook.** Page edited, tag added, tag removed, attachment changed, page trashed. One HTTP call to `/confluence/events`. If the webhook is missed, the daily sweep finds the page anyway.
3. **Stage 1 checks and queues.** Rate limit, size cap, HMAC signature, parse. Write the event once in the ledger. Drop it if we caused it ourselves. Put one `sync_page` job on the queue. Answer Confluence in milliseconds.
4. **A worker claims the job.** `FOR UPDATE SKIP LOCKED` plus a 120 second lease. Two workers never take the same job.
5. **Stage 2 fetches the facts.** Page meta, labels, read restrictions, attachment list through the Confluence API. Body only if the version or the file list moved.
6. **Stage 2 reads the tags.** Labels are matched against `knowledge_scopes.json`. No recognized tag, or `classified`: the page is deactivated and the job ends. One recognized tag: continue.
7. **Stage 2 decides.** Hashes of body, structure, files, title, labels, restrictions. Same fingerprint: stop. Only labels or permissions changed: update the tag columns in place, no embedding, stop. Anything else changed: rebuild the whole page.
8. **Stage 3 builds the whole page again.** HTML to blocks. Blocks to parent chunks (about 1200 tokens) and child chunks (about 400 tokens). Each child gets a context note. Every child is embedded. Nothing is reused from the old build.
9. **Stage 4 writes in staging.** A new `document_version` row in state staging. All chunks inserted with `is_active = false`. Zero children: mark failed, keep the old page live, stop.
10. **Stage 4 swaps.** One transaction: old version to superseded and its chunks inactive, new version to active and its chunks active. In search terms the old page is gone and the new page is in, in the same instant. Old rows are cleaned up later.
11. **Job completes.** Page work and job status commit together. A failure rolls both back, then a third transaction records the attempt.

> **The one sentence version.** Publish a tagged page and it goes in. Remove the tag and it goes out. Change the page and the whole page is thrown out and put back in. Nothing else puts a page in the index.

#### Security inside the ingestion workflow

These checks belong to ingestion. The security chapter repeats them in the full escalation from edge to row.

- **The webhook is signed.** HMAC with a shared secret. Bad signature: 401. Secret not set: 503 and nothing is processed. Rate limit 300 per minute per IP, body cap 512 KiB.
- **We never loop on ourselves.** An event whose actor is our own service account is marked and dropped.
- **Restricted pages fail closed.** If the restrictions fetch fails, the page is stored as readable by nobody. Groups are expanded to members at sync time. A group we cannot expand gets a sentinel no caller can match.
- **The writer role owns the tables.** It is exempt from row security because it writes every row. It never serves a read.
- **`classified` is a hard delete.** The page is deactivated and its chunks removed. The retrieval scope lock is a second wall behind it.

---

## 04.1 · Ingestion, stage 1 · Receive and queue

_Section id: `in1`_

**In plain words (the lede):** Confluence tells us a page changed. This stage checks the message, writes it down once and puts one job on a queue. It never fetches a page and never touches the index. A worker picks the job up later. A daily sweep feeds the same queue, so a missed message is never a special case.

**For leaders: Confluence tells us a page changed, we write it down once and put one job on a list. Nothing else happens here.**

| Field | Value |
|---|---|
| Inputs | a Confluence webhook POST (page, label, attachment, permission, or delete event) or a sweep entry; each with page id, version, space, actor, delivery id |
| Processing rules | rate limit 300/min/IP; body cap 512 KiB; HMAC signature required; dedup on event content + delivery id; drop our own service account's events; one pending `sync_page` job per page; delete events get higher priority |
| Outputs | one row in `event_ledger`; zero or one new row in `job`; HTTP 202 to Confluence |
| Failure behavior | bad signature: 401 and nothing stored. Secret unset: 503. Duplicate delivery: 200, no job. Queue write fails: 500 and Confluence retries |
| Code locations | `confluence_sync/api/webhook.py`, `confluence_sync/application/event_ledger.py`, `platform/queue/`, `confluence_sync/application/sweeps.py` |
| Today | [Unverified] handler coded and unit-tested; no public HTTPS URL, so Confluence cannot reach it. Sweeps and scripts carry changes. |
| Target | [Planned] public URL with the AWS deploy; label sweep replaces the folder-root sweep; three separate mechanisms for dedup, coalescing, and new revisions |

Diagram (Webhook, four checks, event ledger, self-event check, enqueue job, worker claims. Sweeps also enqueue. A reaper frees lost jobs. The worker handles and completes in one transaction, or fails with backoff.)
  - Webhook — /confluence/events → panel `i1-webhook`
  - Four checks — rate, size, HMAC → panel `i1-checks`
  - Event ledger — seen this before? → panel `i1-ledger`
  - Our own write? — drop it, no loop → panel `i1-self`
  - Enqueue — one job per page → panel `i1-enqueue` (changes from today)
  - Worker claims — SKIP LOCKED, lease → panel `i1-claim`
  - Sweeps — drift + label sweeps → panel `i1-sweep` (changes from today)
  - Reaper — frees lost leases → panel `i1-reaper`
  - Fail path — backoff, dead letter → panel `i1-fail`
  - Handle + complete — one transaction → panel `i1-handle`

- **Webhook** One endpoint. It answers fast and does no work. Everything heavy is deferred to the worker.
- **Four checks** Rate limit per IP (300 a minute), body size cap (512 KiB), HMAC signature (fail closed if the secret is unset), then parse. A bad signature is a 401. A missing secret is a 503.
- **Event ledger** Every delivery is written once. The dedup key is the event content plus the delivery id, never the receive time. A redelivery is a quiet no-op.
- **Our own write?** If the actor is our own service account, mark it and stop. Otherwise our sync would trigger itself forever.
- **Enqueue** One pending `sync_page` job per page. Two events on the same page while a job waits collapse into that one job. A running job never blocks a new one, so a label change during a rebuild still gets processed.
- **Worker claims** `FOR UPDATE SKIP LOCKED` means two workers never grab the same job. A 120 second lease is written before any work starts.
- **Handle + complete** The page work and the job status commit together. If the handler raises, both roll back. A third transaction then records the failure, so the attempt count survives the rollback.
- **Sweeps** A daily drift sweep enqueues pages whose version, status, parent, or title moved. A label sweep asks Confluence for every page with a recognized label. Both feed this same queue.

> **Three different things that look alike.** Delivery dedup says: I saw this exact message before, ignore it. Work coalescing says: this page already has a job waiting, no need for a second one. A new revision says: the page changed again, run again. Today one idempotency key does all three, and it drops real work when two different events share a page version. The target keeps them apart.

> **The network leg is not live yet.** [Decision needed] The handler exists and is tested. Confluence needs a public HTTPS URL to post to, and the backend runs on a laptop. Until the AWS deploy lands, changes ride the sweeps and manual scripts.

#### Panels that belong to this section (10)

_Workflow label shown in the drawer: Ingestion, stage 1 \u00b7 Receive and queue_

##### Panel `i1-sweep` · Sweeps: the safety net · [Implemented, needs changing]
- Kind: Outside trigger
- In plain words: Once a day, asks Confluence for every page with each tag and queues them, so a missed doorbell is never a problem.
- Today: Daily lightweight sweep (0 3 * * *) and a complete sweep every 14 days over the pages that source_scope roots cover. Both enqueue sync_page jobs.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Lightweight | enqueue when version, status, parent or title drifted |
  | Complete | enqueue every live page; re-checks labels, permissions, attachments |
  | Label sweep (target) | ask Confluence for every page with a recognized label, across all spaces; enqueue new ones; pages that lost their last label are deactivated |
  | Record | one reconciliation_run row per sweep with counts |
- Where in the code:
  - `confluence_sync/application/reconciliation.py:58-65, 145-221` — _needs_sync, _sweep_space
  - `platform/clients/confluence_client.py` — search_pages_by_labels (target, CQL label search)
- How to test it:
  - A page labeled in a space with no folder root is picked up by the label sweep.
  - A page whose last recognized label was removed is deactivated by the next sweep.
- Target and notes: Target: a daily label sweep (Confluence label search over the names in knowledge_scopes.json) replaces the folder-root sweep. Any tagged page the webhook missed is found within a day.

##### Panel `i1-webhook` · POST /confluence/events · [Unverified]
- Kind: HTTP endpoint
- In plain words: The doorbell Confluence rings when a published page changes. We answer fast and do the work later.
- Today: Handler built and tested. Not reachable from Confluence until the backend has a public HTTPS URL.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Kind | state mutating, no LLM |
  | Transaction | one short one per request |
  | Returns | 200 with accepted, duplicate, ignored, or self_generated |
- Where in the code:
  - `confluence_sync/server/webhook.py:88-126` — receive_confluence_event
- Steps:
  1. Run the four checks.
  2. Parse the JSON into an EventEnvelope.
  3. Call ingest_event.
  4. Log one structured webhook_event line and return.
- How to test it:
  - A valid delivery returns 200 and creates one job.
  - A redelivery returns 200 and creates no job.
- Target and notes: Confluence fires these events only on Publish. A draft never reaches this endpoint.

##### Panel `i1-checks` · Rate limit, size cap, HMAC, parse · [Implemented]
- Kind: Gate
- In plain words: Four quick checks: not too many rings, not too big, the right secret signature, readable.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Rate limit | 300 per minute per client IP |
  | Body cap | 512 KiB, else 413 |
  | Signature | X-Hub-Signature-256, HMAC SHA-256 over the raw body, constant-time compare |
  | No secret configured | 503, fail closed |
  | Bad JSON | 400 |
- Where in the code:
  - `confluence_sync/server/webhook.py:67-101` — _verify_signature and the caps
  - `shared/rate_limiter.py` — SlidingWindowRateLimiter
- Code:
```
expected = hmac.new(secret, raw_body, sha256).hexdigest()
if not hmac.compare_digest(expected, header_without_prefix):
    raise 401
```
- How to test it:
  - Missing header: 401.
  - Wrong signature: 401.
  - Empty CONFLUENCE_WEBHOOK_SECRET: 503.

##### Panel `i1-ledger` · The event ledger · [Implemented]
- Kind: Step
- In plain words: Writes every ring down once. A repeat ring is ignored.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Dedup key | event_type, page_id, cf_version, space_id, status, event_timestamp, delivery_id |
  | Excludes | receive time, so a redelivery is identical |
  | Insert | ON CONFLICT DO NOTHING with no target, so either unique constraint absorbs it |
- Where in the code:
  - `confluence_sync/infrastructure/event_repo.py:25-57` — record_event
  - `confluence_sync/schemas/events.py:46-56` — canonical_dedup_payload
- Steps:
  1. Hash the canonical payload.
  2. Insert. If the hash or the delivery id already exists, get None back.
  3. None means duplicate: mark and stop. Otherwise continue to the self-event check.
- How to test it:
  - Same delivery id, different payload: dedupes quietly, never a 500.

##### Panel `i1-self` · Was this our own write? · [Implemented]
- Kind: Gate
- In plain words: If we caused the change ourselves, stop here, or we would ring our own bell forever.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Check | actor == confluence_service_account_id |
  | Result | ledger row marked done and self_generated, no job |
- Where in the code:
  - `confluence_sync/application/event_service.py:47-60` — ingest_event
- Target and notes: Only matters if the sync account ever writes to Confluence. Today it does not, and the setting is empty.

##### Panel `i1-enqueue` · Enqueue one job per page · [Implemented, needs changing]
- Kind: Step
- In plain words: Puts one job on the list for the page. A page already waiting does not get a second job.
- Today: Idempotency key is sync_page:{page_id}:{event_type}:{version}:{schema}. Two different events at one version get two jobs; two identical ones get one.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Target | one pending sync_page per page (partial unique index on page_id WHERE status = pending) |
  | Running job | never blocks a new pending one, so a change during a rebuild still runs afterward |
  | Delete jobs | priority 50, ahead of syncs |
  | Payload | page id, event type, and (today) the source_scope tags |
- Where in the code:
  - `confluence_sync/application/event_service.py:67-103` — key builders
  - `platform/jobs/queue.py:25-53` — enqueue_job
- Steps:
  1. Build the job row for this page.
  2. Insert with ON CONFLICT DO NOTHING against the pending index.
  3. A conflict means a job already waits: that job will read the latest state anyway, so nothing is lost.
- Code:
```
-- target
CREATE UNIQUE INDEX ux_job_pending_sync_page
  ON job (page_id) WHERE status = 'pending' AND job_type = 'sync_page';
```
- How to test it:
  - Two label changes at one page version both apply.
  - A label change during a running rebuild produces a second run after the first.

##### Panel `i1-claim` · A worker claims the job · [Implemented]
- Kind: Step
- In plain words: A worker takes one job. A lock makes sure no two workers take the same one.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Query | pending or failed, available_at <= now, ORDER BY priority, available_at, LIMIT 1 FOR UPDATE SKIP LOCKED |
  | Lease | 120 seconds, lease_owner set, attempts + 1 |
  | Transaction | its own, committed before work starts |
- Where in the code:
  - `platform/jobs/queue.py:56-87` — claim_job
  - `confluence_sync/application/worker.py:95-100` — transaction 1
- Target and notes: SKIP LOCKED is what lets several workers run without ever sharing a job.

##### Panel `i1-reaper` · The reaper · [Implemented]
- Kind: Housekeeping
- In plain words: Frees a job whose worker died so another worker can take it.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Finds | leased or running jobs whose lease expired |
  | Does | resets them to pending |
- Where in the code:
  - `platform/jobs/queue.py:120-131` — reap_expired
- Target and notes: Recovers work a crashed worker left behind. Every handler is idempotent, so a rerun is safe.

##### Panel `i1-fail` · Retry with backoff, then dead letter · [Implemented]
- Kind: Fail path
- In plain words: Waits and retries a failed job. After a few tries it sets the job aside and tells a human.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Attempts | 5 by default |
  | Backoff | 5 seconds times 2 to the (attempts minus 1), capped at 1 hour |
  | Error text | cut to 4000 characters |
  | After the last attempt | status dead_letter; an operator looks at it |
- Where in the code:
  - `platform/jobs/queue.py:98-117` — fail_job
  - `confluence_sync/application/worker.py:121-128` — transaction 3
- Target and notes: The failure is recorded in its own transaction, so the attempt count survives the rollback that undid the work.

##### Panel `i1-handle` · Handle and complete in one transaction · [Implemented]
- Kind: Step
- In plain words: Saves the page work and the job status together, so a failure undoes both.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Handlers | sync_page, delete_page, reconcile_space |
  | Guarantee | the index change and the succeeded status commit together, or neither does |
  | Drain | up to 100 jobs per tick |
- Where in the code:
  - `confluence_sync/application/worker.py:56-75, 112-120` — handlers and transaction 2
- Steps:
  1. Re-read the job by id.
  2. Run the handler (ingestion stage 2 onward).
  3. Mark succeeded. Commit.
  4. On any exception, roll back and hand off to the fail path.

---

## 04.2 · Ingestion, stage 2 · Decide what changed

_Section id: `in2`_

**In plain words (the lede):** The worker asks Confluence for the page's facts and works out what changed. A text edit, a new file, a new title, a new label and a new permission each need a different response. The decision comes from fingerprints of the content. The event name alone never decides.

**For leaders: a worker looks at the page and decides one of four things: rebuild it whole, update its tags, take it out, or do nothing.**

| Field | Value |
|---|---|
| Inputs | one `sync_page` job; page meta, labels, read restrictions, attachment list from the Confluence API (published version only); the stored hashes of the last build; `knowledge_scopes.json` |
| Processing rules | labels → scope state (ok, conflict, classified, unlabeled); content fingerprint (body, structure, title, attachment ids/versions, pipeline config) → rebuild; metadata fingerprint (labels, restrictions) → in-place update; no recognized tag or classified → deactivate; same fingerprint → stop. Page version is a hint, never a reason to skip |
| Outputs | a decision: rebuild / metadata / deactivate / no-op; updated `page_source` columns; on rebuild, the page blocks handed to stage 3 |
| Failure behavior | Confluence API error: job fails, retries with backoff, then dead letter; restrictions fetch fails: page stored as readable by nobody (fail closed) |
| Code locations | `confluence_sync/domain/change_detection.py → classify`, `confluence_sync/application/sync_service.py → handle_sync_page`, `confluence_sync/domain/labels.py` |
| Today | [Implemented, needs changing] hashes and classify run; the version guard skips label changes at an unchanged version; attachment-only changes never rebuild; folder roots decide membership |
| Target | [Planned] fingerprint replaces the page version as build identity; `attachment_changed` and `title_changed` are rebuild triggers; tags alone decide membership |

Diagram (Fetch page facts, read labels, hash everything, classify. Four outcomes: gone or classified, rebuild, metadata only, no change. Rebuild leads to ingestion stage 3. Metadata only updates tags and access in place.)
  - Fetch page facts — meta, labels, ACL → panel `i2-fetch`
  - Read labels — scope state → panel `i2-labels` (changes from today)
  - Hash everything — one index fingerprint → panel `i2-hash` (changes from today)
  - Classify — what really changed? → panel `i2-classify`
  - Gone or classified — deactivate → panel `i2-gone`
  - Rebuild — body, files, title → panel `i2-rebuild`
  - Metadata only — labels, ACL only → panel `i2-meta`
  - No change — stop here → panel `i2-nochange`
  - Stage 3 · Build — new version → panel `i2-tobuild`
  - Update in place — tags, state, ACL → panel `i2-inplace`

- **Fetch page facts** Page meta (version, status, title, parent), labels, read restrictions, and the attachment list. The body is fetched only when the version or the file list moved.
- **Read labels** Labels are matched against `knowledge_scopes.json`, case-insensitive. The result is a scope state: ok, conflict, classified, or unlabeled. Only "ok" pages are ever served. A page with no recognized tag is never built, and if it was built before it is deactivated now.
- **Hash everything** Content, structure, attachment manifest, title, labels, restrictions, and the pipeline versions. Together they form one index fingerprint. If the fingerprint is the same, nothing changed.
- **Classify** Compares the new hashes with the stored ones. Gone statuses short-circuit first. Then body and file changes. Then metadata changes. The Confluence version number is a hint, never a reason to skip a check.
- **Gone or classified** Trashed, deleted, archived, or now carrying the `classified` label, or its last recognized label was removed. The page is deactivated and its chunks stop being served.
- **Rebuild** Body, section structure, attachments, title, or pipeline config changed. The whole page is built again in stage 3. Every child is embedded again. The old version leaves search the moment the new one goes live.
- **Metadata only** Labels or permissions changed and nothing else. Tags, scope state, and restriction rows are updated in place on the live version. No new embeddings.

#### Decision table: what happens after each kind of change

| An editor does this in Confluence | Rebuild the whole page | Update metadata in place | Deactivate | Do nothing |
|---|---|---|---|---|
| Edits the body and publishes | yes |  |  |  |
| Renames the title or a heading | yes |  |  |  |
| Replaces, adds, or removes an attachment | yes |  |  |  |
| Adds a second recognized tag to an indexed page |  | yes (tags column) |  |  |
| Adds the first recognized tag to a page not indexed | yes (first build) |  |  |  |
| Removes a tag, another recognized tag remains |  | yes (tags column) |  |  |
| Removes the last recognized tag |  |  | yes |  |
| Adds `classified` |  |  | yes, and chunks deleted |  |
| Changes read permissions |  | yes (page_restriction rows) |  |  |
| Trashes, archives, or deletes the page |  |  | yes |  |
| Saves a draft without publishing |  |  |  | yes, no event arrives |
| Publishes with no change (same fingerprint) |  |  |  | yes |

> **How the fingerprint and the metadata path work together.** The index fingerprint has two halves. The **content half** covers body, structure, title, attachment ids and versions, and the parser, chunker, contextualizer, and embedding configuration. If any of it changed, the whole page is rebuilt. The **metadata half** covers labels and read restrictions. If only that half changed, the tags, scope state, and restriction rows are updated on the live version and nothing is embedded. If neither half changed, nothing happens. The full fingerprint (both halves) is also the identity of a build: `document_version` is unique on `(document_id, index_fingerprint)`, so an attachment-only rebuild never collides with the version built at the same Confluence page number. Code: `confluence_sync/domain/change_detection.py → classify`, `confluence_sync/application/sync_service.py → _REBUILD_CLASSES, handle_sync_page`, `ingestion/application/versioning.py → stage_and_activate`, `platform/db/models.py`.

> **Acceptance check for this stage.** Replace a PDF without editing the page body. After the sync, a question returns the new PDF's information and the old attachment's chunks are inactive. Change a label at an unchanged page version: the tag column updates.

#### The change matrix

| What changed in Confluence | How we notice | What we do | Re-embed? |
|---|---|---|---|
| Body text [Implemented, needs changing] | content_hash | throw the whole page out, rebuild it, swap | whole page |
| Section added, moved, removed [Implemented, needs changing] | structure_hash | same: whole page | whole page |
| Attachment added, replaced, removed [Implemented, needs changing] | attachment_manifest_hash | same: whole page, attachments re-extracted | whole page |
| Title or heading renamed [Implemented, needs changing] | title in the fingerprint | same: whole page | whole page |
| Tag added, page not yet indexed [Planned] | labels | first build of the whole page | whole page |
| Tag added or removed, page stays tagged | labels_hash | update tags and scope state in place | no |
| Last recognized tag removed [Planned] | labels | deactivate the page, it leaves search | no |
| `classified` tag added [Planned] | labels | deactivate and delete the chunks | no |
| Read permissions changed | access_scope_hash | replace page_restriction rows in place | no |
| Page trashed, archived, deleted | status | deactivate | no |
| Contextualization prompt version bumped | contextualization_version | rebuild every page | whole corpus |
| Embedding model or dims changed | embedding_model, embedding_dim | new index generation | whole corpus |

> **Two decisions today throw away real changes.** [Implemented, needs changing] First, an attachment-only change never rebuilds, because a second version at the same Confluence page version would violate a uniqueness rule. Second, the version guard skips metadata checks when the page version did not grow, and a label change never grows the version. The fix for both is the same: the fingerprint replaces the page version as the identity of an index build.

#### Panels that belong to this section (10)

_Workflow label shown in the drawer: Ingestion, stage 2 \u00b7 Decide what changed_

##### Panel `i2-fetch` · Fetch the page facts · [Implemented]
- Kind: Step
- In plain words: Asks Confluence for the page's facts: version, title, labels, who may read it, attached files. Only the published version comes back.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Always | meta (version, status, title, parent), labels, read restrictions, attachment list |
  | Body | only when decide_body_fetch says the version or the attachment list moved |
  | Groups | restriction groups expanded to account ids via the v1 member endpoint, cached per run |
- Where in the code:
  - `confluence_sync/application/sync_service.py:77-199` — handle_sync_page
  - `platform/clients/confluence_client.py` — get_page_meta, get_labels, get_restrictions, get_attachments
- Target and notes: The Confluence API returns the published version of a page. Draft edits are invisible to Obi until the editor clicks Publish.

##### Panel `i2-labels` · Labels to scope state · [Implemented, needs changing]
- Kind: Gate
- In plain words: Matches the page's labels against the tag list. One good tag: continue. No tag or a forbidden tag: the page goes out.
- Today: Labels intersected with the scope list. One provider label plus general is fine. Two provider labels give zero label tags and a warning. Result unioned with source_scope tags.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | ok | one provider label, or general, or both |
  | conflict | two or more provider labels; page hidden everywhere |
  | classified | the classified label present; deactivate and purge |
  | unlabeled | no recognized label; not in the corpus (target) |
  | Matching | case-insensitive against config/knowledge_scopes.json |
- Where in the code:
  - `confluence_sync/domain/knowledge_scope.py:24-31` — resolve_knowledge_scope_tags
  - `confluence_sync/application/sync_service.py:103-115, 180-189` — where the tags are threaded
- Code:
```
def resolve(labels, recognized):
    matched = {l.lower() for l in labels} & recognized
    if "classified" in matched: return State.CLASSIFIED, ()
    providers = matched - {"general"}
    if len(providers) > 1: return State.CONFLICT, ()
    if not matched: return State.UNLABELED, ()
    return State.OK, tuple(sorted(matched))
```
- How to test it:
  - mews + toast: conflict, no tags, warning logged.
  - classified + mews: classified wins.
  - general only: ok, tags [general].
  - no label: unlabeled, page deactivated.

##### Panel `i2-hash` · One index fingerprint · [Implemented, needs changing]
- Kind: Step
- In plain words: Makes one fingerprint of the page from its text, structure, files, title, labels, and permissions. Same fingerprint means nothing changed.
- Today: Five hashes exist: content, structure, attachment manifest, access scope, labels. Plus pipeline stamps. The version's identity is (document, cf_version, schema, embedding model).
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Fingerprint = | sha256 of content_hash + structure_hash + attachment_manifest_hash + title + labels_hash + access_scope_hash + parser, chunker, contextualization, embedding, schema versions |
  | Stored on | page_source and document_version |
  | Used for | the version uniqueness key and the no-change short-circuit |
- Where in the code:
  - `confluence_sync/domain/change_detection.py:104-180` — classify computes the hashes
  - `platform/db/models.py` — page_source hashes and stamps
- Target and notes: Attachment content is hashed by the manifest (ids, versions, sizes), not by extracted text, so a replaced PDF with the same name still changes it.

##### Panel `i2-classify` · Classify the change · [Implemented, needs changing]
- Kind: Gate
- In plain words: Compares the new fingerprint with the old one and picks one action: rebuild the whole page, update the tags, take the page out, or do nothing.
- Today: Order: gone statuses, first index, then a version guard that skips work when the version did not grow, then config change, then metadata and body comparisons.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Driven by | status, hashes, pipeline stamps. The event type only picked the job type |
  | Rebuild classes | body_changed, section added, updated, removed, moved, index_config_change, and in the target attachment_changed and title_changed |
  | Metadata only | labels_changed, permissions_changed, parent_changed |
  | Version guard (target) | only decides whether to fetch the body; metadata hashes are always compared |
- Where in the code:
  - `confluence_sync/domain/change_detection.py:104-180` — classify
  - `confluence_sync/application/sync_service.py:36-55` — _REBUILD_CLASSES
- How to test it:
  - Label change at an unchanged page version: metadata_only, not no_change.
  - Attachment replaced, body unchanged: rebuild.
  - Same fingerprint twice: no_change.

##### Panel `i2-gone` · Gone, classified, or unlabeled: deactivate · [Implemented, needs changing]
- Kind: Outcome
- In plain words: The page was deleted, lost its tag, or got the classified tag. It leaves search now.
- Today: Only status trashed/archived/deleted and missing metadata trigger deactivation today; the classified-label and last-recognized-label-removed triggers do not exist yet.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Triggers | status trashed, archived, deleted; meta missing; classified label; last recognized label removed |
  | Does | page_status set, active version superseded, chunks is_active = false |
  | Classified extra | chunk rows deleted, so nothing sits in the store |
- Where in the code:
  - `confluence_sync/application/sync_service.py` — handle_delete_page, deactivate_page
- How to test it:
  - Trash a page: its chunks stop appearing in every scope within the freshness target.
  - Add classified: chunks gone from the table, not only inactive.

##### Panel `i2-rebuild` · Rebuild a new version · [Implemented, needs changing]
- Kind: Outcome
- In plain words: Something in the page changed, so the whole page is built again from scratch.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | When | body, structure, attachments, title, or pipeline config changed; or first index |
  | Reuse | today: a child keeps its vector when its stable_key (position plus body text) matches; target: no reuse |
  | Next | ingestion stage 3 and ingestion stage 4 |
- Where in the code:
  - `confluence_sync/application/sync_service.py:150-165` — the rebuild branch
  - `ingestion/application/versioning.py:187-255` — stage_and_activate
- Target and notes: Target: a rebuild means the whole page. Every parent and every child is created new and every child is embedded. Nothing from the old version is reused.

##### Panel `i2-meta` · Metadata only: update in place · [Implemented]
- Kind: Outcome
- In plain words: Only labels or permissions changed, so only those columns change. No new meaning codes.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | When | labels or permissions changed and nothing else |
  | Does | page_source.tags, scope_state, chunk.tags, chunk.scope_state, page_restriction rows replaced |
  | Does not | touch embeddings or create a version; active_doc_version_id stays |
- Where in the code:
  - `confluence_sync/application/sync_service.py:180-189` — _apply_metadata_only
- How to test it:
  - Add a label: tags change, active_doc_version_id unchanged, action == metadata_only.

##### Panel `i2-nochange` · No change · [Implemented]
- Kind: Outcome
- In plain words: Nothing changed. Stop. This is the usual result of the daily sweep.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | When | the fingerprint equals the stored one |
  | Does | updates last_reconciled_at and stops |

##### Panel `i2-tobuild` · On to ingestion stage 3 · [Implemented]
- Kind: Hand-off
- In plain words: Off to stage 3 to build the whole page again.
- Steps:
  1. The body blocks and attachment blocks are passed to the chunker.
  2. Ingestion stage 3 builds the pieces. Ingestion stage 4 activates them.

##### Panel `i2-inplace` · Update tags, state and restrictions in place · [Implemented]
- Kind: Step
- In plain words: Writes the new tags, state, and permission rows onto the live version. Fast and cheap.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Writes | page_source and every active chunk of the page |
  | Also | page_restriction delete and insert when the access hash moved |
  | Role | writer, so row security never blocks it |
- Where in the code:
  - `confluence_sync/application/sync_service.py` — _apply_metadata_only and the restriction write

---

## 04.3 · Ingestion, stage 3 · Build the chunks

_Section id: `in3`_

**In plain words (the lede):** The page is cut into two kinds of pieces. Big parent pieces give the answer model enough context. Small child pieces are what search matches on. Each child gets a short note about where it sits in the page, then a vector and a keyword index. Every rebuild does this for the whole page and keeps nothing from the old build.

**For leaders: the page is cut into big and small pieces, every small piece gets a meaning code and a word index. The whole page, every time.**

| Field | Value |
|---|---|
| Inputs | the page blocks from stage 2 (HTML, title, heading structure, attachment files) |
| Processing rules | HTML → blocks; blocks → parents (~1200 tokens, cap 2000); parents → children (~400 tokens, 12% overlap); each child gets title + heading path + Haiku context note prepended for embedding; every child embedded (batches of 128); tsvector on every child; attachments: native text only, no OCR, 200 files / 20 MB caps |
| Outputs | parent and child rows in memory with text, embedding input, embedding, tsv, position, links to parent and neighbors; an attachment report |
| Failure behavior | embedding API error: retry, backoff, circuit breaker, then the build fails and the old version stays live; unsupported attachment: empty text plus a flag, build continues; attachment download error: build fails |
| Code locations | `ingestion/domain/normalize.py`, `ingestion/domain/chunking.py`, `ingestion/application/contextualize.py`, `ingestion/application/embedding.py`, `ingestion/infrastructure/attachments.py` |
| Today | [Implemented, needs changing] all steps run; vectors are reused when position + body text match (`stable_key`) |
| Target | [Planned] no vector reuse; attachment report on the version; empty/failed attachment counts in the sweep summary |

Diagram (Normalize blocks, pack parents, split children, contextualize, embed every child. Attachments feed normalize. Children also get a keyword index.)
  - Normalize — HTML to blocks → panel `i3-blocks`
  - Parent chunks — about 1200 tokens → panel `i3-parents`
  - Child chunks — about 400 tokens → panel `i3-children`
  - Contextualize — title + path + note → panel `i3-context`
  - Embed every child — OpenAI 3072 dims → panel `i3-embed` (changes from today)
  - To stage 4 — new version, staging → panel `i4-staging`
  - Attachments — PDF, DOCX, XLSX, CSV → panel `i3-attach`
  - Keyword index — tsvector on children → panel `i3-tsv`

- **Normalize** Confluence HTML becomes a list of blocks: headings, paragraphs, tables, code. Tables and code blocks stay whole. Attachment text is appended as blocks under a heading called Attachments.
- **Parent chunks** Blocks of one section packed to about 1200 tokens, hard cap 2000. Parents are never embedded. They are what the answer model reads.
- **Child chunks** Windows of about 400 tokens inside one parent, with 12 percent overlap. Children are what search matches on. Each child knows its parent, its neighbors, and its position.
- **Contextualize** The text that gets embedded is: page title, heading path, a one or two sentence note written by Haiku from the whole page, then the child text. The verbatim child text is kept separately for citations.
- **Embed every child** Every child of the page, in batches of 128, with retry, backoff, and a circuit breaker. Same provider as the question side. Today the code reuses a vector when a child's position and body text match the old build. The target removes that check: a rebuild embeds the whole page.
- **Keyword index** `to_tsvector('english', title + heading path + text)` on children. Postgres full-text search. Indexed with GIN.
- **Attachments** Native text extraction, never OCR. PDF via pypdf, DOCX via python-docx, XLSX via openpyxl. Cap: 200 files per page, 20 MB each. **Unsupported or failed extraction:** a scanned PDF or an image yields empty text, the attachment is recorded with `extraction = empty`, and the rest of the page still builds. A download or parser error on one attachment fails the whole build: the version is marked failed, the previous version stays live and searchable, and the job retries with backoff, then dead-letters. Each build writes an attachment report (count, extracted, empty, failed) onto `document_version`, and the daily sweep summary lists pages with empty or failed attachments. [Unverified] for the report fields.

> **Every rebuild embeds the whole page: the current rule and the chosen target rule.** [Implemented, needs changing] **Current rule:** a child keeps its old vector when its `stable_key` (position plus body text) matches the previous version. **Chosen target rule:** no reuse. Every child of a rebuilt page is embedded again. **Rejected alternative:** the external review proposes reusing a vector only when the entire embedding input (title, heading path, context note, text, model, dimensions) is byte-identical. That would be correct, but it needs an extra hash column and a second code path for a saving that is small on this corpus. You chose the simpler rule. If the corpus grows, the rejected rule is the one to bring back. Today a child keeps its old vector when its position and body text match. That check saves API calls and nothing else, and it has a bug: the title is part of the embedded text, so a renamed page keeps stale vectors. The target drops the check. A page edit means: all old chunks out, all new chunks embedded, one swap. Simpler code, one fewer hash column, no stale vectors. The corpus is small, so the extra embedding cost is small.

#### One worked example

A short Confluence page, "Toast × QuickBooks: Setup guide", labeled `toast`, with one section "Connecting your Toast account" of about 600 tokens.

```
PARENT 1 (about 600 tokens, not embedded, what the answer model reads)
  heading path: Toast × QuickBooks: Setup guide › Connecting your Toast account
  text: [the whole section, verbatim]

CHILD 1 of parent 1 (about 400 tokens, embedded, what search matches)
  citation text (stored verbatim, shown to the user):
    "In Omniboost, open Integrations and choose Toast. Paste the Toast API key ..."
  embedding input (what goes to the model, stored separately):
    "Toast × QuickBooks: Setup guide › Connecting your Toast account
     This page explains how to connect a Toast POS account to Omniboost and
     which permissions the connecting user needs.
     In Omniboost, open Integrations and choose Toast. Paste the Toast API key ..."
  tags: [toast]   scope_state: ok   position: 0

CHILD 2 of parent 1 (overlaps child 1 by about 12 percent)
  citation text: "... The first sync runs within five minutes and imports the last 30 days ..."
  embedding input: same title, path, and note, then this child's text
  tags: [toast]   scope_state: ok   position: 1
```

The context note (second block in the embedding input) is written once per page by Haiku. Both children carry it. The citation text never contains it, so the user sees only what the page says.

> **Why children search and parents answer.** A small piece matches a question precisely. A big piece gives the model enough around it to answer well. Storing both, linked, gets the best of each. This is the 2026 default for document RAG.

> **Images and scans contribute nothing today.** [Decision needed] That is a deliberate text-first choice. Run a corpus audit first: how many pages depend on a diagram or a scanned PDF? Add OCR or a vision model only where the eval set shows a real gap.

#### Panels that belong to this section (7)

_Workflow label shown in the drawer: Ingestion, stage 3 \u00b7 Build the chunks_

##### Panel `i3-blocks` · Normalize HTML into blocks · [Implemented]
- Kind: Step
- In plain words: Turns the page's HTML into a simple list of blocks: headings, paragraphs, tables, code, plus text from attached files.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Input | Confluence storage-format HTML plus extracted attachment text |
  | Output | a flat list of blocks with a heading path: heading, paragraph, table, code, list |
  | Kept whole | tables and code blocks are never split |
- Where in the code:
  - `ingestion/domain/normalize.py` — block model
  - `ingestion/domain/attachment_extraction.py:attachment_to_blocks` — attachments under the heading Attachments

##### Panel `i3-parents` · Parent chunks · [Implemented]
- Kind: Step
- In plain words: Big pieces of about 1200 tokens, one per section. The answer model reads these.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Size | target 1200 tokens, hard cap 2000 |
  | Boundary | never crosses a heading section |
  | Embedded? | no; parents are read by the answer model |
  | kind | 0 |
- Where in the code:
  - `ingestion/domain/chunking.py:31-39, 62-117` — ChunkConfig, plan_chunks, _pack_parents

##### Panel `i3-children` · Child chunks · [Implemented]
- Kind: Step
- In plain words: Small pieces of about 400 tokens cut from a parent. Search matches on these because small pieces match a question precisely.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Size | target 400 tokens, min 150, max 750 |
  | Overlap | 12 percent |
  | Identity | section_key, positional_key, content_key, stable_key |
  | Links | parent_chunk_id, prev_chunk_id, next_chunk_id |
  | kind | 1 |
- Where in the code:
  - `ingestion/domain/chunking.py` — _split_children
  - `ingestion/application/versioning.py:294-311` — _link_chunks
- Target and notes: Split order: page, heading section, block, paragraph, sentence, word, token. A trailing window shorter than 150 tokens is merged back.

##### Panel `i3-context` · Contextualize each child · [Implemented]
- Kind: Step
- In plain words: Adds the page title, the heading path, and a two-sentence note to each small piece before it is turned into a code, so the code knows where the piece came from.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Prefix | page title and heading path joined by > |
  | Note | one or two sentences written by claude-haiku-4-5 from the whole page, max 128 tokens |
  | Cost | the whole page is a prompt-cached system block, billed once per page |
  | Stored as | retrieval_content (embedded); display_content stays verbatim for citations |
  | Fail-soft | an LLM error gives the prefix only; ingestion never fails on it |
- Where in the code:
  - `ingestion/application/contextualizer.py:45-91` — the composition
- Code:
```
retrieval_content = f"{title} > {heading_path}\n\n{llm_note}\n\n{child_text}"
```

##### Panel `i3-embed` · Embed every child · [Implemented, needs changing]
- Kind: Outside tool
- In plain words: Sends every small piece of the page to the embedding model and stores the 3072 numbers that come back. All pieces, every rebuild.
- Today: OpenAI text-embedding-3-large at 3072 dims (from .env). Code default is Voyage voyage-3-large at 1024. VOYAGE_API_KEY is set and verified; the bake-off is not run.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Batch | 128 texts per call, 20000 per run cap |
  | Resilience | retry with min(0.3 * 2^n, 4) seconds backoff, breaker after 5 failures |
  | Stamp | services.embedding_model records the real producer |
  | Change of model | the version stamp forces a full re-embed |
- Where in the code:
  - `platform/clients/embeddings_client.py:94-131` — _HttpEmbeddingProvider.embed
  - `platform/config/settings.py:61-63` — provider, model, dim
- Target and notes: Today only changed children are embedded (stable_key reuse). Target: all children of the page, every rebuild. Simpler, and no stale title vectors.

##### Panel `i3-attach` · Attachments · [Implemented, needs changing]
- Kind: Outside input
- In plain words: Pulls text out of attached PDF, Word, Excel, and CSV files and adds it to the page. Pictures and scans give no text and are flagged.
- Today: A failed attachment is skipped and the build continues. Attachment content is not part of content_hash, and attachment_changed alone does not rebuild.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Types | PDF (pypdf), DOCX (python-docx), XLSX (openpyxl), CSV, HTML, Markdown, text |
  | Images | empty text plus a needs_ocr flag; never run |
  | Caps | 200 per page, 20 MB each, enforced from metadata and again while streaming |
  | Failure | today: per attachment, skipped; target: see the note |
- Where in the code:
  - `ingestion/domain/attachment_extraction.py:34-69` — extract_attachment
  - `confluence_sync/application/sync_service.py:202-248` — _attachment_blocks
  - `platform/clients/confluence_client.py` — download_attachment (cross-host redirect, auth header dropped)
- Target and notes: Target: a download or parser error on one attachment fails the build; the previous version stays live and searchable; the job retries, then dead-letters. An unsupported type (image, scanned PDF) yields empty text plus a needs_ocr flag and the build continues. The fingerprint makes an attachment change rebuild the page.

##### Panel `i3-tsv` · The keyword index · [Implemented]
- Kind: Step
- In plain words: Gives every small piece a word index, so a search for an exact word or error code still finds it.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Column | chunk.tsv, children only |
  | Built from | to_tsvector('english', title + heading path + text) |
  | Index | ix_chunk_tsv_gin, active children |
- Where in the code:
  - `ingestion/application/versioning.py:40-43, 140` — _tsv
  - `platform/db/models.py:315-320` — the GIN index

---

## 04.4 · Ingestion, stage 4 · Activate

_Section id: `in4`_

**In plain words (the lede):** The new pieces are written to a staging area first. One transaction then flips the live pointer from the old version to the new one. A reader never sees a half-built page. Two old versions stay around, so a bad build can be undone in one step.

**For leaders: the new pieces wait in a side room, then one switch flips. The old page is gone and the new one is live in the same instant.**

| Field | Value |
|---|---|
| Inputs | the built parents and children from stage 3; the `document` row; the current active `document_version` |
| Processing rules | insert a `document_version` in state staging with all hashes; insert all chunks with `is_active = false`; zero children → fail; one transaction: old version superseded and its chunks inactive, new version active and its chunks active, `page_source.active_doc_version_id` repointed; stamp source, tags, scope state; keep two superseded versions, delete older |
| Outputs | one active version per document, enforced by a partial unique index; inactive old rows for rollback |
| Failure behavior | validation gate fails: version marked failed, transaction raises, live page untouched; swap conflict (two actives): Postgres refuses the transaction |
| Code locations | `ingestion/application/versioning.py → stage_and_activate`, `platform/db/models.py` (partial unique index, deferrable FK) |
| Today | [Implemented] staging, gate, swap, GC, rollback all run and are tested |
| Target | [Implemented, needs changing] uniqueness becomes `(document_id, index_fingerprint)`; stamps read tags from labels only |

Diagram (Ensure the document row, create a staging version, insert inactive chunks, validation gate, pointer swap, stamp source and tags. A failed gate marks the version failed. Garbage collection keeps two old versions. Rollback repoints the pointer.)
  - Ensure document — one per page, stable → panel `i4-document`
  - New version — state = staging → panel `i4-staging` (changes from today)
  - Insert chunks — is_active = false → panel `i4-chunks`
  - Validation gate — no children = fail → panel `i4-gate`
  - Pointer swap — all or nothing → panel `i4-swap`
  - Stamp — source, tags, state → panel `i4-stamp` (changes from today)
  - Version failed — never activates → panel `i4-failed`
  - Garbage collect — keep two old versions → panel `i4-gc`
  - Rollback — instant and safe → panel `i4-rollback`

- **Ensure document** One `document` row per page. It is the stable identity that survives every rebuild.
- **New version** A `document_version` row in state staging, carrying every hash and every pipeline stamp it was built with. Its uniqueness key becomes the index fingerprint, so an attachment-only rebuild is allowed.
- **Insert chunks** Parents first, then children linked to their parent and to their neighbors. All inactive.
- **Validation gate** Zero children means something went wrong. The version is marked failed and the transaction raises. The live version is untouched.
- **Pointer swap** Old version to superseded, its chunks inactive. New version to active, its chunks active. `page_source.active_doc_version_id` repointed. Unique constraints make this all or nothing. For search this is "the old page is gone and the new page is in", in the same instant.
- **Stamp** Source id, tags, and scope state are written onto the chunks and the page row here, in one place. This is the seam a second source would plug into.
- **Garbage collect** The two most recent superseded versions stay for rollback. Older ones are deleted; chunks cascade. Inactive chunks are never searched, so keeping two old copies costs disk and nothing else.
- **Rollback** Repoint to an old version and restore its hashes and stamps, so the next sync does not wrongly say "no change".

> **What makes the swap safe.** `active_doc_version_id` is a unique, deferrable foreign key. `document_version` has a partial unique index that allows one active version per document. Postgres refuses any state with two live versions, so the app cannot get it wrong.

#### Panels that belong to this section (9)

_Workflow label shown in the drawer: Ingestion, stage 4 \u00b7 Activate_

##### Panel `i4-staging` · Create the version in staging · [Implemented, needs changing]
- Kind: Step
- In plain words: Creates a new version row marked as waiting, with every hash it was built with.
- Today: Migration 0012 already widened uniqueness to a 7-column key by a different mechanism; neither this 4-column description nor the target's 2-column (document_id, index_fingerprint) key matches the live schema.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Records | content and structure hashes, every pipeline stamp, built_by_job_id |
  | Target uniqueness | (document_id, index_fingerprint) |
  | States | staging, active, superseded, failed |
- Where in the code:
  - `ingestion/application/versioning.py:206-221` — the insert
  - `platform/db/models.py:225-231` — uq_document_version_idem
- How to test it:
  - Replace an attachment only: a new version builds and activates.
  - Run the same job twice: the second is a no-op on the unique key.
- Target and notes: Target: uniqueness becomes (document_id, index_fingerprint); uq_document_version_idem is dropped in migration 0011 (DDL in 08.1). An attachment-only or title-only change may build a new version. Every version is a full build of the page.

##### Panel `i4-document` · Ensure the document row · [Implemented]
- Kind: Step
- In plain words: One row per page that never changes: the page's permanent name tag in our store.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | One per page | document.page_id is unique and a deferrable FK to page_source |
  | Purpose | a stable id across every rebuild |
- Where in the code:
  - `ingestion/application/versioning.py` — stage_and_activate, step 1

##### Panel `i4-chunks` · Insert the chunks inactive · [Implemented]
- Kind: Step
- In plain words: Inserts all the new pieces switched off, so search cannot see them yet.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Order | parents flushed first, then children mapped to (section, parent ordinal) |
  | Flags | is_active = false, is stamped active only by the swap |
  | Uniqueness | (doc_version_id, stable_key) |
- Where in the code:
  - `ingestion/application/versioning.py` — build_chunks, _link_chunks

##### Panel `i4-gate` · Validation gate · [Implemented]
- Kind: Gate
- In plain words: If the build made zero small pieces, marks it failed and keeps the old page live.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Rule | zero child chunks means the build is wrong |
  | Does | version state = failed, raise, transaction rolls back the chunks |
  | Live version | untouched |
- Where in the code:
  - `ingestion/application/versioning.py:238-242` — the gate
- Target and notes: A real page once failed here: an empty page with no text. The failure is visible in job.last_error, and nothing was activated.

##### Panel `i4-swap` · The pointer swap · [Implemented]
- Kind: Step
- In plain words: Flips one switch: old version off, new version on. Nobody ever sees a half-built page.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Old version | state superseded, its chunks is_active = false |
  | New version | state active, its chunks is_active = true |
  | Pointer | page_source.active_doc_version_id = new id, plus title, url, hashes, stamps, tags, current_cf_version |
  | Guarantee | UNIQUE deferrable FK plus a partial unique index (one active per document) |
- Where in the code:
  - `ingestion/application/versioning.py:314-375` — _activate
  - `platform/db/models.py:235-240` — ux_document_version_one_active
- Code:
```
CREATE UNIQUE INDEX ux_document_version_one_active
  ON document_version (document_id) WHERE state = 'active';
```

##### Panel `i4-stamp` · Stamp source, tags and scope state · [Implemented, needs changing]
- Kind: Step
- In plain words: Writes the source, the tags, and the scope state onto the pieces and the page row.
- Today: source_type = confluence, source_id = confluence:default (constants), tags from source_scope union labels.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Written on | every chunk of the version and the page_source row |
  | Target adds | scope_state on both |
  | Future | source_id becomes a parameter when a second source (Zendesk, Notion, uploads) lands |
- Where in the code:
  - `ingestion/application/versioning.py:34-37, 88-92, 352-353` — the seam

##### Panel `i4-failed` · A failed version never activates · [Implemented]
- Kind: Fail path
- In plain words: A failed build never goes live. It stays as a record of what went wrong.
- Today: GC only reaps versions in state=superseded; a failed-state version is never garbage-collected.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | State | failed |
  | Cleanup | GC deletes failed versions later; chunks cascade |

##### Panel `i4-gc` · Garbage collect old versions · [Implemented]
- Kind: Housekeeping
- In plain words: Keeps the last two old versions for rollback and deletes older ones.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Keep | the two most recent superseded versions |
  | Delete | older ones; chunk rows cascade via FK |
- Where in the code:
  - `ingestion/application/versioning.py:378-399` — _gc_superseded

##### Panel `i4-rollback` · Rollback to an older version · [Implemented]
- Kind: Operator action
- In plain words: Points the page back to an old version in one step, without a rebuild.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Does | supersede current, reactivate the target's chunks, repoint the FK and current_cf_version |
  | Also | restores the target's hashes and pipeline stamps on page_source, so the next sync sees a real diff |
  | Self-heals | fields with no version counterpart on the next sweep |
- Where in the code:
  - `ingestion/application/versioning.py:419-460` — rollback_to
- How to test it:
  - Roll back, then sync the same content: no_change.
  - Roll back, then a newer edit arrives: detected, not masked.

---

## 05 · Knowledge scopes: the tag list, and what a tag does

_Section id: `tags`_

**In plain words (the lede):** A knowledge scope is a tag. The list of tags lives in one small file, `config/knowledge_scopes.json`. A Confluence label that matches a name in that file puts the page in the index and decides which widget may see it. Adding or removing a tag is one edit to that file plus a deploy. Everything the tag does after that is automatic.

#### The scope list

| Label | What it means | Who sees the page |
|---|---|---|
| general | shared knowledge for every platform | every widget |
| mews | specific to the Mews platform | the Mews widget (plus everyone sees general) |
| toast | specific to Toast POS (the product, not this repo's codename) | the Toast widget |
| classified [Planned] | never serve this page | nobody, and the page leaves the index |
| opera-cloud [Decision needed] | in the config today; not in your target list | confirm keep or drop |

Today the names in the file carry a test prefix and suffix (`obi-toast-test`). Rename them when the real corpus lands. Labels are matched case-insensitive. Any label not in this file is ignored.

#### Add or remove a tag

Diagram (Edit the scope file, deploy, the label sweep finds pages with the new tag, pages are indexed. Remove a tag from the file, deploy, pages with only that tag are deactivated.)
  - Edit the file — knowledge_scopes.json → panel `ks-edit` (changes from today)
  - Validate — lowercase, unique → panel `ks-validate` (changes from today)
  - Deploy — both apps reload → panel `ks-deploy` (changes from today)
  - Label sweep — find tagged pages → panel `ks-sweep` (changes from today)
  - Pages go in — ingestion runs → panel `ks-index`
  - Widget scope — same slug → panel `ks-widget` (changes from today)
  - Tag removed — from the file → panel `ks-remove` (changes from today)
  - Pages go out — only that tag: deactivate → panel `ks-orphan` (changes from today)

_Adding a tag to the file is the only setup step. Pages with that label are found by the next label sweep, or by the webhook the next time the page is published._

| You want to | You do | Obi does |
|---|---|---|
| Add a new tag, for example `opera` | Add `"opera"` to the list in `config/knowledge_scopes.json`. Deploy. | The label sweep searches Confluence for pages labeled `opera` and queues each one. The tag is now a valid `knowledgeScope` for a widget. |
| Remove a tag | Delete the name from the file. Deploy. | The next sweep re-checks every page. A page whose only recognized tag was the removed one is deactivated. A widget still sending that scope gets a 400. |
| Rename a tag (`obi-toast-test` to `toast`) | Change the name in the file. Relabel the pages in Confluence. Deploy. | Old-name pages deactivate. New-name pages index. Do the relabel first so no page is out of the index in between. |
| Make a page visible to every widget | Label it `general` in Confluence. | Nothing to deploy. The tag columns update on the next event or sweep. |

Diagram (Six things an editor can do and what happens: add a label, change a label, remove the last label, add classified, put two provider labels on one page, edit the body. Below: the scope list file, the scope state, and the filter that uses them.)
  - Add a label — for example mews → panel `tg-add`
  - Change a label — mews to toast → panel `tg-change`
  - Remove last label — page has none left → panel `tg-remove`
  - Add classified — any other labels too → panel `tg-classified` (changes from today)
  - Two provider tags — mews and toast → panel `tg-two`
  - Edit the body — label stays → panel `tg-edit`
  - In the index — build or tag update → panel `tg-first`
  - Tags updated — no re-embed → panel `tg-retag`
  - Deactivate — leaves the index → panel `tg-deactivate` (changes from today)
  - Deactivate + purge — chunks deleted → panel `tg-purge` (changes from today)
  - Excluded: conflict — logged, heals on fix → panel `tg-conflict` (changes from today)
  - Rebuild whole page — out, then back in → panel `tg-rebuild`
  - The scope list — knowledge_scopes.json → panel `tg-config`
  - scope_state — only ok is served → panel `tg-state` (changes from today)
  - The filter — state ok + tag match → panel `tg-filter` (changes from today)

_Every arrow runs through ingestion stage 1 (a label event or a sweep) and stage 2 (classify). Label events never bump the page version._

#### What happens, step by step

| Editor does | Confluence sends | Obi does | How fast |
|---|---|---|---|
| Publishes a page with `toast`, not yet indexed [Planned] | label_added or page_created | the page goes in: fetch, chunk, embed the whole page, activate with tags [toast] | webhook: within a minute. Sweep: daily. |
| Adds `general` to an indexed `toast` page | label_added | tag update only: tags become [general, toast], no re-embed | same |
| Changes `mews` to `toast` | label_deleted, then label_added | two events, one job: tags become [toast], never both | same |
| Removes the last recognized tag [Planned] | label_deleted | the page goes out: chunks inactive, page out of every scope | same |
| Adds `classified` [Planned] | label_added | the page goes out and its chunks are deleted; a later removal of the label re-indexes from scratch | same |
| Puts `mews` and `toast` on one page | label_added | scope_state = conflict, excluded from every scope, a warning is logged; fix the labels and the next sync heals it | same |
| Edits and publishes text on a tagged page [Implemented, needs changing] | page_updated | the whole page goes out and the whole page goes back in: every chunk rebuilt and embedded, one swap, tags carried over | same |
| Saves a draft, does not publish | nothing | nothing. The index shows the last published version. | n/a |
| Replaces a PDF on a tagged page [Implemented, needs changing] | attachment_updated | same as an edit: whole page out, whole page in | same |
| Restricts the page to one group | page_permissions_updated | page_restriction rows replaced; group expanded to members | same |
| Trashes the page | page_trashed | the page goes out | same |

> **The conflict rule and the "empty tags" rule combine badly today.** [Implemented, needs changing] Today a conflict yields zero label tags. Separately, the database treats empty tags as global. So a page with two provider labels can become visible everywhere. The target adds an explicit `scope_state`. Only `ok` is served. Global content must carry `general`. An empty tag list is never treated as public.

> **Tags are the only membership control.** [Planned] Today a page is synced only if a folder root in `source_scope` covers it, and labels add scoping on top. The target drops the folder roots. A page is in the corpus for one reason: it is published and carries a tag from `knowledge_scopes.json`. The webhook watches `label_added`, `label_deleted`, and `page_updated`. A daily label sweep (a Confluence label search across all spaces) catches anything the webhook missed. `source_scope` retires as an ingestion input.

#### Panels that belong to this section (23)

_Workflow label shown in the drawer: Knowledge scopes_

##### Panel `tg-config` · The scope list file · [Implemented, needs changing]
- Kind: Config
- In plain words: The list of tag names in one small file. A name here is a tag; a name not here is ignored.
- Today: apps/web/src/features/chat/model/knowledge-scopes.ts is a hand-written copy of this file's list, checked by a runtime drift test, not generated at build time.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Path | config/knowledge_scopes.json at the repo root |
  | Today | obi-general-test, obi-mews-test, obi-operacloud-test, obi-toast-test |
  | Target | general, mews, toast, classified (confirm opera-cloud) |
  | Rule | startup fails if general is missing |
  | Also read by | the widget build, which imports the JSON and generates its scope list without classified |
- Where in the code:
  - `config/knowledge_scopes.json` — the list
  - `platform/config/knowledge_scopes.py` — loader
  - `apps/web/src/features/chat/model/knowledge-scopes.ts` — generated from the JSON at build time

##### Panel `ks-edit` · Edit knowledge_scopes.json · [Implemented, needs changing]
- Kind: Knowledge scopes
- In plain words: The tag list is one small file. Add a tag's name to the file to create the tag.
- Today: The file holds obi-general-test, obi-mews-test, obi-operacloud-test, obi-toast-test as an object {scopes:[{name,description}]}, not a plain list of slugs. Loaded at startup by both apps.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Path | config/knowledge_scopes.json at the repo root |
  | Shape | a JSON list of lowercase slugs |
  | Rule | a Confluence label that matches a slug (case-insensitive) is a knowledge scope |
- Steps:
  1. Open the file.
  2. Add or remove one slug.
  3. Commit and deploy.
- How to test it:
  - Add a slug, restart, query GET /health: the slug is listed as a valid scope.
- Target and notes: This is the whole setup for a new tag. No table edit, no migration.

##### Panel `ks-validate` · Validate the list · [Implemented, needs changing]
- Kind: Knowledge scopes
- In plain words: The app checks the list at startup and stops with a clear message if a name is wrong.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Lowercase | uppercase slugs are rejected at startup |
  | Unique | a duplicate fails startup |
  | Reserved | classified is always present in the file and is excluded from the generated widget list |
- Steps:
  1. Startup reads the file.
  2. A bad entry stops the app with a clear message.
  3. A good list is cached in memory.
- How to test it:
  - Add 'Toast' with a capital T: startup fails and names the entry.

##### Panel `ks-deploy` · Deploy · [Implemented, needs changing]
- Kind: Knowledge scopes
- In plain words: Ship the new file. The backend and the widget both read it.
- Today: The widget's scope list is a hand-written copy, not generated at build time; a runtime drift test guards it against this file.
- Steps:
  1. The backend restarts and reads the new list.
  2. The widget build imports the same file and generates its scope list, without classified.
  3. Until both are deployed the old list is in force.
- Target and notes: Deploy the backend first. A widget sending a scope the backend does not know gets a 400.

##### Panel `ks-sweep` · The label sweep finds tagged pages · [Planned]
- Kind: Knowledge scopes
- In plain words: Once a day, asks Confluence for every page with each tag in the list and queues the new ones.
- Today: The sweep walks folder roots from source_scope. A label search does not exist yet.
- Steps:
  1. Once a day, for each slug in the list, ask Confluence for every page with that label (CQL label search across all spaces).
  2. Enqueue one sync_page job per page found.
  3. Pages that were indexed but now carry no recognized label are enqueued too, so they deactivate.
- How to test it:
  - Add a new slug, label one Confluence page with it, run the sweep: the page is indexed with that tag.

##### Panel `ks-index` · Pages go in · [Implemented]
- Kind: Knowledge scopes
- In plain words: The queued pages run through ingestion and become searchable in that scope.
- Steps:
  1. The queued job runs ingestion stages 2 to 4 on the page.
  2. Tags on the chunks are the recognized labels.
  3. The page is now searchable in that scope.

##### Panel `ks-widget` · A widget uses the same slug · [Implemented, needs changing]
- Kind: Knowledge scopes
- In plain words: A widget uses the same tag name as its scope, so it only sees pages with that tag.
- Today: The live /embed frame does not set a knowledgeScope prop; only the dev-only scope switcher sets it client-side today. The token-driven scope in step 3 is target, not current.
- Steps:
  1. The embed config sets knowledgeScope to the slug, for example toast.
  2. The gate validates the slug against the list.
  3. In the target the token decides the scope. A known slug that disagrees with the token is ignored and logged. An unknown slug is still a 400 before any search.

##### Panel `ks-remove` · A tag is removed from the file · [Implemented, needs changing]
- Kind: Knowledge scopes
- In plain words: Take the name out of the file and ship it. That label means nothing anymore.
- Steps:
  1. Delete the slug and deploy.
  2. Labels with that name are now ignored.
  3. A widget still sending that scope gets a 400.

##### Panel `ks-orphan` · Pages with only that tag go out · [Planned]
- Kind: Knowledge scopes
- In plain words: Pages that only had the removed tag leave search on the next sweep. Pages with another tag stay.
- Steps:
  1. The next sweep re-reads each indexed page's labels.
  2. A page with no remaining recognized tag is deactivated.
  3. A page that also carries another tag keeps that tag and stays in.
- How to test it:
  - Two pages: one labeled toast only, one labeled toast and general. Remove toast from the file. The first deactivates, the second stays in for general.

##### Panel `tg-add` · Add a label · [Implemented]
- Kind: Editor action
- In plain words: An editor adds a tag like mews in Confluence. That alone puts the page in.
- Steps:
  1. Confluence sends label_added. The page version does not change.
  2. Ingestion stage 1 writes the event and enqueues one job.
  3. Ingestion stage 2 fetches labels, recomputes scope state and labels_hash.
  4. Not indexed yet and the label is recognized: first index (full build).
  5. Already indexed: metadata only, tags updated in place, no re-embed.
- How to test it:
  - active_doc_version_id is unchanged after a label-only change.
  - The page appears in the new scope's results on the next question.

##### Panel `tg-change` · Change a label · [Implemented]
- Kind: Editor action
- In plain words: An editor swaps one tag for another. The page moves scope and is never in both.
- Steps:
  1. Confluence sends label_deleted and then label_added.
  2. With coalescing, both land in one pending job. Without it, two jobs run in order.
  3. The worker reads the current label set, so the result is the same: tags become [toast] and mews is gone.
- How to test it:
  - No stale double tag after mews to toast.

##### Panel `tg-remove` · Remove the last recognized label · [Planned]
- Kind: Editor action
- In plain words: An editor removes the last tag. The page leaves search.
- Today: Today the page keeps its source_scope tags and stays in the index. A page with no recognized tag is invisible to scoped queries but still stored.
- Where in the code:
  - `confluence_sync/application/sync_service.py` — deactivate-on-unlabeled branch (target)
  - `platform/config/settings.py` — cut-over flag only: default on, deleted after verify_knowledge_scope_backfill.py reports zero untagged chunks
- Steps:
  1. Confluence sends label_deleted.
  2. Ingestion stage 2 finds no recognized label: scope_state = unlabeled.
  3. The page is deactivated. Chunks is_active = false. Label-gated ingestion is unconditional in the target.
- Target and notes: Target: removing the last recognized tag deactivates the page. Folder roots (source_scope) no longer keep it in.

##### Panel `tg-classified` · Add the classified label · [Planned]
- Kind: Editor action
- In plain words: An editor adds classified. The page leaves search and its pieces are deleted, whatever other tags it has.
- Steps:
  1. Confluence sends label_added.
  2. Ingestion stage 2 sees classified: state = classified, regardless of other labels.
  3. The page is deactivated and its chunk rows are deleted.
  4. As a second wall, the scope policy never returns a row whose state is not ok.
  5. Removing the label later triggers a fresh first index.
- How to test it:
  - Add classified to an indexed page: its chunks are gone from the table on the next sync.
  - A classified page never appears in any scope, with any token, in any test.
- Target and notes: Deleting rather than deactivating means a database dump or a bug that ignores is_active still cannot leak the content.

##### Panel `tg-two` · Two provider labels on one page · [Implemented, needs changing]
- Kind: Editor mistake
- In plain words: A page carries two platform tags at once. That is a mistake, so the page is hidden from everyone until fixed.
- Today: Zero label tags, a knowledge_scope_conflict warning, the page keeps its source_scope tags. Combined with the empty-tags-means-global rule this can make the page visible everywhere.
- Steps:
  1. Ingestion stage 2 sets scope_state = conflict.
  2. The scope policy hides every row whose state is not ok.
  3. The warning names the page and the labels.
  4. An editor removes one label; the next sync sets state = ok.
- How to test it:
  - mews + toast: zero results for a Mews user, zero for a Toast user, zero for general.
  - Fix the labels: results return without a rebuild.

##### Panel `tg-edit` · Edit the body of a labeled page · [Implemented, needs changing]
- Kind: Editor action
- In plain words: An editor changes the text and publishes. The whole page goes out and the whole page comes back in.
- Steps:
  1. Confluence sends page_updated with a higher version.
  2. Ingestion stage 2: content_hash differs, rebuild.
  3. Ingestion stage 3 rebuilds; unchanged children keep their vectors.
  4. Ingestion stage 4 activates; tags and scope state are carried over from the labels read in this sync.
- Target and notes: Target: an edit throws the whole page out of search and puts the whole page back in, in one swap. No child keeps an old vector.

##### Panel `tg-first` · The page is in the index · [Implemented]
- Kind: Outcome
- In plain words: The page is in the index with its tags and widgets in that scope can find it.
- Steps:
  1. A first build creates document, version, chunks, and activates them with the label tags.
  2. A later label on an indexed page is a metadata-only update.

##### Panel `tg-retag` · Tags updated without a re-embed · [Implemented]
- Kind: Outcome
- In plain words: Only the tag changed, so only the tag column changes.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Touched | page_source.tags, chunk.tags, scope_state, labels_hash, last_indexed_at |
  | Untouched | embeddings, document_version, active_doc_version_id |
- Where in the code:
  - `confluence_sync/application/sync_service.py:180-189` — _apply_metadata_only

##### Panel `tg-deactivate` · Deactivate · [Planned]
- Kind: Outcome
- In plain words: The page's pieces are switched off and search cannot see them.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Does | page_status updated, active version superseded, chunks inactive |
  | Undo | add a recognized label again; the next sync re-indexes |

##### Panel `tg-purge` · Deactivate and purge · [Planned]
- Kind: Outcome
- In plain words: The page's pieces are switched off and deleted.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Does | everything deactivate does, plus DELETE the chunk rows of every version of the page |
  | Keeps | page_source (with state classified) so the sweep knows to skip it |

##### Panel `tg-conflict` · Excluded as a conflict · [Implemented, needs changing]
- Kind: Outcome
- In plain words: The page is marked as a conflict and hidden. Fix the tags in Confluence and the next sync brings it back.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | State | conflict |
  | Visible to | nobody |
  | Log | knowledge_scope_conflict with page_id, title, matched labels |
  | Heals | on the next sync after the labels are fixed |

##### Panel `tg-rebuild` · Rebuild with tags carried · [Implemented, needs changing]
- Kind: Outcome
- In plain words: The whole page is rebuilt with the same tags: old pieces out, new pieces in, one swap.
- Steps:
  1. Same as ingestion stage 3 and 4. The label read in this sync is stamped onto the new version.
- Target and notes: Target: an edit throws the whole page out of search and puts the whole page back in, in one swap. No child keeps an old vector.

##### Panel `tg-state` · scope_state · [Planned]
- Kind: Data
- In plain words: One word per page: ok, conflict, classified, or unlabeled. Only ok pages are ever shown.
- Today: Does not exist yet: no scope_state enum, no chunk/page_source columns, and no consumer reads it.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Values | ok, conflict, classified, unlabeled |
  | Stored on | page_source and chunk (denormalized so search never joins) |
  | Read by | the scope row policy and the readiness gate |
  | Replaces | the rule that an empty tag array means global |
- Code:
```
CREATE TYPE scope_state AS ENUM ('ok','conflict','classified','unlabeled');
ALTER TABLE chunk ADD COLUMN scope_state scope_state NOT NULL DEFAULT 'unlabeled';
ALTER TABLE page_source ADD COLUMN scope_state scope_state NOT NULL DEFAULT 'unlabeled';
```
- Target and notes: Backfill: every active chunk with a recognized tag becomes ok. The readiness gate (verify_knowledge_scope_backfill.py) must report zero rows in any other state before the new policy goes live.

##### Panel `tg-filter` · The filter that uses tags · [Implemented, needs changing]
- Kind: Step
- In plain words: The database rule that shows a piece only when its tag matches the widget's scope and its state is ok.
- Today: App predicate tags && :scopes behind a flag, default off, plus the 0010 RESTRICTIVE policy — coded and tested, not yet applied to Supabase.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Target policy | scope_state = 'ok' AND tags && allowed_scopes |
  | Wildcard | '*' allowed only for the eval role; the public path never sets it |
  | App predicate | kept as a planner hint on ix_chunk_tags_gin |
- Where in the code:
  - `platform/db/schema.py` — the policy DDL
  - `retrieval/infrastructure/search_repo.py:64-69` — the app predicate
- Code:
```
CREATE POLICY chunk_scope_read ON chunk AS RESTRICTIVE FOR SELECT
  USING (
    scope_state = 'ok' AND (
      current_setting('app.allowed_knowledge_scopes', true) = '*'
      OR tags && string_to_array(current_setting('app.allowed_knowledge_scopes', true), ',')
    )
  );
```

---

## 06 · Workflow 2 · Retrieval, from A to Z

_Section id: `retrieve`_

**In plain words (the lede):** Retrieval is the road from a question to a cited answer. It starts when a person types in the chat window. It ends with an answer where every sentence points at a Confluence page, or a clear refusal with a way to reach a human. Five stages run inside one request. This chapter reads the whole road once and the five sections after it open each stage.

Diagram (The widget and the auth host feed gate, search, filter, judge and answer, which read from the Postgres corpus as rag_reader.)
  - Obi widget — question + token → panel `ov-widget`
  - Stage 1 · Gate — who asks, limits → panel `ov-gate`
  - Stage 2 · Search — meaning + keywords → panel `ov-search` (changes from today)
  - Stage 3 · Filter — three locks → panel `ov-filter` (changes from today)
  - Stage 4 · Judge — rerank, anything relevant? → panel `ov-judge` (changes from today)
  - Stage 5 · Answer — enough proof, cite, stream → panel `ov-answer`
  - Auth host — signs a user token → panel `ov-auth` (changes from today)
  - Postgres — read as rag_reader, row security on → panel `ov-corpus`
  - Runs as reader — cannot bypass RLS → panel `s-reader`

_The dashed arrow is an input. The reads in stages 2, 3 and 5 happen inside one authorization context built in stage 1._

#### The whole path, step by step

1. **Someone types a question in the widget.** The widget knows which platform it sits in (`mews`, `toast`) and holds a user token from the host application in memory (section 03.2).
2. **The widget's proxy forwards it.** The browser never talks to the backend. The proxy adds the server key and calls `POST /chat`.
3. **Stage 1 proves who is asking.** Verify the server key and the user token. Read platform and principal from the token, never from the body. Rate limit 20 per minute. Build one authorization context: allowed sources, allowed scopes (always plus `general`), the principal.
4. **Stage 1 handles the easy cases.** Small talk gets a short reply. A too-vague question gets a clarifying question. Otherwise Haiku rewrites the chat history into one standalone question and lists its parts.
5. **Stage 2 embeds the question.** Same model as the pages. Then one transaction as `rag_reader` with both scope settings bound.
6. **Stage 2 searches twice.** Dense: cosine over the HNSW vector index, top 75 child chunks. Keyword: Postgres full text over the GIN index, top 75. Fuse by chunk id with reciprocal rank fusion. Curated entries are in the same pool.
7. **Stage 3 filters.** Lock 1: source row security. Lock 2: scope row security, `scope_state = 'ok'` and a tag match. Both are inside Postgres and ran during the search. Lock 3: page restrictions checked per person. Only permitted rows continue.
8. **Stage 4 reranks.** Cohere cross-encoder scores each matching child against the question. Best score below 0.10: run one fallback search with the user's own words, union, rerank once more.
9. **Stage 4 decides if anything is relevant.** Best score still below the threshold after the fallback: refuse with `weak_score` and a human hand-off. Otherwise the top children move on.
10. **Stage 5 expands to parents.** Each child points at its parent. Parents are what the model reads. Same authorization context, deduped, capped by a token budget.
11. **Stage 5 judges coverage.** Does the final context cover every part of the question? All: proceed. Some: partial answer that names the gap. None: refuse with `insufficient_coverage` and a human hand-off.
12. **Stage 5 generates and enforces.** Sonnet answers from the numbered evidence. Every sentence must cite. Uncited sentences are cut in code. Then one batched judge call checks that each cited source backs its sentence. Unsupported sentences are cut or marked. Nothing left: refuse.
13. **Stage 5 streams and logs.** The finished text streams to the widget as SSE. One `query_trace` row records the question, the candidates, the scores, the scopes, the answer, and the citations.

> **The one sentence version.** Prove who asks, search only the rows that person may see, keep only passages that really answer, and refuse before you guess.

#### Security inside the retrieval workflow

These checks belong to retrieval. The security chapter puts them in the full escalation from edge to row.

- **Lock 0, the edge.** Server key per widget host plus a signed user token. Platform and principal come from the token. The body cannot widen them. [Planned]
- **Lock 1, source.** Postgres row security on `chunk`. Scope not set: zero rows.
- **Lock 2, scope.** A RESTRICTIVE policy. `scope_state = 'ok'` and `tags && allowed_scopes`. Keeps Mews and Toast apart. [Unverified] coded in migration 0010, not applied to Supabase; the flag-gated app predicate is the only scope filter live today
- **Lock 3, page.** Confluence read restrictions applied per person before rerank.
- **The reader role.** `rag_reader` can SELECT and nothing else, and cannot bypass row security.
- **Citations in code.** A passage that says "ignore your rules" cannot change the scope or forge a citation. Both are enforced outside the model.

---

## 06.1 · Retrieval, stage 1 · The gate

_Section id: `rt1`_

**In plain words (the lede):** A question arrives from the chat window. Before any search runs, the gate finds out who is asking: which company, which integration (Mews, Toast, Opera Cloud) and which person. It writes that into one note that every later step obeys. Small talk and vague questions get a short reply without a search. Every other question is rewritten into one clear standalone question.

**For leaders: before we search, we find out who is asking: which company, which integration (Mews, Toast, Opera Cloud), which person. Then we build one note that every later step obeys.**

| Field | Value |
|---|---|
| Inputs | the chat request from the widget proxy: history (≤20 turns), images (≤4), `knowledgeScope`; Authorization header (server key today; host key + signed user token in the target); optional Idempotency-Key |
| Processing rules | verify key and token in constant time; derive company, integration, principal from the token, never the body; rate limit 20/min; validate the body slug for shape and membership against `knowledge_scopes.json` only (unknown: 400); the token decides scope and a known slug that disagrees is ignored and logged; build the authorization context (company, integration, allowed scopes = integration + general, allowed sources, principal); small-talk exact match → short reply; vague check (flag, off) → clarifying question; Haiku rewrite → one standalone question plus its parts |
| Outputs | one authorization context object; the rewritten question and its parts; or a short reply with no search |
| Failure behavior | missing or bad auth: 401 (fail closed); unknown scope: 400; rewrite model error: fall back to the raw text; rate limit: 429 |
| Code locations | `rag_agent/api/chat.py`, `rag_agent/application/auth.py`, `rag_agent/application/rewrite.py`, `apps/web/app/api/chat/route.ts` |
| Today | [Implemented, needs changing] key, limits, small talk, rewrite run; scope and principal come from the body; company is not known |
| Target | [Planned] signed token from the host backend, verified before any claim is read (section 03.2); company + integration in the context; question parts listed for the coverage check |

Diagram (Web proxy, verify host key and user token, limits, build auth context, small talk check, clarification check, rewrite. Small talk and clarification exit early with a short reply. An idempotency cache sits beside verify.)
  - Web proxy — proxies to POST /chat → panel `r1-proxy`
  - Verify — host key + user token → panel `r1-auth` (changes from today)
  - Limits — rate, size, shape → panel `r1-limits`
  - Auth context — company, integration, who → panel `r1-ctx` (changes from today)
  - Small talk? — exact match only → panel `r1-small`
  - Too vague? — flag, default off → panel `r1-clarify`
  - Idempotency — replay, same answer → panel `r1-idem`
  - Short reply — no search, no trace → panel `r1-short`
  - Rewrite — question + its parts → panel `r1-rewrite` (changes from today)

- **Web proxy** The browser never talks to the backend. It calls the widget's own `/api/chat`, which adds the server key and streams the answer back as bytes.
- **Verify** Today: one shared server key per deployment, compared in constant time. Target: a key per widget host plus a signed user token from the host backend (or an agreed auth service). The token says which company the person belongs to, which integration that company runs (Mews, Toast, Opera Cloud), and who the person is. The request body cannot widen that. The contract and the handshake are in section 03.2.
- **Limits** Rate limit (20 a minute), history at most 20 turns of 4000 characters, images capped, scope slug validated, numeric principals rejected. Every LLM call has a timeout, retries, and a breaker.
- **Auth context** One object built here and passed everywhere. Fields: `company_id` (the tenant), `integration` (the knowledge scope: `mews`, `toast`, `opera-cloud`), allowed scopes (the integration plus `general`), allowed sources, the person's principal, the token subject, and `space_id` (the Confluence space the widget is bound to, read by lock 3's space rule). Every database read in retrieval stages 2 to 5 sets its scope from this object. The token decides scope. The body slug is checked for shape only. A slug not in `knowledge_scopes.json` is a 400 before any search. A known slug that disagrees with the token is ignored and logged. The answer model also gets company and integration as plain facts, so it can say "in Mews, do X" instead of guessing.
- **Small talk?** "hi", "thanks", "test". The whole message must match a closed list. A real question that starts with "hi" does not match. The reply is short and carries no citation.
- **Too vague?** Behind a flag, off by default. Twelve words or more skips it. Otherwise one cheap classifier call. A vague question gets a clarifying question with options, which is an open turn, never a refusal.
- **Rewrite** Haiku turns the chat history into one standalone question. In the target it also lists the question's parts ("how to configure", "which permissions", "how to roll back") for the coverage check in retrieval stage 5. Fails open to the raw text.

> **Body fields are not identity.** [Implemented, needs changing] Today `principal` and `knowledge_scope` come from the request body, and the backend trusts them as far as it trusts the proxy. In the target the host backend (or an agreed auth service) signs a token per user. The backend verifies it and derives both values from it. The body slug is checked for shape and membership only. An unknown slug is a 400 before any search. A known slug that disagrees with the token is ignored and logged. This closes the "send another user's principal" path.

> **The answer cache is removed.** A cached answer can outlive a permission change. There is no traffic yet that needs a cache, so the target drops `CachingAnswerService`. Idempotency replay stays, because it is bound to the token, the history, and the scope, and it lives only minutes.

#### Panels that belong to this section (9)

_Workflow label shown in the drawer: Retrieval, stage 1 \u00b7 The gate_

##### Panel `r1-ctx` · Build the authorization context: company, integration, person · [Planned]
- Kind: Step
- In plain words: Writes one note: which company, which integration (Mews, Toast, Opera Cloud), which person, and which pages they may see. Every later step reads only this note.
- Today: Scopes are resolved once per request (resolve_allowed_scopes) and reused by the fallback. The principal string is passed separately. Parent expansion opens its own session.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | company_id | the tenant (hotel or restaurant group), from the token |
  | company_name | display context for the answer and the header; never an access key |
  | integration | the knowledge scope the company runs: mews, toast, opera-cloud; from the token |
  | allowed_scopes | from platforms.json: the integration plus general |
  | allowed_sources | confluence today; a second source later |
  | principal, subject | who the person is: sub from the token; principal from the identity mapping or none |
  | space_id | the Confluence space the widget is bound to; lock 3 drops a candidate page outside it |
- Where in the code:
  - `retrieval/domain/knowledge_scope.py` — resolve_allowed_scopes
  - `retrieval/domain/permission.py:30-37` — classify_scope
  - `rag_agent/application/answer_service.py` — where the context is threaded
- Code:
```
@dataclass(frozen=True)
class AuthContext:
    company_id: str
    company_name: str            # display only
    integration: str             # mews, toast
    allowed_scopes: tuple[str, ...]   # from platforms.json, always has 'general'
    allowed_sources: tuple[str, ...]
    principal: str | None       # from the identity mapping, or None
    space_id: int | None        # the Confluence space the widget is bound to; lock 3's space rule
    token_subject: str
```
- How to test it:
  - Every reader transaction in a request logs the same allowed_sources and allowed_scopes to query_trace.
- Target and notes: Target: company and integration come from the signed token and are also handed to the answer model as plain facts, so an answer can say "in Mews, do X" instead of guessing which system the person uses.

##### Panel `r1-proxy` · The widget's proxy route · [Implemented]
- Kind: Outside system
- In plain words: The browser talks to the widget's own server, which adds the secret key and passes the question on.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Browser calls | POST /api/chat on the widget's own origin |
  | Proxy adds | Authorization: Bearer CHAT_API_KEY, forwards the body as-is |
  | Streams | the SSE bytes back unbuffered |
  | Body cap | 30 MB (four base64 images plus text) |
  | Its own auth | x-widget-access-token today; the user token in the target |
- Where in the code:
  - `apps/web/src/features/chat/server/route-handlers.ts` — handlePostChat, handlePatchFeedback
  - `apps/web/src/features/chat/server/validation.ts` — shape checks only
  - `apps/web/src/platform/automation-api/client.ts` — the backend client

##### Panel `r1-auth` · Verify who is asking · [Implemented]
- Kind: Gate
- In plain words: Checks the widget's key and the person's signed card. Company, integration, and identity come from the card, never from what was typed.
- Today: One CHAT_API_KEY per deployment, compared in constant time against the current and previous key (rotation window), plus a per-user RS256 JWT verified before any search — live-proven for test hosts (commit 59385f4).
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Host key | one per widget host, rotated with an overlap window |
  | User token | a JWT from the trusted issuer: iss, aud, sub, iat, exp, company_id, company_name, integration |
  | Verification | algorithm allow-list, signature by kid, issuer, audience, expiry with 60 s leeway; then the claims become the auth context |
  | Fail closed | 503 if the key or the issuer config is missing, 401 on any mismatch |
- Where in the code:
  - `rag_agent/server/router.py:254-267` — _verify_api_key
  - `docs/runbooks/chat-api-key-rotation.md` — rotation
- How to test it:
  - Expired token: 401.
  - Valid token, body scope for another integration: the token wins and the mismatch is logged.
  - Both compares always run so timing does not reveal which key matched.
- Target and notes: The token contract and the iframe handshake are in section 03.2.

##### Panel `r1-limits` · Limits and validation · [Implemented]
- Kind: Gate
- In plain words: Caps questions per minute, chat length, and image count.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Rate | 20 per minute; keyed on the token subject when there is a token, otherwise on request.client.host. No X-Forwarded-For parsing today: TRUSTED_PROXY_HOPS defaults to 0, set per environment in 7.1.1 once the browser→proxy→API chain is known (decision r1-limits-ipkey, 2026-09-18) |
  | History | 1 to 20 turns, must end on a user turn, 4000 chars per turn |
  | Images | 4 per turn, 5 MB each, checked on every turn |
  | Scope slug | ^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$ |
  | Principal | all-digit values rejected (they would read as space-wide trust) |
  | LLM calls | 30 s timeout, 2 retries, breaker after 5 |
  | Output | answer text capped at 8000 chars |
  | PII | emails, phones, SSNs, card numbers redacted from prompt text (not image bytes) |
- Where in the code:
  - `rag_agent/server/router.py:164-199, 232-307` — ChatRequestBody and the limiter
  - `rag_agent/domain/pii.py` — redact_pii

##### Panel `r1-small` · Small talk short-circuit · [Implemented]
- Kind: Gate
- In plain words: Replies to hi or thanks without searching.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Match | the whole normalized message against a closed set (trailing !.? stripped, whitespace collapsed) |
  | Reply | a short ungrounded greeting from Haiku, 150 tokens, static fallback on error |
  | Trace | none |
  | Images | dropped on this path |
- Where in the code:
  - `rag_agent/domain/small_talk.py:24-94` — is_small_talk
  - `rag_agent/infrastructure/llm_client.py` — generate_small_talk
- Target and notes: Runs before the vagueness check, so a message that is both resolves as small talk (ADR-0008).

##### Panel `r1-clarify` · Too vague to search? · [Implemented]
- Kind: Gate
- In plain words: If the question is too vague, asks a short question back with options.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Flag | enable_clarification_branch, default false |
  | Heuristic | 12 words or more is not vague; skip the call |
  | Otherwise | one Haiku classifier call; fails open to not vague |
  | Reply | a clarifying question with options, needs_clarification = true, refused = false |
  | Trace | none |
- Where in the code:
  - `rag_agent/domain/clarification.py:100-116` — decide_clarification, parse_clarification_reply
  - `rag_agent/domain/prompt.py` — CLARIFICATION_SYSTEM_PROMPT

##### Panel `r1-idem` · Idempotency replay · [Implemented]
- Kind: Data
- In plain words: Returns the same answer if the same request arrives twice, without a second search.
- Today: The cache key already binds sha256(key, history, token_subject, knowledge_scope) — token subject, not body principal.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Header | Idempotency-Key, optional |
  | Cache key | sha256(key / history / principal / knowledge_scope), target: token subject instead of body principal |
  | TTL | minutes; bounded entries |
  | Effect | same request replays the same Answer and trace id, no rerun |
- Where in the code:
  - `rag_agent/server/router.py:243-251, 310-331` — the TTL cache

##### Panel `r1-short` · A short reply without search · [Implemented]
- Kind: Outcome
- In plain words: A short friendly reply with no search and no citation.
- Steps:
  1. Small talk returns a greeting.
  2. A vague question returns a clarifying question with option chips.
  3. Neither writes a query_trace row.

##### Panel `r1-rewrite` · Rewrite into one standalone question · [Implemented, needs changing]
- Kind: Step
- In plain words: Turns the chat so far into one clear question and lists its parts, so we can later check each part was answered.
- Today: Haiku turns the history into a standalone query, 200 tokens, plain text only — not yet the {query, parts} JSON. Single-turn history skips the call. Fails open to the raw text. Stored on the trace.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Target output | the standalone question plus a short list of its parts, as JSON |
  | Parts | used by the coverage check in retrieval stage 5 |
  | Fallback | one part equal to the whole question |
- Where in the code:
  - `rag_agent/infrastructure/llm_client.py:103-117` — AnthropicQueryRewriter.rewrite
  - `rag_agent/domain/prompt.py` — the rewrite prompt
- Code:
```
{
  "query": "How do I configure the Mews export, which permissions does it need, and how do I undo it?",
  "parts": ["configure the export", "required permissions", "undo or roll back"]
}
```

---

## 06.2 · Retrieval, stage 2 · Search

_Section id: `rt2`_

**In plain words (the lede):** Two searches run inside the database at the same time. One finds pieces that mean the same as the question. One finds pieces that share its exact words. Both run only over rows this person may see. The two lists merge into one list of the exact pieces that matched, and each piece keeps its ids and ranks so nothing is lost on the way to the answer.

**For leaders: two searches run inside the database, one for meaning and one for words, and only over rows this person may see. The results are merged into one list of the exact passages that matched.**

| Field | Value |
|---|---|
| Inputs | the authorization context; the rewritten question (embedded with the page model); the active child chunks and curated entries |
| Processing rules | set `app.allowed_sources` and `app.allowed_knowledge_scopes` per transaction (locks 1 and 2 in SQL); dense: cosine over HNSW halfvec, top 75; keyword: ts_rank over GIN, top 75; page ACL predicate inside both queries before LIMIT (target); RRF by chunk id; curated entries retrieved by relevance in both branches |
| Outputs | a candidate list of ≤150 children, each with chunk id, parent id, page id, version id, both ranks, fused score, and `(source_type, item_id)` |
| Failure behavior | scope not set: zero rows, never a leak; embedding API error: the request fails (no silent empty search); image-only turn: empty candidate list by design |
| Code locations | `retrieval/infrastructure/search_repo.py → dense_search, keyword_search`, `retrieval/domain/fusion.py → reciprocal_rank_fusion`, `retrieval/application/retriever.py`, `rag_agent/infrastructure/curated_knowledge_repo.py` |
| Today | [Implemented, needs changing] both searches and RRF run; fusion is by page id; curated entries are the first five by id, added later; lock 3 runs after fusion |
| Target | [Planned] [Priority 1] fusion by chunk id with provenance kept, so the exact matching child reaches the reranker and the answer model; page ACL in SQL; curated entries embedded and fused; collision-safe identities |

Diagram (Embed the query, set locks 1 and 2 in the transaction, dense search, keyword search, reciprocal rank fusion by chunk id, provenance kept. Curated entries join the same candidate pool. In the target lock 3 also runs inside the two SQL searches.)
  - Embed query — same model as pages → panel `r2-embed`
  - Set locks 1 + 2 — in SQL, before LIMIT → panel `r2-gucs`
  - Dense search — top 75 child chunks → panel `r2-dense`
  - Keyword search — top 75 child chunks → panel `r2-keyword`
  - Fuse (RRF) — by chunk id, not page → panel `r2-rrf` (changes from today)
  - Provenance — ids and ranks kept → panel `r2-prov` (changes from today)
  - Curated entries — in the same pool → panel `r2-curated` (changes from today)
  - The indexes — HNSW halfvec, GIN tsv → panel `r2-indexes`
  - Lock 3 in SQL — page ACL, target → panel `r2-aclsql` (changes from today)

_Where each filter runs. Locks 1 and 2 (source, scope) are row security policies: they run inside both SQL searches, before the LIMIT 75, today. Lock 3 (page ACL) runs after fusion in the app today. In the target it also runs inside both searches, before the LIMIT, and the app check stays as a second wall._

- **Embed query** The rewritten question goes through the same embedding model the pages used. A text-empty turn (image only) skips this and builds an empty result instead.
- **Set locks 1 + 2** `SELECT set_config('app.allowed_sources', :s, true)` and the same for `app.allowed_knowledge_scopes`, both bound parameters, both per transaction. Also `hnsw.ef_search=100` and `hnsw.iterative_scan='relaxed_order'`.
- **Dense search** Cosine distance over the HNSW index on active child chunks. Casts to `halfvec(3072)` because pgvector caps plain vectors at 2000 dims. Ties broken by page id.
- **Keyword search** `ts_rank` over the GIN index with an OR-joined query, so a question with one rare word still matches. Same filters as dense.
- **Fuse (RRF)** Score = sum of 1/(60 + rank) across the two lists. **Item ranked today:** page id. **Item ranked in the target:** child chunk id, deduplicated by chunk id. Both searches return `chunk_id, parent_chunk_id, page_id, doc_version_id`. Two sections of one page can both survive. Code: `retrieval/domain/fusion.py → reciprocal_rank_fusion`, `retrieval/application/retriever.py` (candidate assembly).
- **Provenance** Each candidate carries child id, parent id, page id, document version id, keyword rank, dense rank, and fused score. Nothing downstream has to look these up again.
- **Curated entries** Admin-written facts. **Today:** `fetch_curated_entries` returns the first five active entries by id and they are added after the refusal decision. **Target:** each entry gets an embedding and a tsvector at seed time (`scripts/seed_curated_knowledge.py`), is retrieved by relevance in both branches, fused with the document results, reranked by Cohere, and judged by the same coverage check. Identity is `(source_type, item_id)` so a curated id never collides with a chunk id. Permissions apply before its text reaches any model. The "first five" insertion is removed. Code: `rag_agent/infrastructure/curated_knowledge_repo.py`, `rag_agent/domain/curated_knowledge.py → curated_entry_to_hit`.
- **Lock 3 in SQL** [Planned] The page-access predicate (a join on `page_restriction` against the caller's principals) is added to both the dense and the keyword query, next to the source and scope predicates and before the `LIMIT 75`. The app-side check in stage 3 stays as a second check. Code: `retrieval/infrastructure/search_repo.py → dense_search, keyword_search`, `retrieval/domain/permission.py`.

#### What is ranked, where

| Step | Item today | Item in the target | Status |
|---|---|---|---|
| Dense search | child chunk rows, 75 | same | [Implemented] |
| Keyword search | child chunk rows, 75 | same | [Implemented] |
| Fusion (RRF) | page ids | child chunk ids | [Implemented, needs changing] |
| Page ACL | page ids, after fusion, in app | rows, inside both SQL searches, plus the app check | [Implemented, needs changing] |
| Rerank text | one child per page, `DISTINCT ON (page_id)` | the exact matching children, several per page | [Implemented, needs changing] |
| Rerank (Cohere) | one passage per page | child passages | [Implemented, needs changing] |
| Parent expansion | parents of the selected pages | parents of the selected children only | [Implemented, needs changing] |
| Coverage check | none | parent passages, after budget trimming | [Planned] |

#### The limits, and what each one means

| Limit | Value | Meaning | Status |
|---|---|---|---|
| Per search branch | 75 | child chunks returned by dense, and again by keyword, after locks 1 and 2 (and 3 in the target) | [Implemented] |
| Combined candidate pool | up to 150 | the union after fusion, fewer when both branches find the same chunks | [Implemented] |
| Rerank depth | 75 today; the whole pool in the target | how many candidates Cohere scores | [Decision needed] |
| Final passage count | undecided (top-k today comes from `rerank_top_k`) | how many children move on to parent expansion | [Decision needed] |
| Context token budget | undecided | the cap on parent text handed to the answer model | [Decision needed] |
| Rerank text length | 4000 characters | title plus the child's contextual text, cut | [Implemented] |
| Bounded extra retrieval | one extra round, undecided size | if fewer than k permitted children survive lock 3, fetch once more under the same auth context (the first of the two extra reads rule 7 allows) | [Planned] |
| Worst case per question | three searches, two rerank calls | first search, the thin-results refetch (stage 2), the weak-score fallback (stage 4); a latency budget for this path is set on the gold set | [Decision needed] |

Rerank depth, final passage count, and the context budget are set on the gold set. Until then the current values stand and are marked undecided.

#### Curated knowledge: entry point today and in the target

|  | Today | Target |
|---|---|---|
| When it enters | after the refusal decision, in the answer service | inside stage 2, in both search branches |
| How entries are chosen | first five active by id, tag match only | by relevance: embedding plus tsvector, same as chunks |
| Reranked | no | yes, by Cohere, same scale |
| Coverage check | no | yes, as ordinary evidence |
| Identity | integer id | `(source_type='curated', item_id)` |
| Permissions | tag match in app | RESTRICTIVE scope policy on the table, before any model sees text |

> **Acceptance checks for this stage.** (1) A page with setup in section 1 and troubleshooting in section 8: a troubleshooting question sends section 8 to Cohere, and both sections can survive fusion when both are relevant. (2) A question answerable only by curated entry 40 retrieves and cites entry 40; entries 1 to 5 are not injected. (3) Fill the top 75 with pages the person may not read and put the right permitted passage lower: the person still gets it, and no forbidden text reaches Cohere or Claude.

> **Today the answer can get lost between search and rerank.** [Implemented, needs changing] [Priority 1] Search finds a child in section 8 of a long page. Fusion turns that into a page id. The reranker is handed one "representative" child per page, chosen without regard to the match. If that is the overview in section 1, the reranker scores it low and drops the page. Fusing by chunk id fixes this and allows two sections of one page to both survive. This is the first change to ship, because it fixes a direct loss of correct evidence. It is finished only when the same chunk id is what the reranker scores (06.4) and what expands to a parent (06.5).

#### Panels that belong to this section (9)

_Workflow label shown in the drawer: Retrieval, stage 2 \u00b7 Search_

##### Panel `r2-embed` · Embed the question · [Implemented]
- Kind: Outside tool
- In plain words: Turns the question into the same kind of number code as the pages, with the same model.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Model | the same one used for pages (OpenAI text-embedding-3-large, 3072) |
  | Empty text | skipped; an image-only turn builds an empty result |
- Where in the code:
  - `retrieval/application/retriever.py:126` — the embed call
  - `rag_agent/application/answer_service.py:230-237` — the empty-turn path

##### Panel `r2-gucs` · Set the scope for this transaction · [Implemented]
- Kind: Step
- In plain words: Tells the database which sources and scopes this person may see. From here on the database hides everything else, inside the search itself.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Sources | SELECT set_config('app.allowed_sources', :s, true) |
  | Scopes | SELECT set_config('app.allowed_knowledge_scopes', :k, true) |
  | HNSW | SET LOCAL hnsw.ef_search = 100; hnsw.iterative_scan = 'relaxed_order' |
  | Why set_config | SET LOCAL cannot bind a parameter; interpolating would be an injection path |
- Where in the code:
  - `retrieval/infrastructure/search_repo.py:21-49` — apply_hnsw_gucs, apply_source_scope, apply_knowledge_scope
- Code:
```
session.execute(
  text("SELECT set_config('app.allowed_sources', :s, true)"),
  {"s": ",".join(ctx.allowed_sources)},
)
```

##### Panel `r2-dense` · Dense search · [Implemented]
- Kind: Step
- In plain words: Finds the 75 pieces whose number codes point the same way as the question: same meaning, maybe different words.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Distance | cosine, <=> |
  | Index | ix_chunk_embedding_hnsw over halfvec(3072) |
  | Filters | is_active AND kind = 1 AND page_status = current AND source_id = ANY(:sources) AND tags && :scopes |
  | Limit | candidate_k = 75 |
  | Order | distance, then page id |
- Where in the code:
  - `retrieval/infrastructure/search_repo.py:107-136` — dense_search
- Target and notes: iterative_scan = relaxed_order keeps recall up when the row policies prune many candidates. It needs pgvector 0.8 or newer.

##### Panel `r2-keyword` · Keyword search · [Implemented]
- Kind: Step
- In plain words: Finds the 75 pieces that share the most words with the question, which catches exact words like error codes.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Query | plainto_tsquery with AND rewritten to OR |
  | Rank | ts_rank(tsv, query) |
  | Index | ix_chunk_tsv_gin |
  | Filters | the same as dense |
  | Limit | 75 |
- Where in the code:
  - `retrieval/infrastructure/search_repo.py:76-100` — keyword_search

##### Panel `r2-rrf` · Reciprocal rank fusion, by chunk id · [Implemented, needs changing]
- Kind: Step
- In plain words: Merges the two lists into one, by piece. A piece high on both lists rises to the top.
- Today: Fuses two lists of page ids. Ties broken by keyword rank, then page id.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Formula | score = sum over lists of 1 / (60 + rank), 1-based |
  | Target unit | child chunk id |
  | Ties | keyword rank, then chunk id |
  | Output | an ordered list of candidates with provenance |
- Where in the code:
  - `retrieval/domain/fusion.py:14-28` — reciprocal_rank_fusion
  - `retrieval/application/retriever.py:158-162` — the call and tie-break
- Code:
```
def rrf(lists, k0=60):
    fused = defaultdict(float)
    for ranked in lists:
        for rank, chunk_id in enumerate(ranked, start=1):
            fused[chunk_id] += 1.0 / (k0 + rank)
    return sorted(fused, key=lambda c: -fused[c])
```
- How to test it:
  - A child at rank 10 in both lists (2/70 = 0.0286) beats a child at rank 1 in one list only (1/61 = 0.0164). Agreement between the two searches wins.
  - Fusing by chunk keeps two children of one page as two candidates.
- Target and notes: Priority 1 of the target changes, together with exact-child reranking: the passage search found is the passage the reranker scores and the answer model reads.

##### Panel `r2-prov` · Provenance on every candidate · [Planned]
- Kind: Data
- In plain words: Each found piece carries its ids and ranks with it, so later steps never look them up again.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Fields | source_type, item_id, parent_chunk_id, page_id, doc_version_id, keyword_rank, dense_rank, fused_score, later rerank_score |
  | Why | the reranker gets the right passage, the citation names the right version, the trace shows the whole path |
- Code:
```
@dataclass(frozen=True)
class Candidate:
    source_type: str          # 'chunk' or 'curated'
    item_id: int              # chunk id or curated entry id
    parent_chunk_id: int | None
    page_id: int | None
    doc_version_id: int | None
    keyword_rank: int | None
    dense_rank: int | None
    fused: float
    rerank: float | None = None
```
- Target and notes: Priority 1 of the target changes. Provenance is what lets the exact chunk survive from search to the answer model.

##### Panel `r2-curated` · Curated entries: found by relevance, in the same pool · [Implemented, needs changing]
- Kind: Step
- In plain words: Facts written by an admin are searched by relevance in the same pool and scored like any page piece.
- Today: fetch_curated_entries returns the first five active entries by id whose tags match, after the refusal decision, prepended as markers [1..k].
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Target | each entry has an embedding and a tsv; the same two searches run over the curated table and join the pool before fusion |
  | Identity | (source_type = curated, item_id); no synthetic page id, no negative chunk id |
  | Policy | the same RESTRICTIVE scope policy; state ok required |
- Where in the code:
  - `rag_agent/infrastructure/curated_knowledge_repo.py` — fetch_curated_entries (today: first five by id)
  - `rag_agent/domain/curated_knowledge.py` — curated_entry_to_hit
  - `retrieval/application/retriever.py` — candidate fusion
  - `scripts/seed_curated_knowledge.py` — embedding and tsvector at seed time
- How to test it:
  - A question answerable only from a curated entry: the entry is in the top-k and the answer cites it.
  - A curated entry unrelated to the question does not appear.
- Target and notes: Target: identity (source_type=curated, item_id); retrieved by relevance in both branches; fused, reranked, and coverage-checked like any chunk; the RESTRICTIVE scope policy applies before any model sees the text; the first-five insertion is removed.

##### Panel `r2-indexes` · The two search indexes · [Implemented]
- Kind: Data
- In plain words: Two shortcuts that make search fast: one for number codes, one for words.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | HNSW | (embedding::halfvec(3072)) halfvec_cosine_ops, m=16, ef_construction=200, WHERE is_active AND kind = 1 AND embedding IS NOT NULL |
  | GIN | tsv WHERE is_active AND kind = 1 |
  | Why halfvec | pgvector caps a plain vector HNSW index at 2000 dims |
- Where in the code:
  - `platform/db/models.py:63-84, 313-320` — index definitions

##### Panel `r2-aclsql` · Lock 3 inside the SQL searches · [Planned]
- Kind: Retrieval stage 2
- In plain words: Also applies Confluence page permissions inside the search itself, so pages this person may not read never take a spot in the 75.
- Today: The page-access check runs in the app after fusion (retrieval/domain/permission.py). Forbidden pages take up candidate slots and are dropped later.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Target predicate | NOT EXISTS restricted rows for the page, OR the caller's principal is among them |
  | Where | in dense_search and keyword_search, before LIMIT 75, next to the source and scope predicates |
  | Second wall | the app check in stage 3 stays |
  | Measure | filtered recall on the gold set under restrictive permissions; hnsw.iterative_scan stays on |
- Where in the code:
  - `retrieval/infrastructure/search_repo.py` — dense_search, keyword_search, permission predicates
  - `retrieval/domain/permission.py` — the existing rule, reused
- How to test it:
  - Fill the top 75 with pages the caller may not read and put the right permitted passage lower: it is returned, and no forbidden text reaches Cohere or Claude.
  - EXPLAIN on the dense query shows ix_chunk_embedding_hnsw.

---

## 06.3 · Retrieval, stage 3 · Filter: the three locks

_Section id: `rt3`_

**In plain words (the lede):** Three locks decide what a person may see. Two run inside the database itself, so a bug in the app cannot open them. The third checks Confluence page permissions per person. All three run before any text leaves the database for the scoring model.

**For leaders: three locks. Two are rules inside the database that hide rows before they come out. The third checks Confluence page permissions per person.**

| Field | Value |
|---|---|
| Inputs | the candidate list from stage 2; the authorization context; `page_restriction` rows for the candidate pages |
| Processing rules | lock 1: `chunk_source_read` policy on `source_id`; lock 2: RESTRICTIVE `chunk_scope_read` on `scope_state = 'ok' AND tags && allowed_scopes`; lock 3: drop candidates whose page has restriction rows that do not name the principal; groups expanded at sync time |
| Outputs | only permitted candidates, before any text leaves the database for the reranker |
| Failure behavior | a step forgets a GUC: zero rows; reader URL missing in production: startup fails; unexpandable group: the page fails closed |
| Code locations | `alembic/versions/0010_*.py` (scope policy), `retrieval/domain/permission.py`, `platform/db/roles.py` |
| Today | [Unverified] lock 1 live; lock 2 (migration 0010) coded and tested, not applied to Supabase; lock 3 runs in app after fusion |
| Target | [Planned] apply 0010 and run `verify-isolation`; empty tags never public; lock 3 also inside the SQL searches |

Diagram (The rag_reader role runs the search. Lock one is source row security. Lock two is scope row security. Lock three is the page access list. Then candidates go to rerank. An unset scope yields zero rows. Classified or conflicting pages are never served. Group restrictions are expanded at sync time.)
  - rag_reader — not the owner → panel `r3-reader`
  - Lock 1 · Source — RLS, default deny → panel `r3-source`
  - Lock 2 · Scope — RESTRICTIVE RLS → panel `r3-scope` (changes from today)
  - Lock 3 · Page ACL — per person, in app → panel `r3-acl`
  - To rerank — only permitted rows → panel `r3-torerank`
  - Scope unset? — zero rows, no leak → panel `r3-deny`
  - Not "ok"? — classified, conflict → panel `r3-classified` (changes from today)
  - Group members — expanded at sync → panel `r3-groups`

- **rag_reader** A login role that owns nothing, cannot bypass row security, and may only SELECT. The search transaction runs as this role. If the reader URL is missing outside a local environment, startup fails.
- **Lock 1 · Source** A row policy on `chunk`: `source_id` must be in the comma list held in `app.allowed_sources`. Unset means NULL means no match means zero rows. Separates whole source systems, for example Confluence from a future Zendesk.
- **Lock 2 · Scope** A second policy marked RESTRICTIVE, so Postgres ANDs it with lock 1. Target predicate: `scope_state = 'ok' AND tags && allowed_scopes`. All four platforms share one source id, so this lock is what keeps Mews and Toast apart. Same policy on `curated_knowledge_entry`.
- **Lock 3 · Page ACL** The space rule reads `space_id` from the authorization context: a candidate page outside that space is dropped before the principal check. **Today:** for the candidate pages only, load their restriction rows and drop pages the person may not read. Runs after fusion, before rerank. **Target:** the same rule also runs inside both SQL searches before the LIMIT (see stage 2), so forbidden pages never take up candidate slots. The app check stays as a second wall. A page with no rows is open to everyone in the source.
- **Scope unset?** The proof that a forgotten step leaks nothing: `string_to_array(NULL, ',')` matches no row. A negative test asserts a wrong source id returns zero.
- **Group members** Confluence restrictions can name a group. At sync time the group is expanded to account ids. A group we cannot expand gets a sentinel that no caller can match, so the page fails closed.

> **The empty-tags rule goes away.** [Implemented, needs changing] Today the scope policy says "no tags means visible to all". That was the floor for an untagged corpus. With label-gated ingestion every served page has a label, so the floor is a hole. The target requires `scope_state = 'ok'` and a real tag match. Global content carries `general`.

> **A tightly restricted person can end up with thin results.** [Implemented, needs changing] Today lock 3 runs after fusion on the 75 candidates. If most of them are restricted, fewer than the top-k survive, and the right permitted passage lower down is never seen. Target: (1) the page-access predicate runs inside both searches before the LIMIT; (2) the app check stays; (3) `hnsw.iterative_scan` stays on and filtered recall is measured on the gold set under restrictive permissions, because SQL filtering does not make HNSW visit only permitted rows and iterative scans have limits; (4) if fewer than k permitted children survive, one bounded extra retrieval runs under the same auth context, the first of the two extra reads rule 7 allows; (5) confirm with `EXPLAIN` that the dense query hits the `halfvec(3072)` index expression.

#### Panels that belong to this section (8)

_Workflow label shown in the drawer: Retrieval, stage 3 \u00b7 Filter_

##### Panel `r3-scope` · Scope row security · [Unverified]
- Kind: Lock 2
- In plain words: Lock 2: the database shows only pieces whose tag matches this person's integration (or general) and whose state is ok.
- Today: Migration 0010 adds chunk_scope_read and curated_knowledge_entry_scope_read as RESTRICTIVE policies: wildcard OR cardinality(tags) = 0 OR overlap. Coded and tested (502 tests), not applied to Supabase yet. The app predicate is flag-gated and off by default in code.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Target predicate | scope_state = 'ok' AND (wildcard OR tags && allowed_scopes) |
  | Removed | cardinality(tags) = 0 as a public floor |
  | RESTRICTIVE | Postgres ANDs it with the source policy; a permissive one would OR and weaken isolation |
  | Independent of the flag | the policy never reads enable_knowledge_scope_filtering |
- Where in the code:
  - `platform/db/schema.py` — the 0010 DDL
  - `alembic/versions/0010_customer_scope_rls.py` — migration
  - `retrieval/infrastructure/search_repo.py` — apply_knowledge_scope
- How to test it:
  - Flag off, cross-scope query: zero rows.
  - Two-label page: zero rows in every scope.
  - classified: zero rows even with the wildcard, because its chunks are deleted.

##### Panel `r3-acl` · Page-level access list · [Implemented]
- Kind: Lock 3
- In plain words: Lock 3: for each found page, checks Confluence's own permission list for this person and drops pages they may not read.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Data | page_restriction rows: any row means restricted to those principals; zero rows means open |
  | When | after fusion, before rerank, on the candidate pages only |
  | Rule | space scope: page must be in the space; principal: page open or principal listed; no principal: open pages only |
  | Fresh | rows loaded per request, never cached |
- Where in the code:
  - `retrieval/infrastructure/search_repo.py:187-212` — fetch_page_scopes
  - `retrieval/domain/permission.py:30-52` — classify_scope, allowed
  - `retrieval/application/retriever.py:167-176` — the filter
- How to test it:
  - A restricted page never reaches the reranker for a principal not on its list.
  - A group-restricted page is readable by the group's members after expansion.
- Target and notes: space_id comes from the authorization context. A candidate page outside that space is dropped here, before the principal check.

##### Panel `r3-reader` · rag_reader · [Implemented]
- Kind: Database role
- In plain words: The search runs as a limited database user that can only read and cannot switch the locks off.
- Today: Provisioned on Supabase. Logs in through the session pooler. Reads chunk under the source policy, and page_source, page_restriction, curated_knowledge_entry under 0009 reader policies. Has USAGE on the extensions schema for pgvector.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Attributes | LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS |
  | Grants | SELECT on the read tables, default privileges for new ones |
  | Engine | get_reader_engine(), bound to DATABASE_READER_URL |
  | Missing URL outside local | ReaderRoleMisconfiguredError at startup |
- Where in the code:
  - `platform/db/schema.py:78-102` — ensure_reader_role
  - `platform/db/engine.py:49-64` — get_reader_engine
  - `scripts/setup_supabase.py` — provision-reader, verify-isolation (exit codes per failing check)
- Target and notes: A fresh reader on Supabase still needs GRANT USAGE ON SCHEMA extensions and a search_path including extensions, run by hand, because the owner role there is not a superuser.

##### Panel `r3-source` · Source row security · [Implemented]
- Kind: Lock 1
- In plain words: Lock 1: the database shows only pieces from sources this person may see. Nothing allowed means nothing shown.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Policy | chunk_source_read FOR SELECT USING (source_id = ANY(string_to_array(current_setting('app.allowed_sources', true), ','))) |
  | Mode | ENABLE, NO FORCE: owner exempt by ownership, reader bound |
  | Default | unset GUC gives NULL gives no match gives zero rows |
  | Plus | an explicit WHERE source_id = ANY(:sources) for the planner and recall |
- Where in the code:
  - `platform/db/schema.py:52-68` — apply_chunk_rls
  - `retrieval/infrastructure/search_repo.py:38-49, 63` — GUC and predicate
- Code:
```
ALTER TABLE chunk ENABLE ROW LEVEL SECURITY;
ALTER TABLE chunk NO FORCE ROW LEVEL SECURITY;
CREATE POLICY chunk_source_read ON chunk FOR SELECT
  USING (source_id = ANY(string_to_array(current_setting('app.allowed_sources', true), ',')));
```
- How to test it:
  - No GUC: 0 rows. Real source: all rows. Bogus source: 0 rows. (verify-isolation runs exactly this.)

##### Panel `r3-torerank` · Only permitted candidates move on · [Implemented]
- Kind: Hand-off
- In plain words: Only pieces that passed all three locks move on to scoring.
- Steps:
  1. Up to rerank_depth (75) candidates, all three locks passed.
  2. Their text is fetched next, in the same transaction with the same scope.

##### Panel `r3-deny` · A forgotten scope leaks nothing · [Implemented]
- Kind: Fail closed
- In plain words: If a step forgets to set the scope, the database returns zero rows instead of leaking.
- Steps:
  1. A bug drops the set_config call.
  2. current_setting(..., true) returns NULL.
  3. string_to_array(NULL, ',') is NULL. ANY(NULL) matches nothing.
  4. Zero rows. The user gets a refusal, never another customer's page.
- How to test it:
  - test_rls_default_deny_on_reader_role, and verify-isolation on the live store.

##### Panel `r3-classified` · Conflict and classified are never served · [Planned]
- Kind: Fail closed
- In plain words: Pages marked classified or conflict are hidden by the database rule even if pieces remain.
- Today: Does not exist yet: scope_state (the enum, the columns, and every consumer) is entirely unbuilt.
- Steps:
  1. Ingestion stage 2 marks the state.
  2. Classified chunks are deleted outright.
  3. Conflict chunks stay stored but the policy hides them.
  4. Fixing the labels restores a conflict page without a rebuild.

##### Panel `r3-groups` · Groups expanded at sync time · [Implemented]
- Kind: Data
- In plain words: Confluence groups are turned into member lists ahead of time, so the permission check is fast and never guesses.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Endpoint | v1 group member list, per group, cached per sync run |
  | Cannot expand | sentinel principal that no caller can hold; the page fails closed |
  | Stored | one page_restriction row per (page, account id) |
- Where in the code:
  - `platform/clients/confluence_client.py` — _resolve_read_restriction, _fetch_group_members
- Target and notes: The live path for group expansion is still unverified against a real group-restricted page; none of the synced pages had one.

---

## 06.4 · Retrieval, stage 4 · Rerank and judge

_Section id: `rt4`_

**In plain words (the lede):** A scoring model reads the question next to each found piece and gives it a score. It reads the exact piece that matched, never a stand-in from the same page. If even the best score is weak, Obi searches once more with the person's own words and scores the combined list once. The best pieces go on to the answer stage. Still weak: Obi refuses instead of guessing.

**For leaders: a scoring model reads each found passage next to the question. If even the best one is weak we search once more with the person's own words, then decide whether anything is relevant at all.**

| Field | Value |
|---|---|
| Inputs | the permitted candidates; the rewritten question; the original question for the fallback |
| Processing rules | fetch rerank text by exact chunk id (title + contextual text, 4000 chars); Cohere rerank-v3.5 over the pool; top score below `refusal_min_rerank_score` (0.10, provisional) → one fallback search with the original words, union, dedupe by chunk id, rerank once; top-k children move on |
| Outputs | the top-k reranked children with scores on one scale; or a refusal (`no_candidates`, `weak_score`) |
| Failure behavior | Cohere error: retries on 408/409/429/5xx, then the request fails; CI uses an order-preserving fake reranker |
| Code locations | `retrieval/infrastructure/search_repo.py → fetch_rerank_texts`, `retrieval/application/rerank.py`, `rag_agent/application/answer_service.py → _apply_crag_retry` |
| Today | [Implemented, needs changing] rerank and fallback run; rerank text is one child per page; the fallback picks the higher-scoring run instead of reranking the union |
| Target | [Planned] [Priority 1] exact children reranked, fetched by the chunk id that search returned; union reranked once; threshold calibrated on the gold set; coverage check moved to stage 5 |

Diagram (Fetch the matching child passages, cross-encoder rerank, weak check. If weak, a fallback search on the original words, the union is reranked once. Strong: proceed to stage 5. Still weak: refuse.)
  - labels: yes; no, strong enough; still weak
  - Fetch passages — exact matching children → panel `r4-texts` (changes from today)
  - Cross-encoder — Cohere, child passages → panel `r4-rerank` (changes from today)
  - Weak? — top score below 0.10 → panel `r4-weak`
  - Fallback search — original words, once → panel `r4-fallback` (changes from today)
  - Rerank the union — one scale for all → panel `r4-union` (changes from today)
  - Top-k children — to stage 5 → panel `r4-proceed`
  - Refuse — weak_score, no_candidates → panel `r4-refuse`

_Dashed: still weak after the fallback, so refuse. This stage answers "is any passage relevant?". Whether the evidence is enough is decided in stage 5, after the final context is built. Curated entries are in the pool from stage 2 and are scored here like any other passage._

- **Fetch passages** [Priority 1] For each surviving candidate, the text the reranker reads: title plus the child's contextual text, cut at 4000 characters. Code: `retrieval/infrastructure/search_repo.py → fetch_rerank_texts`, fetched by exact chunk id in the target. Today it is one child per page picked without regard to the match. Target: the exact children that matched, several per page allowed.
- **Cross-encoder** Cohere rerank. 75 candidates in today; the whole fused pool (up to 150) in the target; final depth set on the gold set. Top-k out. A fake, order-preserving reranker runs in CI so tests stay deterministic. Retries on 408, 409, 429, and 5xx.
- **Weak?** The top reranked score against `refusal_min_rerank_score`. 0.10 is a provisional number set on a tiny fixture. It must be recalibrated on the eval set, and again whenever the reranker model changes.
- **Fallback search** Maybe the rewrite hurt. Run the search once more with the user's verbatim words, same scope, same limits. This is the second of the two extra reads rule 7 allows; the first is the thin-results refetch in stage 2. Never a loop.
- **Rerank the union** Merge both candidate sets, dedupe by chunk id, rerank once against one question. Today the code picks whichever run had the higher top score, and scores from two different queries are not on one scale.
- **Refuse** Reasons raised here: `no_candidates`, `weak_score`. Stage 5 raises `insufficient_coverage`, `no_citations` and `unsupported`. Each has its own copy and all offer a human hand-off. A refusal writes a `human_handoff` log line.

> **Relevant does not mean sufficient.** One passage can score 0.9 and answer one third of a three-part question. The reranker measures how related a passage is. It cannot tell whether the set of passages is enough. That is what the coverage check adds, and it is why partial answers exist as a distinct outcome.

> **Reranker upgrade is coupled to the threshold.** [Decision needed] Cohere rerank-v4.0 (pro and fast) shipped in December 2025 with a 32k context window. Moving from v3.5 changes the score distribution, so the 0.10 cut moves with it. Swap the model and retune the threshold in one change, both measured on the eval set.

#### Panels that belong to this section (7)

_Workflow label shown in the drawer: Retrieval, stage 4 \u00b7 Rerank and judge_

##### Panel `r4-texts` · Fetch the passages to rerank · [Implemented, needs changing]
- Kind: Step
- In plain words: Fetches the text of each found piece, the exact piece that matched, so the scorer reads the right passage.
- Today: fetch_rerank_texts: DISTINCT ON (page_id), left(title || ' ' || retrieval_content, 4000). One child per page, not necessarily the one that matched.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Target | for each candidate chunk id, title plus its retrieval_content, cut at 4000 chars |
  | Several per page | allowed; a question may need two sections |
  | Scope | same transaction, same GUCs, same ACL result |
- Where in the code:
  - `retrieval/infrastructure/search_repo.py:149-184` — fetch_rerank_texts
- How to test it:
  - A long page where only section 8 matches: the section 8 child is what the reranker receives.
- Target and notes: Priority 1 of the target changes. Today the answer can be found in section 8 and the reranker can receive section 1 of the same page. This fixes a direct loss of correct evidence.

##### Panel `r4-rerank` · Cohere cross-encoder rerank · [Implemented]
- Kind: Outside tool
- In plain words: A scoring model reads the question and each piece together and gives each piece a relevance score.
- Today: rerank-v3.5 via POST /v2/rerank. v4.0-pro and v4.0-fast exist (December 2025, 32k context); not adopted yet.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Input | the question and the candidates: 75 today; the whole fused pool (up to 150) in the target; final depth set on the gold set |
  | Output | top_k with a relevance score each |
  | Resilience | timeout, retry on 408, 409, 429 and 5xx with min(0.3 * 2^n, 4) s, breaker, 1000-doc abuse cap |
  | Offline | FakeReranker keeps input order, so CI is deterministic |
- Where in the code:
  - `platform/clients/reranker_client.py:74, 114-127` — CohereReranker
  - `retrieval/application/retriever.py:173-176` — the call
- Target and notes: A model swap changes the score distribution. Retune refusal_min_rerank_score in the same change, on the gold set.

##### Panel `r4-weak` · Is the best passage too weak? · [Implemented]
- Kind: Gate
- In plain words: Checks whether even the best piece scores low. If so, we do not trust the result yet.
- Today: refusal_min_rerank_score is 0.05, recalibrated 2026-09-12 from the earlier 0.10 provisional value.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Compare | top reranked score against refusal_min_rerank_score = 0.10 |
  | Provisional | set on a saturated 6-case fixture; recalibrate on the gold set |
  | Image turn | never refuses on weak score or no candidates; the image may answer |
- Where in the code:
  - `rag_agent/domain/refusal.py:41-58` — decide_refusal
  - `platform/config/settings.py:99` — the threshold

##### Panel `r4-fallback` · One bounded fallback search · [Implemented, needs changing]
- Kind: Step
- In plain words: Searches once more with the person's exact words, in case our rewrite hurt. Only once.
- Today: _apply_crag_retry: if the rewrite differs from the original and the first result was weak, search once more with the original words and keep whichever run had the higher top score.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Trigger | weak after the first rerank, and the rewrite changed the words |
  | Query | the user's verbatim last turn |
  | Scope | the same auth context |
  | Count | exactly one here (crag_max_retries = 1); with the stage 2 thin-results refetch that is at most two extra reads per question |
- Where in the code:
  - `rag_agent/application/answer_service.py:334-358` — _apply_crag_retry
- Target and notes: Rule 7: at most two extra reads per question, never a loop. The worst case is three searches and two rerank calls; its latency budget is set on the gold set (decision needed).

##### Panel `r4-union` · Rerank the union once · [Planned]
- Kind: Step
- In plain words: Merges both result sets and scores them again against one question, so all scores are on one scale.
- Today: The two result sets are not merged and reranked together; the code picks whichever run had the higher top score, though those scores come from different queries and are not on one scale.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Merge | candidates from both runs, dedupe by chunk id |
  | Rerank against | one intent-preserving question: the rewritten query, or the original if the rewrite failed |
  | Why | scores from two different queries are not on one scale; picking the higher top score can pick the worse evidence |
- How to test it:
  - A rewrite that hurts retrieval: the union still contains the right passage and it ranks first.

##### Panel `r4-proceed` · Top-k children move on to stage 5 · [Implemented]
- Kind: Hand-off
- In plain words: Enough relevant pieces. The best ones move on to the answer stage.
- Steps:
  1. The top-k passages, their scores, and the coverage verdict go to answer assembly.

##### Panel `r4-refuse` · Refuse and hand off · [Implemented, needs changing]
- Kind: Outcome
- In plain words: Says Obi cannot answer this and offers a human, with one of four clear reasons logged.
- Today: Four reasons: no_candidates, weak_score, no_citations, and off_topic (added 2026-09-12).
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Reasons today | no_candidates, weak_score, no_citations |
  | Target adds | insufficient_coverage |
  | Copy | one honest sentence per reason, each ending in the human hand-off line |
  | Log | refusal (reason, top score, threshold) and human_handoff (trace id, raw query, reason) |
  | Widget | red banner plus a contact link |
- Where in the code:
  - `rag_agent/domain/refusal.py:30` — RefusalReason
  - `rag_agent/application/answer_service.py` — _REFUSAL_COPY

---

## 06.5 · Retrieval, stage 5 · Answer

_Section id: `rt5`_

**In plain words (the lede):** The answer model reads the full sections around the matched pieces. Before it writes, Obi checks that the evidence covers every part of the question. The model then writes only from that evidence and numbers every claim. Two checks run before anything is sent: every sentence must point at a real source, and every source must in fact back its sentence. Only then is the answer sent to the chat window and logged.

**For leaders: the model writes an answer only from the passages we hand it, every sentence must point to a source, and we say so plainly when a part of the question is not in the documentation.**

| Field | Value |
|---|---|
| Inputs | the top-k children; the authorization context; the question parts from stage 1; the parent chunks |
| Processing rules | expand selected children to parents under the same auth context; dedupe and merge neighbors; trim to the context token budget keeping evidence per question part first; coverage check on the final context: rerank each parent against each question part (part as query), rule on the best score per part with an unsure band, one Haiku call for the unsure parts only → full / partial / refuse; numbered evidence block; Sonnet, 800 tokens, cached system prompt; valid citation-number checking cuts uncited sentences; batched support check before send: one judge call over every (sentence, cited passage) pair, unsupported sentences cut or marked unverified; replay the finished text over SSE; write `query_trace` |
| Outputs | a streamed answer with citation chips, or a partial answer naming the undocumented part, or a refusal with a human hand-off; one `query_trace` row |
| Failure behavior | generation error: the request fails (never an ungrounded fallback); no valid citation survives: refuse `no_citations`; no sentence survives the support check: refuse `unsupported`; support judge error: retry once, then refuse with `support_unavailable` (default; the alternative is send with every sentence marked unverified, decision needed); image analysis failure: the text answer still goes out |
| Code locations | `rag_agent/application/answer_service.py`, `rag_agent/domain/coverage.py` (proposed), `rag_agent/domain/prompt.py → build_evidence_block`, `rag_agent/domain/citations.py`, `rag_agent/domain/support.py` (proposed), `rag_agent/api/stream.py` |
| Today | [Implemented, needs changing] parents, generation, number check, replay, trace run; parent expansion opens a fresh session and restores the source GUC only; no coverage check |
| Target | [Planned] one auth context for parents; parents of the selected children only [Priority 1]; coverage check on the final context; partial answers; batched support check before send [Priority 2] |

Diagram (Expand children to parents, dedupe and trim to the token budget, coverage check on the final context, build the evidence block, generate, check citation numbers, then the batched support check, then replay the finished answer and write the trace. Nothing survived either check: refuse. Image analysis is separate and never cited.)
  - labels: all; some; none; kept; all cut
  - Expand parents — selected children only → panel `r5-parents` (changes from today)
  - Dedupe + budget — final context → panel `r5-dedupe` (changes from today)
  - Coverage check — on the final context → panel `r5-coverage` (changes from today)
  - Evidence block — [1] title, text → panel `r5-evidence`
  - Generate — Sonnet, 800 tokens → panel `r5-generate`
  - Check cite numbers — cut uncited sentences → panel `r5-enforce`
  - Partial answer — names the missing part → panel `r5-partial` (changes from today)
  - Refuse — insufficient_coverage → panel `r4-refuse`
  - Nothing survived — refuse: no_citations → panel `r5-nocite`
  - Support check — batched, before send → panel `r5-ground` (changes from today)
  - Image analysis — separate, never cited → panel `r5-image`
  - Feedback — thumbs on the trace → panel `r5-feedback`
  - Replay + trace — finished text, SSE → panel `r5-stream`

_Two checks run before anything is sent: the citation-number check, then the batched support check. Image analysis (a separate model call, never cited) and thumbs feedback join at the replay. Live token streaming is not built: the widget receives a replay of the finished, checked answer._

- **Expand parents** Join each child to its parent and read the parent's verbatim text. Target: inside the same authorization context as the search, both scope GUCs set, page ACL applied. Never a fresh session with looser rules.
- **Dedupe + budget** Two children from one parent give one parent. Neighboring parents that overlap are merged. The set is cut to the context token budget (undecided, set on the gold set), and evidence for each part of the question is kept first so trimming does not drop a whole part. Code: `rag_agent/application/answer_service.py`.
- **Coverage check** [Planned] Runs on the final context, after trimming. Stage 1 listed the question's parts (also for a multipart first turn). For each part: is there at least one passage in the final context that covers it? All: proceed. Some: partial answer that names the missing part. None: refuse with `insufficient_coverage`. The mapping: the same cross-encoder that reranked in stage 4 scores every passage in the final context against each question part, with the part as the query (one batched rerank call per part, at most four parts, at most eight parents). That gives `score(part, passage)`. Rule: a part is covered when its best score is at or above `coverage_min_score`; not covered when its best score is below `coverage_min_score` minus `coverage_unsure_band`; unsure in between. For the unsure parts only, one Claude call (Haiku) asks "does this passage state X?" over the (part, passage) pairs and returns yes or no per part. A single-part question skips the extra rerank: its part is the question and stage 4 already scored it. Provisional values: `coverage_min_score` equals the refusal threshold, `coverage_unsure_band` = 0.10; both calibrated on the gold set. Keyword overlap or embedding similarity alone never certifies a part: relevant and sufficient are different things. Code: `rag_agent/domain/coverage.py → decide_coverage` (proposed), `rag_agent/domain/prompt.py → build_evidence_block`.
- **Partial answer** The answer covers the documented parts and ends with one sentence naming the part that is not in the documentation, plus the human hand-off link.
- **Evidence block** Numbered blocks: `[1] Page title` then the parent text. Curated entries are numbered like any other block.
- **Generate** Sonnet with a cached system prompt: answer only from the numbered evidence, cite every factual claim. Errors here propagate. An ungrounded answer is worse than an error.
- **Check citation numbers** This is **valid citation-number checking**, and no more: split into sentences, keep a sentence only if it carries at least one marker that points at a real evidence block, strip invented markers. It does not check that the cited passage supports the sentence. That is the next box. If nothing survives, refuse with `no_citations`.
- **Support check (batched, before send)** [Priority 2] This is **semantic support verification**, separate from the number check above. Marker validity is not proof the passage backs the claim. Before the replay, one judge call reads every (sentence, cited passage) pair of the finished answer and returns one verdict per pair. Verdicts: **supported** when every factual claim in the sentence is stated in the cited passage; **partly supported** when at least one claim is stated and at least one is not; **not supported** when none is. Not supported: the sentence is cut. Partly supported: kept and marked unverified in the widget (default; cutting instead is a decision). Nothing left: refuse with `unsupported`. Judge: `claude-haiku-4-5`, a different model than the generator, with a cached system prompt (`SUPPORT_SYSTEM_PROMPT`) that receives the numbered passages once and the sentences with their markers, and returns one JSON verdict per sentence. Judge error: retry once, then refuse with `support_unavailable` (fail closed; the default until decided otherwise). Latency: provisional budget of 1.5 s at p95 for the call, measured on the gold set. The verdicts go on the trace row and the share of cut sentences feeds the dashboard. Cost: one extra model call per answer, measured on the gold set. The judge is a different model than the generator and is validated against human grades first. Code: `rag_agent/domain/support.py` (proposed).
- **Image analysis** A second, independent model call describes an attached image. Its output never enters citation enforcement and never carries a marker, so an image cannot forge a Confluence source. An image-bearing turn never refuses on a weak score.
- **Replay + trace** This is **completed-answer replay**, not live generation streaming. The finished, checked text is replayed in 40-character chunks every 15 ms. Events: start, token, citations, done. One `query_trace` row holds the query, the candidates, the scores, the allowed sources and scopes, the answer, and the citations.

#### What the answer model receives

One example. Question: "How do I set up the Toast integration, which permissions does it need, and how do I roll it back?" Stage 1 lists three parts: setup, permissions, rollback. After rerank, parent expansion, dedupe, and the budget cut, the final context is:

```
[1] Toast × QuickBooks: Setup guide › Connecting your Toast account
In Omniboost, open Integrations and choose Toast. Paste the Toast API key from
Toast Web › Integrations › API access. Click Connect. The first sync runs within
five minutes and imports the last 30 days of closed checks.

[2] Toast × QuickBooks: Setup guide › Required permissions
The Toast user that creates the API key needs the Restaurant Admin role. In
QuickBooks the connected user needs Company Admin so journal entries can post.

Company: Hotel Group Example · Integration: toast · Scopes: toast, general
```

The coverage check runs on exactly this text. Setup: covered by [1]. Permissions: covered by [2]. Rollback: no passage. Outcome: **partial answer**. The answer explains [1] and [2] with citations and ends with: "Rolling the integration back is not covered in the documentation. Here is how to reach a human." Had the check run before trimming, a rollback passage cut by the budget could have been counted as present.

#### Three things that are easy to overstate

| What we say | What it does | What it does not do | Status |
|---|---|---|---|
| Valid citation-number checking | cuts sentences whose markers point at no evidence block | does not verify the passage supports the sentence | [Implemented] |
| Semantic support verification | one batched judge call over every (sentence, cited passage) pair, before the answer is sent; unsupported sentences are cut, partly supported ones marked | does not catch a false claim that a passage appears to back; adds one model call of latency per answer | [Planned] [Priority 2] |
| Completed-answer replay | streams the finished, checked text in small pieces so the widget feels live | is not live generation streaming; first text appears when the whole answer is done | [Implemented] |
| Live generation streaming | would show model tokens as they are produced | needs per-sentence citation checking; not built, not planned for this cycle | [Decision needed] |

> **Acceptance check for this stage.** Ask for setup, permissions, and rollback. If the final context has no rollback passage, the answer says that rollback is not documented, cites the other two parts, and offers a human.

> **Why the stream is a replay, not live tokens.** Citation enforcement and the support check both run on the complete text. Streaming raw model tokens could show a sentence that is cut a second later. So the pipeline finishes first, then streams. True first-token streaming would need enforcement to run per sentence and is not built.

#### Panels that belong to this section (12)

_Workflow label shown in the drawer: Retrieval, stage 5 \u00b7 Answer_

##### Panel `r5-evidence` · The evidence block · [Implemented]
- Kind: Step
- In plain words: Numbers the big pieces [1], [2], [3] and hands them to the model with the company and integration.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Shape | [n] Page title, newline, parent text |
  | Numbering | 1-based position in the evidence list |
  | Curated | numbered like any other block |
- Where in the code:
  - `rag_agent/domain/prompt.py:161-167` — build_evidence_block

##### Panel `r5-parents` · Expand children to parents · [Implemented, needs changing]
- Kind: Step
- In plain words: Swaps each small piece for its big piece, because the big piece gives the model enough context to answer.
- Today: fetch_parent_texts opens a fresh reader session and re-applies the source GUC. Document 03 section 10 does not mention the knowledge-scope GUC there. Verify in retriever.py:242-250.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Query | chunk c JOIN chunk p ON p.id = c.parent_chunk_id, returning p.display_content keyed by child id |
  | Target | runs inside the same authorization context: both GUCs, page ACL result reused, same transaction or an identical one |
  | Rule | no step may read under looser rules than the search did |
- Where in the code:
  - `retrieval/application/retriever.py:242-250` — fetch_parent_texts
  - `retrieval/infrastructure/search_repo.py:215-232` — the join
- How to test it:
  - Set only the source GUC and request a parent of a tagged child: zero rows.
  - A permitted child yields its parent every time.

##### Panel `r5-dedupe` · Dedupe and trim to the token budget: the final context · [Planned]
- Kind: Step
- In plain words: Reads each big piece once, trims to the text budget, and keeps evidence for every part of the question first.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Same parent twice | one block |
  | Neighboring parents | merged in reading order when both are present |
  | Budget | a token cap on the evidence block; lowest-scoring parents drop first |
  | Order | by best child score |
- How to test it:
  - Two children of one parent produce one evidence block with one marker.
- Target and notes: Target: keep at least one passage per question part before trimming anything else, so the budget cut cannot delete a whole part. The coverage check then runs on what is left.

##### Panel `r5-coverage` · Coverage check on the final context · [Planned]
- Kind: Retrieval stage 5
- In plain words: Checks the final evidence against each part of the question. A part with no passage is named as undocumented instead of guessed.
- Today: Does not exist. One strong passage is treated as enough for any question.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Owner | stage 5, on the final context after parent expansion, dedupe and the token budget |
  | Mapping | the stage 4 cross-encoder scores every parent in the final context against each question part, with the part as the query: one batched rerank call per part (at most four parts, at most eight parents); score(part, passage) |
  | Rule | covered: best score for the part ≥ coverage_min_score; not covered: best score < coverage_min_score − coverage_unsure_band; unsure: in between |
  | Unsure | one Haiku call over the (part, passage) pairs of the unsure parts only; returns yes or no per part |
  | Single part | no extra rerank; the part is the question and stage 4 already scored it |
  | Provisional values | coverage_min_score = the refusal threshold; coverage_unsure_band = 0.10; both calibrated on the gold set |
  | Never | keyword overlap or embedding similarity alone; neither certifies a part |
  | All covered | proceed |
  | Some covered | partial answer that names the uncovered parts |
  | None covered | refuse with insufficient_coverage |
- Where in the code:
  - `rag_agent/domain/coverage.py` — decide_coverage (proposed)
  - `platform/clients/reranker_client.py` — the same Cohere client, part as query
  - `rag_agent/domain/prompt.py` — COVERAGE_JUDGE_SYSTEM_PROMPT (proposed)
  - `platform/config/settings.py` — coverage_min_score, coverage_unsure_band (proposed)
- Steps:
  1. Stage 1 listed the question's parts.
  2. Stage 5 expanded parents, deduped, and trimmed to the token budget. That is the final context.
  3. For each part (when there is more than one): rerank the parents with the part as the query.
  4. Apply the rule on the best score per part. Unsure parts go to one Haiku call.
  5. All parts: full answer. Some: partial answer naming the missing part. None: refuse with insufficient_coverage.
- Code:
```
def decide_coverage(parts, parents, rerank, judge, t, band):
    if len(parts) == 1:
        return "answer", []          # stage 4 already scored the question
    missing, unsure = [], []
    for part in parts:
        best = max(rerank(query=part, docs=parents))
        if best >= t: continue
        (unsure if best >= t - band else missing).append(part)
    if unsure:
        verdicts = judge(unsure, parents)   # one Haiku call, yes/no per part
        missing += [p for p in unsure if not verdicts[p]]
    if not missing: return "answer", []
    if len(missing) < len(parts): return "partial", missing
    return "refuse", parts
```
- How to test it:
  - Ask for setup, permissions, and rollback with no rollback passage in the final context: the answer says rollback is undocumented.
  - A question with familiar keywords but no answering passage: refused, not answered from similarity alone.
- Target and notes: Relevant and sufficient are different things. The reranker measures relevance of one passage. This check measures whether the set of passages is enough. One owner (stage 5), one method (rule, then one Claude call when unsure).

##### Panel `r5-generate` · Generate the answer · [Implemented]
- Kind: Outside tool
- In plain words: The model writes an answer from the numbered pieces only and marks each sentence with the number it used.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Model | claude-sonnet-5, max_tokens 800 |
  | System prompt | cached; answer only from the numbered evidence; cite every factual claim |
  | PII | redact_pii runs on the assembled prompt text |
  | Errors | propagate; no fail-open here |
- Where in the code:
  - `rag_agent/infrastructure/llm_client.py` — AnthropicAnswerGenerator.generate
  - `rag_agent/domain/prompt.py:37-78` — ANSWER_SYSTEM_PROMPT

##### Panel `r5-enforce` · Valid citation-number checking · [Implemented]
- Kind: Gate
- In plain words: Cuts any sentence whose number does not point to a real piece. It checks numbers, not meaning.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Split | into sentences |
  | Keep | a sentence only if it cites at least one valid marker |
  | Strip | invented markers from kept sentences |
  | Nothing left | refuse with no_citations |
  | Limit | checks marker validity, not that the passage supports the claim; see the groundedness sample |
- Where in the code:
  - `rag_agent/domain/citations.py:27-43` — enforce_citations
  - `rag_agent/application/answer_service.py:293-314` — the degrade path
- How to test it:
  - A generator that cites [9] with eight passages: the sentence is dropped.
  - A generator that drops all markers: refusal, not raw text.
- Target and notes: This checks that every marker points at a real evidence block. It does not check that the block supports the sentence. That is the batched support check, which runs next, before anything is sent.

##### Panel `r5-partial` · Partial answer · [Planned]
- Kind: Retrieval stage 5
- In plain words: Answers the parts that are documented and names the part that is not.
- Today: Does not exist; partial answers naming an uncovered part are not produced.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Says | answers the covered parts with citations, then states plainly which parts the sources do not cover |
  | Wire | Answer.partial = true, Answer.missing_parts = [...]; additive fields, no new SSE event |
  | Widget | a small amber note under the answer |
- How to test it:
  - The generated text never claims the missing part; forbidden-claim checks in the gold set catch it.

##### Panel `r5-nocite` · Refuse: nothing survived the checks · [Implemented]
- Kind: Fail path
- In plain words: Every sentence lost its source, or none of them was backed by its source. Obi refuses instead of showing an unsupported answer.
- Today: Only no_citations exists today; unsupported is not a defined RefusalReason and no support-check module exists yet.
- Steps:
  1. The model wrote something, but no sentence cited a valid marker, or no sentence survived the support check.
  2. Refuse with no_citations or unsupported. The user sees the honest copy and a hand-off link.

##### Panel `r5-ground` · Semantic support verification (batched, before send) · [Planned]
- Kind: Check
- In plain words: Before the answer is sent, a judge model reads each sentence next to the source it cites. A sentence its source does not support is cut, or kept with a note that it is unverified.
- Today: Does not exist. A sentence passes today when its citation number points at a real evidence block, even when that block says something else.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | What | every (sentence, cited passage) pair of the finished answer, judged in one batched call |
  | When | after the citation-number check and before the replay; on the hot path by design |
  | Verdicts | supported: every factual claim in the sentence is stated in the cited passage; partly: at least one claim stated and at least one not; not supported: none |
  | Not supported | the sentence is cut |
  | Partly supported | kept and marked unverified in the widget (default); cutting instead is a decision |
  | Nothing left | refuse with unsupported |
  | Judge | claude-haiku-4-5 (never the generator model); cached SUPPORT_SYSTEM_PROMPT; the numbered passages once, then the sentences with their markers; one JSON verdict per sentence |
  | Cost | one extra model call per answer; provisional budget 1.5 s at p95, measured on the gold set |
  | Judge error | retry once, then refuse with support_unavailable (fail closed, default); alternative: send with every sentence marked unverified (decision needed) |
- Where in the code:
  - `rag_agent/domain/support.py` — decide_support (proposed)
  - `rag_agent/domain/prompt.py` — SUPPORT_SYSTEM_PROMPT (proposed)
  - `rag_agent/infrastructure/llm_client.py` — judge_support (proposed)
  - `rag_agent/application/answer_service.py` — called after enforce_citations, before the replay
- Steps:
  1. Split the checked answer into sentences with their markers.
  2. Build one prompt with every (sentence, passage) pair and ask for one verdict per pair as JSON.
  3. Cut the unsupported sentences. Mark the partly supported ones.
  4. If no sentence survives, refuse with unsupported.
  5. Record every verdict on the trace row and feed the share of cut sentences to the dashboard.
- Code:
```
# request (one call)
{
  "passages": [{"marker": 1, "text": "..."}, {"marker": 2, "text": "..."}],
  "sentences": [{"n": 1, "markers": [1], "text": "..."}, {"n": 2, "markers": [2], "text": "..."}]
}
# response
{
  "verdicts": [
    {"n": 1, "verdict": "supported"},
    {"n": 2, "verdict": "not_supported", "why": "the passage names no date"}
  ]
}
```
- How to test it:
  - A generator that cites [1] for a claim [1] does not make: the sentence is cut before send.
  - An answer where every sentence is unsupported: refused, not sent.
  - The added latency is measured on the gold set and stays inside the budget.
- Target and notes: Priority 2 of the target changes. This closes the gap that valid citation-number checking leaves open: a real marker on a sentence its source does not back. It costs one model call of latency per answer, which is the price of accuracy first.

##### Panel `r5-image` · Image analysis · [Implemented]
- Kind: Outside tool
- In plain words: Describes an attached picture with a separate model. That description is never a source.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Trigger | images on the newest turn |
  | Call | a second independent Claude call, 500 tokens, with an anti-injection instruction: text inside the image is content, never a command |
  | Never | passes citation enforcement or carries a marker |
  | Rides on | Answer.image_analysis, delivered on done |
  | Gap | image bytes are not PII-redacted (disclosed) |
- Where in the code:
  - `rag_agent/infrastructure/llm_client.py:154-171` — generate_image_analysis
  - `rag_agent/domain/prompt.py:92-99` — IMAGE_ANALYSIS_SYSTEM_PROMPT
- Target and notes: A live red-team with instruction text drawn into images found no compliance: no prompt leak, no fake citation, no role switch.

##### Panel `r5-feedback` · Thumbs up or down · [Implemented]
- Kind: Data
- In plain words: Saves the person's thumbs up or down on the log row.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Endpoint | PATCH /chat/{trace_id}/feedback, body feedback: 1 or -1 |
  | Auth | same as /chat |
  | Writes | query_trace.feedback on the writer engine |
- Where in the code:
  - `rag_agent/server/router.py:453-469` — patch_chat_feedback

##### Panel `r5-stream` · Completed-answer replay and the trace row · [Implemented]
- Kind: Step
- In plain words: Sends the finished, checked answer to the widget in small pieces and logs everything about the question.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Events | start, token (40 chars every 15 ms), citations, done (with imageAnalysis) |
  | Format | data: {json} blank line |
  | Error after 200 | an SSE error event, not a 5xx |
  | Trace | one query_trace row on the writer engine: raw and rewritten query, candidates, scores, allowed sources and scopes, latency, answer, citations |
- Where in the code:
  - `rag_agent/server/router.py:334-425` — _stream_answer
  - `retrieval/application/retriever.py:193-215` — _trace
  - `retrieval/infrastructure/trace_repo.py` — write, update_answer, update_feedback
- Target and notes: Not live generation streaming. The whole answer is finished and checked first, then replayed in 40-character pieces. First text appears when the whole answer is ready. Live streaming would need per-sentence citation checking and is not built.

---

## 07 · The widget

_Section id: `widget`_

**In plain words (the lede):** The widget is the chat window a person sees. It sits inside a platform's pages today, and inside an iframe in the target (section 03.2). It knows which integration it lives in and holds the person's token in memory. It sends each question through its own small server route, which adds the secret key. It then shows the answer with its citations, or a clear refusal.

Diagram (Launcher and teaser, panel, composer, scope from embed config, access token, proxy route. A screenshot button feeds the composer. The proxy response is rendered as bubbles with citations. Six locales for the UI copy.)
  - Launcher + teaser — closed state → panel `w-launcher`
  - Panel — header, thread, input → panel `w-panel`
  - Composer — text, images, paste → panel `w-composer`
  - Scope — set once per embed → panel `w-scope`
  - User token — from the auth host → panel `w-token` (changes from today)
  - Proxy route — streams bytes back → panel `w-proxy`
  - Six locales — UI copy only → panel `w-i18n`
  - Screenshot — html-to-image → panel `w-screenshot`
  - Render — tokens, cites, chips → panel `w-render`

- **Launcher + teaser** A button in the corner. A nudge card appears after 3 seconds, and again 20 seconds after each close. Opening the panel is the only way into the conversation.
- **Panel** A fixed overlay on the right, full height. Header with menus, the message thread over a decorative contour background, the composer at the bottom.
- **Composer** Text, file attachments, clipboard paste, and the header's screenshot button all feed one attachment pipeline. Images are base64 on the newest turn only.
- **Scope** The embed config says which platform this widget sits in. That becomes `knowledgeScope` on every request. A dev-only switcher exists behind an env flag for testing.
- **User token** Today: a shared invite token per pilot, read from the URL and kept in session storage. Target: the host backend issues a signed token per user. The host page hands it to the Obi iframe by `postMessage`. The iframe keeps it in memory and the proxy forwards it. The backend derives company, integration and identity from it. Design: section 03.2.
- **Proxy route** Adds the server key, forwards the body as-is, streams the SSE bytes back without buffering. Body size capped at 30 MB (four 5 MB images in base64 plus text).
- **Render** Streamed tokens, citation chips with links, a red refusal banner with a human hand-off link, an indigo clarifying banner with option chips, and a labeled "looked at your image" block.
- **Six locales** Greeting, chips, placeholder, and labels are translated. The answer language is whatever the model returns.

> **Embedding on third-party domains: answered by the iframe design.** [Decision needed] Today the proxy and the browser are assumed to share an origin, and the pilot token travels in the URL. Section 03.2 loads the widget in an iframe on the Obi origin, so the proxy and the browser share an origin again. The only cross-origin channel is `postMessage`, checked on both sides. Still to decide: the permitted host domains for the CSP `frame-ancestors` list and the `postMessage` allow-list.

#### Panels that belong to this section (9)

_Workflow label shown in the drawer: The widget_

##### Panel `w-launcher` · Launcher and teaser · [Implemented]
- Kind: UI
- In plain words: The corner button and the small nudge card that appears after a few seconds.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Teaser timing | 3 s after load, again 20 s after each close or dismiss |
  | Panel | opens from the launcher or the teaser |
- Where in the code:
  - `apps/web/src/features/chat/ui/chat-launcher.tsx, teaser-popup.tsx, use-widget-visibility.ts` — the closed state

##### Panel `w-panel` · The panel · [Implemented]
- Kind: UI
- In plain words: The chat window: header, messages, and the typing box.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Layout | fixed overlay, right edge, full height, clamp(360px, 29%, 440px) wide |
  | Parts | panel-header, contour-background, message-list, composer |
  | State | one ChatSessionProvider mounted once in layout.tsx |
- Where in the code:
  - `apps/web/src/features/chat/ui/panel-body.tsx, panel-header.tsx, floating-frame.tsx` — the open state
  - `apps/web/src/features/chat/ui/chat-session-provider.tsx` — messages, pending, locale, knowledgeScope

##### Panel `w-composer` · The composer · [Implemented]
- Kind: UI
- In plain words: Where the person types, pastes, or attaches a picture.
- Today: ≤ 3 images per turn, each ≤ 3 MB; over either limit the composer shows a user-facing error and does not attach, and the backend rejects an over-limit request with a 400 the proxy forwards (decision w-composer-images).
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Inputs | text, file picker, clipboard paste, the header's screenshot button |
  | Images | base64 on the newest turn only, never stored; target ≤ 3 per turn, each ≤ 3 MB; over the limit shows a user-facing error (compress the image). Today (needs change, decision w-composer-images 2026-09-18): 4 per turn, no byte-size check |
  | Empty text plus image | allowed; the backend skips search and still analyzes the image |
  | Disclosure | we do not check images for personal info; skip sensitive screenshots |
- Where in the code:
  - `apps/web/src/features/chat/ui/composer.tsx, attachment-strip.tsx, image-lightbox.tsx` — input and previews

##### Panel `w-scope` · Which platform is this widget in? · [Implemented, needs changing]
- Kind: Config
- In plain words: The widget knows which integration it lives in, and that becomes its scope on every question.
- Today: The live /embed frame never sets a knowledgeScope prop; the dev-only scope switcher is the only client-side way scope is chosen today. The token, not this prop, will decide scope in the target.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Set | once, by the embedding page, as the knowledgeScope prop |
  | Sent | on every request as knowledgeScope |
  | Dev switcher | behind NEXT_PUBLIC_SHOW_SCOPE_SWITCHER = true; never rendered in real embeds |
  | Target | the token carries the integration; a known slug that disagrees with it is ignored and logged; an unknown slug is a 400 |
- Where in the code:
  - `apps/web/src/features/chat/ui/scope-menu.tsx` — the dev switcher
  - `apps/web/src/features/chat/model/knowledge-scopes.ts` — generated from knowledge_scopes.json at build time

##### Panel `w-token` · The user token · [Implemented]
- Kind: Auth
- In plain words: The card that says who the person is. Today a shared pilot token; in the target a signed card per person.
- Today: The host issues a per-user JWT (iss, aud, sub, iat, exp, company_id, company_name, integration) delivered to the iframe by postMessage and held in memory — live-proven for test hosts (commit 59385f4); the ?access_token= pilot path is retired.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Target | a JWT per user from the host backend, delivered to the iframe by postMessage, held in memory, forwarded by the proxy as a bearer header |
  | Carries | iss, aud, sub, iat, exp, company_id, company_name, integration |
  | Never in | a URL, a cookie or web storage; the pilot's ?access_token= path is retired |
  | Cross-origin | the iframe runs on the Obi origin; the only cross-origin channel is postMessage with origin and source checks (section 03.2) |
- Where in the code:
  - `apps/web/src/features/chat/api/access-token.ts` — capture and persist (today)
  - `apps/web/src/features/chat/server/auth.ts` — constant-time compare (today)
- Target and notes: The full contract and the handshake are in section 03.2.

##### Panel `w-proxy` · The proxy route · [Implemented]
- Kind: Server
- In plain words: The widget's own server route that adds the secret key and streams the answer back.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Path | /api/chat and /api/chat/{traceId}/feedback |
  | Adds | the server key from the Next.js server environment; never exposed to the browser |
  | Checks | structural shape only; the backend owns the business caps and its 400 is forwarded as-is |
  | Streams | a byte passthrough, no buffering |
- Where in the code:
  - `apps/web/src/features/chat/server/route-handlers.ts` — handlePostChat, handlePatchFeedback
  - `apps/web/src/app/api/chat/route.ts` — thin entry

##### Panel `w-i18n` · Six locales · [Implemented]
- Kind: UI
- In plain words: Buttons and labels in six languages. The answer is in whatever language the model writes.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Covers | greeting, suggestion chips, placeholder, footer, teaser, menus, banners |
  | Does not cover | the answer text; the model decides that |
- Where in the code:
  - `apps/web/src/features/chat/model/i18n.ts` — the copy table

##### Panel `w-screenshot` · Screenshot of the page behind the widget · [Implemented]
- Kind: Tool
- In plain words: Takes a picture of the page behind the widget and attaches it to the question.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Library | html-to-image |
  | Hides | the widget itself during capture (data-obi-widget-root) |
  | Then | lands in the attachment strip like any image |

##### Panel `w-render` · Rendering the answer · [Implemented]
- Kind: UI
- In plain words: Draws the answer: streamed text, citation chips, a red refusal banner, or a clarifying question with options.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Tokens | appended as they stream |
  | Citations | chips with a link; no URL renders as a span marked unavailable |
  | Refusal | red banner, hand-off email link, feedback thumbs |
  | Clarifying | indigo banner and option chips that send the option as the next turn |
  | Image | a labeled block: looked at your image |
  | Partial (target) | an amber note listing the uncovered parts |
- Where in the code:
  - `apps/web/src/features/chat/ui/message-bubble.tsx, message-list.tsx` — per-turn rendering
  - `apps/web/src/features/chat/api/chat-client.ts` — SSE parsing on blank-line boundaries

---

## 08 · The data, from A to Z

_Section id: `dataz`_

**In plain words (the lede):** One Postgres database holds everything. It is two things at once. As a relational database it has eleven tables for pages, versions, pieces, the job queue and the audit trail. As a vector database it stores one vector per child piece and finds the closest ones to a question fast. This chapter follows one page through both sides.

#### One page, from Confluence to a search hit

1. **A webhook lands.** One row in `event_ledger`. One row in `job`.
2. **The page gets an identity.** One row in `page_source` (Confluence facts, tags, scope state, the pointer to the live version). One row in `document` (the stable id that survives every rebuild).
3. **A build gets a row.** One `document_version` per build, with every hash and pipeline stamp. Never edited after it is written.
4. **The text becomes rows.** Parent and child rows in `chunk`, all linked. Each child row holds its verbatim text, its context text, its tags, its `scope_state`.
5. **The child gets a vector.** The `embedding` column on the same `chunk` row. 3072 floats from OpenAI. This is the vector database part.
6. **The child gets a keyword index.** The `tsv` column, Postgres full text. Same row.
7. **Two indexes make it fast.** HNSW over `embedding` for nearest vectors. GIN over `tsv` for words. Both only cover active children.
8. **Who may read it.** `page_restriction` rows when Confluence restricts the page. Row security policies on `chunk` itself for source and scope.
9. **A question arrives.** The reader searches HNSW and GIN inside one transaction. Row security hides rows the caller may not see before they are ever returned.
10. **The question is logged.** One row in `query_trace`: question, candidates, scores, scopes, answer, citations.

> **Why the vector database is inside Postgres and not next to it.** The vector and the tags and the row security live on the same row. A separate vector store would need the isolation rules built a second time, and a page swap would have to happen in two systems at once. With pgvector the swap is one transaction and the lock is one policy.

---

## 08.1 · The relational database: the eleven tables

_Section id: `data`_

**In plain words (the lede):** This is the table side of Postgres. A page has one document row. A document has many versions and a version is never edited after it is written. A version owns its pieces. The other tables run the queue, the sweeps, the audit trail and curated knowledge.

Diagram (Event ledger feeds job. Page source has one document, which has many document versions, each owning chunks. Page source points at its active version. Page restriction hangs off page source. Reconciliation run, source scope, query trace and curated knowledge entry stand alone.)
  - labels: active_doc_version_id; no hard link into the corpus graph
  - event_ledger — one row per delivery → panel `d-event_ledger`
  - job — the crash-safe queue → panel `d-job` (changes from today)
  - page_source — one row per page → panel `d-page_source` (changes from today)
  - document — stable identity → panel `d-document`
  - document_version — immutable build → panel `d-document_version` (changes from today)
  - chunk — parents and children → panel `d-chunk` (changes from today)
  - reconciliation_run — one row per sweep → panel `d-reconciliation_run`
  - source_scope — retires as sync input → panel `d-source_scope` (changes from today)
  - page_restriction — who may read a page → panel `d-page_restriction`
  - query_trace — one row per question → panel `d-query_trace` (changes from today)
  - curated_knowledge_entry — admin-written facts → panel `d-curated` (changes from today)

_The loop on chunk is parent_chunk_id: a child points at its parent in the same table. Dashed boxes gain or change columns in the target._

#### Columns that change in the target

| Table | Add or change | Why |
|---|---|---|
| page_source | + `scope_state` (ok, conflict, classified, unlabeled); + `index_fingerprint` | explicit quarantine; one identity for a build |
| chunk | + `scope_state`; tags never empty on served rows; the `stable_key` reuse column stops being read | the scope lock reads state; every rebuild embeds the whole page |
| document_version | + `index_fingerprint`; uniqueness becomes (document_id, index_fingerprint) | an attachment-only or title-only change may build a new version |
| job | partial unique index on (page_id) WHERE status = 'pending' | coalesce waiting work without dropping a new revision |
| curated_knowledge_entry | + `embedding`, + `tsv`, + `scope_state` | curated facts compete on relevance instead of arriving by id |
| query_trace | + `token_subject` (hashed), + `candidate_chunk_ids`, + `decision` (answer, partial, refuse reason) | audit the whole judge step, not just the top hits |
| source_scope | retired: no longer read by the sweeps or the stamp step | tags from `knowledge_scopes.json` are the only membership control |

#### The indexes that make search fast

| Index | Type | Over | Only where |
|---|---|---|---|
| ix_chunk_embedding_hnsw | HNSW, m=16, ef_construction=200 | embedding cast to halfvec(3072), cosine | active children with a vector |
| ix_chunk_tsv_gin | GIN | tsv | active children |
| ix_chunk_tags_gin | GIN | tags (array overlap) | active rows |
| ix_chunk_active_source / _space | btree | (is_active, source_id) and (is_active, space_id) | active rows |
| ux_document_version_one_active | partial unique | document_id | state = active |
| ix_job_claim | partial btree | (status, available_at, priority) | pending or failed |

> **Why Postgres and not a separate vector database.** The corpus is small and will stay far below the point where pgvector struggles (tens of millions of vectors). Postgres gives us row security, transactions, and immutable versions in one place. A separate vector store would make us rebuild the isolation boundary there too. If a real scale target ever lands, that is a new decision with its own ADR, not a quiet swap.

#### The target migration (0011), written out

One migration carries every schema change on this page. Apply 0010 live first. Run the backfill, then the readiness gate, before the new policy is trusted. [Planned]

```
-- 0011_target_schema (one migration, one downgrade)

-- 1. scope_state on chunk and page_source
CREATE TYPE scope_state AS ENUM ('ok','conflict','classified','unlabeled');
ALTER TABLE chunk        ADD COLUMN scope_state scope_state NOT NULL DEFAULT 'unlabeled';
ALTER TABLE page_source  ADD COLUMN scope_state scope_state NOT NULL DEFAULT 'unlabeled';

-- 2. index_fingerprint: the identity of a build
ALTER TABLE page_source      ADD COLUMN index_fingerprint text;
ALTER TABLE document_version ADD COLUMN index_fingerprint text;
ALTER TABLE document_version DROP CONSTRAINT uq_document_version_idem;
ALTER TABLE document_version ADD CONSTRAINT uq_document_version_fingerprint
  UNIQUE (document_id, index_fingerprint);
-- ux_document_version_one_active (one active per document) stays as it is

-- 3. one pending sync_page job per page
CREATE UNIQUE INDEX ux_job_pending_sync_page
  ON job (page_id) WHERE status = 'pending' AND job_type = 'sync_page';

-- 4. curated entries searched like chunks
ALTER TABLE curated_knowledge_entry ADD COLUMN embedding vector(3072);
ALTER TABLE curated_knowledge_entry ADD COLUMN tsv tsvector;
ALTER TABLE curated_knowledge_entry ADD COLUMN scope_state scope_state NOT NULL DEFAULT 'ok';
CREATE INDEX ix_curated_embedding_hnsw ON curated_knowledge_entry
  USING hnsw ((embedding::halfvec(3072)) halfvec_cosine_ops)
  WITH (m = 16, ef_construction = 200) WHERE is_active AND embedding IS NOT NULL;
CREATE INDEX ix_curated_tsv_gin ON curated_knowledge_entry USING gin (tsv) WHERE is_active;

-- 5. the scope policy: state ok and a real tag match, no empty-tags floor
DROP POLICY IF EXISTS chunk_scope_read ON chunk;
CREATE POLICY chunk_scope_read ON chunk AS RESTRICTIVE FOR SELECT
  USING (scope_state = 'ok' AND (
    current_setting('app.allowed_knowledge_scopes', true) = '*'
    OR tags && string_to_array(current_setting('app.allowed_knowledge_scopes', true), ',')));
DROP POLICY IF EXISTS curated_knowledge_entry_scope_read ON curated_knowledge_entry;
CREATE POLICY curated_knowledge_entry_scope_read ON curated_knowledge_entry AS RESTRICTIVE FOR SELECT
  USING (scope_state = 'ok' AND (
    current_setting('app.allowed_knowledge_scopes', true) = '*'
    OR tags && string_to_array(current_setting('app.allowed_knowledge_scopes', true), ',')));

-- 6. trace: what the target adds
ALTER TABLE query_trace ADD COLUMN token_subject_hash text;
ALTER TABLE query_trace ADD COLUMN candidate_chunk_ids integer[];
ALTER TABLE query_trace ADD COLUMN decision text;

-- backfill before the policy is trusted: every active chunk with a recognized tag -> 'ok';
-- verify_knowledge_scope_backfill.py must report zero rows in any other state.
```

> **If filtered search ever loses recall, climb this ladder in order.** Raise `ef_search`. Partition `chunk` by source or customer. Quantize. Only then consider `pgvectorscale`, which is not available on Supabase. Climb only against a measured loss on the eval set.

#### Panels that belong to this section (11)

_Workflow label shown in the drawer: The relational database_

##### Panel `d-event_ledger` · event_ledger · [Implemented]
- Kind: Table
- In plain words: One row per doorbell ring from Confluence, used to ignore repeats.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | One row per | webhook or sweep delivery |
  | Unique | payload_hash; delivery_id (partial, when not null) |
  | Columns | event_type, page_id, cf_version, space_id, actor, origin (0 webhook, 1 recon, 2 manual), proc_status, self_generated, payload JSONB |
  | Status enum | received, deduped, queued, processing, done, dead_letter |
- Where in the code:
  - `platform/db/models.py:345-387` — EventLedger

##### Panel `d-job` · job · [Implemented, needs changing]
- Kind: Table
- In plain words: The workers' to-do list: one row per job with a status and a lease.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | One row per | unit of background work |
  | Unique | idempotency_key |
  | Target | plus a partial unique index on (page_id) WHERE status = pending for sync_page |
  | Columns | job_type, status, priority, available_at, attempts, max_attempts (5), lease_owner, lease_expires_at, last_error, source_event_id |
  | Indexes | ix_job_claim (pending, failed), ix_job_lease (leased, running) |
- Where in the code:
  - `platform/db/models.py:390-441` — Job
  - `platform/jobs/queue.py` — all operations

##### Panel `d-page_source` · page_source · [Implemented, needs changing]
- Kind: Table
- In plain words: One row per Confluence page: its facts, tags, state, and a pointer to the live version.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | One row per | Confluence page; the primary key is the Confluence page id |
  | Pointer | active_doc_version_id, UNIQUE, deferrable FK to document_version |
  | Hashes | content, structure, attachment_manifest, access_scope, labels; target: index_fingerprint |
  | Scoping | source_type, source_id, tags; target: scope_state |
  | Stamps | parser, chunker, contextualization, embedding model and dim, retrieval schema |
  | Status enum | current, draft, trashed, archived, deleted |
- Where in the code:
  - `platform/db/models.py:95-158` — PageSource

##### Panel `d-document` · document · [Implemented]
- Kind: Table
- In plain words: One row per page that never changes: the permanent name tag.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | One row per | page |
  | page_id | UNIQUE, deferrable FK to page_source |
  | Purpose | the stable id every version hangs off |
- Where in the code:
  - `platform/db/models.py:180-194` — Document

##### Panel `d-document_version` · document_version · [Implemented, needs changing]
- Kind: Table
- In plain words: One row per build of a page, written once and never edited, with every hash it was built with.
- Today: Migration 0012 already widened the uniqueness constraint to a 7-column key; the 'today' and 'target' unique-key rows below no longer match the live schema.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | One row per | immutable build of a page |
  | State enum | staging, active, superseded, failed |
  | Unique today | (document_id, cf_version, retrieval_schema_version, embedding_model) |
  | Unique target | (document_id, index_fingerprint); DDL in the 0011 migration (08.1) |
  | One active | partial unique index on document_id WHERE state = active |
  | Records | every pipeline stamp, built_by_job_id, activated_at, superseded_at |
- Where in the code:
  - `platform/db/models.py:197-241` — DocumentVersion

##### Panel `d-chunk` · chunk · [Implemented, needs changing]
- Kind: Table
- In plain words: The pieces: big parents and small children in one table. Children carry the meaning code and the word index.
- Today: scope_state does not exist yet; chunk carries only the columns listed below.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | One row per | parent section (kind 0) or child window (kind 1) |
  | Links | doc_version_id (cascade), parent_chunk_id (self), prev and next |
  | Text | display_content (verbatim, for citations), retrieval_content (contextual, embedded) |
  | Search | embedding halfvec(3072) and tsv, children only |
  | Hot-path copies | is_active, space_id, page_status, source_id, tags, access_scope, embedding_model, retrieval_schema_version |
  | Target adds | scope_state |
  | Unique | (doc_version_id, stable_key) |
- Where in the code:
  - `platform/db/models.py:244-342` — Chunk
- Target and notes: Target: + scope_state. The stable_key reuse column stops being read. embedding_input_hash is not added.

##### Panel `d-reconciliation_run` · reconciliation_run · [Implemented]
- Kind: Table
- In plain words: One row per daily sweep: when it ran and what it found.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | One row per | sweep |
  | Columns | scope (all or space:KEY), kind (lightweight, complete, label), status, pages_scanned, drift_detected, jobs_enqueued, orphans_deleted, errors, report JSONB |
- Where in the code:
  - `platform/db/models.py:444-468` — ReconciliationRun

##### Panel `d-source_scope` · source_scope · [Decision needed]
- Kind: Table
- In plain words: The old folder-root rule for which pages to sync. Retired; tags do this now.
- Today: Four active page roots with empty tags cover the four test pages. Nine old roots are inactive.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Was for | which spaces or page trees get synced, and tags to stamp on them |
  | Target | no longer read by the sweeps; labels are the only membership control |
  | Keep or drop | keep the table until label-gated ingestion is proven live, then drop it in a migration |
- Where in the code:
  - `platform/db/models.py:474-507` — SourceScope
  - `confluence_sync/domain/scope_resolver.py` — resolve_space_scope

##### Panel `d-page_restriction` · page_restriction · [Implemented]
- Kind: Table
- In plain words: Who may read a page, copied from Confluence. No rows means everyone in the source may read it.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | One row per | (page, allowed principal) |
  | Meaning | any row means restricted to the listed principals; zero rows means open |
  | Written by | confluence_sync when access_scope_hash changes, as delete plus insert |
  | Read by | fetch_page_scopes for the candidate pages only |
- Where in the code:
  - `platform/db/models.py:161-177` — PageRestriction

##### Panel `d-query_trace` · query_trace · [Implemented, needs changing]
- Kind: Table
- In plain words: One row per question: what was asked, what was found, the scores, the decision, and the answer.
- Today: subject_hash (token subject, hashed) already shipped via migration 0011; candidate_chunk_ids and decision remain target-only.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | One row per | question that reached retrieval |
  | Retrieval half | raw_query, retrieved_page_ids, retrieved_chunk_ids, rerank_scores, allowed_sources, allowed_knowledge_scopes, embedding_model, reranker_model, latency_ms |
  | Answer half | rewritten_query, answer, citations JSONB, feedback |
  | Target adds | token_subject (hashed), candidate_chunk_ids, decision |
  | Written as | the owner, so row security never blocks the insert |
- Where in the code:
  - `platform/db/models.py:510-545` — QueryTrace
  - `retrieval/infrastructure/trace_repo.py` — writers

##### Panel `d-curated` · curated_knowledge_entry · [Implemented, needs changing]
- Kind: Table
- In plain words: Facts written by an admin by hand, searched like any other piece.
- Today: Empty on the live store. Columns: tags, title, body, is_active. RESTRICTIVE scope policy in 0010 (not applied live); reader policy from 0009 live. No migration through 0012 adds embedding, tsv, or scope_state to this table.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Target adds | embedding vector(3072), tsv, scope_state, an HNSW index and a GIN index; DDL in the 0011 migration (08.1) |
  | Seeding | scripts/seed_curated_knowledge.py embeds at seed time |
  | Tags | general for facts every widget may use; a platform tag for the rest; empty is never public |
- Where in the code:
  - `platform/db/models.py:548-569` — CuratedKnowledgeEntry

---

## 08.2 · The vector database: pgvector inside Postgres

_Section id: `vector`_

**In plain words (the lede):** A vector is a list of 3072 numbers that describes what a piece of text means. Two texts with the same meaning get vectors that point the same way. Obi stores one vector per child piece and finds the closest ones to a question in milliseconds. The vector store is the pgvector extension on the same `chunk` table, so row security covers vectors too.

Diagram (Text goes to the embedding model, becomes a vector, is stored as halfvec on the chunk row, indexed by HNSW. A question follows the same path and HNSW returns the nearest chunks. Keyword search runs beside it.)
  - Child text — title + path + note + text → panel `vd-text`
  - Embedding model — OpenAI, 3072 numbers → panel `vd-model`
  - chunk.embedding — vector(3072) → panel `vd-column`
  - HNSW index — halfvec, cosine → panel `vd-hnsw`
  - Nearest 75 — active children only → panel `vd-nearest`
  - Row security — applies to vectors too → panel `vd-rls`
  - The question — same model → panel `vd-question`
  - Keyword side — tsvector + GIN → panel `vd-keyword`
  - Whole page swap — vectors in and out together → panel `vd-swap`

_The question and the page text go through the same model. If they did not, the numbers would not be comparable._

- **Child text** What gets embedded is the page title, the heading path, a short context note, and the child's own words. About 400 tokens.
- **Embedding model** OpenAI `text-embedding-3-large`, 3072 dimensions, set in the root `.env`. The code default says Voyage at 1024. Both paths exist. Pick one as the default so a fresh deploy builds the same index.
- **chunk.embedding** A `vector(3072)` column on the same row as the text, the tags, and the scope state. Parents have no vector. Only children are searched.
- **HNSW index** Hierarchical navigable small world. A graph that finds near vectors without comparing against every row. Built over `embedding::halfvec(3072)` because pgvector caps plain-vector indexes at 2000 dimensions. Cosine distance. `m=16`, `ef_construction=200`, `ef_search=100` at query time.
- **Nearest 75** The 75 active children closest to the question. Ties broken by page id. These go on to fusion with the keyword results.
- **Row security** The vector lives on the `chunk` row, so the source and scope policies filter it like any other column. A caller never receives a vector hit from a row they may not see.
- **Keyword side** A `tsvector` over title, heading path, and text, indexed with GIN. It catches exact words the vector search can miss, like an error code. Both run in the same transaction.
- **Whole page swap** Vectors belong to a `document_version`. When a rebuilt page goes live, all of its old vectors go inactive and all of its new vectors go active in one transaction. The HNSW index never serves a half-swapped page.

> **What "re-embed the whole page" means here.** Every child of the page gets a new vector from the model. Old vectors are not edited. They belong to the superseded version and stop being searched. Two old versions stay for rollback, then their rows are deleted and the HNSW entries go with them.

> **If the corpus ever grows past what pgvector handles well.** [Decision needed] Tens of millions of vectors is the rough line. Before that: raise `ef_search`, partition `chunk`, quantize. A separate vector store is a new decision with its own ADR, because the isolation model would have to be rebuilt there.

#### Panels that belong to this section (9)

_Workflow label shown in the drawer: The vector database_

##### Panel `vd-text` · The text that becomes a vector · [Implemented]
- Kind: Vector database
- In plain words: A small piece of the page plus its title and place in the page: the text that becomes numbers.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Input | page title + heading path + context note + child text |
  | Size | about 400 tokens |
  | Kept separately | the verbatim child text, for citations |

##### Panel `vd-model` · The embedding model · [Decision needed]
- Kind: Vector database
- In plain words: The model that turns text into 3072 numbers. Texts with the same meaning get similar numbers.
- Today: The root .env may override to OpenAI text-embedding-3-large at 3072 dims, but this cannot be verified from source (root .env is gitignored). Code default is Voyage voyage-3-large at 1024.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Batch | 128 children per call |
  | Failure | retry, backoff, circuit breaker |
  | Rule | the question uses the same model |
- Target and notes: Make the code default match the deployed setting, or run the bake-off on the gold set first.

##### Panel `vd-column` · chunk.embedding · [Implemented]
- Kind: Vector database
- In plain words: The 3072 numbers are stored on the piece's own row, next to its text and tags.
- Today: Column type is vector(3072); the code's embedding-model default is Voyage voyage-3-large at 1024 dims, so the deployed dimension depends on an unverifiable .env override.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Type | vector(3072), nullable |
  | Who has one | child chunks only |
  | Same row | text, tags, scope_state, tsv |

##### Panel `vd-hnsw` · The HNSW index · [Implemented]
- Kind: Vector database
- In plain words: A fast lookup map over all the number codes that finds the closest ones without checking every row.
- Today: Regression-tested: dedicated tests pin the index's name, its halfvec/cosine shape above the 2000-dim cap (vector_cosine_ops at or below it, disclosed), and its m=16/ef_construction=200 build params.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Name | ix_chunk_embedding_hnsw |
  | Over | embedding::halfvec(3072), cosine |
  | Build | m=16, ef_construction=200 |
  | Query | hnsw.ef_search=100, iterative_scan=relaxed_order |
  | Only where | is_active and embedding is not null |
- Target and notes: halfvec because pgvector indexes cap plain vectors at 2000 dimensions. Half precision costs almost no recall at this size.

##### Panel `vd-nearest` · The nearest 75 · [Implemented]
- Kind: Vector database
- In plain words: The 75 pieces whose numbers are closest to the question's numbers.
- Steps:
  1. ORDER BY embedding <=> :query_vector LIMIT 75.
  2. Row security filters first.
  3. Ties broken by page id.

##### Panel `vd-rls` · Row security covers vectors too · [Implemented]
- Kind: Vector database
- In plain words: The row locks apply to the numbers too, so a hidden row never comes out of a vector search.
- Today: Regression-tested: dedicated tests pin that embedding lives on chunk, that both the source and knowledge-scope SELECT policies are registered on chunk, and that a raw nearest-neighbor query as the reader never returns a row on a forbidden source even when it is the closest match.
- Steps:
  1. The vector sits on the chunk row.
  2. The source and scope policies apply to every SELECT on chunk.
  3. So a nearest-neighbor hit from a forbidden row is never returned.

##### Panel `vd-question` · The question vector · [Implemented]
- Kind: Vector database
- In plain words: The question is turned into numbers with the same model, so it can be compared with the pieces.
- Today: Code default is Voyage voyage-3-large at 1024 dims; whether a .env override makes the question vector 3072 dims is unverifiable from source.
- Steps:
  1. The rewritten question goes through the same embedding model.
  2. One vector, 3072 numbers.
  3. It is compared with the child vectors by cosine distance.

##### Panel `vd-keyword` · The keyword side · [Implemented]
- Kind: Vector database
- In plain words: Next to the numbers, each piece has a word index that finds exact words the numbers might miss.
- Today: The keyword-search tsv column, its GIN index and the OR-joined/ts_rank query are each pinned by a dedicated panel-id-named regression test.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Column | tsv = to_tsvector('english', title // heading path // text) |
  | Index | ix_chunk_tsv_gin |
  | Query | OR-joined words, ranked by ts_rank |
- Target and notes: Not a vector, but it lives next to one and runs in the same transaction. It catches exact strings like an error code.

##### Panel `vd-swap` · Vectors swap with the page · [Implemented]
- Kind: Vector database
- In plain words: When a page is rebuilt, all its old numbers go off and all its new numbers go on in one switch.
- Steps:
  1. New chunks and their vectors are inserted inactive.
  2. One transaction flips the version pointer.
  3. Old vectors go inactive and leave the HNSW result set at once. Rows are deleted after two more versions.

---

## 09 · Security, from A to Z: the escalation from edge to row

_Section id: `security`_

**In plain words (the lede):** Security is a set of locks, not a single stage. Each lock sits at one point on the road from the outside world to a single database row. This chapter reads the locks in order. Ingestion runs as the table owner and writes every row. Retrieval runs as a limited role that cannot switch any lock off.

#### The escalation, step by step

1. **Ingestion, the webhook.** HMAC signature, rate limit, size cap. Unsigned or oversized: dropped before parsing. Our own writes: dropped, no loop.
2. **Ingestion, the page.** Only published pages arrive. Only pages with a tag from `knowledge_scopes.json` are built. `classified`, or no tag: the page is deactivated. Read restrictions are copied to `page_restriction` rows; a failed fetch stores "nobody".
3. **The store, the roles.** The writer owns the tables and never serves reads. `rag_reader` can SELECT and nothing else, and cannot bypass row security. Supabase's public roles are held back by row security alone, so it stays on for every table.
4. **Retrieval, lock 0, the edge.** Server key per widget host. Signed user token per person from the host backend or an agreed auth service, handed to the Obi iframe by `postMessage`. Company, integration and identity come from the token, never the body. Design: section 03.2. [Planned]
5. **Retrieval, lock 1, source.** Row security: a chunk is visible only if its `source_id` is in the transaction's allowed sources. Not set: zero rows.
6. **Retrieval, lock 2, scope.** A RESTRICTIVE policy, ANDed with lock 1: `scope_state = 'ok' AND tags && allowed_scopes`. This is what keeps Mews and Toast apart. Same policy on curated entries. [Unverified] coded in migration 0010, not applied to Supabase
7. **Retrieval, lock 3, page.** The candidate pages' restriction rows are checked against the person. Filtered before the reranker sees any text.
8. **Retrieval, the answer.** Every sentence must cite a numbered source. Uncited sentences are cut in code. A passage cannot change the scope by saying so.
9. **The audit trail.** One `query_trace` row per question with the scopes that applied, the candidates, and the decision. One `event_ledger` row per webhook delivery.

#### The four retrieval locks

Diagram (Lock 0 at the edge, lock 1 source row security, lock 2 scope row security, lock 3 page access list, then permitted rows. Below: the writer role is exempt, the reader is policy bound, Supabase's anon role is denied, classified is never served, and query_trace keeps the audit trail.)
  - Lock 0 · Edge — host key + user token → panel `s-edge` (changes from today)
  - Lock 1 · Source — Postgres RLS → panel `s-source`
  - Lock 2 · Scope — RESTRICTIVE RLS → panel `s-scope` (changes from today)
  - Lock 3 · Page — restriction rows → panel `s-acl`
  - Permitted rows — what the model reads → panel `s-permitted`
  - Writer — owner, exempt → panel `s-writer`
  - rag_reader — policy bound → panel `s-reader`
  - Supabase anon — public role, denied → panel `s-anon`
  - classified — never in the index → panel `s-classified` (changes from today)
  - Audit trail — who saw what → panel `s-audit`

- **Lock 0 · Edge** The proxy holds a server key per widget host. The host backend (or an agreed auth service) signs a token per user with their company, integration and identity. The iframe holds it in memory and the proxy forwards it. The backend verifies both and builds the auth context. Nothing in the body can widen it. Design: section 03.2.
- **Lock 1 · Source** `chunk_source_read`: a row is visible only if its `source_id` is in the transaction's `app.allowed_sources`. Unset means zero rows. This is what would separate Confluence from a second source.
- **Lock 2 · Scope** `chunk_scope_read`, RESTRICTIVE, ANDed with lock 1. Target predicate: `scope_state = 'ok' AND tags && allowed_scopes`. The same policy on curated entries. The eval role may set the scope to `*`; the public path never does.
- **Lock 3 · Page** Confluence read restrictions, persisted as principal rows, applied to the candidate pages before rerank. Groups are expanded to members at sync time.
- **Writer** Owns the tables. Exempt from row security by ownership because the tables are `NO FORCE`. Needs no superuser, which is why the same design runs on Supabase.
- **rag_reader** `NOSUPERUSER NOBYPASSRLS`, SELECT only. Every search transaction runs as this role. On Supabase it also needs USAGE on the `extensions` schema for pgvector.
- **Supabase anon** Supabase's public REST roles hold SELECT on every table. Row security is the only thing keeping the corpus private from the public internet. Never disable it on any table.
- **classified** A page with this label is deactivated and its chunks deleted. As a second wall, the scope policy hides any row whose state is not `ok`. Belt and suspenders.

#### What happens when a lock is missing

| Situation | Result | Why |
|---|---|---|
| A step forgets to set `app.allowed_sources` | zero rows | `source_id = ANY(NULL)` is never true |
| A step forgets to set `app.allowed_knowledge_scopes` | zero tagged rows | RESTRICTIVE policy fails closed |
| The app-layer tag filter flag is off | still isolated once 0010 is applied; on Supabase today the app predicate is the only scope filter, so the flag must stay on | the database policy does not read the flag, and it is not live yet |
| A page has two provider labels | hidden everywhere | `scope_state = conflict` |
| A request sends another user's principal | ignored | principal comes from the verified token |
| The reader URL is empty in production | startup fails | `ReaderRoleMisconfiguredError` |
| A retrieved passage contains "ignore your rules" | no effect on scope | the scope never comes from text; citations are enforced in code |

> **On dropping row security from curated knowledge.** [Decision needed] You said you lean toward no RLS on `curated_knowledge_entry`. On Supabase the public `anon` role can SELECT that table. Disable RLS and every curated fact becomes readable from the public REST URL with no login. The PLAN records this as a "never do" for good reason. If the goal is "curated facts are visible in every scope", tag them `general` and keep the policy. Same result, no public exposure.

> **Not a full multi-tenant story yet.** These locks close the data layer. The edge binding (lock 0) is the part that ties a real person to a platform, and it is not built. Until it lands, the backend trusts the scope the proxy hands it. Land lock 0 before any public deploy. Its design is section 03.2.

#### Panels that belong to this section (10)

_Workflow label shown in the drawer: Security_

##### Panel `s-writer` · The writer (table owner) · [Implemented]
- Kind: Role
- In plain words: The account that writes rows. It owns the tables, so the locks do not apply to it, and it never answers questions.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Who | the owner role: local rag, Supabase postgres |
  | Exempt because | the tables are NO FORCE ROW LEVEL SECURITY and the owner is exempt by ownership |
  | Needs | no SUPERUSER, no BYPASSRLS; this is what makes the design run on managed Postgres |
  | Used by | worker, webhook, sweeps, ingestion, trace and feedback writes |
- Where in the code:
  - `platform/db/schema.py:52-68` — apply_chunk_rls
  - `docs/adr/0013` — the decision

##### Panel `s-reader` · rag_reader · [Implemented]
- Kind: Role
- In plain words: The account that answers questions. It can only read, and the locks always apply.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Who | HybridRetriever's transactions, curated fetch, parent fetch |
  | Cannot | bypass policies, write, create |
  | Verify | scripts/setup_supabase.py verify-isolation: owner count, reader no-GUC 0, scoped count, bogus 0, halfvec resolves, non-chunk reads, anon denied, scope axis |

##### Panel `s-edge` · The edge · [Implemented]
- Kind: Lock 0
- In plain words: Lock 0, the front door: check the widget's key and the person's signed card before anything else.
- Today: One server key per deployment (CHAT_API_KEY, with rotation overlap), plus a per-user RS256 JWT verified before any search; per-user identity now reaches the backend — live-proven for test hosts (commit 59385f4).
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Host key | per widget host, server to server, never in the browser |
  | User token | signed by the trusted issuer (host backend or agreed auth service): iss, aud, sub, iat, exp, company_id, company_name, integration; reaches the iframe by postMessage only |
  | Rate limit key | the token subject; request.client.host on the pre-token path. No X-Forwarded-For parsing today (TRUSTED_PROXY_HOPS=0, set in 7.1.1) — see decision r1-limits-ipkey |
  | Network | the backend stays private to the proxy; only the proxy holds the host key |
- Where in the code:
  - `rag_agent/server/router.py:254-267` — _verify_api_key
  - `apps/web/src/features/chat/server/auth.ts` — the proxy check today
- How to test it:
  - Forged token: 401.
  - Token for integration A, body scope B: scoped to A.
  - Two different subjects behind one IP do not share a rate bucket.
  - A postMessage from an origin off the allow-list never becomes a token.
- Target and notes: The full design of lock 0 is section 03.2.

##### Panel `s-source` · Source row security · [Implemented]
- Kind: Lock 1
- In plain words: Lock 1: the database shows only pieces from sources this person may see.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | ADR | 0004, 0013 |
  | Fails | closed |
  | Separates | whole source systems by source_id |
- Target and notes: See retrieval stage 3 for the DDL and the default-deny proof.

##### Panel `s-scope` · Scope row security · [Unverified]
- Kind: Lock 2
- In plain words: Lock 2: the database shows only pieces whose tag matches this person's integration.
- Today: Migration 0010 is coded and tested but not applied to Supabase; the app predicate defaults to off in code.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | ADR | 0011, 0014 |
  | Fails | closed for tagged rows; target: closed for every row not in state ok |
  | Separates | platforms that share one source id |
  | Applies to | chunk and curated_knowledge_entry |

##### Panel `s-acl` · Page access list · [Implemented]
- Kind: Lock 3
- In plain words: Lock 3: Confluence page permissions, checked per person.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | ADR | 0005 |
  | Fails | closed: no principal means open pages only; an unexpandable group means nobody |
  | Runs | before rerank, in the app, on candidates |

##### Panel `s-permitted` · The permitted rows · [Implemented]
- Kind: Data
- In plain words: What is left after all locks. Only this reaches the scoring model and the answer model.
- Steps:
  1. Only rows that passed all locks are turned into text.
  2. Only that text reaches the reranker and the generator.
  3. The trace records which sources and scopes were allowed.

##### Panel `s-anon` · Supabase's public roles · [Implemented]
- Kind: Role
- In plain words: Supabase's public account. Row security is the only thing keeping it out, so it is never turned off.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Roles | anon and authenticated |
  | Hold | GRANT SELECT on every table, granted by Supabase |
  | Blocked by | row security with no matching policy |
  | Verified | verify-isolation asserts anon sees zero rows |
- Target and notes: Never DISABLE ROW LEVEL SECURITY on any table, and never run the 0009 downgrade, on Supabase. Either exposes the corpus through the public REST URL.

##### Panel `s-classified` · classified is never served · [Planned]
- Kind: Rule
- In plain words: Pages tagged classified are deleted from the index, and the scope lock hides them a second time.
- Today: Does not exist yet: scope_state is unbuilt, so nothing below enforces this rule today.
- Steps:
  1. The label sets state = classified in ingestion stage 2.
  2. The page is deactivated and its chunk rows deleted.
  3. The scope policy hides any row not in state ok.
  4. The readiness gate reports zero rows in any state but ok before the policy ships.
- How to test it:
  - A classified page: zero rows for every scope, every token, and the eval wildcard.

##### Panel `s-audit` · The audit trail · [Implemented]
- Kind: Data
- In plain words: The logs that show who asked what and what they were allowed to see.
- Today: subject_hash (the token subject, hashed) already shipped via migration 0011 and is written per query; decision stays target-only.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Per query | allowed_sources, allowed_knowledge_scopes, candidates, scores, answer, citations, feedback; target: token subject and decision |
  | Per refusal | a human_handoff log line with trace id, raw query, reason |
  | Per sync | a reconciliation_run row and structured log lines (webhook_event, knowledge_scope_conflict) |
  | Secrets | never logged; the audit line for /chat carries ids and counts, not the message |

---

## 10 · Evaluation: how we know it works

_Section id: `eval`_

**In plain words (the lede):** An evaluation set is a list of real questions with checked right answers. Obi is scored against it after every change. Each stage of retrieval gets its own score, so a failure points at the stage that caused it. Every threshold and every model swap is measured here before it ships. Today this set does not exist.

Diagram (Gold set, split into dev and held-out. Four stages are scored: before rerank, after rerank, context assembly, generation. Below: latency and cost, freshness telemetry, and an LLM judge that assists stage four.)
  - Gold set — 150 to 250 cases → panel `e-gold` (changes from today)
  - Dev / held-out — tune on one only → panel `e-split`
  - Before rerank — did search find it? → panel `e-stage1`
  - After rerank — still near the top? → panel `e-stage2`
  - Context assembly — did the model get it? → panel `e-stage3`
  - Generation — correct and cited → panel `e-stage4`
  - Latency + cost — per stage, per query → panel `e-ops`
  - Freshness checks — index age, recall → panel `e-monitor` (changes from today)
  - LLM judge — a different model → panel `e-judge`

- **Gold set** Questions with reviewed expected evidence and outcomes. Exact error codes, questions phrased unlike the docs, follow-ups, platform-specific and general questions, multi-passage questions, attachment-only and curated-only answers, unanswerable questions, and permission-denied questions.
- **Dev / held-out** Tune thresholds and prompts on the dev half. Report on the held-out half. Never tune against held-out, or the numbers stop meaning anything.
- **Before rerank** Did either search branch return every required passage? Recall at k. If this fails, no prompt change will help.
- **After rerank** Did the required passages stay in the top-k? Precision at 5 and NDCG at 10. This is where the rerank-lift measurement lives.
- **Context assembly** After parent expansion and the budget cut, did the generator receive all the needed evidence?
- **Generation** Was the answer correct, complete, and supported by its citations? Did it refuse when it should have? Did it avoid every forbidden claim?
- **LLM judge** A judge model can grade groundedness and correctness at scale. Use a different model than the generator. Run each judgment two or three times. Validate against human-graded cases before trusting it.
- **Freshness telemetry** Ongoing: how old is the newest index build per page, and does held-out recall hold under scope filters? This catches the silent failures: a corpus that stops covering the questions, or a filter that starves recall.

#### Evidence table: measured, proposed, unverified

| Claim | Kind | Value | Test set | Deployment tested | Permissions | Notes |
|---|---|---|---|---|---|---|
| End-to-end latency p50 5.9 s, p95 7.4 s | Measured | 6 queries, in-process | synthetic fixture, 14 docs | laptop, local Postgres | scope filter off | latency = complete answer ready, not first text; first text is the same moment because streaming is a replay |
| Retrieval recall | Measured | directional only | synthetic fixture | laptop | off | a handful of queries; not a basis for any threshold |
| Refusal threshold 0.10 | Unverified | provisional | tiny fixture | laptop | off | must be recalibrated on the gold set |
| Filtered recall under restrictive permissions | Unverified | not measured | none | none | n/a | needed before trusting HNSW iterative scan under lock 3 |
| Isolation: wrong source id returns zero rows | Measured | pass | negative test in CI | local Postgres | lock 1 only | lock 2 test exists in CI; not run against Supabase |
| Gold set of 150 to 250 cases | Proposed target | 0 today | none | none | n/a | the shared unblocker |
| Recall at 75 per branch ≥ 0.95 on dev | Proposed target | undecided | gold set | Supabase | on | set the number after the first full run |
| Freshness: a change shows within N minutes | Proposed target | N undecided | n/a | AWS deploy | n/a | webhook path: minutes; sweep: a day |

#### One case in the gold set

| Field | Purpose |
|---|---|
| question + history | the input, including prior turns for follow-ups |
| user identity + scopes | which evidence is allowed to exist for this case |
| expected outcome | answer, partial answer, clarify, or refuse (and which reason) |
| required passages | chunk ids that retrieval must find |
| essential facts | what the answer must contain, wording free |
| forbidden claims | what the answer must not say |
| corpus version | the index fingerprints at grading time, for reproducibility |

> **The gold set is the shared unblocker.** [Planned] It calibrates the refusal threshold, decides the reranker upgrade, decides the embedder bake-off, and validates the coverage check. Today `make eval` scores a 14-document synthetic fixture with a handful of queries. Any winner it picks is directional at best.

#### Panels that belong to this section (9)

_Workflow label shown in the drawer: Evaluation_

##### Panel `e-gold` · The gold set · [Planned]
- Kind: Dataset
- In plain words: 150 to 250 real questions with checked right answers: the ruler we measure Obi with.
- Today: Does not exist. Current datasets: retrieval_smoke, permission, ambiguity, out_of_corpus over a 6-page fixture (list_pages() returns 6 ids), a few cases each.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Size | 150 to 250 reviewed cases to start |
  | Must include | exact error codes, questions phrased unlike the docs, follow-ups, platform-specific and general, multi-passage, attachment-only, curated-only, unanswerable, permission-denied |
  | Fields | question and history, identity and scopes, expected outcome, required passages, essential facts, forbidden claims, corpus version |
  | Where | features/evaluation/datasets/, reviewed by a human before use |
- Where in the code:
  - `features/evaluation/datasets/` — JSON cases
  - `features/evaluation/schemas.py` — EvalKind: retrieval, answer, ambiguity, permission, latency

##### Panel `e-split` · Dev and held-out · [Planned]
- Kind: Rule
- In plain words: Half the questions tune the system, the other half give the final score. Never mixed.
- Steps:
  1. Split the cases once, by hand, into two halves.
  2. Tune prompts, thresholds and k on dev.
  3. Report on held-out. Never tune against it.
  4. When held-out is spent (you have looked at it too often), write new cases.

##### Panel `e-stage1` · Before rerank: did search find it? · [Planned]
- Kind: Metric
- In plain words: Did search find the right pieces at all? If not, nothing later can fix it.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Measures | recall at 75 across the fused candidate list; per branch too |
  | If it fails | fix chunking, embeddings, or the keyword query; a prompt change cannot help |
- Where in the code:
  - `features/evaluation/metrics/` — recall, precision, ndcg helpers exist

##### Panel `e-stage2` · After rerank: still near the top? · [Planned]
- Kind: Metric
- In plain words: After scoring, are the right pieces still near the top?
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Measures | precision at 5, NDCG at 10, and the rerank lift (before versus after) |
  | Also | the score distribution, which sets the refusal threshold |
  | If it fails | reranker model, rerank text, or depth |
- Where in the code:
  - `features/evaluation/rerank_lift.py` — evaluate_rerank_lift

##### Panel `e-stage3` · Context assembly: did the model get it? · [Planned]
- Kind: Metric
- In plain words: Did the answer model receive the right pieces after the budget cut?
- Today: Does not exist; no coverage check runs after the budget cut.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Measures | whether every required passage is inside the evidence block after parent expansion, dedupe and the budget cut |
  | If it fails | k, the token budget, or the dedupe rule |

##### Panel `e-stage4` · Generation: correct, complete, cited · [Planned]
- Kind: Metric
- In plain words: Was the answer right, complete, and cited, and did it refuse when it should?
- Today: Does not exist; generation is not yet scored for correctness, citation support or refusal as a distinct eval stage.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Measures | essential facts present, forbidden claims absent, every claim supported by its citation, refusal when expected, partial when expected |
  | Graded by | humans first, then a validated judge model |
  | If it fails | the prompt, the model, or the coverage rule |

##### Panel `e-ops` · Latency and cost · [Planned]
- Kind: Metric
- In plain words: How long each step takes and what it costs, per question.
- Today: A bounded in-process run measured p50 5.9 s and p95 7.4 s end to end on six queries, about 0.23 dollars per run. First-token time was not measured; the SSE path is a replay.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Targets on file | TTFT equals end to end by design (replay). Target: end to end p50 and p95 set on the gold set; p95 under 10 s stays as the ceiling. A TTFT target exists only when live streaming is built. Decision needed. |
  | Measure | per stage: embed, search, rerank, generate; per query cost from token counts |
  | Through | the real /chat SSE path, against the Supabase reader, with scope filtering on |
- Where in the code:
  - `features/evaluation/metrics/latency_metrics.py` — helpers, unwired

##### Panel `e-monitor` · Freshness and recall telemetry · [Planned]
- Kind: Monitor
- In plain words: Ongoing checks in production: how fresh the index is and whether search still finds what it should.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Index age | time since the newest active version per page, against the freshness target |
  | Held-out recall | a small fixed set of questions run daily under each scope; alert on a drop |
  | Groundedness | the support check verdicts from retrieval stage 5, tracked over time: the share of sentences cut or marked unverified; alert on a rise |
  | Why | the common 2026 failure is silent: a corpus that stops covering the questions, or a filter that starves recall |

##### Panel `e-judge` · An LLM as judge · [Planned]
- Kind: Tool
- In plain words: A different model grades answers at scale, checked against human grades first.
- Settings and rules:
  | Setting | Value |
  |---|---|
  | Use for | groundedness and correctness at scale |
  | Rules | a different model than the generator; two or three runs per judgment to see variance; validate against human grades before trusting |
  | Never | let machine-generated test cases in without a human review |

---

## 11 · Open before building

_Section id: `open`_

**In plain words (the lede):** These are the decisions the code cannot make. Each one blocks a part of the target above. Pick them in the order they appear. The embedding decisions from section 03.2 and the folder rename from section 01.2 are listed here too.

- **Curated knowledge and row security.** [Decision needed] You lean toward dropping RLS on that table. On Supabase that exposes it to the public REST role. Recommended: keep the policy, tag shared facts `general`. See section 16.
- **The scope list.** [Decision needed] Confirm general, mews, toast, classified. Confirm whether opera-cloud stays. Confirm the rename from the `obi-*-test` names. You wrote "muse"; the PLAN records that as a dictation of Mews. Confirm.
- **The token issuer.** [Decision needed] Who signs the Obi token: the host backend or an auth service the two teams agree on. Which application hosts Obi first, and who the engineering contact is. The claims are fixed in section 03.2. Blocks lock 0.
- **Permitted host domains.** [Decision needed] The allow-list for CSP `frame-ancestors` and for `postMessage` origins on both sides. Section 03.2.
- **User identity for page permissions.** [Decision needed] Whether embedded users need per-person Confluence page permissions. If yes, the trusted mapping from the token's `sub` to a Confluence principal. Without it: open pages only. Section 03.2.
- **Token lifetime.** [Decision needed] 5 to 15 minutes. Shorter is safer. Longer means fewer refreshes. Section 03.2.
- **Company-specific content.** [Decision needed] Whether pages that belong to one company will enter the corpus. If yes, a company rule next to the tag rule. Section 03.2.
- **The folder rename.** [Decision needed] `frontend/`, `backend/`, `knowledge-base/` as in section 01.2. One pull request, no logic change.
- **The support check's failure mode and budget.** [Decision needed] The page defaults to retry once, then refuse with `support_unavailable`. The alternative is to send with every sentence marked unverified. Also confirm the provisional latency budget of 1.5 s at p95 for the judge call, and whether partly supported sentences are kept and marked (default) or cut. Section 06.5.
- **A freshness target.** [Decision needed] "A label change shows up within N minutes." No number exists. The webhook path can do minutes; the sweep does a day. Pick N so the tests in change 2 have a pass mark.
- **Apply migration 0010 live.** [Unverified, apply first] The scope policy is coded and tested, not yet applied to Supabase. Run `alembic upgrade head` there and `verify-isolation`. Blocks any public deploy.
- **The public URL.** [Decision needed] The Confluence webhook needs an HTTPS endpoint. This comes with the deferred AWS deploy. Until then, sweeps and manual scripts.
- **The embedder default.** [Decision needed] Make the code default match the deployed OpenAI 3072 setting, or run the Voyage bake-off first and pick a winner on the gold set.
- **Reranker v4.0 and the threshold.** [Decision needed] Swap together with a recalibrated threshold, once the gold set exists.
- **Images and scans.** [Decision needed] Run the corpus audit before deciding on OCR or a vision model.

---

## Appendix · Index of every panel

| Panel id | Section | Title | Status |
|---|---|---|---|
| `ov-confluence` | fit | Confluence, the source of truth | Implemented |
| `ov-receive` | fit | Receive and queue | Implemented, needs changing |
| `ov-decide` | fit | Decide what changed | Implemented, needs changing |
| `ov-build` | fit | Build the chunks | Implemented, needs changing |
| `ov-activate` | fit | Activate | Implemented, needs changing |
| `ov-auth` | fit | The auth host: the host backend or an agreed auth service | Implemented |
| `ov-corpus` | fit | The Postgres corpus | Implemented |
| `ov-eval` | fit | The evaluation set | Planned |
| `ov-widget` | fit | The Obi widget | Implemented |
| `ov-gate` | fit | The gate: who are we talking to? | Implemented, needs changing |
| `ov-search` | fit | Search | Implemented, needs changing |
| `ov-filter` | fit | Filter: three locks | Unverified |
| `ov-judge` | fit | Rerank and judge | Implemented, needs changing |
| `ov-answer` | fit | Answer | Implemented, needs changing |
| `sc-frontend` | concerns | One frontend | Implemented |
| `sc-backend` | concerns | One backend | Implemented |
| `sc-kb` | concerns | One knowledge base | Implemented, needs changing |
| `sc-user` | concerns | A Mews user | Planned |
| `em-token` | embed | The signed note (JWT) | Implemented |
| `r1-ctx` | rt1 | Build the authorization context: company, integration, person | Planned |
| `r3-scope` | rt3 | Scope row security | Unverified |
| `r3-acl` | rt3 | Page-level access list | Implemented |
| `r5-evidence` | rt5 | The evidence block | Implemented |
| `cm-root` | code | app/main.py: the wiring | Implemented |
| `cm-sync` | code | features/confluence_sync | Implemented |
| `cm-ingest` | code | features/ingestion | Implemented |
| `cm-retrieval` | code | features/retrieval | Implemented |
| `cm-agent` | code | features/rag_agent | Implemented |
| `cm-eval` | code | features/evaluation | Planned |
| `cm-platform` | code | platform/: shared technical capabilities | Implemented |
| `cm-shared` | code | shared/: small generic helpers | Implemented |
| `cm-alembic` | code | alembic/versions: the migrations | Unverified |
| `cm-scripts` | code | scripts/: operator tools | Implemented |
| `cm-config` | code | config/knowledge_scopes.json: the scope list | Implemented, needs changing |
| `cm-docs` | code | docs/adr: the decisions of record | Implemented |
| `cm-web` | code | apps/web: the widget | Implemented |
| `cm-contracts` | code | packages/contracts | Implemented |
| `cm-tokens` | code | packages/design-tokens | Implemented |
| `cm-infra` | code | infra/foundation: local Postgres | Implemented |
| `em-loader` | embed | obi.js: one script tag | Implemented |
| `em-hostbackend` | embed | The platform's note endpoint | Decision needed |
| `em-backend` | embed | Obi checks the note and picks the pages | Implemented |
| `em-kb` | embed | Obi picks the pages: the shared knowledge base | Implemented, needs changing |
| `tg-config` | tags | The scope list file | Implemented, needs changing |
| `i1-sweep` | in1 | Sweeps: the safety net | Implemented, needs changing |
| `s-writer` | security | The writer (table owner) | Implemented |
| `i1-webhook` | in1 | POST /confluence/events | Unverified |
| `i1-checks` | in1 | Rate limit, size cap, HMAC, parse | Implemented |
| `i1-ledger` | in1 | The event ledger | Implemented |
| `i1-self` | in1 | Was this our own write? | Implemented |
| `i1-enqueue` | in1 | Enqueue one job per page | Implemented, needs changing |
| `i1-claim` | in1 | A worker claims the job | Implemented |
| `i1-reaper` | in1 | The reaper | Implemented |
| `i1-fail` | in1 | Retry with backoff, then dead letter | Implemented |
| `i1-handle` | in1 | Handle and complete in one transaction | Implemented |
| `i2-fetch` | in2 | Fetch the page facts | Implemented |
| `i2-labels` | in2 | Labels to scope state | Implemented, needs changing |
| `i2-hash` | in2 | One index fingerprint | Implemented, needs changing |
| `i2-classify` | in2 | Classify the change | Implemented, needs changing |
| `i2-gone` | in2 | Gone, classified, or unlabeled: deactivate | Implemented, needs changing |
| `i2-rebuild` | in2 | Rebuild a new version | Implemented, needs changing |
| `i2-meta` | in2 | Metadata only: update in place | Implemented |
| `i2-nochange` | in2 | No change | Implemented |
| `i2-tobuild` | in2 | On to ingestion stage 3 | Implemented |
| `i2-inplace` | in2 | Update tags, state and restrictions in place | Implemented |
| `i3-blocks` | in3 | Normalize HTML into blocks | Implemented |
| `i3-parents` | in3 | Parent chunks | Implemented |
| `i3-children` | in3 | Child chunks | Implemented |
| `i3-context` | in3 | Contextualize each child | Implemented |
| `i3-embed` | in3 | Embed every child | Implemented, needs changing |
| `i4-staging` | in4 | Create the version in staging | Implemented, needs changing |
| `i3-attach` | in3 | Attachments | Implemented, needs changing |
| `i3-tsv` | in3 | The keyword index | Implemented |
| `i4-document` | in4 | Ensure the document row | Implemented |
| `i4-chunks` | in4 | Insert the chunks inactive | Implemented |
| `i4-gate` | in4 | Validation gate | Implemented |
| `i4-swap` | in4 | The pointer swap | Implemented |
| `i4-stamp` | in4 | Stamp source, tags and scope state | Implemented, needs changing |
| `i4-failed` | in4 | A failed version never activates | Implemented |
| `i4-gc` | in4 | Garbage collect old versions | Implemented |
| `i4-rollback` | in4 | Rollback to an older version | Implemented |
| `ks-edit` | tags | Edit knowledge_scopes.json | Implemented, needs changing |
| `ks-validate` | tags | Validate the list | Implemented, needs changing |
| `ks-deploy` | tags | Deploy | Implemented, needs changing |
| `ks-sweep` | tags | The label sweep finds tagged pages | Planned |
| `ks-index` | tags | Pages go in | Implemented |
| `ks-widget` | tags | A widget uses the same slug | Implemented, needs changing |
| `ks-remove` | tags | A tag is removed from the file | Implemented, needs changing |
| `ks-orphan` | tags | Pages with only that tag go out | Planned |
| `tg-add` | tags | Add a label | Implemented |
| `tg-change` | tags | Change a label | Implemented |
| `tg-remove` | tags | Remove the last recognized label | Planned |
| `tg-classified` | tags | Add the classified label | Planned |
| `tg-two` | tags | Two provider labels on one page | Implemented, needs changing |
| `tg-edit` | tags | Edit the body of a labeled page | Implemented, needs changing |
| `tg-first` | tags | The page is in the index | Implemented |
| `tg-retag` | tags | Tags updated without a re-embed | Implemented |
| `tg-deactivate` | tags | Deactivate | Planned |
| `tg-purge` | tags | Deactivate and purge | Planned |
| `tg-conflict` | tags | Excluded as a conflict | Implemented, needs changing |
| `tg-rebuild` | tags | Rebuild with tags carried | Implemented, needs changing |
| `tg-state` | tags | scope_state | Planned |
| `tg-filter` | tags | The filter that uses tags | Implemented, needs changing |
| `s-reader` | security | rag_reader | Implemented |
| `r1-proxy` | rt1 | The widget's proxy route | Implemented |
| `r1-auth` | rt1 | Verify who is asking | Implemented |
| `r1-limits` | rt1 | Limits and validation | Implemented |
| `r1-small` | rt1 | Small talk short-circuit | Implemented |
| `r1-clarify` | rt1 | Too vague to search? | Implemented |
| `r1-idem` | rt1 | Idempotency replay | Implemented |
| `r1-short` | rt1 | A short reply without search | Implemented |
| `r1-rewrite` | rt1 | Rewrite into one standalone question | Implemented, needs changing |
| `r2-embed` | rt2 | Embed the question | Implemented |
| `r2-gucs` | rt2 | Set the scope for this transaction | Implemented |
| `r2-dense` | rt2 | Dense search | Implemented |
| `r2-keyword` | rt2 | Keyword search | Implemented |
| `r2-rrf` | rt2 | Reciprocal rank fusion, by chunk id | Implemented, needs changing |
| `r2-prov` | rt2 | Provenance on every candidate | Planned |
| `r2-curated` | rt2 | Curated entries: found by relevance, in the same pool | Implemented, needs changing |
| `r2-indexes` | rt2 | The two search indexes | Implemented |
| `r2-aclsql` | rt2 | Lock 3 inside the SQL searches | Planned |
| `r3-reader` | rt3 | rag_reader | Implemented |
| `r3-source` | rt3 | Source row security | Implemented |
| `r3-torerank` | rt3 | Only permitted candidates move on | Implemented |
| `r3-deny` | rt3 | A forgotten scope leaks nothing | Implemented |
| `r3-classified` | rt3 | Conflict and classified are never served | Planned |
| `r3-groups` | rt3 | Groups expanded at sync time | Implemented |
| `r4-texts` | rt4 | Fetch the passages to rerank | Implemented, needs changing |
| `r4-rerank` | rt4 | Cohere cross-encoder rerank | Implemented |
| `r4-weak` | rt4 | Is the best passage too weak? | Implemented |
| `r4-fallback` | rt4 | One bounded fallback search | Implemented, needs changing |
| `r4-union` | rt4 | Rerank the union once | Planned |
| `r4-proceed` | rt4 | Top-k children move on to stage 5 | Implemented |
| `r4-refuse` | rt4 | Refuse and hand off | Implemented, needs changing |
| `r5-parents` | rt5 | Expand children to parents | Implemented, needs changing |
| `r5-dedupe` | rt5 | Dedupe and trim to the token budget: the final context | Planned |
| `r5-coverage` | rt5 | Coverage check on the final context | Planned |
| `r5-generate` | rt5 | Generate the answer | Implemented |
| `r5-enforce` | rt5 | Valid citation-number checking | Implemented |
| `r5-partial` | rt5 | Partial answer | Planned |
| `r5-nocite` | rt5 | Refuse: nothing survived the checks | Implemented |
| `r5-ground` | rt5 | Semantic support verification (batched, before send) | Planned |
| `r5-image` | rt5 | Image analysis | Implemented |
| `r5-feedback` | rt5 | Thumbs up or down | Implemented |
| `r5-stream` | rt5 | Completed-answer replay and the trace row | Implemented |
| `w-launcher` | widget | Launcher and teaser | Implemented |
| `w-panel` | widget | The panel | Implemented |
| `w-composer` | widget | The composer | Implemented |
| `w-scope` | widget | Which platform is this widget in? | Implemented, needs changing |
| `w-token` | widget | The user token | Implemented |
| `w-proxy` | widget | The proxy route | Implemented |
| `w-i18n` | widget | Six locales | Implemented |
| `w-screenshot` | widget | Screenshot of the page behind the widget | Implemented |
| `w-render` | widget | Rendering the answer | Implemented |
| `d-event_ledger` | data | event_ledger | Implemented |
| `d-job` | data | job | Implemented, needs changing |
| `d-page_source` | data | page_source | Implemented, needs changing |
| `d-document` | data | document | Implemented |
| `d-document_version` | data | document_version | Implemented, needs changing |
| `d-chunk` | data | chunk | Implemented, needs changing |
| `d-reconciliation_run` | data | reconciliation_run | Implemented |
| `d-source_scope` | data | source_scope | Decision needed |
| `d-page_restriction` | data | page_restriction | Implemented |
| `d-query_trace` | data | query_trace | Implemented, needs changing |
| `d-curated` | data | curated_knowledge_entry | Implemented, needs changing |
| `vd-text` | vector | The text that becomes a vector | Implemented |
| `vd-model` | vector | The embedding model | Decision needed |
| `vd-column` | vector | chunk.embedding | Implemented |
| `vd-hnsw` | vector | The HNSW index | Implemented |
| `vd-nearest` | vector | The nearest 75 | Implemented |
| `vd-rls` | vector | Row security covers vectors too | Implemented |
| `vd-question` | vector | The question vector | Implemented |
| `vd-keyword` | vector | The keyword side | Implemented |
| `vd-swap` | vector | Vectors swap with the page | Implemented |
| `s-edge` | security | The edge | Implemented |
| `s-source` | security | Source row security | Implemented |
| `s-scope` | security | Scope row security | Unverified |
| `s-acl` | security | Page access list | Implemented |
| `s-permitted` | security | The permitted rows | Implemented |
| `s-anon` | security | Supabase's public roles | Implemented |
| `s-classified` | security | classified is never served | Planned |
| `s-audit` | security | The audit trail | Implemented |
| `e-gold` | eval | The gold set | Planned |
| `e-split` | eval | Dev and held-out | Planned |
| `e-stage1` | eval | Before rerank: did search find it? | Planned |
| `e-stage2` | eval | After rerank: still near the top? | Planned |
| `e-stage3` | eval | Context assembly: did the model get it? | Planned |
| `e-stage4` | eval | Generation: correct, complete, cited | Planned |
| `e-ops` | eval | Latency and cost | Planned |
| `e-monitor` | eval | Freshness and recall telemetry | Planned |
| `e-judge` | eval | An LLM as judge | Planned |
| `em-button` | embed | The frame: the round button and the chat window | Implemented |