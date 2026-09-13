/**
 * Root layout for the `/test-hosts/*` fake host pages (PLAN 11.1c, ADR-0014) — another of Next's
 * "multiple root layouts" (see `(site)/layout.tsx`'s docstring). Deliberately bare: these pages
 * simulate a THIRD-PARTY page embedding Obi via `obi.js`, so they must not mount our own
 * `ChatSessionProvider`/`ChatWidget` (that would be testing something no real embedder has) and
 * don't need our design tokens either.
 */
export const metadata = {
  title: "Obi test host",
  description: "Simulated third-party page embedding the Obi chat widget.",
};

export default function TestHostsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body style={{ fontFamily: "system-ui, sans-serif" }}>{children}</body>
    </html>
  );
}
