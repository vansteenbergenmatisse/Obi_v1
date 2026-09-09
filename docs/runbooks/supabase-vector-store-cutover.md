# Runbook — cutting the vector store over to managed Postgres (Supabase / RDS)

Stands up the RAG schema, roles, and corpus on a fresh managed-Postgres instance and proves the
ADR-0004 read-path isolation holds there. This is the Phase 6 / ADR-0013 procedure. It is written
for Supabase Cloud on AWS (the decision of record); the identical steps apply to an AWS RDS/Aurora
fallback — only the DSN differs.

The app talks plain Postgres over `psycopg` (a DSN, no Supabase SDK/keys), so this whole runbook is
"provision Postgres + load data + swap a connection string." There is no lock-in.

## Prerequisites

- A managed-Postgres instance reachable by connection string, with **pgvector ≥ 0.8** installed
  (`hnsw.iterative_scan`; the `preflight` gate refuses to migrate below this).
- Connect via the **session pooler / direct port `:5432`**, never the `:6543` transaction pooler —
  the transaction pooler breaks session-scoped `SET`/prepared statements and multi-statement
  transactions (the corpus restore needs both).
- The **writer/owner** DSN in the root `.env` as `DATABASE_URL`, in SQLAlchemy form
  (`postgresql+psycopg://<owner>.<project_ref>:<pw>@<host>:5432/postgres?sslmode=require`). The
  reader DSN is *derived* by the script, not handed over.
- `.env` is gitignored — never commit a real DSN. No credential is ever printed or logged; the
  generated `rag_reader` password is written only into `.env` as `DATABASE_READER_URL`.
- A local source corpus to load (the dev docker DB on `:5434`), or accept the OpenAI-embedding cost
  of a full rebuild (see step 4).

## Why managed Postgres needs the FORCE-RLS drop (ADR-0013)

Managed Postgres gives **no superuser**. Under the old `FORCE ROW LEVEL SECURITY`, even the table
owner is policy-subject, so the writer would be filtered to zero rows and ingestion would break.
The fix (migration `0008_drop_force_rls`): `chunk` keeps RLS **`ENABLE`d** but **`NO FORCE`**, so the
non-superuser *owner* is exempt while the non-owner `rag_reader` stays policy-bound. ADR-0004's
read-path guarantee is unchanged — verified live in step 5.

## Procedure

Run every step from `apps/automation`. Steps are idempotent and safe to re-run.

1. **Preflight** — connectivity, DB identity, current role, and the pgvector gate:

   ```
   uv run python scripts/setup_supabase.py preflight
   ```

   Exits non-zero (and refuses to continue) if auth fails or pgvector < 0.8. Expect
   `is_superuser=off` on managed Postgres — that is the condition the FORCE-drop handles.

2. **Migrate as the table-owner** — builds schema `0001→0008`; the migrations apply RLS
   `ENABLE` + `NO FORCE`:

   ```
   uv run alembic upgrade head
   uv run alembic current      # expect: 0008_drop_force_rls (head)
   ```

3. **Provision the reader** — creates/refreshes the non-owner `rag_reader`, re-asserts RLS, derives
   the pooler reader DSN (`rag_reader.<project_ref>`), and writes `DATABASE_READER_URL` into `.env`
   (password generated, never printed):

   ```
   uv run python scripts/setup_supabase.py provision-reader
   ```

4. **Load the corpus** — dump the content tables from the local dev DB and restore into the target
   *in a single transaction*. Only the five **content** tables are transplanted — the operational
   logs (`job`, `query_trace`, `reconciliation_run`) are runtime state and must not be carried over.

   ```
   # from the repo root; local dev DB is rag:rag@localhost:5434/omniboost_rag
   pg_dump -h localhost -p 5434 -U rag -d omniboost_rag \
     --data-only --no-owner --no-privileges \
     -t public.page_source -t public.document -t public.document_version \
     -t public.source_scope -t public.chunk \
     -f /tmp/corpus_data.sql
   ```

   **FK ordering caveat — the restore must be one transaction.** `page_source ⇄ document_version`
   and `document → page_source` are circular FKs (`INITIALLY DEFERRED`): in autocommit each `COPY`
   would commit and trip the deferred check before the referenced rows exist, so wrap the whole
   restore in `BEGIN … COMMIT`. Separately, `chunk.parent_chunk_id → chunk` is a **non-deferrable**
   self-FK and heap-order `COPY` can load a child before its parent — temporarily make it deferrable
   for the load, then revert:

   ```
   psql "<owner libpq DSN, +psycopg stripped>" -v ON_ERROR_STOP=1 <<'SQL'
   BEGIN;
   ALTER TABLE public.chunk ALTER CONSTRAINT fk_chunk_parent_chunk_id_chunk DEFERRABLE INITIALLY DEFERRED;
   SET CONSTRAINTS ALL DEFERRED;
   \i /tmp/corpus_data.sql
   COMMIT;
   ALTER TABLE public.chunk ALTER CONSTRAINT fk_chunk_parent_chunk_id_chunk NOT DEFERRABLE;
   SQL
   ```

   Reverting the self-FK to `NOT DEFERRABLE` leaves the schema identical to what the migrations
   produce. **Fallback (costs OpenAI embedding spend — ask the operator first):** rebuild from source
   via `scripts/run_reconciliation_once.py` instead of dump/restore.

