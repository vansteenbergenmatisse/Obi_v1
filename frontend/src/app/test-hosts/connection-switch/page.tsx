/**
 * Route-owned test host for the directed-connection switch browser proof (substep 9.3.1,
 * ADR-directed-source-target-routing-labels Option A) — disposable local-browser scaffolding, colocated under `app/test-hosts/**`
 * like the other test hosts, never imported by product code.
 *
 * It renders the REAL embed frame (`EmbedFrame` — the same `initIframeBridge` + `ChatSessionProvider`
 * + `PanelBody` wiring the deployed `/embed` page uses) and drives it with `postMessage`, exactly
 * as the host loader (`obi.js`) would. The bridge is initialised with THIS page's own origin as its
 * single allowed origin, so the proof never couples to the platform allowlist and works under
 * whatever host Playwright serves. The tokens are hand-built, unsigned JWTs: the bridge decodes
 * claims for scope-equality only, never for auth (the backend `TokenVerifier` is the authority),
 * so an unsigned note is a faithful stand-in for the switch-resets-thread behaviour.
 */
"use client";

import { useEffect, useState } from "react";
import { EmbedFrame } from "../../embed/embed-frame";

/** A syntactically-valid JWT carrying display-only claims (no real signature). Mirrors the fixture
 * in `features/embed/tests/iframe-bridge.test.ts`. */
function jwtWithClaims(claims: Record<string, unknown>): string {
  const header = btoa(JSON.stringify({ alg: "RS256", typ: "JWT" }));
  const payload = btoa(JSON.stringify(claims));
  return `${header}.${payload}.signature`;
}

// Two directed connections for the SAME business id — a partner switch (different target, and a
// direction swap of source/target), which must reset the open thread (no cross-connection bleed).
const TOKEN_A = jwtWithClaims({
  business_id: "B-3075",
  source_system: "toast",
  target_system: "mews",
});
const TOKEN_B = jwtWithClaims({
  business_id: "B-3075",
  source_system: "opera-cloud",
  target_system: "toast",
});

export default function ConnectionSwitchHost() {
  const [origin, setOrigin] = useState<string | null>(null);
  useEffect(() => setOrigin(window.location.origin), []);

  function postToFrame(message: Record<string, unknown>): void {
    window.postMessage(message, window.location.origin);
  }

  return (
    <main style={{ padding: "2rem", maxWidth: "44rem" }}>
      <h1>Obi test host: directed connection switch</h1>
      <p>
        Drives the real embed frame with directed <code>source → target</code> tokens (substep
        9.3.1). Open the panel, hand it connection A, ask a question, then switch to connection B —
        the thread must reset.
      </p>
      <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", margin: "1rem 0" }}>
        <button type="button" data-testid="open" onClick={() => postToFrame({ type: "obi:open" })}>
          Open panel
        </button>
        <button
          type="button"
          data-testid="connection-a"
          onClick={() => postToFrame({ type: "obi:token", token: TOKEN_A })}
        >
          Connection A (Toast → Mews)
        </button>
        <button
          type="button"
          data-testid="connection-b"
          onClick={() => postToFrame({ type: "obi:token", token: TOKEN_B })}
        >
          Connection B (Opera Cloud → Toast)
        </button>
      </div>
      {origin ? <EmbedFrame allowedOrigins={[origin]} /> : null}
    </main>
  );
}
