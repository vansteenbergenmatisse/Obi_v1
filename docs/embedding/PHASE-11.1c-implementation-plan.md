# Phase 11.1c — Obi Embed + JWT Edge Binding — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let any platform (Mews, Toast, Opera Cloud, an Omniboost app) embed Obi with one `obi.js` script tag, where a per-click platform-signed JWT — verified server-side — replaces the caller-self-reported `knowledgeScope`, so the customer/integration boundary is bound at the edge instead of trusted from the caller.

**Architecture:** The platform's own server signs a short-lived JWT (`iss`, `aud=obi`, `sub`, `iat`, `exp`, and either all three business values `company_id`/`company_name`/`integration` or none). `obi.js` fetches it at button-click, holds it in memory, posts it into the Obi iframe, and sends it as `Authorization: Bearer <jwt>` on every `POST /api/chat`. The Next proxy forwards the host key on `Authorization` and the JWT on a distinct `X-Obi-Token` header. The Obi backend verifies the JWT (alg allow-list, JWKS-by-`kid`, `iss` ∈ `platforms.json`, `aud`, `exp`) and builds one frozen `AuthContext` whose `allowed_scopes` drive `apply_knowledge_scope` on every reader transaction — on top of the DB backstop from Phase 11.1a (ADR-0014). No token ever touches URL / cookie / web-storage / server log / trace row (only a hash of `sub` is traced).

**Tech Stack:** Backend — Python 3.12, FastAPI, Pydantic v2, SQLAlchemy, Alembic, `pyjwt[crypto]` (new, RS256/ES256 + `PyJWKClient` JWKS-by-`kid`). Frontend — Next.js (App Router), TypeScript strict, no new runtime deps (vanilla loader compiled to `public/obi.js`). Contracts — `@omniboost/contracts` (TS + JSON Schema). DB — Postgres + pgvector on Supabase, RLS per ADR-0004 / ADR-0014.

**Spec:** [`docs/embedding/PHASE-11.1c-obi-embed-jwt-spec.md`](./PHASE-11.1c-obi-embed-jwt-spec.md) (design of record) + [`docs/adr/0014-Customer-Scope-Isolation-Backstop.md`](../adr/0014-Customer-Scope-Isolation-Backstop.md) (the GUC/RLS contract this binds to). Ledger: `docs/rag/PLAN.md` §0.

## Global Constraints

