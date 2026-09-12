/**
 * Shared config for the local test-host token/JWKS routes (PLAN 11.1c, ADR-0014) — see
 * `docs/embedding/obi-embed-local-test-keys.md` for how to generate the matching RS256 key pairs
 * and where they're read from. Not a `features/embed` concern: this is disposable local-browser-
 * proof scaffolding for `config/platforms.local.json`'s `test-*` issuer entries, route-owned by
 * `app/api/test-hosts/**` and `app/.well-known/**` (via the `/api/test-hosts/jwks/[issuer]`
 * rewrite target), never imported by product code.
 */

export type TestHostName = "none" | "mews" | "toast" | "opera-cloud";
export type TestIssuerKey = "test-none" | "test-mews" | "test-toast" | "test-opera";

export interface TestHostConfig {
  name: TestHostName;
  issuerKey: TestIssuerKey;
  issuer: string;
  kid: string;
  privateKeyEnv: string;
  publicKeyEnv: string;
  /** `null` for `none` — a note with no business values (general-only, per ADR-0014). */
  businessClaims: { company_id: string; company_name: string; integration: string } | null;
}

/** 60 minutes, matching `config/platforms.local.json`'s `lifetime_minutes` for every test entry. */
export const TEST_TOKEN_LIFETIME_SECONDS = 60 * 60;

export const TEST_HOSTS: readonly TestHostConfig[] = [
  {
    name: "none",
    issuerKey: "test-none",
    issuer: "https://test-none.local",
    kid: "test-none-1",
    privateKeyEnv: "TEST_OBI_PRIVATE_KEY_NONE",
    publicKeyEnv: "TEST_OBI_PUBLIC_KEY_NONE",
    businessClaims: null,
  },
  {
    name: "mews",
    issuerKey: "test-mews",
    issuer: "https://test-mews.local",
    kid: "test-mews-1",
    privateKeyEnv: "TEST_OBI_PRIVATE_KEY_MEWS",
    publicKeyEnv: "TEST_OBI_PUBLIC_KEY_MEWS",
    businessClaims: { company_id: "c_test_1", company_name: "Test Hotel", integration: "mews" },
  },
  {
    name: "toast",
    issuerKey: "test-toast",
    issuer: "https://test-toast.local",
    kid: "test-toast-1",
    privateKeyEnv: "TEST_OBI_PRIVATE_KEY_TOAST",
    publicKeyEnv: "TEST_OBI_PUBLIC_KEY_TOAST",
    businessClaims: {
      company_id: "c_test_2",
      company_name: "Test Restaurant",
      integration: "toast",
    },
  },
  {
    name: "opera-cloud",
    issuerKey: "test-opera",
    issuer: "https://test-opera.local",
    kid: "test-opera-1",
    privateKeyEnv: "TEST_OBI_PRIVATE_KEY_OPERA",
    publicKeyEnv: "TEST_OBI_PUBLIC_KEY_OPERA",
    businessClaims: {
      company_id: "c_test_3",
      company_name: "Test Resort",
      integration: "opera-cloud",
    },
  },
];

export function byName(name: string): TestHostConfig | undefined {
  return TEST_HOSTS.find((host) => host.name === name);
}

export function byIssuerKey(issuerKey: string): TestHostConfig | undefined {
  return TEST_HOSTS.find((host) => host.issuerKey === issuerKey);
}
