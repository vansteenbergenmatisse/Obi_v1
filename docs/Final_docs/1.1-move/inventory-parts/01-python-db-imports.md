# 1.1 Move · Python inventory part 01 — DB-layer imports

Read-only inventory of every Python reference to the DB layer that must change when
`apps/automation/app/platform/db/` moves to `knowledge-base/schema/` and imports change
from `app.platform.db.*` to `schema.*`.

Scope: `apps/automation`, excluding `.venv`, `__pycache__`, `node_modules`. All paths are
relative to the repo root. Each hit is `path:line: <exact import text>`.

---

## Kind A — `from app.platform.db.models import` / `import app.platform.db.models`

apps/automation/app/features/confluence_sync/domain/scope_resolver.py:14: from app.platform.db.models import SourceScope
apps/automation/app/platform/jobs/queue.py:18: from app.platform.db.models import Job
apps/automation/app/features/confluence_sync/infrastructure/event_repo.py:12: from app.platform.db.models import EventLedger
apps/automation/app/features/confluence_sync/application/knowledge_scope_backfill.py:23: from app.platform.db.models import Chunk
apps/automation/app/features/ingestion/application/versioning.py:30: from app.platform.db.models import KIND_CHILD, KIND_PARENT, Chunk, DocumentVersion, PageSource
apps/automation/app/features/ingestion/infrastructure/page_source_repo.py:9: from app.platform.db.models import Document, PageSource
apps/automation/app/features/confluence_sync/application/sync_service.py:31: from app.platform.db.models import Chunk, PageRestriction, PageSource
apps/automation/app/features/confluence_sync/application/reconciliation.py:36: from app.platform.db.models import PageSource, ReconciliationRun, SourceScope
apps/automation/app/features/confluence_sync/application/worker.py:37: from app.platform.db.models import Job
apps/automation/app/features/retrieval/infrastructure/trace_repo.py:16: from app.platform.db.models import QueryTrace
apps/automation/scripts/seed_curated_knowledge.py:29: from app.platform.db.models import CuratedKnowledgeEntry
apps/automation/scripts/seed_source_scope.py:27: from app.platform.db.models import SourceScope
apps/automation/scripts/verify_knowledge_scope_live.py:69: from app.platform.db.models import Chunk, PageSource
apps/automation/app/platform/db/tests/test_models_indexes.py:32: from app.platform.db.models import EMB_DIM
apps/automation/app/features/confluence_sync/tests/test_event_dedup.py:15: from app.platform.db.models import EventLedger, Job
apps/automation/app/features/confluence_sync/tests/test_scope_tagging_add.py:35: from app.platform.db.models import PageSource
apps/automation/app/features/confluence_sync/tests/test_versioning_failed.py:17: from app.platform.db.models import DocumentVersion
apps/automation/app/features/confluence_sync/tests/test_versioning_swap.py:13: from app.platform.db.models import Chunk, DocumentVersion, PageSource
apps/automation/app/features/confluence_sync/tests/test_versioning_document.py:8: from app.platform.db.models import Document
apps/automation/app/features/confluence_sync/tests/test_reader_vector_access.py:30: from app.platform.db.models import EMB_DIM, KIND_CHILD, Chunk, Document, DocumentVersion, PageSource
apps/automation/app/features/confluence_sync/tests/test_versioning_gate.py:23: from app.platform.db.models import Job
apps/automation/app/features/confluence_sync/tests/test_worker_sync.py:23: from app.platform.db.models import Chunk, DocumentVersion, Job, PageRestriction, PageSource
apps/automation/app/features/confluence_sync/tests/test_scope_tagging_first.py:9: from app.platform.db.models import PageSource
apps/automation/app/features/confluence_sync/tests/test_ingestion_pipeline.py:12: from app.platform.db.models import KIND_PARENT, Chunk, DocumentVersion
apps/automation/app/features/confluence_sync/tests/test_ingestion_pipeline.py:236:     from app.platform.db.models import PageSource   [function-local import]
apps/automation/app/features/confluence_sync/tests/test_ingestion_pipeline.py:264:     from app.platform.db.models import PageSource   [function-local import]
apps/automation/app/features/confluence_sync/tests/test_retrieval_knowledge_scope.py:21: from app.platform.db.models import QueryTrace
apps/automation/app/features/confluence_sync/tests/test_job_queue.py:12: from app.platform.db.models import Job
apps/automation/app/features/confluence_sync/tests/test_reconciliation.py:17: from app.platform.db.models import PageSource, ReconciliationRun, SourceScope
apps/automation/app/features/retrieval/tests/test_vector_data_nearest.py:44: from app.platform.db.models import KIND_CHILD, Chunk, Document, DocumentVersion, PageSource
apps/automation/app/features/confluence_sync/tests/test_attachment_wiring.py:18: from app.platform.db.models import PageSource
apps/automation/app/features/confluence_sync/tests/test_scope_tagging_change.py:31: from app.platform.db.models import PageSource
apps/automation/app/features/confluence_sync/tests/test_webhook.py:18: from app.platform.db.models import EventLedger, Job
apps/automation/app/features/confluence_sync/tests/_helpers.py:12: from app.platform.db.models import KIND_CHILD, Chunk, DocumentVersion, PageRestriction, PageSource
apps/automation/app/features/confluence_sync/tests/test_scope_resolver.py:14: from app.platform.db.models import SourceScope
apps/automation/app/features/confluence_sync/tests/test_scope_tagging_ks_index.py:23: from app.platform.db.models import PageSource
apps/automation/app/features/confluence_sync/tests/test_event_ledger_constraints.py:17: from app.platform.db.models import EventLedger
apps/automation/app/features/confluence_sync/tests/test_scope_tagging_retag.py:26: from app.platform.db.models import PageSource
apps/automation/app/features/confluence_sync/tests/test_versioning_rollback.py:19: from app.platform.db.models import DocumentVersion, PageSource
apps/automation/app/features/retrieval/tests/test_vector_data_keyword.py:31: from app.platform.db.models import KIND_CHILD, Chunk, Document, DocumentVersion, PageSource
apps/automation/app/features/confluence_sync/tests/test_curated_knowledge_repo.py:16: from app.platform.db.models import CuratedKnowledgeEntry
apps/automation/app/features/confluence_sync/tests/test_versioning_gc.py:9: from app.platform.db.models import Chunk, DocumentVersion
apps/automation/app/features/confluence_sync/tests/test_versioning_chunks.py:10: from app.platform.db.models import KIND_CHILD, KIND_PARENT, Chunk
apps/automation/app/features/confluence_sync/tests/test_vector_data_column.py:18: from app.platform.db.models import KIND_PARENT, Chunk
apps/automation/app/features/confluence_sync/tests/test_document_constraints.py:19: from app.platform.db.models import Document, PageSource

