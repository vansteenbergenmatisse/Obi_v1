/**
 * `/embed` CSP — PLAN 11.1c, ADR-0014.
 *
 * `computeEmbedCsp` is the pure decision function; the `middleware()` tests below exercise the
 * real request/response path with a temp `platforms.json` (via the `PLATFORMS_PATH` override) and
 * a stubbed `fetch` standing in for the real `/api/internal/active-domains` round trip (Edge
 * middleware can't call `node:fs` directly — see `middleware.ts`'s docstring). Every assertion
 * checks the header never contains `"*"`.
 */
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import {
  computeEmbedCsp,
  effectiveEmbedderDomains,
  isLocalhostDomain,
  LOCAL_OR_DEV_ENVS,
  toEmbedderOrigins,
} from "../csp";
import { activeDomains } from "../platforms";

const ORIGINAL_PLATFORMS_PATH = process.env.PLATFORMS_PATH;
const ORIGINAL_APP_ENV = process.env.APP_ENV;
let tempDir: string | undefined;

function writePlatformsFile(data: unknown): void {
  tempDir = mkdtempSync(join(tmpdir(), "obi-platforms-"));
  const path = join(tempDir, "platforms.json");
  writeFileSync(path, JSON.stringify(data));
  process.env.PLATFORMS_PATH = path;
}

afterEach(() => {
  if (ORIGINAL_PLATFORMS_PATH === undefined) {
    delete process.env.PLATFORMS_PATH;
  } else {
    process.env.PLATFORMS_PATH = ORIGINAL_PLATFORMS_PATH;
  }
  if (ORIGINAL_APP_ENV === undefined) {
    delete process.env.APP_ENV;
  } else {
    process.env.APP_ENV = ORIGINAL_APP_ENV;
  }
  if (tempDir) {
    rmSync(tempDir, { recursive: true, force: true });
    tempDir = undefined;
  }
});

describe("computeEmbedCsp", () => {
  it("includes every active domain and never emits a wildcard", () => {
    const result = computeEmbedCsp(["app.mews.com", "pos.toasttab.com"], false);
    expect(result.ok).toBe(true);
    expect(result.header).toBe("frame-ancestors app.mews.com pos.toasttab.com");
    expect(result.header).not.toContain("*");
  });

  it("renders frame-ancestors 'none' (not a wildcard) when tolerated locally with no active domains", () => {
    const result = computeEmbedCsp([], true);
    expect(result.ok).toBe(true);
    expect(result.header).toBe("frame-ancestors 'none'");
  });

  it("fails closed (ok: false) when no active domains exist outside local/dev", () => {
    const result = computeEmbedCsp([], false);
    expect(result.ok).toBe(false);
  });
});

describe("computeEmbedCsp localhost filtering (gap CFG-04)", () => {
  it("omits localhost/127.0.0.1 domains from frame-ancestors outside local/dev", () => {
    const result = computeEmbedCsp(["app.mews.com", "localhost:3000", "127.0.0.1:8080"], false);
    expect(result.ok).toBe(true);
    expect(result.header).toBe("frame-ancestors app.mews.com");
    expect(result.header).not.toContain("localhost");
    expect(result.header).not.toContain("127.0.0.1");
    expect(result.header).not.toContain("*");
  });

  it("fails closed when every active domain is localhost outside local/dev", () => {
    const result = computeEmbedCsp(["localhost:3000", "127.0.0.1"], false);
    expect(result.ok).toBe(false);
  });

  it("keeps localhost domains when local/dev — the embed test flow (regression)", () => {
    const result = computeEmbedCsp(["localhost:3000", "localhost:3100"], true);
    expect(result.ok).toBe(true);
    expect(result.header).toBe("frame-ancestors localhost:3000 localhost:3100");
  });
});

