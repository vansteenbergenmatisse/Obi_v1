/**
 * Shared content for the four `/test-hosts/<name>` pages (PLAN 11.1c, ADR-0014) — route-owned,
 * colocated beside its four sibling `page.tsx` files rather than promoted to `components/` (it is
 * specific to this one small route family, never reused elsewhere). Renders exactly the "paste
 * template" a real platform integrator would add to their own page: one `obi.js` script tag plus
 * an `Obi.init({ tokenUrl })` call — shown as literal text AND actually executed, so this page
 * doubles as copy-paste documentation and a live local test.
 */
"use client";

import Script from "next/script";

export interface TestHostContentProps {
  name: string;
  tokenUrl: string;
}

function pasteTemplate(tokenUrl: string): string {
  return [
    '<script src="/obi.js"></script>',
    "<script>",
    `  Obi.init({ tokenUrl: "${tokenUrl}" });`,
    "</script>",
  ].join("\n");
}

export function TestHostContent({ name, tokenUrl }: TestHostContentProps) {
  return (
    <main style={{ padding: "2rem", maxWidth: "40rem" }}>
      <h1>Obi test host: {name}</h1>
      <p>
        This page simulates a third-party platform embedding Obi. It contains nothing but the
        paste template below — the round launcher button and chat iframe are injected entirely by
        <code> obi.js</code>.
      </p>
      <pre
        data-testid="paste-template"
        style={{ background: "whitesmoke", padding: "1rem", overflowX: "auto", color: "black" }}
      >
        {pasteTemplate(tokenUrl)}
      </pre>
      <Script
        src="/obi.js"
        strategy="afterInteractive"
        onLoad={() => {
          window.Obi.init({ tokenUrl });
        }}
      />
    </main>
  );
}
