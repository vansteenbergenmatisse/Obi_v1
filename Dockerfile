# Obi backend image — deploys the FastAPI app + its in-process ingestion worker.
#
# IMPORTANT: build context MUST be the repo root, not backend/. The backend imports the
# `schema` package from ../knowledge-base (editable path dep in backend/pyproject.toml) and
# resolves its config JSON via Path(__file__).resolve().parents[4], i.e. it expects
# backend/ and knowledge-base/ to be siblings under one root. We reproduce that here as
# /app/backend + /app/knowledge-base + /app/config so both the import and the config-path
# resolution work unchanged in the container.
#
#   docker build -t obi-backend .
#
# Run exactly ONE instance: the APScheduler worker, rate limiter and caches are in-process.

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# uv: install into the project's own .venv, copy (not hardlink) from the cache so the layer is
# self-contained, and never touch the network at container start (the venv is fully built here).
ENV UV_PROJECT_ENVIRONMENT=/app/backend/.venv \
    UV_LINK_MODE=copy \
    UV_NO_SYNC=1 \
    PYTHONUNBUFFERED=1

# Copy the two Python trees as siblings, preserving the layout the code depends on.
# knowledge-base first: it is the editable dependency the backend resolves during sync.
COPY knowledge-base/ /app/knowledge-base/
COPY backend/ /app/backend/
# Repo-root config/ holds obi_identity.md, resolved at /app/config/obi_identity.md.
COPY config/ /app/config/

WORKDIR /app/backend

# Resolve exactly the locked dependency set. --no-dev drops pytest/ruff/pyright; --extra attachments
# installs the native document parsers (pypdf/docx/xlsx) so ingestion parses attachments rather than
# skipping them. Local embeddings (sentence-transformers) are intentionally omitted — prod uses a
# hosted embedding provider.
RUN uv sync --frozen --no-dev --extra attachments

EXPOSE 8000

# `exec` makes uvicorn PID 1 so the platform's SIGTERM reaches it directly (graceful shutdown of
# in-flight ingestion jobs on redeploy); `sh -c` expands ${PORT} (set by the platform), default 8000.
# Single uvicorn process — do NOT add --workers, it would double-run the in-process scheduler.
CMD ["sh", "-c", "exec .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
