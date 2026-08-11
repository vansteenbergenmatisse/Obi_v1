/**
 * ChatSessionProvider — the conversation state machine, extracted out of `chat-panel.tsx`
 * (PLAN 4.7.2, architecture decision D0).
 *
 * Feature-internal today (only `ChatPanel` consumes it), but designed to be mounted once at
 * the app root: 4.7.4 moves that mount into `app/layout.tsx` so the floating `ChatWidget` and
 * the full-page panel read the same live session instead of running two independent,
 * contradictory conversations. SSE/citations/refusal/feedback behavior is unchanged from the
 * pre-extraction implementation — see `chat-panel.test.tsx`'s characterization test.
 */
"use client";

import { createContext, useContext, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import type { ChatTurn } from "@omniboost/contracts";
import { ChatRequestError, sendFeedback, streamChat } from "../api/chat-client";
import type { ChatMessage } from "../model/messages";
import type { Locale } from "../model/i18n";

/** Only complete/refused turns (plus every user turn) become resendable history — a
 * streaming placeholder has no final text yet, and an error turn is our own proxy's
 * error message, not something the model actually said. */
function toHistory(messages: ChatMessage[]): ChatTurn[] {
  return messages
    .filter((message) => message.role === "user" || message.status === "complete" || message.status === "refused")
    .map((message) => ({ role: message.role, content: message.text }));
}

export interface ChatSession {
  messages: ChatMessage[];
  pending: boolean;
  sendMessage: (text: string) => Promise<void>;
  handleFeedback: (messageId: string, traceId: string, value: 1 | -1) => Promise<void>;
  /** Clears the thread and starts a new conversation, aborting any in-flight stream first. */
  restart: () => void;
  /** The widget's own UI-copy locale (PLAN 4.7.7) — greeting, chip, placeholder, footer, teaser,
   * menu labels. Does not affect the language the RAG agent answers in; that is unscoped backend
   * work (see `docs/rag/OBI-WIDGET-DESIGN.md` §5). Lives here, not in a component, because both
   * `PanelHeader` (which changes it) and `ChatWidget`'s `TeaserPopup` (which reads it, outside
   * `PanelBody`'s subtree) need the same value. */
  locale: Locale;
  setLocale: (locale: Locale) => void;
}

const ChatSessionContext = createContext<ChatSession | null>(null);

export function ChatSessionProvider({ children }: { children: ReactNode }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [pending, setPending] = useState(false);
  const [locale, setLocale] = useState<Locale>("en");
  const conversationId = useRef<string | undefined>(undefined);
  const nextId = useRef(0);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

  function makeId(prefix: string) {
    nextId.current += 1;
    return `${prefix}-${nextId.current}`;
  }

  async function sendMessage(text: string) {
    const userMessage: ChatMessage = {
      id: makeId("user"),
      role: "user",
      text,
      status: "complete",
    };
    const history = toHistory([...messages, userMessage]);
    setMessages((prev) => [...prev, userMessage]);
    setPending(true);

    const assistantId = makeId("assistant");
    setMessages((prev) => [...prev, { id: assistantId, role: "assistant", text: "", status: "streaming" }]);

    const controller = new AbortController();
    abortRef.current = controller;

    function updateAssistant(patch: Partial<ChatMessage>) {
      setMessages((prev) => prev.map((m) => (m.id === assistantId ? { ...m, ...patch } : m)));
    }

    try {
      await streamChat(
        { conversationId: conversationId.current, history },
        {
          onStart: (id) => {
            conversationId.current = id;
          },
          onToken: (delta) => {
            setMessages((prev) =>
              prev.map((m) => (m.id === assistantId ? { ...m, text: m.text + delta } : m)),
            );
          },
          onCitations: (citations) => updateAssistant({ citations }),
          onDone: (event) => {
            updateAssistant({
              text: event.answer,
              citations: event.citations,
              status: event.refused ? "refused" : "complete",
              traceId: event.traceId ?? undefined,
            });
          },
          onError: (message) => updateAssistant({ text: message, status: "error" }),
        },
        controller.signal,
      );
    } catch (error) {
      const message = error instanceof ChatRequestError ? error.message : "request failed";
      updateAssistant({ text: message, status: "error" });
    } finally {
      setPending(false);
      abortRef.current = null;
    }
  }

  async function handleFeedback(messageId: string, traceId: string, value: 1 | -1) {
    try {
      await sendFeedback(traceId, value);
      setMessages((prev) => prev.map((m) => (m.id === messageId ? { ...m, feedback: value } : m)));
    } catch {
      // Best-effort: a failed rating never blocks or disrupts the conversation.
    }
  }

  function restart() {
    abortRef.current?.abort();
    abortRef.current = null;
    conversationId.current = undefined;
    setMessages([]);
    setPending(false);
  }

  return (
    <ChatSessionContext.Provider
      value={{ messages, pending, sendMessage, handleFeedback, restart, locale, setLocale }}
    >
      {children}
    </ChatSessionContext.Provider>
  );
}

export function useChatSession(): ChatSession {
  const session = useContext(ChatSessionContext);
  if (!session) {
    throw new Error("useChatSession must be used within a ChatSessionProvider");
  }
  return session;
}
