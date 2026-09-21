# 1.1 Move — Inventory Part 05: JS workspace (`apps/web` → `frontend`)

READ-ONLY inventory. Scope: the pnpm/turbo JS workspace only. Move is **`apps/web` → `frontend`**; `packages/*` stays; the Python app `apps/automation` is untouched.

## Widget's pnpm package NAME (load-bearing)

**`web`** — from `apps/web/package.json` line 2 `"name": "web"`. This is the string `pnpm --filter <name>` uses (Makefile lines 67, 68, 95). **A folder rename does NOT change the package name**, so every `pnpm --filter web …` keeps working with no edit. Do not confuse the folder (`apps/web`→`frontend`) with the package name (`web`, unchanged).

---

## Files that NEED editing

### `pnpm-workspace.yaml`
```
pnpm-workspace.yaml:2:  - "apps/web"
```
- New value: `  - "frontend"` (line 3 `- "packages/*"` stays.)

### `pnpm-lock.yaml` (regenerate; do not hand-edit)
```
pnpm-lock.yaml:15:  apps/web:
```
- The importer key `apps/web:` and its `link:../../packages/contracts` relative specifiers become `frontend:` / `link:../packages/contracts` (frontend is one level shallower). CI runs `pnpm install --frozen-lockfile`, so the lockfile MUST match: run `pnpm install --lockfile-only` (or `pnpm install`) after the move to regenerate, rather than editing by hand.

### `apps/web/src/features/embed/platforms.ts` (→ `frontend/src/features/embed/platforms.ts`)
```
apps/web/src/features/embed/platforms.ts:28:// apps/web/src/features/embed -> repo root is five directories up.
apps/web/src/features/embed/platforms.ts:29:const DEFAULT_PLATFORMS_PATH = resolve(here, "../../../../../config/platforms.json");
```
- Depth-sensitive. `apps/web/src/features/embed` is 5 dirs below root; `frontend/src/features/embed` is 4.
- Line 28 comment → `// frontend/src/features/embed -> repo root is four directories up.`
- Line 29 path → `resolve(here, "../../../../config/platforms.json")` (drop ONE `../`).

### `apps/web/src/features/chat/tests/knowledge-scopes.test.ts` (→ under `frontend/…`)
```
apps/web/src/features/chat/tests/knowledge-scopes.test.ts:17:// apps/web/src/features/chat/tests → repo root is six directories up.
apps/web/src/features/chat/tests/knowledge-scopes.test.ts:18:const canonicalPath = resolve(here, "../../../../../../config/knowledge_scopes.json");
```
- Depth-sensitive. `apps/web/src/features/chat/tests` is 6 dirs below root; `frontend/src/features/chat/tests` is 5.
- Line 17 comment → `// frontend/src/features/chat/tests → repo root is five directories up.`
- Line 18 path → `resolve(here, "../../../../../config/knowledge_scopes.json")` (drop ONE `../`).

---

## Files that DO NOT need editing (verified path-independent)

- `package.json` (root) — scripts are `turbo run dev|build|lint`; no path or workspace-path refs.
- `turbo.json` — task pipeline is glob-based (`.next/**`, `dist/**`); no `apps/*` references.
- `apps/web/package.json` — `"name": "web"` unchanged; deps use `workspace:*` (name-resolved, not path).
- `apps/web/tsconfig.json` — only `paths: { "@/*": ["./src/*"] }` and relative `include`/`exclude`; all relative to the package, survive the move.
- `apps/web/next.config.ts` — `transpilePackages` by package name + a rewrite; no filesystem paths.
- `apps/web/playwright.config.ts` — `testDir: "./e2e"` and localhost URLs; all relative/ports, no repo path.
- `apps/web/vitest.config.ts` — all paths are `__dirname`-relative (`./src`, `./src/test-stubs/…`); jsdom config is inline; survives the move. (No separate jsdom config file exists.)
- `apps/web/postcss.config.mjs`, `apps/web/tailwind.config.ts` — no repo-root paths (tailwind.config has only a `apps/web` mention in a doc comment, see below).
- `Makefile` — uses `pnpm --filter web …` (package name, unchanged) and otherwise only `cd apps/automation`; no `apps/web` path.
- `.github/workflows/ci.yml` — only `cd apps/automation`; JS steps are workspace-wide (`pnpm install`, `make test-ui`). No `apps/web` path.

## Comment-only mentions of `apps/web` (cosmetic; optional cleanup, not functional)

```
packages/contracts/src/index.ts:5     packages/contracts/src/index.ts:31
packages/design-tokens/src/tailwind-theme.ts:4
apps/web/tailwind.config.ts:5
apps/web/e2e/widget-mounts.spec.ts:10
apps/web/src/app/api/test-hosts/[name]/obi-token/route.ts:5
```
These are prose in doc-comments referring to "apps/web"; nothing breaks if left, but update for accuracy when the files move.
