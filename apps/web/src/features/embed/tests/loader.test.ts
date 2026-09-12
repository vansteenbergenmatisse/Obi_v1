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
});
