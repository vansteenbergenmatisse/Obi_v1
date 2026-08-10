/**
 * ChatPanel — the chat feature's root UI and public surface.
 *
 * This is what routes render. It owns the conversation's local state and wires
 * the composer, the message list, and the browser client together. Everything
 * below it (Composer, MessageList, the client, the view-model) is internal to
 * the feature; only this component is re-exported from the feature root.
 */
"use client";

import { useEffect, useRef, useState } from "react";
import type { ChatTurn } from "@omniboost/contracts";
import { Composer } from "./composer";
import { MessageList } from "./message-list";
import { ChatRequestError, sendFeedback, streamChat } from "../api/chat-client";
import type { ChatMessage } from "../model/messages";

/** Only complete/refused turns (plus every user turn) become resendable history — a
 * streaming placeholder has no final text yet, and an error turn is our own proxy's
 * error message, not something the model actually said. */
function toHistory(messages: ChatMessage[]): ChatTurn[] {
  return messages
    .filter((message) => message.role === "user" || message.status === "complete" || message.status === "refused")
    .map((message) => ({ role: message.role, content: message.text }));
}

export function ChatPanel() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [pending, setPending] = useState(false);
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

  async function handleSend(text: string) {
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

  return (
    <section className="flex w-full flex-col gap-lg" aria-label="Chat">
      <MessageList messages={messages} onFeedback={handleFeedback} />
      <Composer onSend={handleSend} disabled={pending} />
    </section>
  );
}
