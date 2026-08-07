/**
 * Landing route — a thin, static page.
 *
 * It owns no behavior, so per the architecture standard it stays in `app/` and
 * is NOT a feature. It composes the reusable `PageShell` and links to the chat
 * route, whose UI is owned by `features/chat`.
 */
import Link from "next/link";
import { PageShell } from "@/components/layout/page-shell";
import { Button } from "@/components/ui/button";

export default function HomePage() {
  return (
    <PageShell center>
      <h1 className="text-3xl font-semibold tracking-tight text-text">
        Omniboost RAG
      </h1>
      <p className="max-w-md text-text-muted">
        Accuracy-first, Confluence-native RAG chatbot. The chat surface is
        scaffolded; grounded answers land in Phase 4.
      </p>
      <Link href="/chat">
        <Button>Open chat</Button>
      </Link>
    </PageShell>
  );
}