- **Feature layout (root `CLAUDE.md`):** backend code lives under `apps/automation/app/features/<feature>/` (domain/application/infrastructure/server split) and `apps/automation/app/platform/config/`. Cross-feature imports go through the feature's public `__init__.py` root only; run `make boundaries` before every commit (must exit 0).
- **Package managers do not mix:** `uv` for `apps/automation`, `pnpm` for the JS/TS workspace. Add the JWT dep with `uv add`, never `pip`.
- **No-regression, not zero:** do not let whole-repo Ruff/Pyright counts rise above the ADR-0003 D1 baseline (Ruff 2/15, Pyright 34/1); bring every file you touch clean. Do not reformat files you did not otherwise edit.
- **Test DB:** the hermetic settings fixture uses `omniboost_rag_test`. While `.env` points at Supabase, `make check` needs `DATABASE_URL=<local docker DSN>` as an override (the fixture provisions roles as superuser). `make up` first.
- **Security gate (CLAUDE.local.md rule 2):** every new/changed HTTP or LLM surface runs the `securing-http-and-llm-endpoints` controls. No secret is ever interpolated into SQL or logged; GUCs are set with bound `set_config(..., true)` params only (never string-interpolated).
- **Scope-slug mapping (spec drift #2 — CONFIRMED by operator 2026-09-12):** the JWT `integration` claim carries the **platform key** (`mews`, `toast`, `opera-cloud`) as the human-friendly wire value; `platforms.json`'s `integrations` map resolves that key to the **live `obi-*-test` slugs** (`obi-mews-test`, `obi-toast-test`, `obi-operacloud-test`) plus `obi-general-test`. The recognized-scope vocabulary in `config/knowledge_scopes.json` is NOT renamed. Startup validation rejects any mapped slug not present in `knowledge_scopes.json`.
- **v1 scope (operator decisions, spec §6):** integration-level content scoping only. `principal` stays `None` for embedded users (open Confluence pages only, no per-person page ACL). Body `principal` is always ignored. Token lifetime default 60 min, per platform in `platforms.json`, fetched at button-click. A note with no business values → `general` only (not refused); an unknown `integration` → 401.
- **`allowed_sources` in v1:** every platform uses `("confluence:default",)` — identical to the retriever's existing constructor default. `AuthContext` carries `allowed_sources` for completeness and the future source axis, but v1 threads only `allowed_scopes` per-request; the source GUC keeps being set from the retriever's construction-time default (unchanged). Do not add a per-request sources signature in v1.
- **Message types are exactly three:** `obi:open`, `obi:token`, `obi:clear`. No others.
- **Operator prerequisites (block the *live* done-when checks, not local dev):** (a) migration `0010` applied to Supabase (`0009`→`0010`) — see Task F2; (b) real platform `issuer` / `jwks_url` / `domains` / `integration` values for Mews, Toast, Opera Cloud (kept **inactive** until provided); (c) test companies (one per integration) + one test user in a restricted Confluence group. None of these block local docker development or the test-host proof.

---

## File Structure

**Backend (`apps/automation/`)**
- Create `config/platforms.json` — platform + integration registry (repo-root `config/`, beside `knowledge_scopes.json`).
- Create `app/platform/config/platforms.py` — loader + startup validation, `PlatformRegistry`.
- Create `app/features/rag_agent/application/auth_context.py` — frozen `AuthContext` + builder from verified claims.
- Create `app/features/rag_agent/server/token_verifier.py` — JWT verification (alg allow-list, JWKS-by-`kid`, claim checks).
- Modify `app/features/rag_agent/server/router.py` — new `X-Obi-Token` dependency, `AuthContext` wiring into `post_chat`, body-scope validation, rate-limit key = hash(`sub`).
- Modify `app/features/rag_agent/application/answer_service.py` — `answer(history, auth: AuthContext)`; `AnswerProvider` protocol.
- Modify `app/features/rag_agent/application/answer_cache.py` — cache key derived from `AuthContext`.
- Modify `app/features/rag_agent/__init__.py` — export `AuthContext`, `PlatformRegistry` re-exports as needed.
- Modify `app/platform/config/settings.py` — `platforms_path` / registry accessor; drop no single-issuer vars (none exist).
- Create `alembic/versions/0011_query_trace_subject_hash.py` + modify `app/platform/db/models.py` (`QueryTrace.subject_hash`) + modify `app/features/retrieval/infrastructure/trace_repo.py`.

**Frontend (`apps/web/`)**
- Create `src/app/embed/page.tsx` — the iframe frame (button + chat) with per-request CSP `frame-ancestors`.
- Create `src/features/embed/iframe-bridge.ts` — frame-side postMessage receiver + Bearer sender.
- Create `src/features/embed/loader.ts` — the `Obi.init` / `Obi.clear` loader, compiled to `public/obi.js`.
- Create `src/features/embed/index.ts` — feature public root.
- Modify `src/features/chat/server/route-handlers.ts` + `src/platform/automation-api/client.ts` — forward the incoming `Authorization` JWT as `X-Obi-Token` next to the host key.
- Modify `src/features/chat/api/chat-client.ts` — send `Authorization: Bearer <jwt>` (frame path).
- Delete `src/features/chat/api/access-token.ts` + `src/features/chat/server/auth.ts` (retire the pilot invite token) + untangle their callers.
- Create `src/app/test-hosts/{none,mews,toast,opera-cloud}/page.tsx` + `src/app/api/test-hosts/[name]/obi-token/route.ts` — test host pages + note endpoints.
- Create `src/app/.well-known/[issuer]/obi-jwks.json` route (or per-issuer static) — test JWKS.

**Contracts (`packages/contracts/`)**
- Create `src/token-claims.json` (JSON Schema for the note) + `src/iframe-messages.ts` (the three message types); export from `src/index.ts`.

**Docs / ops**
- Create `docs/embedding/{mews,toast,opera-cloud}.md` — hand-over packs.
- Modify `docs/rag/retrieval/phase-11.md` (or add `phase-11.1c.md`) + `docs/rag/PLAN.md §0`.

---

## Task Group A — Backend: platform registry, JWT verification, AuthContext

### Task A1: Platform registry (`platforms.json` + loader + startup validation)

**Files:**
- Create: `config/platforms.json` (repo root)
- Create: `apps/automation/app/platform/config/platforms.py`
- Test: `apps/automation/app/platform/config/tests/test_platforms.py`
- Modify: `apps/automation/app/platform/config/settings.py` (add `platforms_path` field + `platform_registry` accessor)

**Interfaces:**
- Produces: `PlatformEntry` (frozen: `key: str`, `issuer: str`, `jwks_url: str`, `domains: tuple[str, ...]`, `lifetime_minutes: int`, `algs: tuple[str, ...]`, `active: bool`); `PlatformRegistry` with `.by_issuer(iss: str) -> PlatformEntry | None`, `.scopes_for(integration: str) -> list[str] | None` (None = unknown integration → caller raises 401), `.active_domains() -> list[str]`; `load_platform_registry(platforms_path: Path, recognized_scopes: frozenset[str], *, allow_empty: bool) -> PlatformRegistry`.

- [ ] **Step 1: Write `config/platforms.json`** (repo root, beside `knowledge_scopes.json`)

```json
{
  "_readme": "Platform registry for Obi embed (Phase 11.1c, ADR-0014). 'platforms' = trusted JWT issuers keyed by platform key; the platform key is the JWT 'integration' wire value. 'integrations' maps that key to the live obi-*-test knowledge scopes from config/knowledge_scopes.json. Entries with active=false are skipped by the frame CSP and the frontend loader but STILL verify tokens if one arrives. obi-general-test is always appended; 'classified' is never mappable.",
  "platforms": {
    "mews":        { "issuer": "https://app.mews.com",     "jwks_url": "https://app.mews.com/.well-known/obi-jwks.json",     "domains": ["app.mews.com"],     "lifetime_minutes": 60, "algs": ["RS256", "ES256"], "active": false },
    "toast":       { "issuer": "https://pos.toasttab.com", "jwks_url": "https://pos.toasttab.com/.well-known/obi-jwks.json", "domains": ["pos.toasttab.com"], "lifetime_minutes": 60, "algs": ["RS256", "ES256"], "active": false },
    "opera-cloud": { "issuer": "PLACEHOLDER",              "jwks_url": "PLACEHOLDER",                                        "domains": [],                  "lifetime_minutes": 60, "algs": ["RS256", "ES256"], "active": false }
  },
  "integrations": {
    "mews":        ["obi-mews-test", "obi-general-test"],
    "toast":       ["obi-toast-test", "obi-general-test"],
    "opera-cloud": ["obi-operacloud-test", "obi-general-test"]
  }
}
```

> Real `issuer`/`jwks_url`/`domains` come from the operator per platform (hand-over packs, Task F1). `active` stays `false` until both are filled. `test-*` issuer entries (Task E) are added here in local/staging config only.

- [ ] **Step 2: Write the failing loader test**

```python
# apps/automation/app/platform/config/tests/test_platforms.py
from pathlib import Path
import json
import pytest
from app.platform.config.platforms import load_platform_registry

RECOGNIZED = frozenset({"obi-general-test", "obi-mews-test", "obi-toast-test", "obi-operacloud-test"})

def _write(tmp_path: Path, data: dict) -> Path:
    p = tmp_path / "platforms.json"
    p.write_text(json.dumps(data))
    return p

def test_maps_platform_key_to_live_slugs(tmp_path):
    p = _write(tmp_path, {
        "platforms": {"mews": {"issuer": "https://app.mews.com", "jwks_url": "https://app.mews.com/j", "domains": ["app.mews.com"], "lifetime_minutes": 60, "algs": ["RS256"], "active": True}},
        "integrations": {"mews": ["obi-mews-test", "obi-general-test"]},
    })
    reg = load_platform_registry(p, RECOGNIZED, allow_empty=False)
    assert reg.by_issuer("https://app.mews.com").key == "mews"
    assert reg.scopes_for("mews") == ["obi-general-test", "obi-mews-test"]  # sorted, general always present
    assert reg.scopes_for("unknown") is None
    assert reg.active_domains() == ["app.mews.com"]

def test_unknown_slug_in_integrations_stops_startup(tmp_path):
    p = _write(tmp_path, {
        "platforms": {"mews": {"issuer": "i", "jwks_url": "j", "domains": ["d"], "lifetime_minutes": 60, "algs": ["RS256"], "active": True}},
        "integrations": {"mews": ["obi-not-a-real-scope"]},
    })
    with pytest.raises(ValueError, match="not in knowledge_scopes"):
        load_platform_registry(p, RECOGNIZED, allow_empty=False)

def test_empty_platforms_stops_startup_when_not_allowed(tmp_path):
    p = _write(tmp_path, {"platforms": {}, "integrations": {}})
    with pytest.raises(ValueError, match="no platforms"):
        load_platform_registry(p, RECOGNIZED, allow_empty=False)

def test_empty_platforms_allowed_locally(tmp_path):
    p = _write(tmp_path, {"platforms": {}, "integrations": {}})
    reg = load_platform_registry(p, RECOGNIZED, allow_empty=True)
    assert reg.active_domains() == []

def test_general_always_appended_even_if_omitted(tmp_path):
    p = _write(tmp_path, {
        "platforms": {"mews": {"issuer": "i", "jwks_url": "j", "domains": ["d"], "lifetime_minutes": 60, "algs": ["RS256"], "active": True}},
        "integrations": {"mews": ["obi-mews-test"]},
    })
    reg = load_platform_registry(p, RECOGNIZED, allow_empty=False)
    assert "obi-general-test" in reg.scopes_for("mews")

def test_classified_scope_is_never_mappable(tmp_path):
    p = _write(tmp_path, {
        "platforms": {"mews": {"issuer": "i", "jwks_url": "j", "domains": ["d"], "lifetime_minutes": 60, "algs": ["RS256"], "active": True}},
        "integrations": {"mews": ["classified", "obi-general-test"]},
    })
    with pytest.raises(ValueError, match="classified"):
        load_platform_registry(p, RECOGNIZED, allow_empty=False)
```

- [ ] **Step 3: Run to verify failure** — `DATABASE_URL=<local dsn> uv run pytest app/platform/config/tests/test_platforms.py -v` → FAIL (`ModuleNotFoundError: app.platform.config.platforms`).

- [ ] **Step 4: Implement the loader**

```python
# apps/automation/app/platform/config/platforms.py
"""Platform + integration registry for Obi embed (Phase 11.1c, ADR-0014).

The JWT 'integration' claim carries the platform KEY (e.g. "mews"); this registry
maps that key to the live obi-*-test knowledge scopes and holds the trusted-issuer
verification config. Validated at startup: every mapped scope must exist in
config/knowledge_scopes.json; 'classified' is never mappable; empty platforms stops
startup outside local (allow_empty=False)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

_GENERAL = "obi-general-test"
_FORBIDDEN = frozenset({"classified"})

DEFAULT_PLATFORMS_PATH = Path(__file__).resolve().parents[5] / "config" / "platforms.json"


@dataclass(frozen=True, slots=True)
class PlatformEntry:
    key: str
    issuer: str
    jwks_url: str
    domains: tuple[str, ...]
    lifetime_minutes: int
    algs: tuple[str, ...]
    active: bool


@dataclass(frozen=True, slots=True)
class PlatformRegistry:
    _by_issuer: dict[str, PlatformEntry]
    _scopes: dict[str, tuple[str, ...]]

    def by_issuer(self, iss: str) -> PlatformEntry | None:
        return self._by_issuer.get(iss)

    def scopes_for(self, integration: str) -> list[str] | None:
        scopes = self._scopes.get(integration)
        return list(scopes) if scopes is not None else None

    def active_domains(self) -> list[str]:
        out: list[str] = []
        for e in self._by_issuer.values():
            if e.active:
                out.extend(e.domains)
        return sorted(set(out))


def load_platform_registry(
    platforms_path: Path,
    recognized_scopes: frozenset[str],
    *,
    allow_empty: bool,
) -> PlatformRegistry:
    data = json.loads(platforms_path.read_text())
    platforms = data.get("platforms", {})
    integrations = data.get("integrations", {})

    if not platforms and not allow_empty:
        raise ValueError("platforms.json has no platforms outside local")

    by_issuer: dict[str, PlatformEntry] = {}
    for key, raw in platforms.items():
        entry = PlatformEntry(
            key=key,
            issuer=str(raw["issuer"]),
            jwks_url=str(raw["jwks_url"]),
            domains=tuple(str(d) for d in raw.get("domains", [])),
            lifetime_minutes=int(raw["lifetime_minutes"]),
            algs=tuple(str(a) for a in raw["algs"]),
            active=bool(raw.get("active", False)),
        )
        if "HS256" in entry.algs:
            raise ValueError(f"platform {key}: HS256 is forbidden")
        by_issuer[entry.issuer] = entry

    scopes: dict[str, tuple[str, ...]] = {}
    for integration, slugs in integrations.items():
        resolved = set()
        for slug in slugs:
            s = str(slug).strip().lower()
            if s in _FORBIDDEN:
                raise ValueError(f"integration {integration}: '{s}' is never mappable")
            if s not in recognized_scopes:
                raise ValueError(f"integration {integration}: '{s}' not in knowledge_scopes.json")
            resolved.add(s)
        resolved.add(_GENERAL)
        scopes[integration] = tuple(sorted(resolved))

    return PlatformRegistry(_by_issuer=by_issuer, _scopes=scopes)
```

- [ ] **Step 5: Wire into `settings.py`** — add a field and a cached accessor mirroring `knowledge_scope_set`:

```python
# in class Settings(BaseSettings)
platforms_path: str = ""  # empty => DEFAULT_PLATFORMS_PATH
allow_empty_platforms: bool = False  # set True in the local .env / test fixture

@cached_property
def platform_registry(self) -> PlatformRegistry:
    from app.platform.config.platforms import DEFAULT_PLATFORMS_PATH, load_platform_registry
    path = Path(self.platforms_path) if self.platforms_path else DEFAULT_PLATFORMS_PATH
    return load_platform_registry(path, self.knowledge_scope_set, allow_empty=self.allow_empty_platforms)
```

Set `allow_empty_platforms=True` in the hermetic test settings fixture so unrelated tests don't need a `platforms.json`. Add a startup validator that touches `settings.platform_registry` in `main.py`'s lifespan (fail fast) — mirror `_require_general_knowledge_scope`.

- [ ] **Step 6: Run tests** — `DATABASE_URL=<local dsn> uv run pytest app/platform/config/tests/test_platforms.py -v` → PASS. `make boundaries` → 0.

- [ ] **Step 7: Commit** — `git commit -m "feat(embed): platform+integration registry with startup validation (11.1c A1)"`

---

### Task A2: `AuthContext` (frozen edge identity)

**Files:**
- Create: `apps/automation/app/features/rag_agent/application/auth_context.py`
- Test: `apps/automation/app/features/rag_agent/tests/test_auth_context.py`
- Modify: `apps/automation/app/features/rag_agent/__init__.py` (export `AuthContext`, `build_auth_context`, `general_only_context`)

**Interfaces:**
- Consumes: `PlatformRegistry` (A1).
- Produces: `AuthContext` (frozen: `company_id: str | None`, `company_name: str | None`, `integration: str | None`, `allowed_scopes: tuple[str, ...]`, `allowed_sources: tuple[str, ...]`, `principal: str | None`, `token_subject: str | None`); `build_auth_context(claims: VerifiedClaims, registry: PlatformRegistry) -> AuthContext` (raises `UnknownIntegrationError` → caller maps to 401); `general_only_context() -> AuthContext` (the tokenless/internal path: general-only, `principal=None`). `VerifiedClaims` is the frozen output of Task A3.

- [ ] **Step 1: Write the failing test** (includes done-when 3a — `company_id`-only differences do not change scopes)

```python
# apps/automation/app/features/rag_agent/tests/test_auth_context.py
import pytest
from app.platform.config.platforms import load_platform_registry
from app.features.rag_agent.application.auth_context import (
    AuthContext, build_auth_context, general_only_context, UnknownIntegrationError,
)
from app.features.rag_agent.server.token_verifier import VerifiedClaims

# build a small registry inline via a tmp file (reuse the A1 helper pattern) ...
def _registry(tmp_path):
    import json
    p = tmp_path / "platforms.json"
    p.write_text(json.dumps({
        "platforms": {"mews": {"issuer": "https://app.mews.com", "jwks_url": "j", "domains": ["app.mews.com"], "lifetime_minutes": 60, "algs": ["RS256"], "active": True}},
        "integrations": {"mews": ["obi-mews-test", "obi-general-test"]},
    }))
    return load_platform_registry(p, frozenset({"obi-general-test", "obi-mews-test"}), allow_empty=False)

def _claims(**over):
    base = dict(issuer="https://app.mews.com", subject="u1", company_id="c1", company_name="Hotel", integration="mews")
    base.update(over)
    return VerifiedClaims(**base)

def test_builds_scoped_context(tmp_path):
    ctx = build_auth_context(_claims(), _registry(tmp_path))
    assert ctx.integration == "mews"
    assert ctx.allowed_scopes == ("obi-general-test", "obi-mews-test")
    assert ctx.principal is None                       # v1: embedded users are principal-less
    assert ctx.allowed_sources == ("confluence:default",)
    assert ctx.token_subject == "u1"

def test_company_id_only_difference_yields_identical_scopes(tmp_path):
    reg = _registry(tmp_path)
    a = build_auth_context(_claims(company_id="c1"), reg)
    b = build_auth_context(_claims(company_id="c2"), reg)
    assert a.allowed_scopes == b.allowed_scopes          # done-when 3a (replaces the dropped mews-2 browser proof)

def test_no_business_values_is_general_only(tmp_path):
    ctx = build_auth_context(_claims(company_id=None, company_name=None, integration=None), _registry(tmp_path))
    assert ctx.allowed_scopes == ("obi-general-test",)
    assert ctx.integration is None

def test_unknown_integration_raises(tmp_path):
    with pytest.raises(UnknownIntegrationError):
        build_auth_context(_claims(integration="wordpress"), _registry(tmp_path))

def test_general_only_context_helper():
    ctx = general_only_context()
    assert ctx.allowed_scopes == ("obi-general-test",)
    assert ctx.token_subject is None and ctx.principal is None
```

- [ ] **Step 2: Run to verify failure** → FAIL (module missing).

- [ ] **Step 3: Implement**

```python
# apps/automation/app/features/rag_agent/application/auth_context.py
from __future__ import annotations
from dataclasses import dataclass
from app.platform.config.platforms import PlatformRegistry
from app.features.rag_agent.server.token_verifier import VerifiedClaims

_DEFAULT_SOURCES = ("confluence:default",)


class UnknownIntegrationError(ValueError):
    """The verified integration claim is not in the platform registry -> 401."""


@dataclass(frozen=True, slots=True)
class AuthContext:
    company_id: str | None
    company_name: str | None
    integration: str | None
    allowed_scopes: tuple[str, ...]
    allowed_sources: tuple[str, ...]
    principal: str | None
    token_subject: str | None


def general_only_context() -> AuthContext:
    return AuthContext(None, None, None, ("obi-general-test",), _DEFAULT_SOURCES, None, None)


def build_auth_context(claims: VerifiedClaims, registry: PlatformRegistry) -> AuthContext:
    if claims.integration is None:
        # no business values -> general only, still identified by subject
        return AuthContext(
            company_id=None, company_name=None, integration=None,
            allowed_scopes=("obi-general-test",), allowed_sources=_DEFAULT_SOURCES,
            principal=None, token_subject=claims.subject,
        )
    scopes = registry.scopes_for(claims.integration)
    if scopes is None:
        raise UnknownIntegrationError(claims.integration)
    return AuthContext(
        company_id=claims.company_id, company_name=claims.company_name, integration=claims.integration,
        allowed_scopes=tuple(scopes), allowed_sources=_DEFAULT_SOURCES,
        principal=None,  # v1: embedded users have no per-person Confluence ACL
        token_subject=claims.subject,
    )
```

- [ ] **Step 4: Export** from `rag_agent/__init__.py`: `AuthContext`, `build_auth_context`, `general_only_context`, `UnknownIntegrationError`.

- [ ] **Step 5: Run tests** → PASS. `make boundaries` → 0.

- [ ] **Step 6: Commit** — `git commit -m "feat(embed): frozen AuthContext + integration->scope resolution (11.1c A2)"`

---

### Task A3: JWT verifier (`token_verifier.py`)

**Files:**
- Modify: `apps/automation/pyproject.toml` (`uv add "pyjwt[crypto]"`)
- Create: `apps/automation/app/features/rag_agent/server/token_verifier.py`
- Test: `apps/automation/app/features/rag_agent/tests/test_token_verifier.py`

**Interfaces:**
- Consumes: `PlatformRegistry` (A1).
- Produces: `VerifiedClaims` (frozen: `issuer: str`, `subject: str`, `company_id: str | None`, `company_name: str | None`, `integration: str | None`); `TokenError(Exception)` (all verification failures → the router maps to a bare 401, no detail); `TokenVerifier(registry, *, jwks_client_factory=...)` with `.verify(token: str) -> VerifiedClaims`. JWKS clients (`jwt.PyJWKClient`) are built once per issuer and cached; an unknown `kid` triggers one refresh.

- [ ] **Step 1: Write failing tests** (use `cryptography` to mint a throwaway RS256 keypair; stub the JWKS client with a factory so no network I/O)

```python
# apps/automation/app/features/rag_agent/tests/test_token_verifier.py
import time, json
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from app.platform.config.platforms import load_platform_registry
from app.features.rag_agent.server.token_verifier import TokenVerifier, TokenError

ISS = "https://app.mews.com"

@pytest.fixture
def keypair():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key

@pytest.fixture
def registry(tmp_path):
    p = tmp_path / "platforms.json"
    p.write_text(json.dumps({
        "platforms": {"mews": {"issuer": ISS, "jwks_url": "https://app.mews.com/j", "domains": ["app.mews.com"], "lifetime_minutes": 60, "algs": ["RS256", "ES256"], "active": True}},
        "integrations": {"mews": ["obi-mews-test", "obi-general-test"]},
    }))
    return load_platform_registry(p, frozenset({"obi-general-test", "obi-mews-test"}), allow_empty=False)

def _verifier(registry, key):
    # factory returns an object with get_signing_key_from_jwt(token).key -> public key
    class _StubJWK:
        def get_signing_key_from_jwt(self, token):
            class _K: pass
            k = _K(); k.key = key.public_key(); return k
    return TokenVerifier(registry, jwks_client_factory=lambda url: _StubJWK())

def _sign(key, alg="RS256", **claims):
    now = int(time.time())
    payload = {"iss": ISS, "aud": "obi", "sub": "u1", "iat": now, "exp": now + 3600}
    payload.update(claims)
    return jwt.encode(payload, key, algorithm=alg, headers={"kid": "k1"})

def test_valid_token(registry, keypair):
    tok = _sign(keypair, company_id="c1", company_name="Hotel", integration="mews")
    vc = _verifier(registry, keypair).verify(tok)
    assert vc.subject == "u1" and vc.integration == "mews" and vc.issuer == ISS

def test_unknown_issuer_rejected(registry, keypair):
    tok = _sign(keypair, iss="https://evil.example")
    with pytest.raises(TokenError):
        _verifier(registry, keypair).verify(tok)

def test_hs256_rejected(registry, keypair):
    # attacker downgrades to HS256 signed with the public key bytes
    pub = keypair.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    import jwt as _jwt
    now = int(time.time())
    tok = _jwt.encode({"iss": ISS, "aud": "obi", "sub": "u1", "iat": now, "exp": now + 60}, pub, algorithm="HS256", headers={"kid": "k1"})
    with pytest.raises(TokenError):
        _verifier(registry, keypair).verify(tok)

def test_wrong_audience_rejected(registry, keypair):
    with pytest.raises(TokenError):
        _verifier(registry, keypair).verify(_sign(keypair, aud="not-obi"))

def test_expired_rejected(registry, keypair):
    now = int(time.time())
    tok = jwt.encode({"iss": ISS, "aud": "obi", "sub": "u1", "iat": now - 7200, "exp": now - 3600}, keypair, algorithm="RS256", headers={"kid": "k1"})
    with pytest.raises(TokenError):
        _verifier(registry, keypair).verify(tok)

def test_lifetime_over_platform_max_rejected(registry, keypair):
    now = int(time.time())
    tok = jwt.encode({"iss": ISS, "aud": "obi", "sub": "u1", "iat": now, "exp": now + 60 * 60 * 5}, keypair, algorithm="RS256", headers={"kid": "k1"})
    with pytest.raises(TokenError):
        _verifier(registry, keypair).verify(tok)  # 5h > lifetime_minutes 60

def test_missing_iat_rejected(registry, keypair):
    now = int(time.time())
    tok = jwt.encode({"iss": ISS, "aud": "obi", "sub": "u1", "exp": now + 60}, keypair, algorithm="RS256", headers={"kid": "k1"})
    with pytest.raises(TokenError):
        _verifier(registry, keypair).verify(tok)
```

- [ ] **Step 2: Run to verify failure** → FAIL (module missing; also confirms `pyjwt[crypto]` + `cryptography` importable after `uv add`).

- [ ] **Step 3: Implement** (fixed verification order per spec; any failure → `TokenError`, no detail)

```python
# apps/automation/app/features/rag_agent/server/token_verifier.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable
import jwt
from app.platform.config.platforms import PlatformEntry, PlatformRegistry

_LEEWAY_SECONDS = 60
_AUD = "obi"


class TokenError(Exception):
    """Any JWT verification failure. The router maps this to a bare 401, no detail leaked."""


@dataclass(frozen=True, slots=True)
class VerifiedClaims:
    issuer: str
    subject: str
    company_id: str | None
    company_name: str | None
    integration: str | None


class TokenVerifier:
    def __init__(
        self,
        registry: PlatformRegistry,
        *,
        jwks_client_factory: Callable[[str], "jwt.PyJWKClient"] | None = None,
    ) -> None:
        self._registry = registry
        self._factory = jwks_client_factory or (lambda url: jwt.PyJWKClient(url, cache_keys=True))
        self._clients: dict[str, "jwt.PyJWKClient"] = {}

    def _client(self, entry: PlatformEntry) -> "jwt.PyJWKClient":
        client = self._clients.get(entry.jwks_url)
        if client is None:
            client = self._factory(entry.jwks_url)
            self._clients[entry.jwks_url] = client
        return client

    def verify(self, token: str) -> VerifiedClaims:
        try:
            # 1. read iss WITHOUT verifying signature to find the entry
            unverified = jwt.decode(token, options={"verify_signature": False})
            iss = str(unverified.get("iss", ""))
            entry = self._registry.by_issuer(iss)
            if entry is None:
                raise TokenError("unknown issuer")

            # 2. reject header alg not in the entry allow-list (never HS256)
            header = jwt.get_unverified_header(token)
            alg = str(header.get("alg", ""))
            if alg not in entry.algs or alg.startswith("HS"):
                raise TokenError("disallowed alg")

            # 3. resolve signing key by kid (PyJWKClient caches; refreshes on unknown kid)
            signing_key = self._client(entry).get_signing_key_from_jwt(token).key

            # 4. verify signature + registered claims
            payload = jwt.decode(
                token, signing_key, algorithms=list(entry.algs), audience=_AUD, issuer=iss,
                leeway=_LEEWAY_SECONDS,
                options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            )

            # 5. bound the lifetime by the platform max
            if int(payload["exp"]) - int(payload["iat"]) > entry.lifetime_minutes * 60:
                raise TokenError("lifetime exceeds platform max")

            # 6. business values: all three or none
            biz = (payload.get("company_id"), payload.get("company_name"), payload.get("integration"))
            if any(v is not None for v in biz) and not all(v is not None for v in biz):
                raise TokenError("partial business claims")

            return VerifiedClaims(
                issuer=iss, subject=str(payload["sub"]),
                company_id=payload.get("company_id"), company_name=payload.get("company_name"),
                integration=payload.get("integration"),
            )
        except TokenError:
            raise
        except Exception as exc:  # any jwt/crypto error collapses to a bare TokenError
            raise TokenError("invalid token") from exc
```

- [ ] **Step 4: Run tests** → PASS (all seven). Note: PyJWT enforces `aud`/`iss`/`exp`/`iat`/`require` for us; step 5 adds the platform-max bound; step 2 blocks the HS256 downgrade before signature check.

- [ ] **Step 5: Commit** — `git commit -m "feat(embed): JWT verifier (alg allow-list, JWKS-by-kid, claim checks) (11.1c A3)"`

---

## Task Group B — Thread AuthContext through the read path + trace

### Task B1: `AnswerService.answer(history, auth: AuthContext)` + router wiring

**Files:**
- Modify: `apps/automation/app/features/rag_agent/application/answer_service.py` (`AnswerProvider` protocol + `AnswerService.answer` signature + internal scope resolution removed in favor of `auth.allowed_scopes`)
- Modify: `apps/automation/app/features/rag_agent/application/answer_cache.py` (`CachingAnswerService` cache key from `AuthContext`)
- Modify: `apps/automation/app/features/rag_agent/server/router.py` (new `X-Obi-Token` dependency, build `AuthContext`, body-scope validation, rate-limit key = hash(`sub`))
- Test: `apps/automation/app/features/rag_agent/tests/test_router_auth_context.py` (new) + update `test_answer_service.py`, `test_answer_cache.py`, existing router tests.

**Interfaces:**
- Consumes: `AuthContext`, `build_auth_context`, `general_only_context`, `TokenVerifier`, `TokenError`, `UnknownIntegrationError` (A2/A3).
- Produces: `AnswerProvider.answer(self, history, auth: AuthContext) -> Answer`; `AnswerService.answer(history, auth)`; a FastAPI dependency `get_auth_context(request, settings, verifier) -> AuthContext` reading header `X-Obi-Token` (constant name `_OBI_TOKEN_HEADER = "X-Obi-Token"`).

- [ ] **Step 1: Write the failing router test** — the token drives scopes; body `knowledgeScope` disagreeing is ignored+logged; unknown body slug → 400; unknown integration → 401; tokenless → general-only.

```python
# apps/automation/app/features/rag_agent/tests/test_router_auth_context.py
# Build a TestClient with a fake AnswerProvider that records the AuthContext it received,
# and a TokenVerifier stub keyed on header value. Assert:
def test_token_integration_drives_scopes(client_with_recorder, mews_token):
    r = client_with_recorder.post("/chat", headers={"Authorization": "Bearer HOSTKEY", "X-Obi-Token": mews_token}, json={"history": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 200
    assert recorder.last_auth.allowed_scopes == ("obi-general-test", "obi-mews-test")

def test_body_scope_disagreeing_with_token_is_ignored(client_with_recorder, mews_token):
    r = client_with_recorder.post("/chat", headers={"Authorization": "Bearer HOSTKEY", "X-Obi-Token": mews_token}, json={"history": [{"role": "user", "content": "hi"}], "knowledgeScope": "obi-toast-test"})
    assert r.status_code == 200
    assert recorder.last_auth.allowed_scopes == ("obi-general-test", "obi-mews-test")  # token wins

def test_unknown_body_scope_is_400_before_search(client_with_recorder, mews_token):
    r = client_with_recorder.post("/chat", headers={"Authorization": "Bearer HOSTKEY", "X-Obi-Token": mews_token}, json={"history": [{"role": "user", "content": "hi"}], "knowledgeScope": "not-a-real-slug!!"})
    assert r.status_code in (400, 422)
    assert recorder.last_auth is None  # never reached the service

def test_unknown_integration_is_401(client_with_recorder, wordpress_token):
    r = client_with_recorder.post("/chat", headers={"Authorization": "Bearer HOSTKEY", "X-Obi-Token": wordpress_token}, json={"history": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 401

def test_tokenless_request_is_general_only(client_with_recorder):
    r = client_with_recorder.post("/chat", headers={"Authorization": "Bearer HOSTKEY"}, json={"history": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 200
    assert recorder.last_auth.allowed_scopes == ("obi-general-test",)

def test_bad_token_is_401_before_search(client_with_recorder):
    r = client_with_recorder.post("/chat", headers={"Authorization": "Bearer HOSTKEY", "X-Obi-Token": "garbage"}, json={"history": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 401
    assert recorder.last_auth is None
```

- [ ] **Step 2: Run to verify failure** → FAIL.

- [ ] **Step 3: Change `AnswerProvider` + `AnswerService.answer`** — replace `(history, scope, knowledge_scope=None)` with `(history, auth: AuthContext)`. Inside `answer`, delete the `resolve_allowed_scopes(...)` call; use `allowed_scopes = list(auth.allowed_scopes)` and pass `scope=auth.principal` where the old `scope`/`principal` was used (v1 `principal` is `None`). Keep the `recognized_knowledge_scopes` / `default_knowledge_scope` constructor kwargs only if still needed by `resolve_allowed_scopes` elsewhere; otherwise remove them (search for other callers first — `make boundaries` + grep). Curated + CRAG retry reuse `auth.allowed_scopes` unchanged.

- [ ] **Step 4: Update `CachingAnswerService`** — key becomes `(history, auth.token_subject, tuple(auth.allowed_scopes))` (never the raw token). Update `answer_cache.py` + its tests.

- [ ] **Step 5: Add the router dependency + wiring** in `router.py`:

```python
_OBI_TOKEN_HEADER = "X-Obi-Token"

def get_token_verifier_dep(request: Request) -> TokenVerifier:
    return request.app.state.token_verifier  # built once in main.py lifespan from settings.platform_registry

def get_auth_context(
    request: Request,
    settings: Settings = Depends(get_settings_dep),
    verifier: TokenVerifier = Depends(get_token_verifier_dep),
) -> AuthContext:
    raw = request.headers.get(_OBI_TOKEN_HEADER, "")
    if not raw:
        return general_only_context()                    # tokenless internal/eval path
    try:
        claims = verifier.verify(raw)
        return build_auth_context(claims, settings.platform_registry)
    except (TokenError, UnknownIntegrationError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token")
```

In `post_chat`: add `auth: AuthContext = Depends(get_auth_context)` (runs after `_verify_api_key`). Validate the body `knowledge_scope` for membership: unknown recognized-slug → `HTTPException(400)` *before* streaming; a recognized slug disagreeing with `auth.allowed_scopes` → log one line and ignore (do not use it). Pass `auth` into `_stream_answer` → `service.answer(body.history, auth)`. `body.principal` is ignored entirely.

- [ ] **Step 6: Rate-limit key = hash of subject.** Change `_rate_limit_key` to prefer the verified subject: `key = "sub:" + sha256(auth.token_subject)` when present, else `"ip:" + client_ip`. Compute the hash with the shared hashing helper if one exists in `app/shared/` (reuse-before-add — grep first); otherwise `hashlib.sha256(sub.encode()).hexdigest()`. Note: `get_auth_context` must run before the limiter — reorder so verification precedes rate-limiting, but keep `_verify_api_key` (host key) first of all.

- [ ] **Step 7: Build the verifier + registry in `main.py` lifespan** — `app.state.token_verifier = TokenVerifier(settings.platform_registry)`; touching `settings.platform_registry` here is the fail-fast startup check from A1.

- [ ] **Step 8: Run the full suite** — `DATABASE_URL=<local dsn> uv run pytest -q` → all pass (update any existing router/answer tests that called the old signature). `make boundaries` → 0. Ruff/format/pyright clean on touched files.

- [ ] **Step 9: Commit** — `git commit -m "feat(embed): thread AuthContext through /chat; token integration drives scopes (11.1c B1)"`

---

### Task B2: `query_trace.subject_hash` (migration `0011`)

**Files:**
- Create: `apps/automation/alembic/versions/0011_query_trace_subject_hash.py`
- Modify: `apps/automation/app/platform/db/models.py` (`QueryTrace.subject_hash`), `apps/automation/app/platform/db/schema.py` if the create_all==migration contract needs it
- Modify: `apps/automation/app/features/retrieval/infrastructure/trace_repo.py` (`write_query_trace(..., subject_hash: str | None = None)`)
- Test: `apps/automation/app/platform/db/tests/test_migration_0011_subject_hash.py` + update `trace_repo` tests

**Interfaces:**
- Consumes: nothing new.
- Produces: `QueryTrace.subject_hash: Mapped[str | None]`; `write_query_trace(..., subject_hash=None)` persists it; `AnswerService._persist` passes `hash(auth.token_subject)` (or None when tokenless).

- [ ] **Step 1: Write the failing migration test** — real Alembic up/down/up: column present after `0011`, gone after downgrade, back on re-upgrade; `down_revision == "0010_customer_scope_rls"`.

```python
# asserts the column exists and is nullable text after upgrade, absent after downgrade
def test_0011_adds_subject_hash(alembic_runner, inspector):
    alembic_runner.migrate_up_to("0011_query_trace_subject_hash")
    cols = {c["name"] for c in inspector.get_columns("query_trace")}
    assert "subject_hash" in cols
    alembic_runner.migrate_down_one()
    cols = {c["name"] for c in inspector.get_columns("query_trace")}
    assert "subject_hash" not in cols
```

- [ ] **Step 2: Run to verify failure** → FAIL.

- [ ] **Step 3: Write the migration + model column**

```python
# alembic/versions/0011_query_trace_subject_hash.py
revision = "0011_query_trace_subject_hash"
down_revision = "0010_customer_scope_rls"

def upgrade() -> None:
    op.add_column("query_trace", sa.Column("subject_hash", sa.Text(), nullable=True))

def downgrade() -> None:
    op.drop_column("query_trace", "subject_hash")
```

```python
# models.py, in class QueryTrace(Base), near allowed_knowledge_scopes:
subject_hash: Mapped[str | None] = mapped_column(Text, nullable=True)  # sha256(sub) — never the token/raw subject
```

- [ ] **Step 4: Persist it** — add `subject_hash: str | None = None` to `write_query_trace` insert; `AnswerService._persist` computes it from `auth.token_subject` (same hash helper as the rate-limit key) and passes it. Assert in a `trace_repo` test that the row carries the hash and never the raw subject.

- [ ] **Step 5: Run tests** → PASS. `make check` (with `DATABASE_URL` override) → green.

- [ ] **Step 6: Commit** — `git commit -m "feat(embed): query_trace.subject_hash (hash of sub, never raw) — migration 0011 (11.1c B2)"`

---

## Task Group C — Contracts

### Task C1: token-claims JSON Schema + iframe message types + drift test

**Files:**
- Create: `packages/contracts/src/token-claims.json`
- Create: `packages/contracts/src/iframe-messages.ts`
- Modify: `packages/contracts/src/index.ts` (export the message types)
- Test: `apps/automation/app/features/rag_agent/tests/test_token_claims_contract.py` (drift test: the JSON Schema's required/enum matches the verifier's `options["require"]` + `_AUD` + business-value rule)

**Interfaces:**
- Produces: `token-claims.json` (JSON Schema draft 2020-12): required `iss`, `aud`(const `obi`), `sub`, `iat`, `exp`; optional `company_id`, `company_name`, `integration` with an `allOf`/`dependentRequired` rule enforcing all-three-or-none. `iframe-messages.ts`: `type ObiMessage = ObiOpen | ObiToken | ObiClear` where the three `type` literals are exactly `"obi:open"`, `"obi:token"`, `"obi:clear"`; `ObiToken` carries `token: string`.

- [ ] **Step 1: Write `token-claims.json`** with the required list, `aud` const, and the all-three-or-none `dependentRequired` (`company_id`→`company_name`,`integration`, etc.).
- [ ] **Step 2: Write `iframe-messages.ts`** — the discriminated union, `export`ed; re-export from `index.ts`.
- [ ] **Step 3: Write the failing drift test** — load `token-claims.json`, assert its `required` == the verifier's required set and `properties.aud.const == "obi"` and the dependentRequired rule mirrors `token_verifier`'s partial-business-claims check.
- [ ] **Step 4: Run to verify failure**, then make it pass (the schema is the source; if drift, fix the schema to match the verifier which is the security-authoritative side).
- [ ] **Step 5: `pnpm --filter @omniboost/contracts build`** (or the workspace's typecheck) → clean.
- [ ] **Step 6: Commit** — `git commit -m "feat(embed): token-claims schema + iframe message contracts + drift test (11.1c C1)"`

---

## Task Group D — Frontend: frame, bridge, loader, proxy

### Task D1: `/embed` frame page with per-request CSP `frame-ancestors`

**Files:**
- Create: `apps/web/src/app/embed/page.tsx` (+ `layout.tsx` if the frame needs an isolated shell without the global `ChatWidget`)
- Create/modify: a route segment config or middleware that sets `Content-Security-Policy: frame-ancestors <active domains>` built at request time from `platforms.json` active domains; empty list outside local → 403.
- Test: `apps/web/src/features/embed/tests/frame-csp.test.ts`

**Interfaces:**
- Consumes: the active-domain list (read server-side from the same `platforms.json`; add a tiny TS reader `src/features/embed/platforms.ts` mirroring the backend registry's `active_domains()`, or expose the list via an env-injected build value — prefer reading the JSON server-side).
- Produces: an `/embed` route that renders the round button + the existing `ChatWidget`, sending `frame-ancestors`.

- [ ] **Step 1: Write the failing CSP test** — request `/embed`, assert the response `Content-Security-Policy` header contains each active domain and no `*`; with an empty active list + non-local env, assert 403.
- [ ] **Step 2: Implement** the frame page reusing `ChatWidget`/`ChatSessionProvider` (no `knowledgeScope` prop — scope now comes from the token, server-side). Set the CSP header via the App Router `headers()` in a route handler or `middleware.ts` scoped to `/embed`, computed from the active-domain reader.
- [ ] **Step 3: Run tests** → PASS.
- [ ] **Step 4: Commit** — `git commit -m "feat(embed): /embed frame with per-request frame-ancestors CSP (11.1c D1)"`

### Task D2: frame-side `iframe-bridge.ts`

**Files:**
- Create: `apps/web/src/features/embed/iframe-bridge.ts`
- Create: `apps/web/src/features/embed/index.ts` (public root exporting the bridge init + message types)
- Test: `apps/web/src/features/embed/tests/iframe-bridge.test.ts` (jsdom postMessage)

**Interfaces:**
- Consumes: `ObiMessage` types (C1); the platform entry domains (via a value the frame is initialized with from D1).
- Produces: `initIframeBridge({ allowedOrigins: string[], onToken, onClear })` — accepts `obi:token`/`obi:clear` only from `window.parent` and only when `event.origin ∈ allowedOrigins`; holds the token in a module variable (never cookie/localStorage/sessionStorage/URL); exposes `getToken()`.

- [ ] **Step 1: Write failing tests** — (a) a `obi:token` from an allowed origin sets the token; (b) same message from a disallowed origin is ignored + one `console.warn`, token stays null; (c) a message from a non-parent window source is ignored; (d) `obi:clear` drops the token; (e) `getToken()` never reads from any storage (assert `localStorage`/`sessionStorage` untouched).
- [ ] **Step 2: Run to verify failure.**
- [ ] **Step 3: Implement** — `window.addEventListener("message", handler)`, guard `event.source === window.parent && allowedOrigins.includes(event.origin)`, switch on the three exact types.
- [ ] **Step 4: Wire the token into the chat POST** — `chat-client.ts` `streamChat` sends `Authorization: Bearer ${getToken()}` (frame path) when a token exists; block send when none (return a "needs token" state). On backend 401, signal the loader to renew once (a callback/event), then retry.
- [ ] **Step 5: Run tests** → PASS.
- [ ] **Step 6: Commit** — `git commit -m "feat(embed): frame-side iframe bridge (origin-checked, in-memory token) (11.1c D2)"`

### Task D3: the loader → `public/obi.js`

**Files:**
- Create: `apps/web/src/features/embed/loader.ts`
- Add a build step (package.json script + `apps/web/public/` output) compiling `loader.ts` → `apps/web/public/obi.js` (esbuild/tsup — check the workspace for an existing bundler before adding one; if none, a minimal `esbuild` devDep is justified). Create `apps/web/public/`.
- Test: `apps/web/src/features/embed/tests/loader.test.ts`

**Interfaces:**
- Produces: global `window.Obi` with `Obi.init({ tokenUrl })` and `Obi.clear()`. Behavior: inject the iframe (`src` = our `/embed` origin); draw the round button; on button click `postMessage({type:"obi:open"}, OBI_ORIGIN)` and `fetch(tokenUrl, { credentials: "same-origin" })` (rides the platform session cookie, no CORS); `postMessage({type:"obi:token", token}, OBI_ORIGIN)` with the exact Obi origin as target (never `*`); set a timer to renew before `exp` (decode `exp` client-side, no verification — display only); renew on next activity after long idle; on a backend 401 renew once; `Obi.clear()` → `postMessage({type:"obi:clear"}, OBI_ORIGIN)` + forget.

- [ ] **Step 1: Write failing tests** (jsdom) — `Obi.init` injects one iframe with the correct `src`; button click fetches `tokenUrl` and posts `obi:token` targeted at the exact origin (assert the `targetOrigin` arg is `OBI_ORIGIN`, never `"*"`); `Obi.clear()` posts `obi:clear`; the renew timer fires before `exp`.
- [ ] **Step 2: Run to verify failure.**
- [ ] **Step 3: Implement `loader.ts`** with `OBI_ORIGIN` injected at build time (env). Only three message types out.
- [ ] **Step 4: Add the bundling script** — `"build:obi": "esbuild src/features/embed/loader.ts --bundle --minify --format=iife --outfile=public/obi.js"`; hook it into the web `build`.
- [ ] **Step 5: Run tests + build** → PASS; `public/obi.js` produced.
- [ ] **Step 6: Commit** — `git commit -m "feat(embed): obi.js loader (button, token fetch, silent renew, clear) (11.1c D3)"`

### Task D4: proxy forwards the JWT; retire the pilot invite token

**Files:**
- Modify: `apps/web/src/features/chat/server/route-handlers.ts` (read incoming `Authorization`, pass the raw JWT down)
- Modify: `apps/web/src/platform/automation-api/client.ts` (`callAutomationApi` adds `X-Obi-Token: <jwt>` next to the unchanged host-key `Authorization`)
- Delete: `apps/web/src/features/chat/api/access-token.ts`, `apps/web/src/features/chat/server/auth.ts`
- Modify callers: `chat-session-provider.tsx` (remove `captureWidgetAccessToken`), `chat-client.ts` (remove `accessTokenHeaders`/`x-widget-access-token`), `route-handlers.ts` (remove `rejectUnauthorized`/`verifyWidgetAccessToken`), `chat/index.ts` exports.
- Test: update `route-handlers` tests; add a test that a `Bearer <jwt>` on the incoming request arrives as `X-Obi-Token` on the outgoing automation call with the host key still on `Authorization`.

**Interfaces:**
- Consumes: incoming request `Authorization: Bearer <jwt>` (from the frame).
- Produces: outgoing automation call headers `Authorization: Bearer <CHAT_API_KEY>` **and** `X-Obi-Token: <jwt>` (only when the incoming JWT is present).

- [ ] **Step 1: Write the failing proxy test** — POST with `Authorization: Bearer JWT123` → the stubbed `callAutomationApi` receives `{ authorization: "Bearer <hostkey>", "x-obi-token": "JWT123" }`. A request with no incoming Authorization → no `X-Obi-Token`.
- [ ] **Step 2: Run to verify failure.**
- [ ] **Step 3: Implement** the header split in `client.ts` (extend `callAutomationApi` opts with `userToken?: string`) and thread the incoming bearer through `handlePostChat`. Delete the two pilot files and every reference.
- [ ] **Step 4: Run web tests + typecheck** → PASS; no dangling imports (`pnpm --filter web typecheck`).
- [ ] **Step 5: Commit** — `git commit -m "feat(embed): proxy forwards user JWT as X-Obi-Token; retire pilot invite token (11.1c D4)"`

---

## Task Group E — Test host pages (unblocks browser proof)

### Task E1: test keys + JWKS + note endpoints

**Files:**
- Create: `apps/web/src/app/api/test-hosts/[name]/obi-token/route.ts` — signs a short-lived RS256 JWT for `none`/`mews`/`toast`/`opera-cloud` using a per-issuer test private key from server env.
- Create: the test JWKS routes (`/.well-known/obi-jwks.json` per test issuer) serving the public keys — or serve them from the automation side; keep them reachable at the `jwks_url` recorded in the local `platforms.json`.
- Modify: local/staging `platforms.json` (or a local override file) to add `test-mews`, `test-toast`, `test-opera` issuer entries + `active: true` for local; add `none` mapping semantics (no integration claim).
- Add test keypairs to the dev env (documented in the runbook; private keys never committed).

**Interfaces:**
- Produces: `GET /api/test-hosts/<name>/obi-token` → `{ token }` signed per the table in the spec §4 (RS256, `kid`, 60-min lifetime, `aud=obi`, the page's business values or none).

- [ ] **Step 1:** generate three RS256 keypairs; put private keys in the dev env; publish the public keys at each test issuer's `obi-jwks.json`.
- [ ] **Step 2:** implement the note endpoints (Node `jsonwebtoken` or `jose` — check web deps; `jose` is the modern choice and has no native build). One endpoint per name mapping to the claim set in spec §4.
- [ ] **Step 3:** add the three `test-*` entries to the local `platforms.json` + integrations (`test-mews→mews`, etc.) so the backend verifier trusts them locally.
- [ ] **Step 4:** manual smoke — `curl /api/test-hosts/mews/obi-token` returns a token that the backend verifier accepts (integration test against the automation `/chat`).
- [ ] **Step 5: Commit** — `git commit -m "feat(embed): test-host note endpoints + test JWKS (local/staging) (11.1c E1)"`

### Task E2: the four test-host pages

**Files:**
- Create: `apps/web/src/app/test-hosts/{none,mews,toast,opera-cloud}/page.tsx` — each containing exactly the paste template: the `obi.js` script tag + `Obi.init({ tokenUrl: "/api/test-hosts/<name>/obi-token" })`.
- Test: an e2e/integration check (Playwright if present, else a scripted fetch-through) proving the done-when items.

- [ ] **Step 1:** create the four pages from the template.
- [ ] **Step 2: Prove the done-when set** (spec §"Done when" 1-7): each page loads the button, opens chat, gets answers; `mews`→Mews+general only, `toast`→Toast+general, `opera-cloud`→Opera+general, `none`→general only (three-way isolation); a tampered/expired/missing token → 401 before search + one renewal; cross-origin/non-parent postMessage ignored with one log line; silent renewal after an hour; `Obi.clear()` empties the frame and blocks send until a new token. Record results in the hand-back report.
- [ ] **Step 3: Commit** — `git commit -m "feat(embed): four test-host pages + three-way isolation proof (11.1c E2)"`

---

## Task Group F — Ops & hand-over

### Task F1: three platform hand-over packs + inactive registry entries

**Files:**
- Create: `docs/embedding/mews.md`, `docs/embedding/toast.md`, `docs/embedding/opera-cloud.md`
- Confirm `config/platforms.json` carries all three platform entries `active: false` with placeholder issuer/jwks/domains + the integration map (done in A1; verify Opera Cloud's `obi-operacloud-test` exists in `knowledge_scopes.json` — it does).

- [ ] **Step 1:** write each pack: the exact script tag + `Obi.init({ tokenUrl })` line; the note structure (default with no values + with the three values); a **reference note endpoint in Node and in Python** (signed-in users only, three values or none, RS256, `kid` in header, agreed 60-min lifetime); the four things we need back (issuer URL, JWKS URL, the browser domain(s), the `integration` value); the done-when checks; a request checklist (contact, one test company per integration, one test user in a restricted Confluence group); and the **one line that activates** the platform (flip `active: false`→`true` once issuer/jwks/domains are filled).
- [ ] **Step 2:** cross-link each pack from `docs/rag/PLAN.md §0` and this plan.
- [ ] **Step 3: Commit** — `git commit -m "docs(embed): Mews/Toast/Opera Cloud hand-over packs + inactive registry entries (11.1c F1)"`

### Task F2: live migration ops (operator-gated) + phase doc + ledger

**Files:**
- Modify/create: `docs/rag/retrieval/phase-11.md` (append an 11.1c section) or a new `docs/rag/retrieval/phase-11.1c.md`; the counterpart under `docs/rag/ingestion/` is **not** needed (11.1c is read-path only).
- Modify: `docs/rag/PLAN.md §0` — record commit refs, test counts, deviations; move item 0 to done when the phase lands.
- Modify: `docs/runbooks/` — add the "apply `0010` then `0011` to Supabase" step + the test-key handling note.

- [ ] **Step 1 (OPERATOR):** with `.env` pointed at Supabase, `uv run alembic upgrade head` advances live `0009`→`0010`→`0011`; then `uv run python scripts/setup_supabase.py verify-isolation` (expect the scope-axis line + exit 0). This closes the last CRITICAL pre-public-deploy gate (customer isolation fail-open → fail-closed) **and** adds the new trace column.
- [ ] **Step 2:** write the phase doc: what runs on the read path now (token → verifier → AuthContext → both GUCs), which files, cross-link ADR-0014 + this plan.
- [ ] **Step 3:** update `PLAN.md §0` ledger.
- [ ] **Step 4: Commit** — `git commit -m "docs(embed): phase-11.1c read-path doc + PLAN ledger + runbook migration step (11.1c F2)"`

---

## Self-Review

**Spec coverage** (spec §"What to build"):
- §1 backend accept+verify → A1 (registry+startup validation), A3 (verifier), A2+B1 (AuthContext, threading, both GUCs, body-rule, rate-limit key, `query_trace` hash via B2), settings (no old single-issuer vars — none exist). ✅
- §2 frontend frame+loader → D1 (frame+CSP), D2 (bridge), D3 (loader), D4 (proxy forward + retire pilot). ✅
- §3 contracts → C1. ✅
- §4 test host pages → E1+E2 (four pages, note endpoints, three-way isolation, done-when 3a covered by the A2 backend unit test). ✅
- §5 setup for three platforms → F1 (packs + inactive entries). ✅
- §6 decisions → encoded in Global Constraints + A2 (`principal` None, no-values=general, unknown integration=401) + F1 (all three prepared, none active). ✅
- §"Done when" 1-7 + 3a → E2 (browser) + A2 (`company_id`-only unit proof) + B1 (401-before-search, tokenless=general). ✅
- Ops prereq (apply `0010`) → F2 + Global Constraints. ✅

**Placeholder scan:** the only literal `PLACEHOLDER` values are in `config/platforms.json` Opera Cloud issuer/jwks — intentional, gated by `active: false`, filled by the operator (F1). All security-critical logic (verifier order, AuthContext resolution, GUC threading, header split) is written out in full. No "add validation"/"handle edge cases" hand-waving.

**Type consistency:** `VerifiedClaims` (A3) is consumed unchanged by `build_auth_context` (A2). `AuthContext` fields (`allowed_scopes`, `token_subject`, `principal`) are used identically in B1/B2. `apply_knowledge_scope` / `apply_source_scope` signatures match the map. `_OBI_TOKEN_HEADER = "X-Obi-Token"` is the single header name across B1 and D4. The three message-type literals (`obi:open`/`obi:token`/`obi:clear`) are identical across C1, D2, D3.

**Open decision — RESOLVED 2026-09-12:** the scope-slug mapping (platform key as JWT wire value → `obi-*-test` slugs) is confirmed by the operator. No open decisions block execution; the remaining prerequisites are operator-supplied *values* (real platform issuer/JWKS/domains, test companies, restricted user) and the live migration apply, all listed in Global Constraints.