Count: 45 (of which 2 are function-local imports — see Anomalies)

---

## Kind B — `from app.platform.db.engine import`

apps/automation/app/main.py:47: from app.platform.db.engine import get_reader_sessionmaker, get_sessionmaker, session_scope
apps/automation/app/platform/db/__init__.py:2: from app.platform.db.engine import get_engine, get_sessionmaker, session_scope
apps/automation/app/features/confluence_sync/server/webhook.py:40: from app.platform.db.engine import session_scope
apps/automation/app/features/confluence_sync/application/worker.py:36: from app.platform.db.engine import session_scope
apps/automation/app/features/rag_agent/server/router.py:162: from app.platform.db.engine import session_scope
apps/automation/scripts/verify_knowledge_scope_backfill.py:31: from app.platform.db.engine import session_scope
apps/automation/scripts/seed_curated_knowledge.py:28: from app.platform.db.engine import session_scope
apps/automation/scripts/seed_source_scope.py:26: from app.platform.db.engine import session_scope
apps/automation/scripts/run_reconciliation_once.py:36: from app.platform.db.engine import session_scope
apps/automation/scripts/verify_knowledge_scope_live.py:68: from app.platform.db.engine import session_scope
apps/automation/app/features/confluence_sync/tests/test_versioning_failed.py:15: from app.platform.db.engine import get_sessionmaker
apps/automation/app/features/confluence_sync/tests/_helpers.py:10: from app.platform.db.engine import get_sessionmaker, session_scope
apps/automation/app/features/confluence_sync/tests/test_answer_workflow.py:19: from app.platform.db.engine import get_reader_sessionmaker, get_sessionmaker
apps/automation/app/features/confluence_sync/tests/test_reconciliation.py:15: from app.platform.db.engine import session_scope
apps/automation/app/features/confluence_sync/tests/test_versioning_gate.py:21: from app.platform.db.engine import session_scope
apps/automation/app/features/confluence_sync/tests/test_scope_tagging_change.py:30: from app.platform.db.engine import session_scope
apps/automation/app/features/confluence_sync/tests/test_job_queue.py:10: from app.platform.db.engine import get_sessionmaker, session_scope
apps/automation/app/features/confluence_sync/tests/test_versioning_swap.py:11: from app.platform.db.engine import session_scope
apps/automation/app/features/confluence_sync/tests/test_chat_endpoint.py:29: from app.platform.db.engine import get_reader_sessionmaker, get_sessionmaker
apps/automation/app/features/confluence_sync/tests/test_versioning_rollback.py:18: from app.platform.db.engine import session_scope
apps/automation/app/features/confluence_sync/tests/test_attachment_wiring.py:17: from app.platform.db.engine import session_scope
apps/automation/app/features/confluence_sync/tests/test_curated_knowledge_repo.py:15: from app.platform.db.engine import get_sessionmaker
apps/automation/app/features/confluence_sync/tests/test_scope_tagging_add.py:34: from app.platform.db.engine import get_reader_sessionmaker, get_sessionmaker
apps/automation/app/features/confluence_sync/tests/test_event_dedup.py:14: from app.platform.db.engine import session_scope
apps/automation/app/features/confluence_sync/tests/test_retrieval_knowledge_scope.py:20: from app.platform.db.engine import get_reader_sessionmaker, get_sessionmaker
apps/automation/app/features/confluence_sync/tests/test_ingestion_pipeline.py:203:     from app.platform.db.engine import session_scope   [function-local import]
apps/automation/app/features/confluence_sync/tests/test_ingestion_pipeline.py:235:     from app.platform.db.engine import session_scope   [function-local import]
apps/automation/app/features/confluence_sync/tests/test_ingestion_pipeline.py:263:     from app.platform.db.engine import session_scope   [function-local import]
apps/automation/app/features/confluence_sync/tests/test_ingestion_pipeline.py:297:     from app.platform.db.engine import session_scope   [function-local import]
apps/automation/app/features/confluence_sync/tests/test_knowledge_scope_backfill.py:20: from app.platform.db.engine import get_sessionmaker
apps/automation/app/features/confluence_sync/tests/test_worker_sync.py:21: from app.platform.db.engine import session_scope
apps/automation/app/features/confluence_sync/tests/test_webhook.py:16: from app.platform.db.engine import session_scope
apps/automation/app/features/confluence_sync/tests/test_scope_tagging_ks_index.py:22: from app.platform.db.engine import get_reader_sessionmaker, get_sessionmaker
apps/automation/app/features/confluence_sync/tests/test_fallback_eval.py:22: from app.platform.db.engine import get_sessionmaker
apps/automation/app/features/confluence_sync/tests/test_customer_isolation_backstop.py:31: from app.platform.db.engine import get_reader_sessionmaker
apps/automation/app/features/confluence_sync/tests/test_customer_isolation_backstop.py:45:     from app.platform.db.engine import get_sessionmaker   [function-local import]
apps/automation/app/features/confluence_sync/tests/test_retrieval_eval.py:38: from app.platform.db.engine import get_reader_sessionmaker, get_sessionmaker
apps/automation/app/features/confluence_sync/tests/test_verify_isolation_script.py:20: from app.platform.db.engine import get_sessionmaker

