// @vitest-environment jsdom
/**
 * The Obi embed loader (`obi.js` source, PLAN 11.1c, ADR-0014). Imported fresh per test
 * (`vi.resetModules` + dynamic import) since it installs `window.Obi` as a side effect and keeps
 * iframe/timer state in module scope. `OBI_ORIGIN` falls back to `window.location.origin`
 * (jsdom's default `http://localhost/`) since `__OBI_ORIGIN__` is only replaced by esbuild's
 * `--define` in the real `build:obi` bundle, never under vitest.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const TOKEN_URL = "/api/test-hosts/mews/obi-token";

function fakeJwt(expSecondsFromNow: number): string {
  const header = btoa(JSON.stringify({ alg: "RS256", typ: "JWT" }));
  const payload = btoa(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + expSecondsFromNow }));
  return `${header}.${payload}.signature`;
}

async function loadObi(): Promise<typeof window.Obi> {
  vi.resetModules();
  await import("../loader");
  return window.Obi;
}

describe("Obi loader", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    document.body.innerHTML = "";
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
    document.body.innerHTML = "";
  });

  it("Obi.init injects exactly one iframe pointed at the embed origin's /embed route", async () => {
    const Obi = await loadObi();
    Obi.init({ tokenUrl: TOKEN_URL });

    const iframes = document.querySelectorAll("iframe");
    expect(iframes.length).toBe(1);
    expect(iframes[0].src).toBe(`${window.location.origin}/embed`);
  });

  it("injects the two-tone sparkle 'star' launcher (not a plain text button), matching ChatLauncher", async () => {
    const Obi = await loadObi();
    Obi.init({ tokenUrl: TOKEN_URL });

    const button = document.querySelector("button") as HTMLButtonElement;
    // The star mark, not the old black "Obi" text.
    expect(button.textContent).not.toContain("Obi");
    expect(button.getAttribute("aria-label")).toBe("Open Obi chat");
    expect(button.getAttribute("aria-expanded")).toBe("false");
    const paths = button.querySelectorAll("svg path");
    expect(paths.length).toBe(2);
    // The two-tone fills are Obi's accent + accent-secondary design tokens.
    expect(paths[0].getAttribute("fill")).toBe("#635bff");
    expect(paths[1].getAttribute("fill")).toBe("#8f8af7");
    // Hover/focus states come from a single scoped style tag injected into <head>.
    expect(document.getElementById("obi-launcher-style")).not.toBeNull();
  });

  it("toggles: a second launcher click hides the iframe without clearing the token or re-fetching", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ token: fakeJwt(3600) }), { status: 200 }),
    );
    const Obi = await loadObi();
    Obi.init({ tokenUrl: TOKEN_URL });

    const iframe = document.querySelector("iframe") as HTMLIFrameElement;
    const postMessageSpy = vi.fn();
    Object.defineProperty(iframe, "contentWindow", { value: { postMessage: postMessageSpy } });
    const button = document.querySelector("button") as HTMLButtonElement;

    button.click(); // open
    expect(iframe.style.display).toBe("block");
    expect(button.getAttribute("aria-expanded")).toBe("true");

    button.click(); // close (toggle)
    expect(iframe.style.display).toBe("none");
    expect(button.getAttribute("aria-expanded")).toBe("false");
    // A host-side hide never forgets the token, so no obi:clear is sent.
    for (const call of postMessageSpy.mock.calls) {
      expect(call[0].type).not.toBe("obi:clear");
    }
  });

  it("posts obi:token to the exact OBI_ORIGIN (never '*') after a launcher click fetches the token", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ token: fakeJwt(3600) }), { status: 200 }),
    );

    const Obi = await loadObi();
    Obi.init({ tokenUrl: TOKEN_URL });

    const iframe = document.querySelector("iframe") as HTMLIFrameElement;
    const postMessageSpy = vi.fn();
    Object.defineProperty(iframe, "contentWindow", { value: { postMessage: postMessageSpy } });

    const button = document.querySelector("button") as HTMLButtonElement;
    button.click();

    expect(fetchMock).toHaveBeenCalledWith(TOKEN_URL, { credentials: "same-origin" });
    // the click itself posts obi:open synchronously
    expect(postMessageSpy).toHaveBeenCalledWith({ type: "obi:open" }, window.location.origin);

    await vi.waitFor(() => {
      expect(postMessageSpy).toHaveBeenCalledWith(
        expect.objectContaining({ type: "obi:token" }),
        window.location.origin,
      );
    });

    for (const call of postMessageSpy.mock.calls) {
      expect(call[1]).not.toBe("*");
    }
  });

  it("Obi.clear() posts obi:clear to the exact OBI_ORIGIN", async () => {
    const Obi = await loadObi();
    Obi.init({ tokenUrl: TOKEN_URL });

    const iframe = document.querySelector("iframe") as HTMLIFrameElement;
    const postMessageSpy = vi.fn();
    Object.defineProperty(iframe, "contentWindow", { value: { postMessage: postMessageSpy } });

    Obi.clear();

    expect(postMessageSpy).toHaveBeenCalledWith({ type: "obi:clear" }, window.location.origin);
  });

  it("schedules a silent renewal before the token's exp", async () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "Date"] });
    const token1 = fakeJwt(120); // expires in 2 minutes; renew-before-expiry is 60s -> fires ~60s in
    const token2 = fakeJwt(3600);
    fetchMock
      .mockResolvedValueOnce(new Response(JSON.stringify({ token: token1 }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ token: token2 }), { status: 200 }));

    const Obi = await loadObi();
    Obi.init({ tokenUrl: TOKEN_URL });

    const iframe = document.querySelector("iframe") as HTMLIFrameElement;
    const postMessageSpy = vi.fn();
    Object.defineProperty(iframe, "contentWindow", { value: { postMessage: postMessageSpy } });

    const button = document.querySelector("button") as HTMLButtonElement;
    button.click();

    await vi.advanceTimersByTimeAsync(0); // let the click-time fetch resolve
    expect(fetchMock).toHaveBeenCalledTimes(1);

    // Still well before the scheduled renewal (~60s out).
    await vi.advanceTimersByTimeAsync(30_000);
    expect(fetchMock).toHaveBeenCalledTimes(1);

    // Past the renewal point, still before the token's actual 120s expiry.
    await vi.advanceTimersByTimeAsync(40_000);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("retries the token-endpoint fetch once on a 401 from the platform's own server", async () => {
    fetchMock
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ token: fakeJwt(3600) }), { status: 200 }));

    const Obi = await loadObi();
    Obi.init({ tokenUrl: TOKEN_URL });

    const button = document.querySelector("button") as HTMLButtonElement;
    button.click();

    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  });

  it("LC-5: a token fetch in flight when Obi.clear() runs never posts obi:token", async () => {
    // The click-time fetch hangs; we resolve it by hand AFTER clear() so the fetch is genuinely
    // still in flight at logout — the exact resurrection window LC-5 closes.
    let resolveFetch: ((response: Response) => void) | undefined;
    fetchMock.mockImplementation(
      () => new Promise<Response>((resolve) => (resolveFetch = resolve)),
    );

    const Obi = await loadObi();
    Obi.init({ tokenUrl: TOKEN_URL });

    const iframe = document.querySelector("iframe") as HTMLIFrameElement;
    const postMessageSpy = vi.fn();
    Object.defineProperty(iframe, "contentWindow", { value: { postMessage: postMessageSpy } });

    const button = document.querySelector("button") as HTMLButtonElement;
    button.click(); // posts obi:open + starts the (hanging) token fetch
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    Obi.clear(); // logout while the fetch is still in flight

    // The in-flight fetch now resolves with a perfectly valid token — it must be dropped.
    resolveFetch?.(new Response(JSON.stringify({ token: fakeJwt(3600) }), { status: 200 }));
    await new Promise((resolve) => setTimeout(resolve, 0));
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(postMessageSpy).not.toHaveBeenCalledWith(
      expect.objectContaining({ type: "obi:token" }),
      expect.anything(),
    );
  });

  it("LC-5: a renewal fetch in flight when Obi.init re-points never posts the stale token", async () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "Date"] });
    const token1 = fakeJwt(120); // renewal fires ~60s in (120s exp − 60s renew-before)
    let resolveRenewal: ((response: Response) => void) | undefined;
    fetchMock
      .mockResolvedValueOnce(new Response(JSON.stringify({ token: token1 }), { status: 200 }))
      .mockImplementationOnce(
        () => new Promise<Response>((resolve) => (resolveRenewal = resolve)),
      );

    const Obi = await loadObi();
    Obi.init({ tokenUrl: TOKEN_URL });

    const button = document.querySelector("button") as HTMLButtonElement;
    button.click();
    await vi.advanceTimersByTimeAsync(0); // click-time fetch resolves token1 + schedules renewal
    expect(fetchMock).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(65_000); // renewal fires → fetch #2 is now in flight
    expect(fetchMock).toHaveBeenCalledTimes(2);

    // Re-point Obi at a different signed-in user before the renewal resolves.
    Obi.init({ tokenUrl: "/api/test-hosts/toast/obi-token" });
    const newIframe = document.querySelector("iframe") as HTMLIFrameElement;
    const newSpy = vi.fn();
    Object.defineProperty(newIframe, "contentWindow", { value: { postMessage: newSpy } });

    // The prior identity's renewal now resolves — its token must NOT reach the re-pointed frame.
    resolveRenewal?.(new Response(JSON.stringify({ token: fakeJwt(3600) }), { status: 200 }));
    await vi.advanceTimersByTimeAsync(0);
    await vi.advanceTimersByTimeAsync(0);

    expect(newSpy).not.toHaveBeenCalledWith(
      expect.objectContaining({ type: "obi:token" }),
      expect.anything(),
    );
  });

  it("Obi.destroy() removes the launcher and iframe so no widget is left in the DOM", async () => {
    const Obi = await loadObi();
    Obi.init({ tokenUrl: TOKEN_URL });
    expect(document.querySelectorAll("iframe").length).toBe(1);
    expect(document.querySelectorAll("button").length).toBe(1);

    Obi.destroy();

    expect(document.querySelectorAll("iframe").length).toBe(0);
    expect(document.querySelectorAll("button").length).toBe(0);
  });

  it("re-init points at a new tokenUrl without leaking a second launcher/iframe (user switch)", async () => {
    // The multi-user test host re-points Obi at a different signed-in user by calling init again;
    // init must be idempotent (tear down first) so the host page never accumulates duplicate
    // widgets and the previous user's iframe (its conversation) is gone.
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ token: fakeJwt(3600) }), { status: 200 }),
    );
    const Obi = await loadObi();

    Obi.init({ tokenUrl: "/api/test-hosts/mews/obi-token" });
    const firstIframe = document.querySelector("iframe");
    Obi.init({ tokenUrl: "/api/test-hosts/toast/obi-token" });

    expect(document.querySelectorAll("iframe").length).toBe(1);
    expect(document.querySelectorAll("button").length).toBe(1);
    // The original iframe was torn down, not reused — so no stale conversation carries over.
    expect(document.querySelector("iframe")).not.toBe(firstIframe);

    // The launcher now fetches the NEW user's token endpoint.
    (document.querySelector("button") as HTMLButtonElement).click();
    expect(fetchMock).toHaveBeenCalledWith("/api/test-hosts/toast/obi-token", {
      credentials: "same-origin",
    });
  });
});
