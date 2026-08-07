/**
 * ChatPanel — the chat feature's root UI and public surface.
 *
 * This is what routes render. It owns the conversation's local state and wires
 * the composer, the message list, and the browser client together. Everything
 * below it (Composer, MessageList, the client, the view-model) is internal to
 * the feature; only this component is re-exported from the feature root.
 *
 * The runtime is a Phase-1 stub (`/api/chat` returns 501), so an assistant turn
 * currently renders that error honestly instead of a fabricated answer.
 */
"use client";

import { useRef, useState } from "react";
import { Composer } from "./composer";
import { MessageList } from "./message-list";
import { sendChat } from "../api/chat-client";
import type { ChatMessage } from "../model/messages";

export function ChatPanel() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [pending, setPending] = useState(false);
  const conversationId = useRef<string | undefined>(undefined);
  const nextId = useRef(0);

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
    setMessages((prev) => [...prev, userMessage]);
    setPending(true);

    const result = await sendChat({
      conversationId: conversationId.current,
      message: text,
    });

    const assistantMessage: ChatMessage = result.ok
      ? {
          id: makeId("assistant"),
          role: "assistant",
          text: result.answer,
          status: "complete",
        }
      : {
          id: makeId("assistant"),
          role: "assistant",
          text: result.error,
          status: "error",
        };

    setMessages((prev) => [...prev, assistantMessage]);
    setPending(false);
  }

  return (
    <section className="flex w-full flex-col gap-lg" aria-label="Chat">
      <MessageList messages={messages} />
      <Composer onSend={handleSend} disabled={pending} />
    </section>
  );
}
