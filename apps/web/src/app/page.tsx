/**
 * Landing route — a thin, static page.
 *
 * It owns no behavior, so per the architecture standard it stays in `app/` and
 * is NOT a feature. It composes the reusable `PageShell`... normally — for now it's wrapped in
 * `DevPreviewBackdrop`, a dev-only decorative backdrop so the globally-mounted chat widget
 * previews against realistic page content instead of a blank page (see
 * `docs/rag/OBI-WIDGET-DESIGN.md` §7). Safe to delete; not part of the product.
 */
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { DevPreviewBackdrop } from "./dev-preview-backdrop";

export default function HomePage() {
  return (
    <DevPreviewBackdrop>
      <h1 className="text-3xl font-semibold tracking-tight text-text">
        Omniboost RAG
      </h1>
      {/* `max-w-[28rem]`, not `max-w-md` — this repo's named max-width scale resolves to the
          `spacing.md` token (16px) instead of Tailwind's default 28rem; every other max-width
          in the widget already works around this with a bracket value, see e.g.
          `message-bubble.tsx`'s `max-w-[82%]`. */}
      <p className="max-w-[28rem] text-text-muted">
        Accuracy-first, Confluence-native RAG chatbot. Try the assistant in
        the bottom-right corner, or open the full chat view.
      </p>
      <Link href="/chat">
        <Button>Open chat</Button>
      </Link>
    </DevPreviewBackdrop>
  );
}
