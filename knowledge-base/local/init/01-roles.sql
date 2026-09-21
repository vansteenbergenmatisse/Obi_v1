-- Roles for source-level Row-Level Security (ADR-0004).
--
-- Runs once, on a FRESH data volume, via the postgres image's /docker-entrypoint-initdb.d hook.
-- The compose POSTGRES_USER (`rag`) is the owner/superuser and acts as the WRITER — it bypasses
-- RLS, which is what lets ingestion/worker/reconcile write freely. This script adds the non-owner
-- READER role that retrieval connects as, so the chunk_source_read policy actually constrains it.
--
-- Grants use ALTER DEFAULT PRIVILEGES so tables created LATER by `alembic upgrade` are covered,
-- plus a GRANT over any tables that already exist. The password is a local-dev default — override
-- it (and DATABASE_READER_URL) in real deployments.

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rag_reader') THEN
    CREATE ROLE rag_reader LOGIN PASSWORD 'rag_reader'
      NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
  END IF;
END
$$;

GRANT USAGE ON SCHEMA public TO rag_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO rag_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO rag_reader;
