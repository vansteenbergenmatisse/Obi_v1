# Brief · How to add an integration

**Audience:** an Obi maintainer (us), working locally. No external platform cooperation needed — adding an integration is a pure config change plus Confluence labels.

An **integration** is the underlying software a customer runs (`mews`, `toast`, `opera-cloud`). It arrives in the verified JWT as the `integration` claim, is validated against the issuing platform's `allowed_integrations`, and maps to one or more **knowledge scopes** (Confluence tags) that isolate what retrieval is allowed to read. Adding one touches **two JSON files** and the **Confluence labels** — no Python or TypeScript changes.

> Rule that never bends: the request body never decides access. The `integration` value is only ever trusted from the verified token (project rule #2). Adding an integration to a platform's `allowed_integrations` is a **trust decision** — you are declaring that platform is allowed to assert that integration on behalf of its users.

---

## The two config files you edit

| File | What you add |
|---|---|
| `knowledge-base/config/knowledge_scopes.json` | the new scope (Confluence tag) the integration's content lives under |
| `knowledge-base/config/platforms.json` | the `integration → scope` mapping, and the `allowed_integrations` entry on whichever platform is trusted to assert it |

Both are the single canonical source: the backend reads them at startup, the widget generates its scope list from `knowledge_scopes.json` at build time, and ingestion eligibility reads the same scope file. There is no second list to keep in sync (except the local test scaffold — see the last step).

---

## Steps (worked example: adding `cloudbeds`)

### 1. Add the knowledge scope
`knowledge-base/config/knowledge_scopes.json` → append to `scopes`:
```json
{ "name": "obi-cloudbeds-test", "label": "Cloudbeds", "description": "Cloudbeds PMS integration content." }
```
- `name` **must be lowercase and unique** — it is the exact Confluence tag (Confluence lowercases labels) and the internal scope id.
- Never touch `obi-general-test` or `classified`; both must stay present. `classified` is reserved and never offered.
- This alone makes the backend recognize the new scope — the loader validates the file at startup. Nothing on the frontend needs changing: the dev widget scope switcher (and the generated `knowledge-scopes.ts` list) was removed (2026-09-23), so the widget no longer carries a scope list.

### 2. Map the integration → scope
`knowledge-base/config/platforms.json` → `integrations` map:
```json
"cloudbeds": ["obi-cloudbeds-test"]
```
- The key is the **integration claim value**. The value is a list of scope `name`s from step 1.
- Do **not** list `obi-general-test` — the loader adds it automatically (startup `ValueError` if you do).
- Never list `classified`.

### 3. Grant a platform the right to assert it
`knowledge-base/config/platforms.json` → `platforms` map. Either:
- **the hub vends it** — add `"cloudbeds"` to an existing platform's `allowed_integrations` (e.g. `datahub`), **or**
- **a self-serving platform** — add a new platform entry whose `allowed_integrations` is just `["cloudbeds"]` (adding a platform is its own runbook — see [`add-a-host-platform.md`](./add-a-host-platform.md)).

Every value in any `allowed_integrations` **must** be a key of the `integrations` map (startup validation enforces this).

### 4. Label the Confluence pages
Tag the pages that belong to this integration with the exact scope name `obi-cloudbeds-test`. Nothing in ingestion code changes — eligibility reads the same scope file.

### 5. (Only if you use the local embed test) keep the test scaffold in lockstep
`knowledge-base/config/platforms.local.json` and `frontend/src/app/api/test-hosts/config.ts` must agree, or the local embed flow 401s. Add:
- a `test-cloudbeds` platform entry in `platforms.local.json` with `allowed_integrations: ["cloudbeds"]` and the `integrations` mapping;
- a matching `TEST_HOSTS` entry in `config.ts` whose `businessClaims.integration` is `"cloudbeds"`, plus the `TestHostName` / `TestIssuerKey` union members and the RS256 key-pair env vars.

This lockstep is asserted by `test_platforms_local_file_allowed_integrations_match_test_hosts`. See [`localhost-test.md`](./localhost-test.md) to actually run it.

### 6. Test + gate
Add tests (next section), then `make check` (boundaries + tests). If retrieval behaviour is affected, `make eval` too — no retrieval change ships without a before/after gold-set number (project rule #11). Append a `ledger.md` + `progress-log.md` entry.

---

## Where the code enforces all this (links)

| Concern | Location |
|---|---|
| Scope registry loader + validation | `backend/app/platform/config/knowledge_scopes.py` → `load_recognized_knowledge_scopes` |
| Platform + integration loader, startup validation | `backend/app/platform/config/platforms.py` → `load_platform_registry` (integration→scope loop, `allowed_integrations` check) |
| `integration → scopes` at request time | `backend/app/platform/config/platforms.py` → `PlatformRegistry.scopes_for` / `allowed_scopes_for` |
| The verified claim → auth context | `backend/app/features/rag_agent/application/auth_context.py` → `build_auth_context` |
| `allowed_integrations` gate (401) | `auth_context.py` → `IntegrationNotAllowedError` (and `UnknownIntegrationError`, `InactivePlatformError`) |
| The claim source (verified JWT only) | `backend/app/features/rag_agent/server/token_verifier.py` → `VerifiedClaims.integration` |
| Scope used in retrieval | `backend/app/features/retrieval/infrastructure/search_repo.py` → `apply_knowledge_scope` (sets the `app.allowed_knowledge_scopes` GUC) |

---

## Tests that already protect this, and where a new one goes

**Unit (temp JSON + fakes, no network):**
- `backend/app/platform/config/tests/test_platforms.py` — mapping, `allowed_integrations` startup gate, the pinned real-file set.
- `backend/app/features/rag_agent/tests/test_auth_context.py` — `test_unknown_integration_raises`, `test_cross_issuer_integration_is_rejected`, `test_hub_vends_multiple_product_integrations`, `test_self_serving_platform_asserting_own_integration_is_allowed`.

**DB (local pgvector, RLS, rolled back per test):**
- `backend/app/features/confluence_sync/tests/test_retrieval_knowledge_scope.py` — a page tagged for one scope never leaks under another.
- `backend/app/features/confluence_sync/tests/test_customer_isolation_backstop.py` — scope-RLS fails closed.

**A new integration's proof belongs in:** the config/mapping proof → `test_platforms.py` + `test_auth_context.py` (unit); the isolation proof (a page tagged `obi-<x>-test` is never returned under a different integration's scope) → a DB test next to the ones in `test_retrieval_knowledge_scope.py`. Name it `test_<stage>_<behavior>` and name the design panel/requirement it protects.

---

## Pitfalls

- `obi-general-test` is added by the loader — **never** hand-list it in a mapping.
- `classified` is reserved — never mappable, never offered; a `classified` Confluence label *removes* a page from the index.
- A self-serving platform must never be given another tenant's integration in `allowed_integrations` (that is the CIP-A1 cross-integration boundary).
- Active **production** platforms must be real `https` issuers — the loader rejects placeholder / non-https / loopback / `.local` issuers outside offline mode. A new integration on the still-placeholder `datahub` entry does not go live until `datahub` has real issuer values (Bucket 1 — external).