Count: 38 (of which 5 are function-local imports — see Anomalies)

---

## Kind C — `from app.platform.db.enums import`

apps/automation/app/platform/db/schema.py:16: from app.platform.db.enums import PG_ENUMS
apps/automation/app/platform/db/models.py:38: from app.platform.db.enums import (
apps/automation/app/platform/jobs/queue.py:17: from app.platform.db.enums import JobStatus
apps/automation/app/features/confluence_sync/infrastructure/event_repo.py:11: from app.platform.db.enums import EventProcStatus, PageStatus
apps/automation/app/features/confluence_sync/application/sync_service.py:88:         from app.platform.db.enums import PageStatus   [function-local import]
apps/automation/app/features/confluence_sync/application/reconciliation.py:35: from app.platform.db.enums import PageStatus, ReconStatus
apps/automation/app/features/confluence_sync/application/event_service.py:22: from app.platform.db.enums import EventProcStatus
apps/automation/app/features/ingestion/domain/change_detection.py:14: from app.platform.db.enums import ChangeClass, PageStatus
apps/automation/app/features/ingestion/application/versioning.py:29: from app.platform.db.enums import DocState, PageStatus
apps/automation/app/features/retrieval/tests/test_vector_data_nearest.py:43: from app.platform.db.enums import DocState, PageStatus
apps/automation/app/features/confluence_sync/tests/test_reader_vector_access.py:29: from app.platform.db.enums import DocState, PageStatus
apps/automation/app/features/confluence_sync/tests/_helpers.py:11: from app.platform.db.enums import DocState
apps/automation/app/features/confluence_sync/tests/test_reconciliation.py:16: from app.platform.db.enums import ReconStatus
apps/automation/app/features/confluence_sync/tests/test_versioning_gate.py:22: from app.platform.db.enums import JobStatus
apps/automation/app/features/confluence_sync/tests/test_versioning_swap.py:12: from app.platform.db.enums import DocState
apps/automation/app/features/confluence_sync/tests/test_job_queue.py:11: from app.platform.db.enums import JobStatus
apps/automation/app/features/confluence_sync/tests/test_document_constraints.py:18: from app.platform.db.enums import PageStatus
apps/automation/app/features/confluence_sync/tests/test_versioning_failed.py:16: from app.platform.db.enums import DocState
apps/automation/app/features/confluence_sync/tests/test_ingestion_pipeline.py:11: from app.platform.db.enums import DocState
apps/automation/app/features/confluence_sync/tests/test_versioning_gc.py:8: from app.platform.db.enums import DocState
apps/automation/app/features/confluence_sync/tests/test_worker_sync.py:22: from app.platform.db.enums import DocState, JobStatus, PageStatus
apps/automation/app/features/retrieval/tests/test_vector_data_keyword.py:30: from app.platform.db.enums import DocState, PageStatus
apps/automation/app/features/confluence_sync/tests/test_webhook.py:17: from app.platform.db.enums import EventProcStatus
apps/automation/app/features/confluence_sync/tests/test_event_ledger_constraints.py:16: from app.platform.db.enums import EventProcStatus

Count: 24 (of which 1 is a function-local import — see Anomalies)

---

## Kind D — `from app.platform.db.base import`

apps/automation/alembic/env.py:9: from app.platform.db.base import Base
apps/automation/app/platform/db/schema.py:15: from app.platform.db.base import Base
apps/automation/app/platform/db/__init__.py:1: from app.platform.db.base import Base
apps/automation/app/platform/db/models.py:37: from app.platform.db.base import Base
apps/automation/app/platform/db/tests/test_models_constraints.py:18: from app.platform.db.base import Base

Count: 5

---

## Kind E — `from app.platform.db import ...` (submodule-as-name) and `from app.platform.db.schema`

No `from app.platform.db.schema import` hits exist. All hits here are
`from app.platform.db import <submodule>` (schema / models / engine as engine_mod).

apps/automation/alembic/versions/0001_core_schema.py:18: from app.platform.db import schema
apps/automation/alembic/versions/0002_provider_tags_and_rls.py:29: from app.platform.db import schema
apps/automation/alembic/versions/0009_reconcile_non_chunk_rls.py:33: from app.platform.db import schema
apps/automation/alembic/versions/0010_customer_scope_rls.py:34: from app.platform.db import schema
apps/automation/alembic/env.py:12: from app.platform.db import models  # noqa: F401
apps/automation/scripts/setup_supabase.py:36: from app.platform.db import engine as engine_mod
apps/automation/scripts/setup_supabase.py:37: from app.platform.db import schema
apps/automation/app/platform/db/schema.py:14: from app.platform.db import models  # noqa: F401
apps/automation/app/platform/db/tests/test_models_constraints.py:17: from app.platform.db import models  # noqa: F401
apps/automation/app/platform/db/tests/test_engine_reader_role.py:17: from app.platform.db import engine as engine_mod
apps/automation/app/platform/db/tests/test_migration_0009_reader_rls_reconcile.py:26: from app.platform.db import engine as engine_mod
apps/automation/app/platform/db/tests/test_migration_0010_scope_rls.py:28: from app.platform.db import engine as engine_mod
apps/automation/app/platform/db/tests/test_models_indexes.py:31: from app.platform.db import engine as engine_mod
apps/automation/app/platform/db/tests/test_migration_0007_knowledge_scope.py:23: from app.platform.db import engine as engine_mod
apps/automation/app/platform/db/tests/test_migration_0011_subject_hash.py:22: from app.platform.db import engine as engine_mod
apps/automation/app/platform/db/tests/test_reader_default_privileges.py:24: from app.platform.db import schema
apps/automation/app/platform/db/tests/test_r3_reader_role_protect.py:27: from app.platform.db import schema
apps/automation/app/tests/test_cm_root_wiring.py:17: from app.platform.db import engine as engine_mod
apps/automation/app/features/confluence_sync/tests/test_reader_vector_access.py:27: from app.platform.db import engine as engine_mod
apps/automation/app/features/confluence_sync/tests/test_reader_vector_access.py:28: from app.platform.db import schema
apps/automation/app/features/retrieval/tests/test_s_reader_role_usage.py:36: from app.platform.db import engine as engine_mod
apps/automation/app/features/retrieval/tests/test_s_reader_role_usage.py:37: from app.platform.db import schema
apps/automation/app/features/confluence_sync/tests/test_force_rls_managed_postgres.py:27: from app.platform.db import engine as engine_mod
apps/automation/app/features/retrieval/tests/test_vector_data_keyword.py:28: from app.platform.db import engine as engine_mod
apps/automation/app/features/retrieval/tests/test_vector_data_keyword.py:29: from app.platform.db import schema
apps/automation/app/features/retrieval/tests/test_vector_data_nearest.py:41: from app.platform.db import engine as engine_mod
apps/automation/app/features/retrieval/tests/test_vector_data_nearest.py:42: from app.platform.db import schema
apps/automation/app/features/confluence_sync/tests/test_customer_isolation_backstop.py:29: from app.platform.db import engine as engine_mod
apps/automation/app/features/confluence_sync/tests/test_customer_isolation_backstop.py:30: from app.platform.db import schema
apps/automation/app/features/confluence_sync/tests/test_reader_rls_reconcile.py:25: from app.platform.db import engine as engine_mod
apps/automation/app/features/confluence_sync/tests/test_reader_rls_reconcile.py:26: from app.platform.db import schema
apps/automation/app/features/confluence_sync/tests/conftest.py:20: from app.platform.db import engine as engine_mod
apps/automation/app/features/confluence_sync/tests/conftest.py:21: from app.platform.db import schema
apps/automation/app/features/rag_agent/tests/test_s_reader_curated_fetch.py:39: from app.platform.db import engine as engine_mod
apps/automation/app/features/rag_agent/tests/test_s_reader_curated_fetch.py:40: from app.platform.db import schema

Count: 35

Note on rewrite: `from app.platform.db import schema` / `models` / `engine as engine_mod`
becomes `from schema import ...` (or `import schema as ...`) once the package is `schema.*`;
`from app.platform.db import schema` collides in naming with the new root name `schema` and
must be handled with care during the move.

---

## Anomalies (NOT simple module-level imports)

### Docstring / comment string literals containing `app.platform.db.schema` (no rewrite as import; prose only)

apps/automation/app/features/retrieval/tests/test_s_reader_role_usage.py:17: ``app.platform.db.schema`` primitives and connection pattern as   [docstring]
apps/automation/app/features/retrieval/tests/test_vector_data_nearest.py:16: exact same ``app.platform.db.schema`` primitives and connection pattern as   [docstring]
apps/automation/app/features/retrieval/tests/test_vector_data_keyword.py:10: ``app.platform.db.schema`` primitives (``create_all``) rather than inventing a new one. The   [docstring]
apps/automation/app/features/rag_agent/tests/test_s_reader_curated_fetch.py:10: the same ``app.platform.db.schema`` primitives and connection pattern as   [docstring]

These 4 are prose in docstrings, not imports. They still reference the old dotted path and
should be updated for accuracy, but they are not counted in the import kind totals above.

### Function-local (indented) imports — real imports, but inside a function body, not module top-level

apps/automation/app/features/confluence_sync/application/sync_service.py:88 (enums) — inside a function
apps/automation/app/features/confluence_sync/tests/test_ingestion_pipeline.py:203, 235, 263, 297 (engine) — inside functions
apps/automation/app/features/confluence_sync/tests/test_ingestion_pipeline.py:236, 264 (models) — inside functions
apps/automation/app/features/confluence_sync/tests/test_customer_isolation_backstop.py:45 (engine) — inside a function

These 8 are counted in their respective kind totals (they are genuine imports that must be
rewritten); flagged here only because they are not at module scope.

---

## Totals

- Kind A (`.models` import): 45 hits
- Kind B (`.engine` import): 38 hits
- Kind C (`.enums` import): 24 hits
- Kind D (`.base` import): 5 hits
- Kind E (`from app.platform.db import <submodule>`): 35 hits
- Import hits total (A+B+C+D+E): 147
- Docstring/comment string-literal hits (not imports): 4
- Function-local (indented) imports, already included in A/B/C above: 8
- DISTINCT files touched (any `app.platform.db` reference, import or docstring): 80
