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
  _request: Request,
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

  const privateKey = await importPKCS8(privateKeyPem, "RS256");
  const now = Math.floor(Date.now() / 1000);

  const token = await new SignJWT({ ...(host.businessClaims ?? {}) })
    .setProtectedHeader({ alg: "RS256", kid: host.kid })
    .setIssuer(host.issuer)
    .setAudience("obi")
    .setSubject(`test-subject-${host.name}`)
    .setIssuedAt(now)
    .setExpirationTime(now + TEST_TOKEN_LIFETIME_SECONDS)
    .sign(privateKey);

  return NextResponse.json({ token });
}
