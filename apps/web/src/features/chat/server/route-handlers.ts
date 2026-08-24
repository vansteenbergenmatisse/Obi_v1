/**
 * Chat proxy server handlers (PLAN 4.5). Composed by `app/api/chat/route.ts` and
 * `app/api/chat/[traceId]/feedback/route.ts` — the route files stay thin; this module owns
 * the integration with the Python automation API end to end (validation, auth-header
 * injection, streaming passthrough), per the repo standard's feature-ownership rule.
 *
 * Both surfaces are a thin 1:1 proxy over an already-secured backend (`rag_agent/server/
 * router.py`'s `security_baseline`); the controls below describe this proxy hop specifically,
 * not the backend's (union of both applies end to end):
 *
 * security_baseline (surface: POST /api/chat, tier STATE-MUTATING + LLM-CALL):
 *   C1_auth:        covered   - two independent secrets, one per leg. `WIDGET_ACCESS_TOKEN`
 *                               (`server/auth.ts`) gates browser->proxy: a shared invite token,
 *                               constant-time compared, fails closed (503) if unconfigured
 *                               (`docs/future-ideas/IDEAS.md` idea #6 — closes the
 *                               previously-documented gap on this leg). `CHAT_API_KEY` is read
 *                               server-side only and injected as `Authorization: Bearer` on the
 *                               outbound call; never sent to or readable by the browser.
 *   C2_rate_limit:  opted_out - the backend enforces C2 authoritatively on every request that
 *                               reaches it; a second, weaker in-memory limiter here (no shared
 *                               store across serverless instances) would be redundant and could
 *                               drift from the backend's config. The backend's 429 is forwarded
 *                               verbatim. Note: a request rejected by the new C1 token check
 *                               never reaches the backend, so it's invisible to that counter —
 *                               accepted because the rejection itself is cheap (no LLM call, no
 *                               backend round trip, no corpus access) and the token is meant to
 *                               be high-entropy, making brute-forcing it impractical regardless
 *                               of request volume.
 *   C3_input:       covered   - `validation.ts` rejects malformed shape/JSON and a hard
 *                               resource-exhaustion body-size ceiling before any network call.
 *   C4_timeout:     covered   - `AbortSignal.timeout` on the outbound fetch (platform/
 *                               automation-api); single attempt, no proxy-level retry (see
 *                               that module's docstring for why retrying is unsafe here).
 *   C5_output_rate: covered   - the backend already paces/caps the SSE stream; this proxy
 *                               passes the body through untouched (no re-buffering).
 *   C6_redaction:   opted_out - no LLM call happens in this process; redaction is the
 *                               backend's (`rag_agent/domain/pii.py`).
 *   C9_audit:       covered   - one structured log line per call (status + latency only —
 *                               never message/answer text, matching the backend's posture).
 *   C10_abuse:      opted_out - inherited from the backend's rate limit + abuse caps (C2 note).
 *
 * security_baseline (surface: PATCH /api/chat/{traceId}/feedback, tier STATE-MUTATING):
 *   Same C1/C3/C4/C9 mechanisms as above, scaled down; C2/C10 opted out for the same
 *   inherited-from-backend reason.
 */

import type { ChatRequest, FeedbackRequest } from "@omniboost/contracts";
import {
  AutomationApiConfigError,
  callAutomationApi,
  readAutomationApiConfig,
} from "@/platform/automation-api";
import { verifyWidgetAccessToken } from "./auth";
import { parseChatRequestBody, parseFeedbackBody } from "./validation";

const IDEMPOTENCY_HEADER = "idempotency-key";
// Resource-exhaustion ceiling, not a business-rule cap (see validation.ts) — must stay above the
// backend's own legitimate max so its real caps (chat_max_images_per_turn=4 x
// chat_max_image_bytes=5_000_000) stay authoritative, not silently pre-empted here. Base64 inflates
// raw bytes by ~4/3: 4 * 5_000_000 * 4/3 ~= 26.7MB for one turn's images alone. 30MB leaves headroom
// for JSON/text overhead while still bounding a pathologically oversized body (PLAN 7.8 fix — the
// pre-image 200_000 ceiling, set at Phase 4.5 for text-only history, was never raised when Phase 7
// added image attachments, so it 413'd almost every real screenshot/photo before reaching the backend).
const MAX_BODY_BYTES = 30_000_000;
const FEEDBACK_TIMEOUT_MS = 15_000;

function errorResponse(status: number, error: string): Response {
  return Response.json({ error }, { status });
}

/** Runs first in both handlers, before any body parsing (C1) — an unauthenticated request never
 * pays for JSON parsing or reaches the backend. Never logs the attempted token value. */
