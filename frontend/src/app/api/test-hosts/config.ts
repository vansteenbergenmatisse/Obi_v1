/**
 * Shared config for the local test-host token/JWKS routes (PLAN 11.1c) — see
 * `docs/embedding/obi-embed-local-test-keys.md` for how to generate the matching RS256 key pairs
 * and where they're read from. Not a `features/embed` concern: this is disposable local-browser-
 * proof scaffolding for `config/platforms.local.json`'s `test-*` issuer entries, route-owned by
 * `app/api/test-hosts/**` and `app/.well-known/**` (via the `/api/test-hosts/jwks/[issuer]`
 * rewrite target), never imported by product code.
 */

export type TestHostName = "none" | "mews" | "toast" | "opera-cloud" | "quickbooks";
export type TestIssuerKey =
  | "test-none"
  | "test-mews"
  | "test-toast"
  | "test-opera"
  | "test-quickbooks";

export interface TestHostConfig {
  name: TestHostName;
  issuerKey: TestIssuerKey;
  issuer: string;
  kid: string;
  privateKeyEnv: string;
  publicKeyEnv: string;
  /** `null` for `none` — a note with no business values (general-only, per ADR-db-level-customer-scope-isolation-backstop). */
  businessClaims: { company_id: string; company_name: string; integration: string } | null;
  /** Directed source → target connection claims (substep 9.3.1, ADR-directed-source-target-routing-labels Option A). When the mint
   * route is asked for the directed form (`?form=directed`) it emits THESE instead of
   * `businessClaims`, so the same test host can demonstrate both the legacy note and the directed
   * connection form. Absent on hosts that have no directed demo. */
  directedClaims?: { source_system: string; target_system: string; business_id: string };
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
    // Directed demo: Toast (POS) → Mews (PMS), the launch connection.
    directedClaims: { source_system: "toast", target_system: "mews", business_id: "B-3075" },
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
    // Directed demo in the OTHER direction: Opera Cloud (PMS) → Toast (POS) — a direction swap
    // relative to the toast host, so a connection-switch renewal visibly changes the connection.
    directedClaims: { source_system: "opera-cloud", target_system: "toast", business_id: "B-3075" },
  },
  {
    // DISABLED-source demo (ADR-source-system-decides-widget-eligibility): a directed connection whose SOURCE is an accounting product
    // (quickbooks-online) that is NOT in product_catalog.json's enabled_sources. The widget must
    // stay hidden. Only exercised by `widget-hidden-when-source-disabled.spec.ts` and only when
    // TEST_OBI_PRIVATE_KEY_QUICKBOOKS is present locally (same signed-key caveat as the other test
    // hosts); the matching platforms.local.json issuer is only needed for the backend-verified
    // visibility probe, not for the loader's client-side source_system decode.
    name: "quickbooks",
    issuerKey: "test-quickbooks",
    issuer: "https://test-quickbooks.local",
    kid: "test-quickbooks-1",
    privateKeyEnv: "TEST_OBI_PRIVATE_KEY_QUICKBOOKS",
    publicKeyEnv: "TEST_OBI_PUBLIC_KEY_QUICKBOOKS",
    businessClaims: null,
    // QuickBooks Online (accounting, NOT an enabled source) → Mews — the directed source the
    // loader decodes and rejects.
    directedClaims: {
      source_system: "quickbooks-online",
      target_system: "mews",
      business_id: "B-3075",
    },
  },
];

export function byName(name: string): TestHostConfig | undefined {
  return TEST_HOSTS.find((host) => host.name === name);
}

export function byIssuerKey(issuerKey: string): TestHostConfig | undefined {
  return TEST_HOSTS.find((host) => host.issuerKey === issuerKey);
}
