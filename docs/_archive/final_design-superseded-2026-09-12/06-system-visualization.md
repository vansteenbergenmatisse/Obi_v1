# 06 — System Visualization

The whole system as a set of Mermaid diagrams: top-level architecture, the data model, the ingestion
sequence, the retrieval + answer sequence, the security layering, and the deployment view. Each
diagram has a short caption. For the narrative behind any of them, follow the cross-links to docs
02–05.

---

## (i) Top-level architecture

```mermaid
flowchart LR
  subgraph Browser
    W["Obi widget<br/>apps/web/features/chat"]
  end
  subgraph Next["Next.js (apps/web)"]
    RH["chat route handler /<br/>automation-api proxy<br/>(holds CHAT_API_KEY)"]
  end
  subgraph FastAPI["apps/automation (FastAPI)"]
    WH["POST /confluence/events<br/>(webhook)"]
    CH["POST /chat (SSE)<br/>PATCH /chat/:id/feedback"]
    WK["job worker + scheduler"]
    ING["confluence_sync + ingestion<br/>(writer role)"]
    RET["retrieval + rag_agent<br/>(reader role)"]
  end
  subgraph PG[("PostgreSQL 16 + pgvector + tsvector")]
    T["page_source, document,<br/>document_version, chunk (HNSW+GIN),<br/>page_restriction, event_ledger, job,<br/>query_trace, curated_knowledge_entry, ..."]
  end
  subgraph Ext["External APIs"]
    CF["Confluence REST"]
    EMB["Embeddings (Voyage / OpenAI)"]
    CO["Cohere rerank-v3.5"]
    AN["Anthropic (Sonnet / Haiku)"]
  end

  W -->|"HTTPS (no secret in browser)"| RH
  RH -->|"Bearer CHAT_API_KEY"| CH
  CF -->|"webhook HMAC"| WH
  WH --> ING
  WK --> ING
  ING -->|writer, BYPASS RLS| PG
  ING --> EMB
  ING --> AN
  ING --> CF
  CH --> RET
  RET -->|"reader, RLS enforced"| PG
  RET --> EMB
  RET --> CO
  RET --> AN
  CH -->|SSE stream| RH
  RH -->|SSE| W
```

Caption: The browser widget never holds a secret — the Next.js proxy injects `CHAT_API_KEY` on the
server side and forwards the SSE stream back. `apps/automation` is one FastAPI service with two
independent internal flows: the ingestion/write path (writer DB role, bypasses RLS) fed by the
Confluence webhook and the scheduled worker, and the retrieval/answer path (reader DB role, RLS
enforced) behind `POST /chat`. Both share one Postgres + pgvector store. External calls: an embedder,
Cohere for reranking, and Anthropic for rewrite/answer/vision.

---

## (ii) Data model (ER)

```mermaid
erDiagram
  PAGE_SOURCE ||--|| DOCUMENT : "1 per page"
  PAGE_SOURCE ||--o{ PAGE_RESTRICTION : "0..n principals"
  PAGE_SOURCE }o--o| DOCUMENT_VERSION : "active_doc_version_id"
  DOCUMENT ||--o{ DOCUMENT_VERSION : "many versions"
  DOCUMENT_VERSION ||--o{ CHUNK : "parents + children"
  CHUNK ||--o{ CHUNK : "parent_chunk_id"
  EVENT_LEDGER ||--o{ JOB : "source_event_id"
  PAGE_SOURCE {
    bigint page_id PK
    bigint space_id
    string source_id "RLS key"
    text_array tags "scope filter"
    bigint active_doc_version_id FK "UNIQUE"
    enum page_status
    bytea content_hash
    bytea labels_hash
  }
  PAGE_RESTRICTION {
    bigint page_id PK "FK to page_source"
    string principal PK
  }
  DOCUMENT {
    bigint id PK
    bigint page_id FK "UNIQUE"
  }
  DOCUMENT_VERSION {
    bigint id PK
    bigint document_id FK
    int cf_version
    enum state "staging|active|superseded|failed"
    string embedding_model
    int embedding_dim
  }
  CHUNK {
    bigint id PK
    bigint doc_version_id FK
    smallint kind "0 parent 1 child"
    bigint parent_chunk_id FK
    text display_content
    text retrieval_content
    vector embedding "children"
    tsvector tsv "children"
    bool is_active
    text_array tags
  }
  EVENT_LEDGER {
    bigint id PK
    bytea payload_hash "UNIQUE"
    string delivery_id "partial-unique"
    enum proc_status
  }
  JOB {
    bigint id PK
    string idempotency_key "UNIQUE"
    enum status
    bigint source_event_id FK
  }
  QUERY_TRACE {
    bigint id PK
    text raw_query
    text_array allowed_sources
    text_array allowed_knowledge_scopes
    text answer
    smallint feedback
  }
  CURATED_KNOWLEDGE_ENTRY {
    bigint id PK
    text_array tags "empty = all scopes"
    text title
    text body
    bool is_active
  }
```

