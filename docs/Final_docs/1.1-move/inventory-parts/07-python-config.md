# 07 · Python config inventory (`apps/automation/pyproject.toml`)

Source: `apps/automation/pyproject.toml`. The dir moves to `backend/`, keeping the inner `app/` package.
Because `app/` is kept as-is, every path-based config (`packages`, `include`, `testpaths`, `venv`) stays valid unchanged.

## `[project]` — name, dependencies, optional-dependencies

```toml
1  [project]
2  name = "omniboost-rag-automation"
3  dynamic = ["version"]
4  description = "Confluence-native RAG automation service: sync, ingestion, retrieval, RAG agent, evals"
5  requires-python = ">=3.12,<3.14"
6  dependencies = [
7      "fastapi>=0.115",
8      "uvicorn[standard]>=0.32",
9      "pydantic>=2.9",
10     "pydantic-settings>=2.5",
11     "sqlalchemy>=2.0.35",
12     "alembic>=1.13",
13     "psycopg[binary]>=3.2",
14     "pgvector>=0.3.6",
15     "httpx>=0.27",
16     "tenacity>=9.0",
17     "apscheduler>=3.10",
18     "structlog>=24.4",
19     "python-dotenv>=1.0",
20     "pyjwt[crypto]>=2.14.0",
25     "tiktoken>=0.8",
26 ]
28 [project.optional-dependencies]
29 dev = [
30     "pytest>=8.3",
31     "pytest-asyncio>=0.24",
32     "ruff>=0.7",
33     "pyright>=1.1.380",
35     "beautifulsoup4>=4.12",
36 ]
39 tokenizers = ["tiktoken>=0.8"]
41 attachments = ["pypdf>=5.0", "python-docx>=1.1", "openpyxl>=3.1"]
43 local-embeddings = ["sentence-transformers>=3.0"]
```

- Move effect: name/description/deps/optional-deps all stay. **ADD** to `dependencies`: `"obi-knowledge-base"` (the new `schema` package, dist name `obi-knowledge-base`) as a workspace member dependency, plus a `[tool.uv.sources]` entry pinning it to the workspace.

## `[build-system]` + hatch build (lines 45–53)

```toml
45 [build-system]
46 requires = ["hatchling"]
47 build-backend = "hatchling.build"
49 [tool.hatch.version]
50 path = "app/__init__.py"
52 [tool.hatch.build.targets.wheel]
53 packages = ["app"]
```

- Move effect: unchanged — `app/` package is kept, so `packages = ["app"]` and version path stay valid.

## `[tool.ruff]` (lines 55–60)

```toml
55 [tool.ruff]
56 line-length = 100
57 target-version = "py312"
59 [tool.ruff.lint]
60 select = ["E", "F", "I", "UP", "B", "SIM"]
```

- Move effect: unchanged (no paths).

## `[tool.pytest.ini_options]` (lines 62–69)

```toml
62 [tool.pytest.ini_options]
63 asyncio_mode = "auto"
64 testpaths = ["app", "tests"]
65 python_files = ["test_*.py", "*_test.py"]
66 addopts = "--strict-markers"
67 markers = [
68     "db: requires a real local Postgres with migrations applied (substep 0.5.1, harness.md)",
69 ]
```

- Move effect: `testpaths = ["app", "tests"]` stays valid — both relative to the (moved) package root.

## `[tool.pyright]` (lines 71–76)

```toml
71 [tool.pyright]
72 include = ["app"]
73 pythonVersion = "3.12"
74 typeCheckingMode = "basic"
75 venvPath = "."
76 venv = ".venv"
```

- Move effect: unchanged — `include = ["app"]` and `venv = ".venv"` are relative to the package root.

## `[tool.uv]` / `[tool.coverage]`

- **No `[tool.uv]` section** in this file today. **No `[tool.coverage]` section.**
- Move effect: a `[tool.uv.sources]` section (pointing `obi-knowledge-base` at `{ workspace = true }`) is an **ADD** here; the top-level workspace `[tool.uv.workspace] members = [...]` is an **ADD** at the new root.

## Root pyproject / uv.lock

- **No root-level `pyproject.toml` exists today** (only `apps/automation/pyproject.toml`; the JS side is separate). No `[tool.uv]` workspace is declared anywhere.
- **`uv.lock` lives at `apps/automation/uv.lock`** — the single lockfile, co-located with the only Python project.
- Move effect: introducing the uv workspace means a new **root `pyproject.toml`** with `[tool.uv.workspace]` and a **single root `uv.lock`** (uv keeps one lock at the workspace root); the current `apps/automation/uv.lock` moves under the workspace root accordingly.
