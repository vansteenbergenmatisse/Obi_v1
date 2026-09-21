import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Transpile the workspace packages so their TS sources are compiled by Next.
  transpilePackages: ["@omniboost/contracts", "@omniboost/design-tokens"],

  // PLAN 11.1c (ADR-0014): local test-host JWKS. `config/platforms.local.json`'s test issuer
  // entries record `jwks_url`s under `/.well-known/<issuer>/obi-jwks.json` (the conventional path
  // a real platform would use) — rewritten here to the actual App Router implementation rather
  // than relying on a literal dot-prefixed `.well-known` folder being treated as an ordinary App
  // Router segment (unverified Next.js behavior).
  async rewrites() {
    return [
      {
        source: "/.well-known/:issuer/obi-jwks.json",
        destination: "/api/test-hosts/jwks/:issuer",
      },
    ];
  },
};

export default nextConfig;