Caption: One page → one `document` → many immutable `document_version`s → many `chunk`s (parents +
children, child→parent via `parent_chunk_id`). The `page_source.active_doc_version_id` UNIQUE deferred
FK plus the "one active version per document" partial-unique index are what make activation an atomic
pointer swap. `event_ledger`/`job` are the ingestion plumbing; `query_trace` and
`curated_knowledge_entry` stand apart from the corpus graph. Full column detail and the two search
indexes are in [`04-data-model.md`](./04-data-model.md).

---

## (iii) Ingestion sequence

```mermaid
sequenceDiagram
  autonumber
  participant CF as Confluence
  participant WH as webhook.py
  participant EL as event_ledger
  participant JQ as job queue
  participant WK as worker (3 txns)
  participant SS as sync_service
  participant ING as ingestion (chunk/ctx/embed)
  participant VER as versioning
  participant PG as Postgres

  CF->>WH: POST /confluence/events (HMAC)
  WH->>WH: rate limit, body cap, verify signature, parse
  WH->>EL: record_event (dedup on payload_hash / delivery_id)
  alt duplicate or self-generated
    EL-->>WH: no job
  else new event
    WH->>JQ: enqueue_job (idempotency_key)
  end
  Note over WK: Txn 1 - claim (FOR UPDATE SKIP LOCKED), lease + attempts++
  WK->>JQ: claim_job
  Note over WK,VER: Txn 2 - handle + complete atomically
  WK->>SS: handle_sync_page
  SS->>CF: fetch meta, labels, restrictions, attachments
  SS->>SS: classify change (status + version + hashes)
  alt rebuild (body/section/config change)
    SS->>ING: chunk (parent/child) -> contextualize -> embed children -> tsv
    ING->>VER: stage_and_activate
    VER->>PG: insert document_version (staging), chunks is_active=false
    VER->>PG: activate - supersede old, flip is_active, repoint active_doc_version_id
    VER->>PG: gc superseded beyond retain window
  else metadata-only (labels/perms/title)
    SS->>PG: re-stamp tags / status (no re-embed)
  else no change
    SS->>PG: touch last_reconciled_at
  end
  WK->>JQ: complete_job (succeeded)
  Note over WK: Txn 3 - on exception, fail_job independently (retry/backoff/dead-letter)
```

Caption: A webhook is validated, deduped into `event_ledger`, and enqueued as an idempotent job (unless
it is a duplicate or one of our own writes). The worker runs each job in three separate transactions so
the lease/attempt bookkeeping and the actual index mutation never share a rollback. `sync_service`
classifies the change from status/version/hashes and either rebuilds (full chunk→context→embed→stage→
atomic-activate→GC), applies a metadata-only tag/status update with no re-embed, or does nothing. See
[`02-ingestion.md`](./02-ingestion.md).

---

## (iv) Retrieval + answer sequence

```mermaid
sequenceDiagram
  autonumber
  participant U as Browser widget
  participant PX as Next.js proxy
  participant API as POST /chat (router)
  participant AS as AnswerService
  participant HR as HybridRetriever (reader)
  participant PG as Postgres (RLS)
  participant CO as Cohere rerank
  participant AN as Anthropic

  U->>PX: message + history
  PX->>API: Bearer CHAT_API_KEY, ChatRequestBody
  API->>API: auth, IP rate limit, validate, idempotency
  API->>AS: answer(history, principal, knowledge_scope)
  alt small talk / clarification
    AS->>AN: light generation (no retrieval, no trace)
    AN-->>AS: reply
  else normal question
    AS->>AN: rewrite to standalone query (routing_model)
    AS->>HR: retrieve_with_context(query, scope, k, knowledge_scopes)
    HR->>PG: set_config app.allowed_sources + HNSW GUCs
    HR->>PG: keyword (GIN) then dense (HNSW) over candidate_k=75
    HR->>HR: RRF fuse (k0=60), tie-break by keyword rank
    HR->>PG: fetch page_restriction for candidates -> principal ACL filter
    HR->>CO: rerank <=75 permitted -> top k
    CO-->>HR: scored top-k
    AS->>HR: CRAG retry once if weak (verbatim query)
    AS->>AS: decide_refusal (top_score < 0.10 -> refuse)
    AS->>HR: fetch_parent_texts (child -> parent context)
    AS->>AS: prepend curated hits, build evidence block
    AS->>AN: grounded generation (answer_model), forced citations
    AN-->>AS: answer text
    AS->>AS: enforce_citations (strip uncited; degrade to refusal if none)
    opt image on last turn
      AS->>AN: generate_image_analysis (separate, uncited call)
    end
    HR->>PG: write query_trace (writer engine)
  end
  AS-->>API: Answer
  API-->>PX: SSE start / token / citations / done
  PX-->>U: SSE stream
```

