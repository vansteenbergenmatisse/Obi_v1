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
 *   C1_auth:        covered   - CHAT_API_KEY is read server-side only and injected as
 *                               `Authorization: Bearer` on the outbound call; never sent to
 *                               or readable by the browser. The browser->proxy leg has no
 *                               additional auth (documented gap, same posture as the backend's
 *                               own principal-trust model — no end-user login system exists yet).
 *   C2_rate_limit:  opted_out - the backend enforces C2 authoritatively on the exact same
 *                               request; a second, weaker in-memory limiter here (no shared
 *                               store across serverless instances) would be redundant and could
 *                               drift from the backend's config. The backend's 429 is forwarded
 *                               verbatim.
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
import { parseChatRequestBody, parseFeedbackBody } from "./validation";

const IDEMPOTENCY_HEADER = "idempotency-key";
const MAX_BODY_BYTES = 200_000; // resource-exhaustion ceiling, not a business-rule cap (see validation.ts)
const FEEDBACK_TIMEOUT_MS = 15_000;

function errorResponse(status: number, error: string): Response {
  return Response.json({ error }, { status });
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
