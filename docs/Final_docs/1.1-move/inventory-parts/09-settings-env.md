# 09 · settings.py + env path defaults

## Tag-list (knowledge_scopes.json) default path — CRITICAL

`settings.py` does NOT compute the tag-list path itself. It imports `load_recognized_knowledge_scopes` from `knowledge_scopes.py`, which hardcodes the default relative to `__file__`:

- `apps/automation/app/platform/config/knowledge_scopes.py:17-19`: `DEFAULT_KNOWLEDGE_SCOPES_PATH = Path(__file__).resolve().parents[5] / "config" / "knowledge_scopes.json"` — 5 levels up from the module file = **repo-root `config/`**. No env override exists for this path.
- Same pattern for platforms: `apps/automation/app/platform/config/platforms.py:23`: `DEFAULT_PLATFORMS_PATH = Path(__file__).resolve().parents[5] / "config" / "platforms.json"` (overridable via `PLATFORMS_PATH` env).
- Obi identity: `settings.py:29`: `DEFAULT_OBI_IDENTITY_PATH = Path(__file__).resolve().parents[5] / "config" / "obi_identity.md"` — note **parents[5]** from `settings.py` (deeper file, `.../config/settings.py`) still resolves to repo-root `config/`. Overridable via `obi_identity_path`.

Move impact: all three `parents[5] / "config"` anchors break once `config/` moves. When `settings.py`/`platforms.py`/`knowledge_scopes.py` themselves move under `backend/` (apps/automation->backend), BOTH the `parents[N]` depth AND the `config/`->`knowledge-base/config/` target change.

## Env-based path defaults / references (values redacted)

- `settings.py:34`: `env_file=(".env", "../../.env")` — relative to CWD (backend folder + repo root).
- `settings.py:250`: `platforms_path: str = ""` (empty -> repo-root default above); `PLATFORMS_PATH=<redacted>` set in `.env:96` and `apps/web/.env.local:169`.
- `settings.py:257`: `obi_identity_path: str = ""` (empty -> repo-root default).
- `.env.example:63`: comment references `infra/foundation/init/01-roles.sql` (moves -> `knowledge-base/local`).
- `.env.example:129` / `.env:79`: comment says scopes live in `apps/automation/config/knowledge_scopes.json` — STALE: actual code default is repo-root `config/knowledge_scopes.json`.
- `apps/web/.env.example:19`: comment example `config/platforms.local.json`.
- No compose-file or data-dir path default found in settings.py.
