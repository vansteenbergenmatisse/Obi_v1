// @vitest-environment jsdom
/**
 * Loader source-enablement hide (ADR-0023, supersedes the ADR-0022 target gate; panel mi-gate).
 * The loader decodes the directed `source_system` claim at `init()` and refuses to mount the
 * launcher/iframe when the source is not one Obi supports — a no-flash, load-time hide,
 * cross-checked server-side by `GET /chat/visibility` → `obi:hidden` (covered separately). The
 * target is never checked: a source can have hundreds of targets.
 *
 * `__OBI_ENABLED_SOURCES__` is replaced by esbuild `--define` only in the real `build:obi` bundle,
 * as the normalized (lowercase, single-spaced) ids, display names and aliases of the catalog's
 * `enabled_sources`; under vitest it is undefined, so a test that needs a concrete set stubs it on
 * `globalThis` BEFORE importing the loader (the module reads it once at load). An absent/empty set
 * means "all sources enabled" — so every existing loader test, which never stubs it, keeps mounting
 * synchronously.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const TOKEN_URL = "/api/test-hosts/toast/obi-token?form=directed";

/** The names the real build injects for enabled_sources = mews, toast, opera-cloud. */
const ENABLED_NAMES = ["mews", "toast", "opera-cloud", "opera cloud", "operacloud"];

/** A syntactically-valid JWT carrying display-only `source_system`/`target_system` claims (no
 * real signature — the loader decodes it for the hide decision only, never for auth). */
function jwtWith(source: string | null, target: string | null = "NetSuite"): string {
  const header = btoa(JSON.stringify({ alg: "RS256", typ: "JWT" }));
  const claims: Record<string, unknown> = { exp: Math.floor(Date.now() / 1000) + 3600 };
  if (source !== null) claims.source_system = source;
  if (target !== null) claims.target_system = target;
  const payload = btoa(JSON.stringify(claims));
  return `${header}.${payload}.signature`;
}

async function loadObi(): Promise<typeof window.Obi> {
  vi.resetModules();
  await import("../loader");
  return window.Obi;
}

describe("Obi loader · source-enablement hide (panel mi-gate · ADR-0023)", () => {
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

  // panel mi-gate · ADR-0023 — a known source that is not enabled never mounts: no launcher, no
  // iframe, no flash. xero is in the catalog but not in enabled_sources.
  it("test_loader_hides_when_decoded_source_not_enabled", async () => {
    vi.stubGlobal("__OBI_ENABLED_SOURCES__", JSON.stringify(ENABLED_NAMES));
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ token: jwtWith("Xero", "Mews") }), { status: 200 }),
    );

    const Obi = await loadObi();
    Obi.init({ tokenUrl: TOKEN_URL });

    // The gate awaits the eligibility fetch; give microtasks a few turns to settle, then assert
    // nothing ever mounted.
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledWith(TOKEN_URL, { credentials: "same-origin" }));
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(document.querySelectorAll("iframe").length).toBe(0);
    expect(document.querySelectorAll("button.obi-launcher").length).toBe(0);
  });

  // panel mi-gate · ADR-0023 — a source the catalog does not know (Base's "PEP PMS") is not a
  // supported source either, so the widget never mounts.
  it("test_loader_hides_when_decoded_source_unknown", async () => {
    vi.stubGlobal("__OBI_ENABLED_SOURCES__", JSON.stringify(ENABLED_NAMES));
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ token: jwtWith("PEP PMS", "NetSuite") }), { status: 200 }),
    );

    const Obi = await loadObi();
    Obi.init({ tokenUrl: TOKEN_URL });

    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalled());
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(document.querySelectorAll("iframe").length).toBe(0);
    expect(document.querySelectorAll("button.obi-launcher").length).toBe(0);
  });

  // panel mi-gate · ADR-0023 — an enabled source mounts whatever its target, and a display name
  // ("Opera  Cloud", any case or spacing) matches like the backend's lenient resolver.
  it("test_loader_mounts_when_decoded_source_enabled_by_display_name", async () => {
    vi.stubGlobal("__OBI_ENABLED_SOURCES__", JSON.stringify(ENABLED_NAMES));
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ token: jwtWith("Opera  CLOUD", "NetSuite") }), { status: 200 }),
    );

    const Obi = await loadObi();
    Obi.init({ tokenUrl: TOKEN_URL });

    await vi.waitFor(() => {
      expect(document.querySelectorAll("iframe").length).toBe(1);
      expect(document.querySelectorAll("button.obi-launcher").length).toBe(1);
    });
  });

  // panel mi-gate · ADR-0023 — default: an absent enabled set means "all enabled", so even a
  // disabled-looking source mounts (the build simply didn't inject the set). Proves the fail-safe
  // default `__OBI_ENABLED_SOURCES__` empty/absent ⇒ all enabled.
  it("test_loader_mounts_when_enabled_set_absent_all_enabled", async () => {
    // No stub for __OBI_ENABLED_SOURCES__ → the module sees it undefined.
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ token: jwtWith("quickbooks-online") }), { status: 200 }),
    );

    const Obi = await loadObi();
    Obi.init({ tokenUrl: TOKEN_URL });

    // Mounts synchronously (no eligibility fetch when the set is absent).
    expect(document.querySelectorAll("iframe").length).toBe(1);
    expect(document.querySelectorAll("button.obi-launcher").length).toBe(1);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  // panel mi-gate · ADR-0023 — fail-open: a failed eligibility fetch (e.g. the platform's token
  // endpoint is down) must NOT hide the widget. The server-authoritative visibility probe is the
  // real gate; the load-time decode is a no-flash optimization only.
  it("test_loader_mounts_when_eligibility_fetch_fails", async () => {
    vi.stubGlobal("__OBI_ENABLED_SOURCES__", JSON.stringify(ENABLED_NAMES));
    fetchMock.mockResolvedValue(new Response(null, { status: 503 }));

    const Obi = await loadObi();
    Obi.init({ tokenUrl: TOKEN_URL });

    await vi.waitFor(() => {
      expect(document.querySelectorAll("iframe").length).toBe(1);
      expect(document.querySelectorAll("button.obi-launcher").length).toBe(1);
    });
  });

  // panel mi-gate · ADR-0023 — the server-authoritative cross-check: an `obi:hidden` posted by the
  // loader's OWN iframe, from the exact Obi origin, tears the widget down. A message from a foreign
  // origin is ignored (no destroy).
  it("test_loader_destroys_on_obi_hidden_from_own_frame_only", async () => {
    // No enabled-set stub → mounts synchronously.
    const Obi = await loadObi();
    Obi.init({ tokenUrl: TOKEN_URL });
    const iframe = document.querySelector("iframe") as HTMLIFrameElement;
    // jsdom gives the <iframe> a real contentWindow; pin it to `window` so a dispatched
    // MessageEvent can carry a matching `source` (mirrors embed-frame.test.tsx).
    Object.defineProperty(iframe, "contentWindow", { value: window, configurable: true });

    // Foreign origin → ignored.
    window.dispatchEvent(
      new MessageEvent("message", {
        data: { type: "obi:hidden" },
        origin: "https://evil.example",
        source: window,
      }),
    );
    expect(document.querySelectorAll("iframe").length).toBe(1);

    // Own frame + exact Obi origin → destroy.
    window.dispatchEvent(
      new MessageEvent("message", {
        data: { type: "obi:hidden" },
        origin: window.location.origin,
        source: window,
      }),
    );
    expect(document.querySelectorAll("iframe").length).toBe(0);
    expect(document.querySelectorAll("button.obi-launcher").length).toBe(0);
  });
});