5. **Prove parity** — RLS isolation on the live instance, then retrieval parity:

   ```
   uv run python scripts/setup_supabase.py verify-isolation   # owner sees rows; reader no-GUC=0, scoped=only its source, bogus=0
   make eval                                                  # retrieval quality on the live store
   ```

   The cross-provider (Mews vs Toast) exclusion is **not** demonstrable on real data — the whole
   corpus is `general` — it stays proven by `test_retrieval_knowledge_scope.py`. Run the local
   isolation suite against the **local superuser docker**, not the managed instance (the fixture
   `ALTER ROLE`s, which the managed `postgres` role can't do):

   ```
   DATABASE_URL="postgresql+psycopg://rag:rag@localhost:5434/omniboost_rag" DATABASE_READER_URL="" \
     uv run pytest -q app/features/confluence_sync/tests/test_retrieval_knowledge_scope.py \
                      app/features/confluence_sync/tests/test_force_rls_managed_postgres.py
   ```

6. **Cut over / roll back.** Cutover is just leaving `DATABASE_URL` pointed at the managed instance.
   **Rollback is a one-line revert** of `DATABASE_URL` in `.env` back to the local/previous DSN — the
   old store is untouched by this procedure. No data is destroyed on either side.

## Gotcha: the test suite reads `DATABASE_URL`

The pytest fixture derives its hermetic `<db>_test` database from `get_settings().database_url`
(`confluence_sync/tests/conftest.py`) and provisions roles as a superuser. While `.env`'s
`DATABASE_URL` points at managed Postgres, `make check` / `make test` will fail role setup. Run the
suite with `DATABASE_URL` overridden to the local docker DSN (as in step 5). This is expected, not a
regression.

## Recorded result — first live run (2026-09-09)

Project `vtpbwkbbkfukfmytlqns`, region `eu-west-1`, session pooler `:5432`, db `postgres`.

- **preflight:** `role='postgres' is_superuser=off`, **pgvector 0.8.2** (gate passed).
  (A preflight bug was fixed this run: the `alembic_version` existence guard put the table in the
  `FROM` of a `WHERE to_regclass(...)` check, which still raised `UndefinedTable` on a pre-migration
  DB — now `to_regclass` is checked first.)
- **migrate:** schema built to `0008_drop_force_rls`; `chunk` confirmed `rowsecurity=t forcerowsecurity=f`,
  policy `chunk_source_read` present.
- **provision-reader:** `rag_reader.<ref>` created; `DATABASE_READER_URL` written to `.env`.
- **corpus load:** `page_source 9 / document 9 / document_version 9 / chunk 85 / source_scope 9`;
  single source `confluence:default`; commit clean; self-FK reverted to non-deferrable.
- **verify-isolation:** owner 85; reader no-GUC **0**; reader scoped **85**; reader bogus **0** —
  ADR-0004 default-deny holds live. (Also proves `rag_reader` authenticates through the pooler.)
- **make eval (live):** retrieval_smoke recall@5 **1.000** / mrr 0.750 / hit_rate@5 1.000;
  ambiguity recall@5 1.000; permission recall@5 0.667; out_of_corpus 0.000 (correct).
- **local isolation suite:** 24 passed; full suite **483 passed**, boundaries clean.
- **Not done (deliberately):** production traffic was **not** switched, and the mixed working tree
  was **not** committed — those are operator decisions. Before any *public* deploy, land **Phase
  11.1a** (the customer-axis fail-open backstop); the source-axis RLS proven here does not cover the
  Mews/Opera/Toast scope axis.
