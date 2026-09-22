// @vitest-environment jsdom
/**
 * Frame-side bridge — PLAN 11.1c, ADR-0014. Uses `window.dispatchEvent(new MessageEvent(...))`
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
});
