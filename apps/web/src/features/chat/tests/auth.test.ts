import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { ACCESS_TOKEN_HEADER, verifyWidgetAccessToken } from "../server/auth";

const ORIGINAL_ENV = process.env.WIDGET_ACCESS_TOKEN;

function requestWithHeader(headerValue?: string): Request {
  const headers: Record<string, string> = {};
  if (headerValue !== undefined) {
    headers[ACCESS_TOKEN_HEADER] = headerValue;
  }
  return new Request("http://localhost/api/chat", { method: "POST", headers });
}

describe("verifyWidgetAccessToken", () => {
  afterEach(() => {
    if (ORIGINAL_ENV === undefined) {
      delete process.env.WIDGET_ACCESS_TOKEN;
    } else {
      process.env.WIDGET_ACCESS_TOKEN = ORIGINAL_ENV;
    }
  });

  it("fails closed with 'unconfigured' when WIDGET_ACCESS_TOKEN is unset", () => {
    delete process.env.WIDGET_ACCESS_TOKEN;
    const result = verifyWidgetAccessToken(requestWithHeader("anything"));
    expect(result).toEqual({ ok: false, reason: "unconfigured" });
  });

  it("fails closed with 'unconfigured' even when the header happens to be empty too", () => {
    delete process.env.WIDGET_ACCESS_TOKEN;
    const result = verifyWidgetAccessToken(requestWithHeader());
    expect(result).toEqual({ ok: false, reason: "unconfigured" });
  });

  describe("when WIDGET_ACCESS_TOKEN is configured", () => {
    beforeEach(() => {
      process.env.WIDGET_ACCESS_TOKEN = "correct-horse-battery-staple";
    });

    it("rejects a missing header", () => {
      const result = verifyWidgetAccessToken(requestWithHeader());
      expect(result).toEqual({ ok: false, reason: "invalid" });
    });

    it("rejects an empty header", () => {
      const result = verifyWidgetAccessToken(requestWithHeader(""));
      expect(result).toEqual({ ok: false, reason: "invalid" });
    });

    it("rejects a wrong token of the same length", () => {
      const result = verifyWidgetAccessToken(requestWithHeader("correct-horse-battery-staplf"));
      expect(result).toEqual({ ok: false, reason: "invalid" });
    });

    it("rejects a wrong token of a different length without throwing", () => {
      expect(() => verifyWidgetAccessToken(requestWithHeader("short"))).not.toThrow();
      const result = verifyWidgetAccessToken(requestWithHeader("short"));
      expect(result).toEqual({ ok: false, reason: "invalid" });
    });

    it("rejects a wrong token that is much longer than the configured one", () => {
      const result = verifyWidgetAccessToken(
        requestWithHeader("correct-horse-battery-staple-and-then-some-more-text"),
      );
      expect(result).toEqual({ ok: false, reason: "invalid" });
    });

    it("accepts the exact correct token", () => {
      const result = verifyWidgetAccessToken(requestWithHeader("correct-horse-battery-staple"));
      expect(result).toEqual({ ok: true });
    });
  });

  it("never includes the attempted token value in the result", () => {
    process.env.WIDGET_ACCESS_TOKEN = "correct-horse-battery-staple";
    const result = verifyWidgetAccessToken(requestWithHeader("some-wrong-secret-value"));
    expect(JSON.stringify(result)).not.toContain("some-wrong-secret-value");
  });
});