describe("isLocalhostDomain — full loopback set (gap BIT-A-R1)", () => {
  it("matches localhost and any *.localhost, with or without a port", () => {
    expect(isLocalhostDomain("localhost")).toBe(true);
    expect(isLocalhostDomain("localhost:3000")).toBe(true);
    expect(isLocalhostDomain("app.localhost")).toBe(true);
    expect(isLocalhostDomain("app.localhost:8080")).toBe(true);
    expect(isLocalhostDomain("LOCALHOST")).toBe(true);
  });

  it("matches the whole 127.0.0.0/8 loopback block with valid octets", () => {
    expect(isLocalhostDomain("127.0.0.1")).toBe(true);
    expect(isLocalhostDomain("127.0.0.1:8080")).toBe(true);
    expect(isLocalhostDomain("127.0.0.2")).toBe(true);
    expect(isLocalhostDomain("127.255.255.255")).toBe(true);
    expect(isLocalhostDomain("127.1.2.3:9000")).toBe(true);
  });

  it("matches the 0.0.0.0 wildcard-bind address", () => {
    expect(isLocalhostDomain("0.0.0.0")).toBe(true);
    expect(isLocalhostDomain("0.0.0.0:5000")).toBe(true);
  });

  it("matches IPv6 loopback ::1, bare and bracketed with a port", () => {
    expect(isLocalhostDomain("::1")).toBe(true);
    expect(isLocalhostDomain("[::1]")).toBe(true);
    expect(isLocalhostDomain("[::1]:3000")).toBe(true);
  });

  it("does NOT treat a real public host as loopback", () => {
    expect(isLocalhostDomain("app.mews.com")).toBe(false);
    expect(isLocalhostDomain("pos.toasttab.com:443")).toBe(false);
  });

  it("does NOT treat a hostname that merely starts with 127. as an IPv4 loopback", () => {
    expect(isLocalhostDomain("127.example.com")).toBe(false);
    expect(isLocalhostDomain("localhost.evil.com")).toBe(false);
    expect(isLocalhostDomain("notlocalhost")).toBe(false);
    // 256 is not a valid octet — not a loopback IPv4 (and not 127.x anyway)
    expect(isLocalhostDomain("127.0.0.256")).toBe(false);
  });
});

describe("expanded loopback stripping outside local/dev (gap BIT-A-R1)", () => {
  const loopbackDomains = ["::1", "[::1]:3000", "127.0.0.2", "127.255.255.255", "0.0.0.0:5000"];

  it("effectiveEmbedderDomains strips every loopback form and keeps the real domain", () => {
    expect(
      effectiveEmbedderDomains([...loopbackDomains, "app.mews.com"], false),
    ).toEqual(["app.mews.com"]);
  });

  it("effectiveEmbedderDomains keeps every loopback form in local/dev", () => {
    expect(effectiveEmbedderDomains([...loopbackDomains, "app.mews.com"], true)).toEqual([
      ...loopbackDomains,
      "app.mews.com",
    ]);
  });

  it("toEmbedderOrigins emits only the https real-domain origin outside local/dev", () => {
    const origins = toEmbedderOrigins([...loopbackDomains, "app.mews.com"], false);
    expect(origins).toEqual(["https://app.mews.com"]);
    expect(origins.join(" ")).not.toContain("::1");
    expect(origins.join(" ")).not.toContain("127.");
    expect(origins.join(" ")).not.toContain("0.0.0.0");
  });

  it("computeEmbedCsp drops every loopback form from frame-ancestors outside local/dev", () => {
    const result = computeEmbedCsp([...loopbackDomains, "app.mews.com"], false);
    expect(result.ok).toBe(true);
    expect(result.header).toBe("frame-ancestors app.mews.com");
    expect(result.header).not.toContain("::1");
    expect(result.header).not.toContain("127.");
    expect(result.header).not.toContain("0.0.0.0");
    expect(result.header).not.toContain("*");
  });

  it("computeEmbedCsp fails closed when every domain is a loopback form outside local/dev", () => {
    const result = computeEmbedCsp(loopbackDomains, false);
    expect(result.ok).toBe(false);
  });
});

