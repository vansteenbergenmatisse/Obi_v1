# Architecture decisions of record

Each decision has a name that says what was decided. Cite it by that identifier, e.g.
`ADR-source-system-decides-widget-eligibility`. Changing a decision needs a new ADR.

Until 2026-10-20 the ADRs were numbered (`ADR-0001` … `ADR-0023`). Code, config and docs now use
the names below. The append-only `docs/Final_docs/ledger.md` and `progress-log.md` keep the old
numbers in their history; this table resolves them.

| Old number | Identifier | File | Decision |
|---|---|---|---|
| 0001 | `ADR-fastapi-nextjs-postgres-pgvector-stack` | [fastapi-nextjs-postgres-pgvector-stack.md](fastapi-nextjs-postgres-pgvector-stack.md) | Repository Archetype and Stack |
| 0002 | `ADR-hybrid-retrieval-over-versioned-chunk-store` | [hybrid-retrieval-over-versioned-chunk-store.md](hybrid-retrieval-over-versioned-chunk-store.md) | Retrieval and Versioning Model |
| 0003 | `ADR-features-import-only-through-public-root` | [features-import-only-through-public-root.md](features-import-only-through-public-root.md) | Feature Boundary Enforcement |
| 0004 | `ADR-source-id-row-security-with-reader-writer-roles` | [source-id-row-security-with-reader-writer-roles.md](source-id-row-security-with-reader-writer-roles.md) | Multi-Source Provider Tagging and Row-Level Security |
| 0005 | `ADR-rerank-then-verify-cited-answers` | [rerank-then-verify-cited-answers.md](rerank-then-verify-cited-answers.md) | Reranking and the Answer Pipeline |
| 0006 | `ADR-defer-product-and-package-extraction` | [defer-product-and-package-extraction.md](defer-product-and-package-extraction.md) | Defer Multi-Product Extraction |
| 0007 | `ADR-separate-frontend-backend-repos` | — | deleted — superseded by `ADR-keep-frontend-backend-in-one-repo-for-now` |
| 0008 | `ADR-ambiguity-clarification-then-fallback-answer` | [ambiguity-clarification-then-fallback-answer.md](ambiguity-clarification-then-fallback-answer.md) | Ambiguity Clarification and Fallback |
| 0009 | `ADR-vision-grounded-image-analysis` | [vision-grounded-image-analysis.md](vision-grounded-image-analysis.md) | Vision-Grounded Image Analysis |
| 0010 | `ADR-keep-frontend-backend-in-one-repo-for-now` | [keep-frontend-backend-in-one-repo-for-now.md](keep-frontend-backend-in-one-repo-for-now.md) | Re-defer Frontend/Backend Repository Separation |
| 0011 | `ADR-knowledge-scope-tagging-and-filtering` | — | deleted — the knowledge-scope axis was retired by `ADR-routing-labels-sole-content-axis` |
| 0012 | — | — | never written (a planned repo-split ADR; see `docs/future-ideas/IDEAS.md` #5) |
| 0013 | `ADR-supabase-postgres-store-without-force-rls` | [supabase-postgres-store-without-force-rls.md](supabase-postgres-store-without-force-rls.md) | Production Vector Store = Managed Postgres (Supabase on AWS), and Dropping FORCE on chunk RLS |
| 0014 | `ADR-db-level-customer-scope-isolation-backstop` | [db-level-customer-scope-isolation-backstop.md](db-level-customer-scope-isolation-backstop.md) | Customer/Knowledge-Scope Isolation Backstop (DB-level, fail-closed) |
| 0015 | `ADR-change-detection-by-content-fingerprints` | [change-detection-by-content-fingerprints.md](change-detection-by-content-fingerprints.md) | Change-Detection Fingerprints |
| 0016 | `ADR-scope-state-materialized-as-tags` | — | deleted — tags are inert since `ADR-routing-labels-sole-content-axis` |
| 0017 | `ADR-signed-token-verified-at-the-edge` | [signed-token-verified-at-the-edge.md](signed-token-verified-at-the-edge.md) | Edge Token Verification |
| 0018 | `ADR-folder-dependencies-point-one-way` | [folder-dependencies-point-one-way.md](folder-dependencies-point-one-way.md) | One-Way Folder Dependency Direction |
| 0019 | `ADR-page-acl-enforced-in-app-layer-only` | [page-acl-enforced-in-app-layer-only.md](page-acl-enforced-in-app-layer-only.md) | Page-Principal ACL Is App-Layer-Only In v1 |
| 0020 | `ADR-directed-source-target-routing-labels` | [directed-source-target-routing-labels.md](directed-source-target-routing-labels.md) | Directed-Connection Retrieval Routing (Option A) |
| 0021 | `ADR-routing-labels-sole-content-axis` | [routing-labels-sole-content-axis.md](routing-labels-sole-content-axis.md) | Retire the Knowledge-Scope `-test` Tags; Routing Labels Are the Sole Content Axis |
| 0022 | `ADR-widget-hides-via-visibility-probe` | [widget-hides-via-visibility-probe.md](widget-hides-via-visibility-probe.md) | Target-Enablement Widget Eligibility in the Directed Path |
| 0023 | `ADR-source-system-decides-widget-eligibility` | [source-system-decides-widget-eligibility.md](source-system-decides-widget-eligibility.md) | The Source System Decides Widget Eligibility |
