/**
 * Landing route — a thin, static page.
 *
 * It owns no behavior, so per the architecture standard it stays in `app/` and
 * is NOT a feature. Wrapped in `DevPreviewBackdrop`, a dev-only decorative backdrop so the
 * globally-mounted chat widget previews against realistic page content instead of a blank page
 * (see `docs/rag/OBI-WIDGET-DESIGN.md` §7). Safe to delete; not part of the product.
 *
 * The old standalone `/chat` full-page route was removed (PLAN 4.7.7) — the floating widget,
 * mounted globally in `app/layout.tsx`, is now the only chat surface.
 */
import { DevPreviewBackdrop } from "./dev-preview-backdrop";
import { isLocalOrDevEnv } from "@/features/embed/csp";

// Obi embed test-host pages (PLAN 11.1c) — local-only scaffolding, each simulates a third-party
// site embedding Obi under a different scope. Never rendered in production.
const TEST_HOSTS = [
  { name: "Mews", href: "/test-hosts/mews", scope: "Mews + general" },
  { name: "Toast", href: "/test-hosts/toast", scope: "Toast + general" },
  { name: "Opera Cloud", href: "/test-hosts/opera-cloud", scope: "Opera Cloud + general" },
  { name: "None", href: "/test-hosts/none", scope: "general only" },
];

export default function HomePage() {
  const showTestHosts = isLocalOrDevEnv();
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
        the bottom-right corner.
      </p>

      {showTestHosts && (
        <nav aria-label="Obi embed test hosts" className="mt-8 max-w-[28rem]">
          <p className="text-sm font-medium text-text-muted">Embed test hosts (dev only)</p>
          <ul className="mt-2 flex flex-col gap-1">
            {TEST_HOSTS.map((host) => (
              <li key={host.href}>
                <a
                  href={host.href}
                  className="text-text underline underline-offset-2 hover:no-underline"
                >
                  {host.name}
                </a>
                <span className="text-text-muted"> — {host.scope}</span>
              </li>
            ))}
          </ul>
        </nav>
      )}
    </DevPreviewBackdrop>
  );
}
