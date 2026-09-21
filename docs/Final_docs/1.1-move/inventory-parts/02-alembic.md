# 1.1 Move · Inventory Part 02 · Alembic

Read-only inventory for the move:
- `apps/automation/alembic/` -> `knowledge-base/migrations/`
- `apps/automation/alembic.ini` -> `knowledge-base/migrations/alembic.ini`
- db package -> `knowledge-base/schema/` (imported as `schema`)

## 1. `apps/automation/alembic.ini`

Path-naming lines (whole file inspected; only the `[alembic]` block names paths):

```
apps/automation/alembic.ini:2: script_location = alembic
apps/automation/alembic.ini:3: prepend_sys_path = .
apps/automation/alembic.ini:4: path_separator = os
```

- `sqlalchemy.url`: NOT present in `alembic.ini`. It is set at runtime in `env.py` (see below).
- No other line in the file names a path (remaining sections are logging config only).

Move implications:
- `script_location = alembic` is relative to the ini's directory. After the move both `alembic.ini` and the `alembic/` tree land under `knowledge-base/migrations/`, so the migration tree will be at `knowledge-base/migrations/alembic/`. Either keep that nesting (value stays `alembic`) or flatten and update this value.
- `prepend_sys_path = .` prepends the ini's directory (`knowledge-base/migrations/`) to `sys.path`. Today with `prepend_sys_path = .` run from `apps/automation/`, the `app` package is importable. After the move, `.` will point at `knowledge-base/migrations/`, which will NOT expose the backend `app` package — relevant to the `app.*` imports below.

## 2. `apps/automation/alembic/env.py`

Top-of-file import + config block, verbatim (lines 1-17):

```
apps/automation/alembic/env.py:1: """Alembic environment. URL and metadata come from application settings/models."""
apps/automation/alembic/env.py:2:
apps/automation/alembic/env.py:3: from __future__ import annotations
apps/automation/alembic/env.py:4:
apps/automation/alembic/env.py:5: from alembic import context
apps/automation/alembic/env.py:6: from sqlalchemy import engine_from_config, pool
apps/automation/alembic/env.py:7:
apps/automation/alembic/env.py:8: from app.platform.config import get_settings
apps/automation/alembic/env.py:9: from app.platform.db.base import Base
apps/automation/alembic/env.py:10:
apps/automation/alembic/env.py:11: # register models on the metadata
apps/automation/alembic/env.py:12: from app.platform.db import models  # noqa: F401
apps/automation/alembic/env.py:13:
apps/automation/alembic/env.py:14: config = context.config
apps/automation/alembic/env.py:15: config.set_main_option("sqlalchemy.url", get_settings().database_url)
apps/automation/alembic/env.py:16:
apps/automation/alembic/env.py:17: target_metadata = Base.metadata
```

Every import in env.py:

```
apps/automation/alembic/env.py:5: from alembic import context
apps/automation/alembic/env.py:6: from sqlalchemy import engine_from_config, pool
apps/automation/alembic/env.py:8: from app.platform.config import get_settings
apps/automation/alembic/env.py:9: from app.platform.db.base import Base
apps/automation/alembic/env.py:12: from app.platform.db import models  # noqa: F401
```

`set_main_option` / `sqlalchemy.url` lines:

```
apps/automation/alembic/env.py:15: config.set_main_option("sqlalchemy.url", get_settings().database_url)
apps/automation/alembic/env.py:22:         url=config.get_main_option("sqlalchemy.url"),
```

No `sys.path` manipulation exists inside `env.py` (path setup is delegated to `prepend_sys_path` in `alembic.ini`).

### Backend (`app.*`) imports — MOVE BLOCKER

`env.py` imports `app.platform.config` (a backend module):
- `env.py:8: from app.platform.config import get_settings` — YES, imports `app.platform.config`.

It also depends on two more backend modules:
- `env.py:9: from app.platform.db.base import Base`
- `env.py:12: from app.platform.db import models`

After the move, migrations live under `knowledge-base/` and MUST NOT import `app.*`. All three imports (lines 8, 9, 12) plus the `set_main_option` at line 15 (which calls `get_settings().database_url`) must be reworked to source the URL and metadata without the backend `app` package — e.g. from `schema` (the moved db package) and from an env var / alembic config, not `app.platform.config`.

## 3. `apps/automation/alembic/versions/*.py` importing from `app.platform.db`

Twelve version files exist (`0001`–`0012`). Four import from `app.platform.db` (the moved db package; import symbol is `schema`, not an `enums` module here):

```
apps/automation/alembic/versions/0001_core_schema.py:18: from app.platform.db import schema
apps/automation/alembic/versions/0002_provider_tags_and_rls.py:29: from app.platform.db import schema
apps/automation/alembic/versions/0009_reconcile_non_chunk_rls.py:33: from app.platform.db import schema
apps/automation/alembic/versions/0010_customer_scope_rls.py:34: from app.platform.db import schema
```

After the move these become `from schema import schema` (or equivalent), since the db package moves to `knowledge-base/schema/` and is imported as `schema`. The other eight version files (0003–0008, 0011, 0012) have no `app.*` import.
