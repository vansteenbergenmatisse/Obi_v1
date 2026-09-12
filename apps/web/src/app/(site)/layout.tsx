/**
 * Root layout for the main product surface — the `(site)` route group (PLAN 11.1c). Moved out of
 * a single top-level `app/layout.tsx` into this named group so the Obi `/embed` frame and the
 * `/test-hosts/*` fake host pages can each have their OWN root layout (no `ChatSessionProvider`/
 * `ChatWidget`, no shared cookie/HTML shell) via Next's documented "multiple root layouts"
 * pattern — a route group changes nothing about the URL (`/` still resolves here), it only lets
 * `app/embed/layout.tsx` and `app/test-hosts/layout.tsx` opt out of this one.
 */
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { ChatSessionProvider, ChatWidget } from "@/features/chat";
import "../globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-sans", display: "swap" });

export const metadata: Metadata = {
  title: "Omniboost RAG",
  description: "Accuracy-first, Confluence-native RAG chatbot.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning className={inter.variable}>
      <body className="bg-surface text-text font-sans antialiased">
        <ChatSessionProvider>
          {children}
          <ChatWidget />
        </ChatSessionProvider>
      </body>
    </html>
  );
}