Caption: The proxy adds the bearer secret; the router enforces the HTTP/LLM control set. Small-talk and
clarification short-circuit before retrieval. A normal question is rewritten, searched two ways (keyword
then dense, fused by RRF), filtered by source RLS + knowledge-scope + principal ACL, reranked by Cohere,
optionally retried once (CRAG), abstained on if weak, expanded to parent context, and generated with
forced citations (uncited claims stripped). The result streams back as SSE. See
[`03-retrieval.md`](./03-retrieval.md).

---

## (v) Security / RLS layering

```mermaid
flowchart TB
  REQ["Read request<br/>scope + principal + knowledge_scope"] --> L1
  subgraph L1["Layer 1 - Source RLS (DB-enforced, default-DENY, fails CLOSED)"]
    G1["set_config('app.allowed_sources', :s, true)"]
    G2["WHERE source_id = ANY(:sources)"]
    POL["POLICY chunk_source_read, role rag_reader (non-owner)"]
  end
  L1 --> L2
  subgraph L2["Layer 2 - Knowledge scope (DB RESTRICTIVE RLS + app predicate, fails CLOSED)"]
    K0["set_config('app.allowed_knowledge_scopes', :s, true) - every reader txn"]
    K1["RESTRICTIVE POLICY chunk_scope_read / curated_..._scope_read (ADR-0014)"]
    K2["+ app predicate tags && :knowledge_scopes (flag-gated, defense-in-depth)"]
  end
  L2 --> L3
  subgraph L3["Layer 3 - Principal ACL (request-scoped, pre-rerank)"]
    A1["fetch page_restriction for candidates"]
    A2["PrincipalPermissionPolicy.allowed"]
  end
  L3 --> OUT["permitted candidates -> rerank -> answer"]

  subgraph DES["Design decisions (ADRs)"]
    I1["Managed PG: RLS ENABLE + NO FORCE, owner exempt by ownership (ADR-0013)"]
    I2["Customer axis: RESTRICTIVE scope-GUC RLS, ANDs with source, fail-closed (ADR-0014)"]
  end
  L1 -. "portable to managed PG" .-> I1
  L2 -. "fails closed like source RLS" .-> I2
```

Caption: Three layers gate every read. Layers 1 and 2 are hard, database-enforced, default-deny
boundaries — Layer 1 isolates source systems, Layer 2 isolates the customer/platform axis with a
`RESTRICTIVE` scope-GUC RLS policy (ADR-0014) that ANDs on top of Layer 1, backed by a redundant
flag-gated app predicate. Layer 3 (principal ACL) runs before rerank so the cross-encoder never scores a
document the principal cannot see. The two design decisions worth calling out (managed-PG `NO FORCE`;
fail-closed customer axis) are attached to the layers they support — see
[`05-security-isolation.md`](./05-security-isolation.md).

---

## (vi) Deployment view (dev vs. prod)

```mermaid
flowchart LR
  subgraph DEV["Local dev (today)"]
    direction TB
    D1["apps/web: next dev"]
    D2["apps/automation: uvicorn"]
    D3[("Docker pgvector/pgvector:pg16<br/>on :5434 (infra/)")]
    D4["Offline fallbacks:<br/>FakeEmbedder / FakeReranker,<br/>fixture Confluence gateway"]
    D1 --> D2 --> D3
    D2 -.-> D4
  end
  subgraph PROD["Production - Supabase Cloud on AWS"]
    direction TB
    P1["apps/web (deployed)"]
    P2["apps/automation (deployed)"]
    P3[("Supabase Cloud on AWS<br/>managed Postgres + pgvector >= 0.8<br/>session pooler / direct :5432")]
    P4["writer DATABASE_URL +<br/>reader DATABASE_READER_URL"]
    P5["RDS / Aurora = reversible<br/>DSN-swap fallback"]
    P1 --> P2 --> P3
    P2 --- P4
    P3 -. "connection-string swap<br/>+ re-apply roles/RLS" .-> P5
  end
  DEV -. "alembic upgrade head (0001..0010)<br/>+ recreate roles + RLS + load corpus" .-> PROD
```

Caption: In dev, both apps run locally against a Docker `pgvector/pgvector:pg16` container on port
5434, with deterministic offline fallbacks (Fake embedder/reranker, fixture Confluence) so the whole
system runs with no API keys. Production targets **Supabase Cloud on AWS** — managed Postgres + pgvector
≥ 0.8, reached over the session-pooler/direct port 5432 by plain DSN, with separate writer and reader
connection strings. RLS is `ENABLE`d + `NO FORCE` (ADR-0013, owner exempt by ownership) and the
customer axis is backstopped by `RESTRICTIVE` scope-GUC RLS (ADR-0014). **RDS/Aurora is a reversible
fallback** (a DSN swap + role/RLS re-apply). No scale/latency target is defined. Live cutover status is
tracked in `docs/rag/PLAN.md` §0.
