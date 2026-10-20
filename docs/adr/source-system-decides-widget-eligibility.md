# The Source System Decides Widget Eligibility

Identifier: `ADR-source-system-decides-widget-eligibility` (formerly numbered 0023). File paths updated to the current layout (`backend/`, `frontend/`, `knowledge-base/`) on 2026-10-20; the decision is unchanged.

Status: Accepted
Date: 2026-10-20
Supersedes: ADR-widget-hides-via-visibility-probe Decision on WHICH endpoint gates (target → source). ADR-widget-hides-via-visibility-probe's mechanism — the
`GET /chat/visibility` probe, the 403 render, the `obi:hidden` frame→host message, the init-time
eligibility fetch — stays as decided there.
Governs: `knowledge-base/config/product_catalog.json` (`enabled_sources`, renamed from
`enabled_targets`), `backend/app/platform/config/product_catalog.py` (`enabled_sources`,
`build_labels`), `backend/app/features/rag_agent/application/auth_context.py`
(`SourceNotEnabledError`, `_build_directed_context`), `backend/app/features/rag_agent/server/router.py`
(reason `source_not_enabled`), `packages/contracts/src/openapi/chat.yaml`,
`frontend/src/features/embed/loader.ts` (`__OBI_ENABLED_SOURCES__`, `source_system` decode),
`frontend/scripts/enabled-source-names.mjs`.

## Context

ADR-widget-hides-via-visibility-probe hid Obi when the directed token's TARGET was not enabled, and treated an unknown source or
target as a 400 error. The first real partner token (Base, 2026-10-16) showed why that does not fit:
Base sends the customer's actual systems (`source_system: "PEP PMS"`, `target_system: "NetSuite"`),
and a source system can connect to hundreds of targets. Checking every target against our catalog
would refuse most real connections, and an unknown system produced an error in an already-mounted
widget instead of hiding it.

The owner decided (2026-10-20): only the source system matters. If the source is one Obi supports
(today Mews, Toast, Opera Cloud), Obi shows and answers; the target is assumed supported and never
checked.

## Decision

1. **The source gates, the target never does.** In the directed path the source must resolve in the
   catalog (lenient resolver: id, display name or alias, case/space insensitive), be vendable by the
   issuing platform (`allowed_integrations`, 401 otherwise) and be in `enabled_sources` (403
   `source_not_enabled` otherwise). An unknown source is also `source_not_enabled` (403), so Obi
   hides instead of erroring.
2. **The target is routing input only.** It is resolved with the same resolver. Known: the four
   routing labels as before (ADR-directed-source-target-routing-labels). Unknown: `target_slug = None` and routing falls back to the
   boxes the source alone can fill, `[obi-general, {source}-general]` — never a fabricated system,
   never a wildcard. No vend, enablement, role or allowlist check applies to the target.
3. **`enabled_targets` is renamed `enabled_sources`** with the same value (`mews`, `toast`,
   `opera-cloud`). Absent still means every product is enabled.
4. **The loader matches names the way the backend does.** `build:obi` injects every normalized name
   an enabled source answers to (id, label, aliases), and the loader normalizes the decoded
   `source_system` the same way before comparing.

## Consequences

- Base can send any customer's systems unchanged. A PEP PMS customer sees no widget; a Toast
  customer sees Obi for every target, including NetSuite.
- Security: dropping the target's vend check does not widen data access. Routing labels are
  product-level content, not customer data; company isolation still rides `business_id` from the
  verified token (never-bend rules 2–3), the source keeps its vend check, and nothing reads the
  request body. A hub can now steer a known target's direction label it was not trusted to vend;
  the worst case is answers from another product's public integration pages.
- Retrieval: the only routing change is the unknown-target fallback. That path was unreachable before
  (an unknown target was a 400), so the gold set has no case it changes; no before/after number was
  owed or produced (never-bend rule 11 noted, not waived).
- `UnknownIntegrationError` no longer fires in the directed path; it remains for the slot form.
