/**
 * Route-owned content for `/test-hosts/multi` (PLAN §0 NEXT STEP, 2026-09-13) — colocated beside
 * `test-host-content.tsx` rather than promoted to `components/` (specific to this one route). It
 * hosts all three signed-in BUSINESS users at once (Mews / Toast / Opera Cloud, each a different
 * company) so the operator can switch — at random or by name — and prove the per-user identity
 * feature live: switch user, ask Obi "what company am I?", and the answer follows the active token.
 *
 * The three users come straight from `TEST_HOSTS` (filtering out the tokenless `none`) so the list
 * stays a single source of truth. Switching re-points the embedded widget via `Obi.init` — which is
 * idempotent (see `features/embed/loader.ts`): it tears down the previous user's launcher + iframe
 * first, so no conversation or cached answer bleeds from one identity to the next.
 */
"use client";

import Script from "next/script";
import { useEffect, useState } from "react";
import { TEST_HOSTS, type TestHostConfig } from "../api/test-hosts/config";
import { tokenUrlFor } from "./token-url";

type BusinessHost = TestHostConfig & {
  businessClaims: NonNullable<TestHostConfig["businessClaims"]>;
};

const BUSINESS_HOSTS: readonly BusinessHost[] = TEST_HOSTS.filter(
  (host): host is BusinessHost => host.businessClaims !== null,
);

export function MultiUserContent() {
  const [activeIndex, setActiveIndex] = useState(0);
  const [scriptLoaded, setScriptLoaded] = useState(false);
  const active = BUSINESS_HOSTS[activeIndex];

  // Re-point the widget at the active user once obi.js is loaded, and again on every switch.
  useEffect(() => {
    if (!scriptLoaded) return;
    window.Obi.init({ tokenUrl: tokenUrlFor(active.name) });
  }, [scriptLoaded, active.name]);

  function switchToRandom() {
    setActiveIndex((current) => {
      if (BUSINESS_HOSTS.length < 2) return current;
      // Never re-pick the current user, so a click always visibly changes who is active.
      let next = current;
      while (next === current) {
        next = Math.floor(Math.random() * BUSINESS_HOSTS.length);
      }
      return next;
    });
  }

  return (
    <main style={{ padding: "2rem", maxWidth: "44rem" }}>
      <h1>Obi test host: multiple users</h1>
      <p>
        Three signed-in users, three different companies. Switch between them, then open Obi and ask
        <em> &ldquo;what company am I?&rdquo;</em> or <em>&ldquo;which integration do we use?&rdquo;</em>
        — the answer should match whoever is active below.
      </p>

      <section
        data-testid="active-user"
        aria-live="polite"
        style={{
          margin: "1.5rem 0",
          padding: "1rem 1.25rem",
          border: "2px solid #635bff",
          borderRadius: "0.5rem",
          background: "#f5f5ff",
          color: "black",
        }}
      >
        <div style={{ fontSize: "0.8rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>
          Active user
        </div>
        <div style={{ fontSize: "1.25rem", fontWeight: 600, marginTop: "0.25rem" }}>
          {active.businessClaims.company_name}
        </div>
        <div style={{ marginTop: "0.25rem" }}>
          user <code>{active.name}</code> · integration <code>{active.businessClaims.integration}</code>{" "}
          · company id <code>{active.businessClaims.company_id}</code>
        </div>
      </section>

      <button
        type="button"
        onClick={switchToRandom}
        style={{
          padding: "0.6rem 1rem",
          fontSize: "1rem",
          borderRadius: "0.5rem",
          border: "1px solid #635bff",
          background: "#635bff",
          color: "white",
          cursor: "pointer",
        }}
      >
        Switch to a random user
      </button>

      <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginTop: "1rem" }}>
        {BUSINESS_HOSTS.map((host, index) => {
          const isActive = index === activeIndex;
          return (
            <button
              key={host.name}
              type="button"
              aria-pressed={isActive}
              onClick={() => setActiveIndex(index)}
              style={{
                padding: "0.5rem 0.85rem",
                borderRadius: "0.5rem",
                border: isActive ? "2px solid #635bff" : "1px solid #ccc",
                background: isActive ? "#e6e6ff" : "white",
                color: "black",
                cursor: "pointer",
                fontWeight: isActive ? 600 : 400,
              }}
            >
              Switch to {host.name} ({host.businessClaims.company_name})
            </button>
          );
        })}
      </div>

      <Script
        src="/obi.js"
        strategy="afterInteractive"
        onLoad={() => {
          setScriptLoaded(true);
        }}
      />
    </main>
  );
}