describe("isLocalhostDomain — loopback aliases + .local (gap BIT-LOOPBACK-EDGE-1 / CFG-DOMLOCAL-1)", () => {
  it("matches the trailing-dot FQDN loopback forms", () => {
    expect(isLocalhostDomain("localhost.")).toBe(true);
    expect(isLocalhostDomain("127.0.0.1.")).toBe(true);
    expect(isLocalhostDomain("app.localhost.")).toBe(true);
  });

  it("matches the fully-expanded IPv6 loopback (bare and bracketed with a port)", () => {
    expect(isLocalhostDomain("0:0:0:0:0:0:0:1")).toBe(true);
    expect(isLocalhostDomain("[0:0:0:0:0:0:0:1]:3000")).toBe(true);
  });

  it("matches the IPv4-mapped IPv6 loopback (dotted and hex, whole 127.0.0.0/8)", () => {
    expect(isLocalhostDomain("::ffff:127.0.0.1")).toBe(true);
    expect(isLocalhostDomain("[::ffff:127.0.0.1]:3000")).toBe(true);
    expect(isLocalhostDomain("::ffff:7f00:1")).toBe(true);
    expect(isLocalhostDomain("::ffff:127.255.255.255")).toBe(true);
  });

  it("treats a .local TLD host as non-production (CFG-DOMLOCAL-1)", () => {
    expect(isLocalhostDomain("app.acme.local")).toBe(true);
    expect(isLocalhostDomain("acme.local")).toBe(true);
    expect(isLocalhostDomain("app.acme.local:3000")).toBe(true);
    expect(isLocalhostDomain("acme.local.")).toBe(true);
  });

  it("does NOT over-match lookalikes", () => {
    expect(isLocalhostDomain("example.local.com")).toBe(false);
    expect(isLocalhostDomain("127.example.com")).toBe(false);
    expect(isLocalhostDomain("app.mews.com")).toBe(false);
    expect(isLocalhostDomain("notlocalhost")).toBe(false);
    expect(isLocalhostDomain("2001:db8::7f00:1")).toBe(false);
    expect(isLocalhostDomain("::ffff:126.0.0.1")).toBe(false);
    expect(isLocalhostDomain("::ffff:8.8.8.8")).toBe(false);
  });
});

describe("effectiveEmbedderDomains strips aliases + .local outside local/dev (gap BIT-LOOPBACK-EDGE-1 / CFG-DOMLOCAL-1)", () => {
  const aliasDomains = [
    "localhost.",
    "127.0.0.1.",
    "0:0:0:0:0:0:0:1",
    "::ffff:127.0.0.1",
    "::ffff:7f00:1",
    "app.acme.local",
  ];

  it("strips every alias/.local form and keeps the real domain outside local/dev", () => {
    expect(effectiveEmbedderDomains([...aliasDomains, "app.mews.com"], false)).toEqual([
      "app.mews.com",
    ]);
  });

  it("keeps every alias/.local form in local/dev (the embed test flow, regression)", () => {
    expect(effectiveEmbedderDomains([...aliasDomains, "app.mews.com"], true)).toEqual([
      ...aliasDomains,
      "app.mews.com",
    ]);
  });

  it("computeEmbedCsp drops every alias/.local form from frame-ancestors outside local/dev", () => {
    const result = computeEmbedCsp([...aliasDomains, "app.mews.com"], false);
    expect(result.ok).toBe(true);
    expect(result.header).toBe("frame-ancestors app.mews.com");
    expect(result.header).not.toContain(".local");
    expect(result.header).not.toContain("::");
    expect(result.header).not.toContain("*");
  });
});

