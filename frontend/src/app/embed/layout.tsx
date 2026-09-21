/**
 * Root layout for the Obi `/embed` frame (PLAN 11.1c, ADR-0014) — one of Next's "multiple root
 * layouts" (see `(site)/layout.tsx`'s docstring). Deliberately does NOT mount
 * `ChatSessionProvider`/`ChatWidget` at this level: `page.tsx` does that itself, scoped to this
 * one route, with no `knowledgeScope` prop — scope now comes from the verified token, not a
 * deployment-time prop. Keeps `globals.css` (design tokens, Tailwind) so the widget renders
 * pixel-identical to the main site inside the iframe.
 */
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "../globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-sans", display: "swap" });

export const metadata: Metadata = {
  title: "Obi",
  description: "Obi chat frame.",
};

export default function EmbedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning className={inter.variable}>
      <body className="bg-transparent text-text font-sans antialiased">{children}</body>
    </html>
  );
}
