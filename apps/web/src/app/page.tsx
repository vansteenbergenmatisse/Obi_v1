/**
 * Phase 1 placeholder home page.
 *
 * The full streaming chat UI (message list, composer, citations) lands in
 * Phase 4 under `src/features/chat`. This shell exists so the app builds and
 * renders a stable landing surface.
 */
export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-md p-xl text-center">
      <h1 className="text-3xl font-semibold tracking-tight text-text">
        Omniboost RAG
      </h1>
      <p className="max-w-md text-text-muted">
        Chat coming in Phase 4. This is the Phase 1 shell of the
        Confluence-native, accuracy-first RAG chatbot.
      </p>
    </main>
  );
}