describe("toEmbedderOrigins — bridge allow-list scheme + loopback posture (gap BIT-A1)", () => {
  it("outside local/dev emits ONLY https origins for real domains and drops every loopback origin", () => {
    const origins = toEmbedderOrigins(
      ["app.mews.com", "localhost:3000", "127.0.0.1:8080"],
      false,
    );
    expect(origins).toEqual(["https://app.mews.com"]);
    // No plaintext-http origin, and no loopback origin at all, in production.
    expect(origins.some((o) => o.startsWith("http://"))).toBe(false);
    expect(origins.join(" ")).not.toContain("localhost");
    expect(origins.join(" ")).not.toContain("127.0.0.1");
  });

  it("outside local/dev emits https for every real domain, never plaintext http", () => {
    expect(toEmbedderOrigins(["app.mews.com", "pos.toasttab.com"], false)).toEqual([
      "https://app.mews.com",
      "https://pos.toasttab.com",
    ]);
  });

  it("keeps loopback origins and both schemes in local/dev (the embed test flow, regression)", () => {
    expect(toEmbedderOrigins(["localhost:3000", "app.mews.com"], true)).toEqual([
      "https://localhost:3000",
      "http://localhost:3000",
      "https://app.mews.com",
      "http://app.mews.com",
    ]);
  });

  it("never emits a wildcard in either environment", () => {
    for (const origin of [
      ...toEmbedderOrigins(["app.mews.com", "localhost:3000"], true),
      ...toEmbedderOrigins(["app.mews.com", "localhost:3000"], false),
    ]) {
      expect(origin).not.toBe("*");
      expect(origin).not.toContain("*");
    }
  });
});

describe("env signal contract (gap CFG-H)", () => {
  it("pins the frontend's own canonical local/dev env-value set", () => {
    // This is the FRONTEND's OWN set and is intentionally allowed to differ from the backend's
    // ENV-based _OFFLINE_ENVS (backend/app/platform/config/settings.py), which has since narrowed
    // to drop dev/development. The two sides read different vars — the frontend keys off
    // NODE_ENV/APP_ENV (so "development" stays in, matching Next's own dev NODE_ENV); the backend
    // keys off ENV. Each side pins its own set independently; there is no "identical cross-side
    // contract." See csp.ts's LOCAL_OR_DEV_ENVS docstring.
    expect(new Set(LOCAL_OR_DEV_ENVS)).toEqual(
      new Set(["local", "dev", "development", "test", "ci"]),
    );
  });
});

describe("activeDomains", () => {
  it("returns the sorted, de-duplicated domains of active entries only", () => {
    writePlatformsFile({
      platforms: {
        mews: { domains: ["app.mews.com"], active: true },
        toast: { domains: ["pos.toasttab.com", "app.mews.com"], active: true },
        "opera-cloud": { domains: ["opera.example.com"], active: false },
      },
    });

    expect(activeDomains()).toEqual(["app.mews.com", "pos.toasttab.com"]);
  });

  it("returns an empty list for a missing/malformed file", () => {
    process.env.PLATFORMS_PATH = "/nonexistent/platforms.json";
    expect(activeDomains()).toEqual([]);
  });
});

describe("middleware", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("sets frame-ancestors with the active domains and no wildcard on a normal request", async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify({ domains: ["app.mews.com"] }), { status: 200 }));
    process.env.APP_ENV = "local";

    const { middleware } = await import("../../../middleware");
    const response = await middleware(new NextRequest("http://localhost/embed"));

    expect(response.status).not.toBe(403);
    const csp = response.headers.get("content-security-policy");
    expect(csp).toContain("app.mews.com");
    expect(csp).not.toContain("*");
  });

  it("responds 403 when there are no active domains outside local/dev", async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify({ domains: [] }), { status: 200 }));
    process.env.APP_ENV = "production";

    const { middleware } = await import("../../../middleware");
    const response = await middleware(new NextRequest("http://localhost/embed"));

    expect(response.status).toBe(403);
  });

  it("fails toward 403 (never allow-all) when the internal active-domains fetch itself fails", async () => {
    fetchMock.mockRejectedValue(new Error("network down"));
    process.env.APP_ENV = "production";

    const { middleware } = await import("../../../middleware");
    const response = await middleware(new NextRequest("http://localhost/embed"));

    expect(response.status).toBe(403);
  });
});

describe("GET /api/internal/active-domains", () => {
  it("returns the active domains computed from the current platforms file", async () => {
    writePlatformsFile({
      platforms: { mews: { domains: ["app.mews.com"], active: true } },
    });

    const { GET } = await import("../../../app/api/internal/active-domains/route");
    const response = GET();

    expect(await response.json()).toEqual({ domains: ["app.mews.com"] });
  });
});
