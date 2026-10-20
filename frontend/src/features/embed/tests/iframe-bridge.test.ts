// @vitest-environment jsdom
/**
 * Frame-side bridge — PLAN 11.1c. Uses `window.dispatchEvent(new MessageEvent(...))`
 * with an explicit `source` so both the allowed-parent and rejected-non-parent cases are under
 * direct control (jsdom's top-level `window.parent` is `window` itself, since there is no real
 * outer frame in a test).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getToken, initIframeBridge } from "../iframe-bridge";

const ALLOWED_ORIGIN = "https://app.mews.com";
const DISALLOWED_ORIGIN = "https://evil.example.com";

function post(data: unknown, origin: string, source: MessageEventSource | null = window.parent) {
  window.dispatchEvent(new MessageEvent("message", { data, origin, source }));
}

/** A syntactically-valid JWT carrying the given display-only business claims (no real signature —
 * the bridge decodes claims for equality only, never for auth). */
function jwtWithClaims(claims: Record<string, unknown>): string {
  const header = btoa(JSON.stringify({ alg: "RS256", typ: "JWT" }));
  const payload = btoa(JSON.stringify(claims));
  return `${header}.${payload}.signature`;
}

/** A JWT whose payload is encoded in the REAL base64url alphabet (url-safe `-`/`_`, `=` padding
 * stripped) — what an actual JWT looks like, unlike `btoa`'s padded-standard base64. Exercises the
 * bridge's `-`→`+` / `_`→`/` conversion and its padless `atob`. */
function jwtWithClaimsB64url(claims: Record<string, unknown>): string {
  const header = btoa(JSON.stringify({ alg: "RS256", typ: "JWT" }));
  const std = btoa(JSON.stringify(claims));
  const payload = std.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  return `${header}.${payload}.signature`;
}

