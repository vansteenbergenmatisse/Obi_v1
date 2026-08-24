/**
 * Browser -> proxy auth (C1) for the chat surface. Distinct from `platform/automation-api`'s
 * `CHAT_API_KEY`, which secures the proxy -> backend leg only — this is a separate shared secret
 * for the leg that had none (`docs/future-ideas/IDEAS.md` idea #6). `WIDGET_ACCESS_TOKEN` is
 * read fresh from `process.env` on every call (no caching), same posture as
 * `readAutomationApiConfig()`: unset means fail closed, not "auth disabled".
 */
import { timingSafeEqual } from "node:crypto";

export const ACCESS_TOKEN_HEADER = "x-widget-access-token";

export type WidgetAuthResult =
  | { ok: true }
  | { ok: false; reason: "unconfigured" | "invalid" };

/** `timingSafeEqual` throws on mismatched buffer lengths (unlike Python's `hmac.compare_digest`,
 * which the backend's `_verify_api_key` uses) — length is checked first so an attacker-controlled
 * token length can never crash the handler, and the length check itself is cheap/non-secret
 * (token length is not the thing being protected here). */
function safeEqual(a: string, b: string): boolean {
  const bufA = Buffer.from(a);
  const bufB = Buffer.from(b);
  return bufA.length === bufB.length && timingSafeEqual(bufA, bufB);
}

export function verifyWidgetAccessToken(request: Request): WidgetAuthResult {
  const configured = process.env.WIDGET_ACCESS_TOKEN ?? "";
  if (!configured) {
    return { ok: false, reason: "unconfigured" };
  }
  const provided = request.headers.get(ACCESS_TOKEN_HEADER) ?? "";
  if (!provided || !safeEqual(provided, configured)) {
    return { ok: false, reason: "invalid" };
  }
  return { ok: true };
}