function rejectUnauthorized(request: Request, logPrefix: string): Response | null {
  const auth = verifyWidgetAccessToken(request);
  if (auth.ok) return null;
  const status = auth.reason === "unconfigured" ? 503 : 401;
  console.warn(`${logPrefix}_unauthorized`, { status });
  return errorResponse(status, status === 503 ? "chat is not configured" : "unauthorized");
}

async function readJsonBody(request: Request): Promise<ParsedBody> {
  let raw: string;
  try {
    raw = await request.text();
  } catch {
    return { ok: false, error: "could not read request body" };
  }
  if (raw.length > MAX_BODY_BYTES) {
    return { ok: false, error: "request body too large", status: 413 };
  }
  if (!raw) {
    return { ok: false, error: "request body must not be empty" };
  }
  try {
    return { ok: true, value: JSON.parse(raw) as unknown };
  } catch {
    return { ok: false, error: "malformed JSON body" };
  }
}

type ParsedBody =
  | { ok: true; value: unknown }
  | { ok: false; error: string; status?: number };

function toBackendChatBody(request: ChatRequest): Record<string, unknown> {
  return {
    conversation_id: request.conversationId,
    history: request.history,
    principal: request.principal,
    knowledge_scope: request.knowledgeScope,
  };
}

/** Forwards the backend's JSON body + status verbatim — used both for error responses and for
 * the feedback PATCH's plain (non-streaming) success body. */
async function forwardBackendJson(backendResponse: Response): Promise<Response> {
  const body = await backendResponse
    .json()
    .catch(() => ({ error: `upstream error (${backendResponse.status})` }));
  return Response.json(body, { status: backendResponse.status });
}

export async function handlePostChat(request: Request): Promise<Response> {
  const unauthorized = rejectUnauthorized(request, "chat_proxy");
  if (unauthorized) return unauthorized;

  const parsedBody = await readJsonBody(request);
  if (!parsedBody.ok) {
    return errorResponse(parsedBody.status ?? 400, parsedBody.error);
  }

  const parsed = parseChatRequestBody(parsedBody.value);
  if (!parsed.ok) {
    return errorResponse(400, parsed.error);
  }

  let config;
  try {
    config = readAutomationApiConfig();
  } catch (error) {
    if (error instanceof AutomationApiConfigError) {
      console.error("chat_proxy_unconfigured", { error: error.message });
      return errorResponse(503, "chat is not configured");
    }
    throw error;
  }

  const idempotencyKey = request.headers.get(IDEMPOTENCY_HEADER) ?? undefined;
  const startedAt = Date.now();
  let backendResponse: Response;
  try {
    backendResponse = await callAutomationApi(config, {
      path: "/chat",
      method: "POST",
      body: toBackendChatBody(parsed.value),
      idempotencyKey,
    });
  } catch (error) {
    console.error("chat_proxy_upstream_failed", {
      error: error instanceof Error ? error.message : String(error),
    });
    return errorResponse(502, "chat backend unreachable");
  }

  console.info("chat_proxy_request", {
    status: backendResponse.status,
    latencyMs: Date.now() - startedAt,
  });

  if (!backendResponse.ok || !backendResponse.body) {
    return forwardBackendJson(backendResponse);
  }

  return new Response(backendResponse.body, {
    status: backendResponse.status,
    headers: {
      "content-type": backendResponse.headers.get("content-type") ?? "text/event-stream",
      "cache-control": "no-cache, no-transform",
      connection: "keep-alive",
    },
  });
}

export async function handlePatchFeedback(request: Request, traceId: string): Promise<Response> {
  const unauthorized = rejectUnauthorized(request, "chat_feedback_proxy");
  if (unauthorized) return unauthorized;

  const parsedBody = await readJsonBody(request);
  if (!parsedBody.ok) {
    return errorResponse(parsedBody.status ?? 400, parsedBody.error);
  }

  const parsed = parseFeedbackBody(parsedBody.value);
  if (!parsed.ok) {
    return errorResponse(400, parsed.error);
  }

  let config;
  try {
    config = readAutomationApiConfig();
  } catch (error) {
    if (error instanceof AutomationApiConfigError) {
      console.error("chat_feedback_proxy_unconfigured", { error: error.message });
      return errorResponse(503, "chat is not configured");
    }
    throw error;
  }

  let backendResponse: Response;
  try {
    backendResponse = await callAutomationApi(
      { ...config, timeoutMs: FEEDBACK_TIMEOUT_MS },
      {
        path: `/chat/${encodeURIComponent(traceId)}/feedback`,
        method: "PATCH",
        body: parsed.value satisfies FeedbackRequest,
      },
    );
  } catch (error) {
    console.error("chat_feedback_proxy_upstream_failed", {
      error: error instanceof Error ? error.message : String(error),
    });
    return errorResponse(502, "chat backend unreachable");
  }

  console.info("chat_feedback_proxy_request", { traceId, status: backendResponse.status });

  return forwardBackendJson(backendResponse);
}