describe("initIframeBridge", () => {
  let teardown: (() => void) | undefined;
  let warnSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    warnSpy = vi.spyOn(console, "warn").mockImplementation(() => undefined);
  });

  afterEach(() => {
    teardown?.();
    teardown = undefined;
    warnSpy.mockRestore();
  });

  it("sets the token from obi:token when the origin is allowed and the source is the parent", () => {
    teardown = initIframeBridge({ allowedOrigins: [ALLOWED_ORIGIN] });

    post({ type: "obi:token", token: "jwt-abc" }, ALLOWED_ORIGIN);

    expect(getToken()).toBe("jwt-abc");
    expect(warnSpy).not.toHaveBeenCalled();
  });

  it("ignores obi:token from a disallowed origin, warns once, and leaves the token null", () => {
    teardown = initIframeBridge({ allowedOrigins: [ALLOWED_ORIGIN] });

    post({ type: "obi:token", token: "jwt-abc" }, DISALLOWED_ORIGIN);

    expect(getToken()).toBeNull();
    expect(warnSpy).toHaveBeenCalledTimes(1);
  });

  it("ignores a message whose source is not window.parent, even from an allowed origin", () => {
    teardown = initIframeBridge({ allowedOrigins: [ALLOWED_ORIGIN] });

    post({ type: "obi:token", token: "jwt-abc" }, ALLOWED_ORIGIN, null);

    expect(getToken()).toBeNull();
    expect(warnSpy).toHaveBeenCalledTimes(1);
  });

  it("drops the token on obi:clear", () => {
    teardown = initIframeBridge({ allowedOrigins: [ALLOWED_ORIGIN] });
    post({ type: "obi:token", token: "jwt-abc" }, ALLOWED_ORIGIN);
    expect(getToken()).toBe("jwt-abc");

    post({ type: "obi:clear" }, ALLOWED_ORIGIN);

    expect(getToken()).toBeNull();
  });

  it("invokes onToken/onClear callbacks", () => {
    const onToken = vi.fn();
    const onClear = vi.fn();
    teardown = initIframeBridge({ allowedOrigins: [ALLOWED_ORIGIN], onToken, onClear });

    post({ type: "obi:token", token: "jwt-abc" }, ALLOWED_ORIGIN);
    expect(onToken).toHaveBeenCalledWith("jwt-abc");

    post({ type: "obi:clear" }, ALLOWED_ORIGIN);
    expect(onClear).toHaveBeenCalledTimes(1);
  });

  it("invokes onOpen on obi:open without setting a token (the message carries no data)", () => {
    const onOpen = vi.fn();
    teardown = initIframeBridge({ allowedOrigins: [ALLOWED_ORIGIN], onOpen });

    expect(() => post({ type: "obi:open" }, ALLOWED_ORIGIN)).not.toThrow();
    expect(onOpen).toHaveBeenCalledTimes(1);
    expect(getToken()).toBeNull();
  });

  it("does not invoke onOpen for an obi:open from a disallowed origin", () => {
    const onOpen = vi.fn();
    teardown = initIframeBridge({ allowedOrigins: [ALLOWED_ORIGIN], onOpen });

    post({ type: "obi:open" }, DISALLOWED_ORIGIN);

    expect(onOpen).not.toHaveBeenCalled();
    expect(warnSpy).toHaveBeenCalledTimes(1);
  });

  it("BIT-7: rejects obi:token with a missing token (currentToken stays null)", () => {
    const onToken = vi.fn();
    teardown = initIframeBridge({ allowedOrigins: [ALLOWED_ORIGIN], onToken });

    post({ type: "obi:token" }, ALLOWED_ORIGIN);

    expect(getToken()).toBeNull();
    expect(onToken).not.toHaveBeenCalled();
  });

  it("BIT-7: rejects obi:token with a non-string token (currentToken stays null)", () => {
    const onToken = vi.fn();
    teardown = initIframeBridge({ allowedOrigins: [ALLOWED_ORIGIN], onToken });

    post({ type: "obi:token", token: 12345 }, ALLOWED_ORIGIN);
    post({ type: "obi:token", token: { jwt: "x" } }, ALLOWED_ORIGIN);
    post({ type: "obi:token", token: "" }, ALLOWED_ORIGIN);

    expect(getToken()).toBeNull();
    expect(onToken).not.toHaveBeenCalled();
  });

  it("BIT-7: ignores an unknown message type (e.g. obi:evil) — no token stored, no callback", () => {
    const onToken = vi.fn();
    const onOpen = vi.fn();
    const onClear = vi.fn();
    teardown = initIframeBridge({ allowedOrigins: [ALLOWED_ORIGIN], onToken, onOpen, onClear });

    expect(() =>
      post({ type: "obi:evil", token: "jwt-abc" }, ALLOWED_ORIGIN),
    ).not.toThrow();

    expect(getToken()).toBeNull();
    expect(onToken).not.toHaveBeenCalled();
    expect(onOpen).not.toHaveBeenCalled();
    expect(onClear).not.toHaveBeenCalled();
  });

  it("LC-2/LC-3/LC-6: fires onScopeChange when a renewal token changes integration/company", () => {
    const onScopeChange = vi.fn();
    teardown = initIframeBridge({ allowedOrigins: [ALLOWED_ORIGIN], onScopeChange });

    // First token establishes the scope — no prior scope to differ from, so no reset.
    post(
      { type: "obi:token", token: jwtWithClaims({ integration: "mews", company_id: "c1" }) },
      ALLOWED_ORIGIN,
    );
    expect(onScopeChange).not.toHaveBeenCalled();

    // A renewal for the SAME scope (only exp refreshed) must NOT reset the conversation.
    post(
      { type: "obi:token", token: jwtWithClaims({ integration: "mews", company_id: "c1" }) },
      ALLOWED_ORIGIN,
    );
    expect(onScopeChange).not.toHaveBeenCalled();

    // A token whose integration/company differ DID cross into another corpus/identity → reset.
    post(
      { type: "obi:token", token: jwtWithClaims({ integration: "toast", company_id: "c2" }) },
      ALLOWED_ORIGIN,
    );
    expect(onScopeChange).toHaveBeenCalledTimes(1);
  });

  it("LC-F2: decodeScope reads claims from a REAL base64url payload (url-safe -/_, no = padding)", () => {
    const onScopeChange = vi.fn();
    teardown = initIframeBridge({ allowedOrigins: [ALLOWED_ORIGIN], onScopeChange });

    // A claim value whose STANDARD base64 carries +, / and = — so the url-safe conversion in the
    // fixture (and the bridge's inverse `-`→`+` / `_`→`/` + padless atob) is genuinely exercised;
    // a padded-standard-base64 fixture via btoa alone would never hit the `-`/`_` branch.
    const claims = { integration: "mews", company_id: "co-????>>>" };
    const std = btoa(JSON.stringify(claims));
    expect(/[+/=]/.test(std)).toBe(true); // fixture guard: this really is a non-trivial base64url case
    const b64urlToken = jwtWithClaimsB64url(claims);
    expect(b64urlToken.split(".")[1]).not.toContain("="); // no padding, url-safe alphabet

    // A standard-base64 token establishes the scope; the base64url token carries the SAME claims,
    // so if the url-safe payload decoded correctly it must NOT count as a scope change.
    post({ type: "obi:token", token: jwtWithClaims(claims) }, ALLOWED_ORIGIN);
    expect(onScopeChange).not.toHaveBeenCalled();
    post({ type: "obi:token", token: b64urlToken }, ALLOWED_ORIGIN);
    expect(onScopeChange).not.toHaveBeenCalled();

    // A base64url token whose claims DIFFER must decode correctly and trigger the reset — proving
    // the decode read the real values, not garbage.
    post(
      {
        type: "obi:token",
        token: jwtWithClaimsB64url({ integration: "toast", company_id: "c2" }),
      },
      ALLOWED_ORIGIN,
    );
    expect(onScopeChange).toHaveBeenCalledTimes(1);
  });

  it("mi-contract · 8.4.2: a slot-shaped note (context.slots) is accepted and threaded like a legacy note", () => {
    // panel mi-contract · substep 8.4.2 — the note now carries company_id + three slots inside the
    // opaque JWT (T6 no-op: same `obi:token` message, richer claims). The bridge must accept it
    // exactly as it accepts a legacy single-integration note.
    const onToken = vi.fn();
    teardown = initIframeBridge({ allowedOrigins: [ALLOWED_ORIGIN], onToken });

    const slotToken = jwtWithClaims({
      company_id: "c1",
      context: { slots: { pos: "toast", pms: "mews", accounting: null } },
    });
    post({ type: "obi:token", token: slotToken }, ALLOWED_ORIGIN);

    expect(getToken()).toBe(slotToken);
    expect(onToken).toHaveBeenCalledWith(slotToken);
    expect(warnSpy).not.toHaveBeenCalled();
  });

  it("mi-contract · 8.4.2: a renewal that changes a SLOT (not integration/company) resets the conversation", () => {
    // panel mi-contract · substep 8.4.2 — two slot-shaped notes for the SAME company_id, differing
    // only in the PMS slot, crossed into a different integration context (LC-2/LC-3/LC-6) → reset.
    // Pre-8.4.2 `decodeScope` read only `integration`/`company_id`, so these two looked identical
    // and NO reset fired (the red state this proves fixed).
    const onScopeChange = vi.fn();
    teardown = initIframeBridge({ allowedOrigins: [ALLOWED_ORIGIN], onScopeChange });

    post(
      {
        type: "obi:token",
        token: jwtWithClaims({
          company_id: "c1",
          context: { slots: { pos: "toast", pms: "mews", accounting: null } },
        }),
      },
      ALLOWED_ORIGIN,
    );
    expect(onScopeChange).not.toHaveBeenCalled();

    // Same company, same POS, but the PMS slot changed — a different integration context.
    post(
      {
        type: "obi:token",
        token: jwtWithClaims({
          company_id: "c1",
          context: { slots: { pos: "toast", pms: "opera-cloud", accounting: null } },
        }),
      },
      ALLOWED_ORIGIN,
    );
    expect(onScopeChange).toHaveBeenCalledTimes(1);
  });

  it("mi-contract · 8.4.2: a renewal to the IDENTICAL slot-shaped context does NOT reset", () => {
    // panel mi-contract · substep 8.4.2 — a plain token refresh (same slots) must not wipe the
    // open conversation.
    const onScopeChange = vi.fn();
    teardown = initIframeBridge({ allowedOrigins: [ALLOWED_ORIGIN], onScopeChange });

    const claims = {
      company_id: "c1",
      context: { slots: { pos: "toast", pms: "mews", accounting: null } },
    };
    post({ type: "obi:token", token: jwtWithClaims(claims) }, ALLOWED_ORIGIN);
    post({ type: "obi:token", token: jwtWithClaims(claims) }, ALLOWED_ORIGIN);
    expect(onScopeChange).not.toHaveBeenCalled();
  });

  it("mi-contract · 8.4.2: crossing from a legacy note to a slot-shaped note resets the conversation", () => {
    // panel mi-contract · substep 8.4.2 — a legacy single-integration note followed by a
    // slot-shaped note for a different company is a different corpus/identity → reset.
    const onScopeChange = vi.fn();
    teardown = initIframeBridge({ allowedOrigins: [ALLOWED_ORIGIN], onScopeChange });

    post(
      { type: "obi:token", token: jwtWithClaims({ integration: "mews", company_id: "c1" }) },
      ALLOWED_ORIGIN,
    );
    expect(onScopeChange).not.toHaveBeenCalled();

    post(
      {
        type: "obi:token",
        token: jwtWithClaims({
          company_id: "c2",
          context: { slots: { pos: "toast", pms: "mews", accounting: null } },
        }),
      },
      ALLOWED_ORIGIN,
    );
    expect(onScopeChange).toHaveBeenCalledTimes(1);
  });

  it("widget · 9.3.1: a renewal that switches the directed connection resets the conversation", () => {
    // panel mi-contract/mi-gate · substep 9.3.1 — two directed notes for the SAME business_id,
    // differing only in which systems the connection joins, crossed into a different connection
    // context (ADR-directed-source-target-routing-labels Option A) → reset. Without source/target in the scope signature these two
    // would look identical and NO reset would fire (the red state this proves fixed).
    const onScopeChange = vi.fn();
    teardown = initIframeBridge({ allowedOrigins: [ALLOWED_ORIGIN], onScopeChange });

    post(
      {
        type: "obi:token",
        token: jwtWithClaims({
          business_id: "B-3075",
          source_system: "toast",
          target_system: "mews",
        }),
      },
      ALLOWED_ORIGIN,
    );
    expect(onScopeChange).not.toHaveBeenCalled();

    // Same business, but the target changed (mews → xero) — a different connection.
    post(
      {
        type: "obi:token",
        token: jwtWithClaims({
          business_id: "B-3075",
          source_system: "toast",
          target_system: "xero",
        }),
      },
      ALLOWED_ORIGIN,
    );
    expect(onScopeChange).toHaveBeenCalledTimes(1);
  });

  it("widget · 9.3.1: a direction swap (source↔target) resets the conversation", () => {
    // panel mi-gate · substep 9.3.1 — direction is primary (ADR-directed-source-target-routing-labels D4): toast→mews is NOT the
    // same connection as mews→toast, so a renewal that swaps the direction must reset the thread.
    const onScopeChange = vi.fn();
    teardown = initIframeBridge({ allowedOrigins: [ALLOWED_ORIGIN], onScopeChange });

    post(
      {
        type: "obi:token",
        token: jwtWithClaims({ business_id: "B-1", source_system: "toast", target_system: "mews" }),
      },
      ALLOWED_ORIGIN,
    );
    post(
      {
        type: "obi:token",
        token: jwtWithClaims({ business_id: "B-1", source_system: "mews", target_system: "toast" }),
      },
      ALLOWED_ORIGIN,
    );
    expect(onScopeChange).toHaveBeenCalledTimes(1);
  });

  it("widget · 9.3.1: a renewal to the IDENTICAL directed connection does NOT reset", () => {
    // panel mi-contract · substep 9.3.1 — a plain token refresh (same source/target/business_id)
    // must not wipe the open conversation.
    const onScopeChange = vi.fn();
    teardown = initIframeBridge({ allowedOrigins: [ALLOWED_ORIGIN], onScopeChange });

    const claims = { business_id: "B-9", source_system: "toast", target_system: "mews" };
    post({ type: "obi:token", token: jwtWithClaims(claims) }, ALLOWED_ORIGIN);
    post({ type: "obi:token", token: jwtWithClaims(claims) }, ALLOWED_ORIGIN);
    expect(onScopeChange).not.toHaveBeenCalled();
  });

  it("sec · 8.4.2: a slot-shaped note is held in memory only — no web storage, cookie, or logged context", () => {
    // panel mi-contract · substep 8.4.2 — the extended context rides inside the opaque JWT; storing
    // it must not spill the slot values to sessionStorage/localStorage/a cookie or any console
    // channel (never-bend rule 10).
    sessionStorage.clear();
    globalThis.localStorage?.clear();
    const cookieBefore = document.cookie;
    const consoleSpies = (["log", "info", "error", "debug"] as const).map((m) =>
      vi.spyOn(console, m).mockImplementation(() => undefined),
    );
    teardown = initIframeBridge({ allowedOrigins: [ALLOWED_ORIGIN] });

    const slotToken = jwtWithClaims({
      company_id: "secret-co",
      context: { slots: { pos: "toast", pms: "mews", accounting: "quickbooks-online" } },
    });
    post({ type: "obi:token", token: slotToken }, ALLOWED_ORIGIN);

    expect(getToken()).toBe(slotToken); // non-vacuous: the note really was handled
    expect(sessionStorage.length).toBe(0);
    expect(globalThis.localStorage?.length ?? 0).toBe(0);
    expect(document.cookie).toBe(cookieBefore);
    for (const spy of [warnSpy, ...consoleSpies]) {
      for (const call of spy.mock.calls) {
        const serialized = JSON.stringify(call);
        expect(serialized).not.toContain(slotToken);
        expect(serialized).not.toContain("secret-co");
      }
    }
    for (const spy of consoleSpies) spy.mockRestore();
  });

  it("BIT-9: logs rejection codes/events only — the token value never reaches any console output", () => {
    // Negative test: accepted-vs-rejected is logged as fixed code strings, never the JWT. Drive an
    // accepted path plus both rejection paths, all carrying the SAME token, and assert no console
    // channel ever received the token value.
    const token = "jwt.SECRET-payload.sig-value";
    const otherSpies = (["log", "info", "error", "debug"] as const).map((m) =>
      vi.spyOn(console, m).mockImplementation(() => undefined),
    );
    teardown = initIframeBridge({ allowedOrigins: [ALLOWED_ORIGIN] });

    post({ type: "obi:token", token }, ALLOWED_ORIGIN); // accepted (no console)
    post({ type: "obi:token", token }, DISALLOWED_ORIGIN); // rejected origin -> warn code
    post({ type: "obi:token", token }, ALLOWED_ORIGIN, null); // non-parent source -> warn code

    // Non-vacuous: the accepted token really was stored, so "never logged" is a real guarantee.
    expect(getToken()).toBe(token);
    expect(warnSpy).toHaveBeenCalled(); // the rejections DID log — with codes only
    for (const spy of [warnSpy, ...otherSpies]) {
      for (const call of spy.mock.calls) {
        expect(JSON.stringify(call)).not.toContain(token);
      }
    }
    for (const spy of otherSpies) spy.mockRestore();
  });

  it("resets to null token on re-init (a fresh frame load never carries a stale token)", () => {
    teardown = initIframeBridge({ allowedOrigins: [ALLOWED_ORIGIN] });
    post({ type: "obi:token", token: "jwt-abc" }, ALLOWED_ORIGIN);
    expect(getToken()).toBe("jwt-abc");
    teardown();

    teardown = initIframeBridge({ allowedOrigins: [ALLOWED_ORIGIN] });
    expect(getToken()).toBeNull();
  });
});

