/**
 * Local test-host note-minting endpoint (PLAN 11.1c, ADR-0014) — signs a short-lived RS256 JWT
 * the way a real platform's own server would, for `/test-hosts/<name>` to fetch via `obi.js`'s
 * `Obi.init({ tokenUrl })`. Never used outside local/dev browser proof — the private keys live in
 * `frontend/.env.local` only (gitignored, generated with `openssl`, see
 * `docs/embedding/obi-embed-local-test-keys.md`).
 */
import { SignJWT, importPKCS8 } from "jose";
import { NextResponse } from "next/server";
import { TEST_TOKEN_LIFETIME_SECONDS, byName } from "../../config";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ name: string }> },
): Promise<Response> {
  const { name } = await params;
  const host = byName(name);
  if (!host) {
    return NextResponse.json({ error: "unknown test host" }, { status: 404 });
  }

  const privateKeyPem = process.env[host.privateKeyEnv];
  if (!privateKeyPem) {
    return NextResponse.json({ error: "test signing key not configured" }, { status: 503 });
  }

  // `?form=directed` mints the directed source → target connection form (substep 9.3.1,
  // ADR-0020 Option A) instead of the legacy business claims, so a test host can exercise either
  // token shape. A host without directedClaims falls back to its legacy note. The two forms are
  // mutually exclusive on a token — the directed note never also carries the legacy trio.
  const wantsDirected = new URL(request.url).searchParams.get("form") === "directed";
  const claims =
    wantsDirected && host.directedClaims ? host.directedClaims : (host.businessClaims ?? {});

  const privateKey = await importPKCS8(privateKeyPem, "RS256");
  const now = Math.floor(Date.now() / 1000);

  const token = await new SignJWT({ ...claims })
    .setProtectedHeader({ alg: "RS256", kid: host.kid })
    .setIssuer(host.issuer)
    .setAudience("obi")
    .setSubject(`test-subject-${host.name}`)
    .setIssuedAt(now)
    .setExpirationTime(now + TEST_TOKEN_LIFETIME_SECONDS)
    .sign(privateKey);

  return NextResponse.json({ token });
}
