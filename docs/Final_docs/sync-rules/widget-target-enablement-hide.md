# Widget source-enablement hide (frontend)

> The filename keeps its old "target" name for link stability. Since 2026-10-20 the gate is on the
> **source** (ADR-source-system-decides-widget-eligibility); the target is never checked.

- **Workflow:** embed / widget (frontend)
- **Owning code:** `frontend/src/features/embed/loader.ts` (the host-page `obi.js` loader),
  `frontend/scripts/enabled-source-names.mjs` (the build-time name list),
  `frontend/src/app/embed/embed-frame.tsx` (the `/embed` frame), `frontend/src/features/chat/api/chat-client.ts`
  (`checkVisibility`), `frontend/src/features/chat/server/route-handlers.ts` (`handleGetVisibility`)
  + `frontend/src/app/api/chat/visibility/route.ts` (the proxy), `packages/contracts/src/iframe-messages.ts`
  (the `obi:hidden` message)
- **Design panel:** panel mi-gate (source-enablement visibility gate), directed path
- **Authorized by:** ADR-source-system-decides-widget-eligibility (which gates), building on the
  mechanism of ADR-widget-hides-via-visibility-probe (probe, 403 render, `obi:hidden`). The backend
  403 (`reason: source_not_enabled`) is the authority; this hide is UX.
- **Status:** Unverified (frontend coded + unit/mocked-browser proven; the signed-key e2e needs a
  local key, see below)

## What it does

When Obi is embedded on a platform page whose directed token names a **source** system that is not
enabled (`knowledge-base/config/product_catalog.json` → `enabled_sources`, today
`["mews","toast","opera-cloud"]`) or not known at all, the widget never appears. The target is never
checked: a Toast customer sees Obi for any target, NetSuite included. Two layers:

1. **Load-time, no-flash (loader).** `__OBI_ENABLED_SOURCES__` is injected into `obi.js` at build by
   esbuild `--define` from `scripts/enabled-source-names.mjs` — every normalized name an enabled source
   answers to (id, label, aliases) — exactly how `__OBI_ORIGIN__` is injected (`frontend/package.json`
   `build:obi`). In `init()`, before mounting, the loader fetches the token once and decodes its
   (display-only, non-trust) `source_system`, normalized the way the backend does (case-folded,
   whitespace collapsed). If that source is not enabled it returns without mounting — no launcher, no
   iframe, no flash. The set absent/empty ⇒ **all enabled** (fail-open); a failed eligibility fetch or a
   token with no `source_system` (a legacy single-integration note) also mounts. The trust-bearing token
   fetch still happens fresh at click.
2. **Server-authoritative cross-check (frame).** On every token receipt, `embed-frame.tsx` calls
   `GET /chat/visibility` through the same-origin Next proxy that injects the host `CHAT_API_KEY` and
   forwards the user token as `X-Obi-Token` (`/api/chat/visibility` → `handleGetVisibility`, mirroring
   `POST /api/chat`). On `{"visible":false,"reason":"source_not_enabled"}` it posts the one frame→host
   message `obi:hidden`, and the loader `destroy()`s the widget. A hard failure (400/401/429/503) is
   **never** coerced to hidden — the widget stays mounted.

## Why it does it

A source system can connect to hundreds of targets; checking each target against our catalog would
refuse most real connections (Base's first token was `PEP PMS → NetSuite`). So only the source decides
(owner, 2026-10-20). The backend's `POST /chat` 403 with `reason: source_not_enabled` is the real
authority — it never names the product id (never-bend rule 10). The frontend hide is pure UX: show
nothing rather than a widget that can only refuse. The two-layer split exists so the common case has no
flash (the loader decodes locally) while correctness stays server-authoritative (the probe can hide a
widget the loader mounted, e.g. when the enabled set was absent at build). Fail-open on every uncertain
signal (missing set, fetch failure, probe outage) is deliberate: an outage must not blank the widget for
everyone, and the backend 403 still blocks the actual answer.

Two conventions are bent, both authorized by ADR-widget-hides-via-visibility-probe and isolated to this component:
- one **eligibility-only token fetch at `init`** in addition to the click-time fetch (`loader.ts`);
- a **4th `ObiMessage` type, `obi:hidden`** — the only frame→host message (`iframe-messages.ts`,
  `chat-client.ts`). It is validated separately from the three host→frame types: the frame's bridge
  accepts only `OBI_MESSAGE_TYPES`, the loader accepts `obi:hidden` only from its own iframe's
  `contentWindow` at the exact Obi origin.

## How we know it works

- **Loader, unit** (`frontend/src/features/embed/tests/loader-source-gate.test.ts`):
  `test_loader_hides_when_decoded_source_not_enabled`, `test_loader_hides_when_decoded_source_unknown`,
  `test_loader_mounts_when_decoded_source_enabled_by_display_name`,
  `test_loader_mounts_when_enabled_set_absent_all_enabled` (the fail-safe default),
  `test_loader_mounts_when_eligibility_fetch_fails` (fail-open), and
  `test_loader_destroys_on_obi_hidden_from_own_frame_only` (origin/source-guarded teardown).
- **Visibility client, unit** (`frontend/src/features/chat/tests/chat-client.test.ts`):
  `test_visibility_gets_own_proxy_route_with_bearer_token`, `test_visibility_reports_visible_true`,
  `test_visibility_reports_hidden_with_reason`, `test_visibility_hard_failure_throws_never_masked_as_hidden`,
  `test_visibility_401_notifies_onUnauthorized`, `test_visibility_malformed_body_throws`.
- **Proxy, unit** (`frontend/src/features/chat/tests/route-handlers.test.ts`):
  `mi_gate_visibility_route_wires_to_handle_get_visibility`, `mi_gate_visibility_injects_host_key_and_threads_user_token`,
  `mi_gate_visibility_forwards_backend_hidden_and_hard_failures_verbatim`,
  `mi_gate_visibility_fails_closed_503_when_unconfigured`, `mi_gate_visibility_returns_502_when_the_upstream_call_fails`,
  `mi_gate_visibility_never_exposes_the_host_key_to_the_browser`.
- **Frame, unit/integration** (`frontend/src/app/embed/embed-frame.test.tsx`):
  `test_embed_posts_obi_hidden_when_visibility_reports_hidden` (posted to the exact host origin, never `"*"`),
  `test_embed_does_not_hide_on_visibility_hard_failure`.
- **Browser (e2e)** (`frontend/e2e/widget-hidden-when-source-disabled.spec.ts` + `/test-hosts/quickbooks`
  stub minting `source_system: "quickbooks-online"`, `target_system: "mews"`): launcher count 0.
  **Caveat:** needs `TEST_OBI_PRIVATE_KEY_QUICKBOOKS` (RS256, gitignored — same signed-key class as
  `widget-mounts.spec.ts`). Without the key the token route 503s and the loader fails open (mounts), so
  the spec only passes where the key is configured.
- **Not yet proven:** the live signed-key browser run in CI is deferred to where the quickbooks key exists.