describe("getToken", () => {
  it("never reads any web storage API", () => {
    const localGet = vi.spyOn(Storage.prototype, "getItem");
    initIframeBridge({ allowedOrigins: [ALLOWED_ORIGIN] })();

    getToken();

    expect(localGet).not.toHaveBeenCalled();
    localGet.mockRestore();
  });

  it("never WRITES the token to web storage or a cookie when handling obi:token (BIT-3/BIT-9)", () => {
    // The rule is "never a cookie / localStorage / sessionStorage" — a READ-only spy misses a
    // WRITE, and in jsdom a `Storage.prototype.setItem` spy is NOT hit by `sessionStorage.setItem`
    // (the instance has its own method), so we assert storage CONTENTS directly (a write bumps
    // `.length`). Non-vacuous: getToken() proves the token was genuinely handled, not dropped.
    // (This jsdom env exposes sessionStorage; localStorage is guarded defensively for portability.)
    sessionStorage.clear();
    globalThis.localStorage?.clear();
    const cookieBefore = document.cookie;
    const warn = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    const teardown = initIframeBridge({ allowedOrigins: [ALLOWED_ORIGIN] });

    post({ type: "obi:token", token: "jwt-secret-xyz" }, ALLOWED_ORIGIN);

    expect(getToken()).toBe("jwt-secret-xyz");
    expect(sessionStorage.length).toBe(0); // no sessionStorage write
    expect(globalThis.localStorage?.length ?? 0).toBe(0); // no localStorage write
    expect(document.cookie).toBe(cookieBefore); // no cookie write

    teardown();
    warn.mockRestore();
  });
});
