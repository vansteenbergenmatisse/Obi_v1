/**
 * Serves the PUBLIC half of a local test issuer's key pair as a JWKS document (PLAN 11.1c,
 * ADR-0014) — the actual implementation behind the public `/.well-known/<issuer>/obi-jwks.json`
 * URL recorded in `config/platforms.local.json` (reached via `next.config.ts`'s rewrite, since
 * relying on a literal dot-prefixed `.well-known` App Router folder being treated as an ordinary
 * segment is unverified Next.js behavior — this route is the one actually exercised). Only ever
 * reads the `TEST_OBI_PUBLIC_KEY_*` env vars; the matching private keys never appear here.
 */
import { exportJWK, importSPKI } from "jose";
import { NextResponse } from "next/server";
import { byIssuerKey } from "../../config";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ issuer: string }> },
): Promise<Response> {
  const { issuer } = await params;
  const host = byIssuerKey(issuer);
  if (!host) {
    return NextResponse.json({ keys: [] }, { status: 404 });
  }

  const publicKeyPem = process.env[host.publicKeyEnv];
  if (!publicKeyPem) {
    return NextResponse.json({ error: "test public key not configured" }, { status: 503 });
  }

  const publicKey = await importSPKI(publicKeyPem, "RS256");
  const jwk = await exportJWK(publicKey);

  return NextResponse.json({
    keys: [{ ...jwk, kid: host.kid, alg: "RS256", use: "sig" }],
  });
}
