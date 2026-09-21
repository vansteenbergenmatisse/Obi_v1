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
