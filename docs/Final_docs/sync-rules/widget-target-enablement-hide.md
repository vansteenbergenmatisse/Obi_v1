# Widget target-enablement hide (frontend)

- **Workflow:** embed / widget (frontend)
- **Owning code:** `frontend/src/features/embed/loader.ts` (the host-page `obi.js` loader),
  `frontend/src/app/embed/embed-frame.tsx` (the `/embed` frame), `frontend/src/features/chat/api/chat-client.ts`
  (`checkVisibility`), `frontend/src/features/chat/server/route-handlers.ts` (`handleGetVisibility`)
  + `frontend/src/app/api/chat/visibility/route.ts` (the proxy), `packages/contracts/src/iframe-messages.ts`
  (the `obi:hidden` message)
- **Design panel:** panel mi-gate (target-enablement visibility gate), directed path
- **Authorized by:** ADR-0022 "Target-Enablement Widget Eligibility in the Directed Path" (amending
  ADR-0020 D4/D5) — the backend 403 (`reason: target_not_enabled`) is the authority; this hide is UX
- **Status:** Implemented, needs changing → Unverified (frontend coded + unit/mocked-browser proven;
  the signed-key e2e needs a local key, see below)

## What it does

When Obi is embedded on a platform page whose verified directed token points at a **target** integration
that is not in the enabled set (`knowledge-base/config/product_catalog.json` → `enabled_targets`, today
`["mews","toast","opera-cloud"]`), the widget never appears. Two layers:

1. **Load-time, no-flash (loader).** `__OBI_ENABLED_TARGETS__` is injected into `obi.js` at build by
   esbuild `--define` from `enabled_targets` — exactly how `__OBI_ORIGIN__` is injected
   (`frontend/package.json` `build:obi`). In `init()`, before mounting, the loader fetches the token once
   and decodes its (display-only, non-trust) `target_system`; if that target is not enabled it returns
   without mounting — no launcher, no iframe, no flash. The set absent/empty ⇒ **all enabled** (fail-open);
   a failed eligibility fetch or a token with no `target_system` (a legacy single-integration note) also
   mounts. The trust-bearing token fetch still happens fresh at click.
2. **Server-authoritative cross-check (frame).** On every token receipt, `embed-frame.tsx` calls
   `GET /chat/visibility` through the same-origin Next proxy that injects the host `CHAT_API_KEY`
   (`/api/chat/visibility` → `handleGetVisibility`, mirroring `POST /api/chat`). On `{"visible":false,
   "reason":"target_not_enabled"}` it posts the one frame→host message `obi:hidden`, and the loader
   `destroy()`s the widget. A hard failure (400/401/429/503) is **never** coerced to hidden — the widget
   stays mounted.

## Why it does it

The directed routing path (ADR-0020) does not itself gate widget visibility; the allowlist lapse let a
not-yet-enabled target still render Obi. ADR-0022 partially reverses that for **widget eligibility only**
(retrieval routing is unchanged). The backend's `POST /chat` 403 with `reason: target_not_enabled` is the
real authority — it never names the product id (never-bend rule 10). The frontend hide is pure UX: show
nothing rather than a widget that can only refuse. The two-layer split exists so the common case has no
flash (the loader decodes locally) while correctness stays server-authoritative (the probe can hide a
widget the loader mounted, e.g. when the enabled set was absent at build). Fail-open on every uncertain
signal (missing set, fetch failure, probe outage) is deliberate: an outage must not blank the widget for
everyone, and the backend 403 still blocks the actual answer.

Two conventions are bent, both authorized by ADR-0022 and isolated to this component:
- one **eligibility-only token fetch at `init`** in addition to the click-time fetch (`loader.ts`);
- a **4th `ObiMessage` type, `obi:hidden`** — the only frame→host message (`iframe-messages.ts`,
  `chat-client.ts`). It is validated separately from the three host→frame types: the frame's bridge
  accepts only `OBI_MESSAGE_TYPES`, the loader accepts `obi:hidden` only from its own iframe's
  `contentWindow` at the exact Obi origin.

## How we know it works

- **Loader, unit** (`frontend/src/features/embed/tests/loader-target-gate.test.ts`): `test_loader_hides_when_decoded_target_not_enabled`,
  `test_loader_mounts_when_decoded_target_enabled`, `test_loader_mounts_when_enabled_set_absent_all_enabled`
  (the fail-safe default), `test_loader_mounts_when_eligibility_fetch_fails` (fail-open), and
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
- **Browser (e2e)** (`frontend/e2e/widget-hidden-when-target-disabled.spec.ts` + `/test-hosts/quickbooks`
  stub minting `target_system: "quickbooks-online"`): launcher count 0. **Caveat:** needs
  `TEST_OBI_PRIVATE_KEY_QUICKBOOKS` (RS256, gitignored — same signed-key class as `widget-mounts.spec.ts`).
  Without the key the token route 503s and the loader fails open (mounts), so the committed spec only
  passes where the key is configured. Validated locally with an ephemeral key (fresh server, CI mode):
  the spec passes (launcher count 0).
- **Gate:** `make boundaries` green; `pnpm typecheck` clean; full `vitest` suite green for the touched
  files (one pre-existing, unrelated unhandled-rejection flake in `loader.test.ts`'s renewal-timer path,
  present on the un-modified loader too).
- **Not yet proven:** the backend side (403 precedence, `/chat/visibility` live answer) is owned elsewhere;
  the live signed-key browser run in CI is deferred to where the quickbooks key exists.
