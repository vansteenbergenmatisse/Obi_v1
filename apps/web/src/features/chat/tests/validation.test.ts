import { describe, expect, it } from "vitest";
import { parseChatRequestBody, parseFeedbackBody } from "../server/validation";

describe("parseChatRequestBody", () => {
  it("accepts a well-formed request and passes fields through unchanged", () => {
    const result = parseChatRequestBody({
      conversationId: "conv-1",
      principal: "user-1",
      history: [{ role: "user", content: "hello" }],
    });
    expect(result).toEqual({
      ok: true,
      value: {
        conversationId: "conv-1",
        principal: "user-1",
        history: [{ role: "user", content: "hello" }],
      },
    });
  });

  it("accepts a minimal request with only history", () => {
    const result = parseChatRequestBody({ history: [{ role: "user", content: "hi" }] });
    expect(result.ok).toBe(true);
  });

  it.each([null, undefined, "string", 42])("rejects a non-object body: %s", (body) => {
    expect(parseChatRequestBody(body)).toEqual({
      ok: false,
      error: "request body must be a JSON object",
    });
  });

  it("rejects a missing history field", () => {
    expect(parseChatRequestBody({})).toEqual({
      ok: false,
      error: "history must be a non-empty array",
    });
  });

  it("rejects an empty history array", () => {
    expect(parseChatRequestBody({ history: [] })).toEqual({
      ok: false,
      error: "history must be a non-empty array",
    });
  });

  it("rejects history longer than the resource-exhaustion ceiling", () => {
    const history = Array.from({ length: 201 }, (_, i) => ({
      role: i % 2 === 0 ? "user" : "assistant",
      content: "x",
    }));
    const result = parseChatRequestBody({ history });
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toMatch(/exceeds 200 turns/);
    }
  });

  it("rejects a turn with an invalid role", () => {
    const result = parseChatRequestBody({ history: [{ role: "system", content: "hi" }] });
    expect(result.ok).toBe(false);
  });

  it("accepts a turn with empty content and no images (the backend has no min_length either)", () => {
    const result = parseChatRequestBody({ history: [{ role: "user", content: "" }] });
    expect(result.ok).toBe(true);
  });

  it("accepts an image-only turn with empty content (ADR-0009 decision 4)", () => {
    const result = parseChatRequestBody({
      history: [
        { role: "user", content: "", images: [{ mediaType: "image/png", data: "abc123" }] },
      ],
    });
    expect(result.ok).toBe(true);
  });

  it("accepts a resent history where an older, no-longer-newest image-only turn has aged out to empty content and no images (PLAN 7.8 bug E)", () => {
    // ADR-0009 decision 2: images are only ever resent on the newest turn. An older turn that was
    // originally image-only (content: "") therefore has neither content nor images once resent —
    // this must still parse, or every conversation that ever sent one image-only turn would be
    // permanently broken from that point on.
    const result = parseChatRequestBody({
      history: [
        { role: "user", content: "" },
        { role: "assistant", content: "I don't have that in the documentation." },
        {
          role: "user",
          content: "What colors are in this image?",
          images: [{ mediaType: "image/png", data: "abc123" }],
        },
      ],
    });
    expect(result.ok).toBe(true);
  });

  it("rejects history that does not end on a user turn", () => {
    const result = parseChatRequestBody({
      history: [
        { role: "user", content: "hi" },
        { role: "assistant", content: "hello" },
      ],
    });
    expect(result).toEqual({ ok: false, error: "history must end on a user turn" });
  });

  it("rejects a non-string conversationId", () => {
    const result = parseChatRequestBody({
      conversationId: 123,
      history: [{ role: "user", content: "hi" }],
    });
    expect(result).toEqual({ ok: false, error: "conversationId must be a string" });
  });

  it("rejects a non-string principal", () => {
    const result = parseChatRequestBody({
      principal: { id: 1 },
      history: [{ role: "user", content: "hi" }],
    });
    expect(result).toEqual({ ok: false, error: "principal must be a string" });
  });
});

describe("parseFeedbackBody", () => {
  it.each([-1, 1])("accepts feedback value %d", (feedback) => {
    expect(parseFeedbackBody({ feedback })).toEqual({ ok: true, value: { feedback } });
  });

  it.each([0, 2, -2, "1", null, undefined])("rejects invalid feedback value: %s", (feedback) => {
    expect(parseFeedbackBody({ feedback })).toEqual({
      ok: false,
      error: "feedback must be -1 or 1",
    });
  });

  it("rejects a non-object body", () => {
    expect(parseFeedbackBody("nope")).toEqual({
      ok: false,
      error: "request body must be a JSON object",
    });
  });
});
