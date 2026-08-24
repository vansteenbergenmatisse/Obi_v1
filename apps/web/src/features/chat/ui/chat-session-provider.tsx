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
import type { ChatTurn, ImageAttachment } from "@omniboost/contracts";
import { captureWidgetAccessToken } from "../api/access-token";
import { ChatRequestError, sendFeedback, streamChat } from "../api/chat-client";

const ACCESS_TOKEN_EXPIRED_MESSAGE =
  "Your access link has expired — open the chat from your invite link again.";
import type { ChatMessage, SentImage } from "../model/messages";
import type { Locale } from "../model/i18n";

/** Only complete/refused/clarifying turns (plus every user turn) become resendable history —
 * a streaming placeholder has no final text yet, and an error turn is our own proxy's error
 * message, not something the model actually said. A clarifying turn's question is real
 * assistant output the next call needs as context (PLAN 9.5), so it counts here too. */
function toHistory(messages: ChatMessage[]): ChatTurn[] {
  return messages
    .filter(
      (message) =>
        message.role === "user" ||
        message.status === "complete" ||
        message.status === "refused" ||
        message.status === "clarifying",
    )
    .map((message) => ({ role: message.role, content: message.text }));
}

export interface ChatSession {
  messages: ChatMessage[];
  pending: boolean;
  /** `images` (PLAN 7.5) rides on this turn only — ADR-0009 decision 2, no history resend. */
  sendMessage: (text: string, images?: SentImage[]) => Promise<void>;
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

export interface ChatSessionProviderProps {
  children: ReactNode;
  /**
   * Which third-party platform this deployment/embed is scoped to
   * (ADR-0011 decision 6) — set once at widget initialization (the
   * embedding page/deployment declares which platform it is), not
   * re-derived per message. Omitted means the backend's default/general
   * scope applies. A visible switcher for this value is PLAN 10.8, not
   * this plumbing.
   */
  knowledgeScope?: string;
}

export function ChatSessionProvider({ children, knowledgeScope }: ChatSessionProviderProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [pending, setPending] = useState(false);
  const [locale, setLocale] = useState<Locale>("en");
  const conversationId = useRef<string | undefined>(undefined);
  const nextId = useRef(0);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

  // Runs once per full page load (this provider is mounted once at the app root) — picks up an
  // invite link's `?access_token=` if present (idea #6), otherwise reuses whatever was already
  // captured this session.
  useEffect(() => {
    captureWidgetAccessToken();
  }, []);

  function makeId(prefix: string) {
    nextId.current += 1;
    return `${prefix}-${nextId.current}`;
  }

  async function sendMessage(text: string, images: SentImage[] = []) {
    const userId = makeId("user");
    const userMessage: ChatMessage = {
      id: userId,
      role: "user",
      text,
      status: "complete",
      images:
        images.length > 0
          ? images.map((image, index) => ({
              id: `${userId}-image-${index}`,
              previewUrl: image.previewUrl,
              alt: image.alt,
            }))
          : undefined,
    };
    const history = toHistory([...messages, userMessage]);
    // The newest turn only (ADR-0009 decision 2) — `toHistory` never carries images itself, so
    // the wire payload is attached here, after history is built, not baked into the mapper.
    if (images.length > 0) {
      const wireImages: ImageAttachment[] = images.map(({ mediaType, data }) => ({
        mediaType,
        data,
      }));
      history[history.length - 1] = { ...history[history.length - 1], images: wireImages };
    }
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
        { conversationId: conversationId.current, history, knowledgeScope },
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
              status: event.needsClarification ? "clarifying" : event.refused ? "refused" : "complete",
              traceId: event.traceId ?? undefined,
              imageAnalysis: event.imageAnalysis ?? undefined,
              clarificationOptions: event.clarificationOptions ?? undefined,
            });
          },
          onError: (message) => updateAssistant({ text: message, status: "error" }),
        },
        controller.signal,
      );
    } catch (error) {
      const message =
        error instanceof ChatRequestError
          ? error.status === 401
            ? ACCESS_TOKEN_EXPIRED_MESSAGE
            : error.message
          : "request failed";
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
