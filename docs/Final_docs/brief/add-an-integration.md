# Brief · How to add a system (an integration)

**Audience:** an Obi maintainer (us), working locally. No partner cooperation needed — adding a system is a config change plus Confluence labels.

A **system** (still called an *integration* in `platforms.json`) is software a customer connects through Omniboost: `mews`, `toast`, `opera-cloud`, `quickbooks-online`, `xero`. A partner's token names two of them for one connection: `source_system` and `target_system`, plus `business_id`. Only the **source** decides whether Obi shows (`ADR-source-system-decides-widget-eligibility`); the target only picks routing labels. Content reaches a chat through **routing labels** on the Confluence pages (`ADR-routing-labels-sole-content-axis`, `ADR-directed-source-target-routing-labels`). There are no knowledge-scope tags any more.

> Rule that never bends: the request body never decides access. `source_system`, `target_system` and `business_id` are only ever trusted from the verified token (project rule #2). Adding a system to a partner's `allowed_integrations` is a **trust decision** — you are declaring that partner may name it as a source on behalf of its users.

---

## The files you edit

| File | What you add |
|---|---|
| `knowledge-base/config/product_catalog.json` | the product: canonical id, `label`, `role` (`pos` / `pms` / `accounting`), `aliases`, `connection_types`; and, if it may open Obi as a source, its id in `enabled_sources` |
| `knowledge-base/config/platforms.json` | the id as a key of the `integrations` map (value `[]`) and in the `allowed_integrations` of each partner trusted to name it as a source |

`product_catalog.json` is the one place that defines a product. `platforms.json` is the issuer registry and the claim allow-list; the loader cross-checks that every `integrations` key resolves in the catalog. `knowledge-base/config/knowledge_scopes.json` is not touched: it now holds only the reserved `classified` entry.

---

## Steps (worked example: adding `cloudbeds`)

### 1. Add the product to the catalog
`knowledge-base/config/product_catalog.json` → `products`:
```json
"cloudbeds": { "label": "Cloudbeds", "role": "pms", "aliases": [], "connection_types": ["pos-pms", "pms-accounting"] }
```
- The id is a short lowercase slug, unique across ids and aliases; never `obi-*`, `classified` or `general`.
- The startup loader (`backend/app/platform/config/product_catalog.py`) validates the file and stops the backend on a bad entry.

### 2. Decide whether it may open Obi as a source
Add `"cloudbeds"` to `enabled_sources` if a chat whose source is Cloudbeds should show Obi. Leave it out and such a chat is refused with 403 `source_not_enabled` (the widget stays hidden). As a target it needs nothing: the target is never checked.

### 3. Grant a partner the right to name it
`knowledge-base/config/platforms.json`:
- add `"cloudbeds": []` to the `integrations` map (the list stays empty — the old scope mapping is retired);
- add `"cloudbeds"` to the `allowed_integrations` of each partner (`base`, `datahub`) trusted to vend it. Every `allowed_integrations` value must be a key of `integrations` (startup validation enforces this).

### 4. Label the Confluence pages
A page is in the index when it is published and carries at least one recognized routing label; `classified` removes it. For the new system the label forms are:
- `cloudbeds-general` — Cloudbeds content for any connection where Cloudbeds is source or target;
- `cloudbeds-to-pos`, `cloudbeds-to-pms`, `cloudbeds-to-accounting` — content for a connection from Cloudbeds to that kind of target;
- `obi-general` — content for every chat.

A directed chat searches only pages carrying one of its four labels: `obi-general`, `{source}-general`, `{target}-general`, `{source}-to-{target role}`. An unknown target falls back to `obi-general` + `{source}-general`. Nothing in ingestion code changes — labels are validated against the catalog.

### 5. (Only if you use the local embed test) keep the test scaffold in lockstep
`knowledge-base/config/platforms.local.json` and `frontend/src/app/api/test-hosts/config.ts` must agree, or the local embed flow 401s. Add a `test-cloudbeds` platform entry with `allowed_integrations: ["cloudbeds"]` and the `integrations` key, plus a matching `TEST_HOSTS` entry (its `directedClaims` naming `cloudbeds` as `source_system`) and its RS256 key-pair env vars. The lockstep is asserted by `test_platforms_local_file_allowed_integrations_match_test_hosts`. See [`localhost-test.md`](./localhost-test.md) to run it.

### 6. Test + gate
Add tests (next section), then `make check` (boundaries + tests). If retrieval behaviour is affected, `make eval` too — no retrieval change ships without a before/after gold-set number (project rule #11). Append a `ledger.md` + `progress-log.md` entry.

---

## Where the code enforces all this (links)

| Concern | Location |
|---|---|
| Product catalog loader, `enabled_sources`, routing-label forms | `backend/app/platform/config/product_catalog.py` |
| Platform loader, `allowed_integrations` check | `backend/app/platform/config/platforms.py` → `load_platform_registry` |
| The verified claims → auth context (source decides) | `backend/app/features/rag_agent/application/auth_context.py` → `build_auth_context`, `_build_directed_context` |
| Vend gate (401) and source gate (403) | `auth_context.py` → `IntegrationNotAllowedError`, `SourceNotEnabledError` |
| The claim source (verified JWT only) | `backend/app/features/rag_agent/server/token_verifier.py` → `VerifiedClaims` |
| The four labels per chat | `backend/app/features/rag_agent/application/chat_session.py` |
| Membership decision at ingestion | `backend/app/features/confluence_sync/domain/ingest_decision.py` |
| Label filter in retrieval | `backend/app/features/retrieval/infrastructure/search_repo.py` → `apply_allowed_labels` (sets the `app.allowed_labels` GUC) |

---

## Tests that already protect this, and where a new one goes

**Unit (temp JSON + fakes, no network):**
- `backend/app/platform/config/tests/test_product_catalog.py` — catalog rules, aliases, `enabled_sources`.
- `backend/app/platform/config/tests/test_platforms.py` — `allowed_integrations` startup gate, the pinned real-file set.
- `backend/app/features/rag_agent/tests/test_mi_gate_directed.py` — source decides, target never checked.
- `backend/app/features/rag_agent/tests/test_chat_session.py` — the four routing labels per chat.

**DB (local pgvector, RLS, rolled back per test):**
- `backend/app/features/retrieval/tests/test_label_hardfilter_db.py` — a directed chat never reads a page outside its labels.
- `backend/app/features/confluence_sync/tests/test_sync_rules_membership.py` — routing labels decide index membership.

**A new system's proof belongs in:** the catalog and gate proof → `test_product_catalog.py` + `test_mi_gate_directed.py` (unit); the routing proof (a page labelled `cloudbeds-general` is returned for a Cloudbeds chat and not for an unrelated one) → a DB test next to `test_label_hardfilter_db.py`. Name it `test_<stage>_<behavior>` and name the design panel it protects.

---

## Pitfalls

- `classified` is reserved — a `classified` Confluence label *removes* a page from the index, whatever other labels it carries.
- Mews, Toast and Opera Cloud are systems, never platforms. Do not add a platform entry for a system.
- A partner should never be given a system it is not trusted to vend in `allowed_integrations` (the CIP-A1 boundary).
- Active **production** platforms must be real `https` issuers — the loader rejects placeholder / non-https / loopback / `.local` issuers outside offline mode. A new system on a still-inactive partner entry does not go live until that partner is active.
