/**
 * Chat route — a thin entrypoint.
 *
 * It only composes: `PageShell` for layout and the `chat` feature's public
 * `ChatPanel`. No business rules live here — the chat capability is owned end
 * to end by `features/chat` and reached through its public root.
 */
import { PageShell } from "@/components/layout/page-shell";
import { ChatPanel } from "@/features/chat";

export default function ChatPage() {
  return (
    <PageShell>
      <h1 className="text-xl font-semibold tracking-tight text-text">Chat</h1>
      <ChatPanel />
    </PageShell>
  );
}
