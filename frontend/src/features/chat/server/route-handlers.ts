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
 *   C1_auth:        covered   - PLAN 11.1c (ADR-db-level-customer-scope-isolation-backstop) retired the pilot invite-token gate
 *                               (`WIDGET_ACCESS_TOKEN`/`access-token.ts`/`auth.ts` — deleted) that
 *                               previously guarded this leg. The browser->proxy leg is no longer
 *                               invite-gated: any request reaches this handler, but the platform-
 *                               signed user JWT on the incoming `Authorization: Bearer <jwt>`
 *                               header (present only from the Obi `/embed` frame) is forwarded to
 *                               the backend as `X-Obi-Token`, which is the actual scope authority
 *                               — the backend's `TokenVerifier` verifies it and derives
 *                               general-only access when it is absent or unverifiable. `CHAT_API_KEY`
 *                               is read server-side only and injected as `Authorization: Bearer`
 *                               on the *outbound* call to the backend (the host key, distinct from
 *                               the inbound JWT above); never sent to or readable by the browser.
 *   C2_rate_limit:  opted_out - the backend enforces C2 authoritatively on every request that
 *                               reaches it (keyed on the verified token subject when present, else
 *                               client IP); a second, weaker in-memory limiter here (no shared
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
 *                               never message/answer text or the JWT value, matching the
 *                               backend's posture).
 *   C10_abuse:      opted_out - inherited from the backend's rate limit + abuse caps (C2 note).
 *
 * security_baseline (surface: PATCH /api/chat/{traceId}/feedback, tier STATE-MUTATING):
 *   Same C3/C4/C9 mechanisms as above, scaled down; C2/C10 opted out for the same
 *   inherited-from-backend reason. This surface never reads the user JWT — feedback is a
 *   trace-id-keyed update, not a scoped read.
 *
 * security_baseline (surface: GET /api/chat/visibility, tier AUTHENTICATED-READ — sync-rules
 * ADR-source-system-decides-widget-eligibility, the source-enablement visibility probe):
 *   C1_auth:        covered   - identical to POST /api/chat: the incoming per-user JWT
 *                               (`Authorization: Bearer`) is threaded to the backend as
 *                               `X-Obi-Token` (the scope authority, verified by `TokenVerifier`);
 *                               the host `CHAT_API_KEY` is injected server-side as the outbound
 *                               `Authorization` and never reaches the browser. A tokenless context
 *                               is general-only and always visible.
 *   C2_rate_limit:  opted_out - the backend enforces C2 authoritatively (same note as POST /chat);
 *                               a second, driftable limiter here would be redundant. The 429 is
 *                               forwarded verbatim.
 *   C3_input:       covered   - no request body and no caller-supplied parameters at all; there is
 *                               nothing to validate beyond the Bearer header shape
 *                               (`extractUserToken`), which is checked. The backend re-validates the
 *                               verified token and 400s an unknown/malformed value fail-closed.
 *   C4_timeout:     covered   - `AbortSignal.timeout` on the outbound fetch (10s, tighter than the
 *                               chat path); single attempt, no proxy-level retry (same rationale).
 *   C9_audit:       covered   - one structured log line (status only — never the JWT value).
 *   C5/C6/C7/C8/C10 opted_out - read-only, no LLM, no state mutation, no shared-resource write in
 *                               this process; abuse/cost are inherited from the backend (C2 note).
 */

import type { ChatRequest, FeedbackRequest } from "@omniboost/contracts";
import {
  AutomationApiConfigError,
  callAutomationApi,
  readAutomationApiConfig,
} from "@/platform/automation-api";
import { parseChatRequestBody, parseFeedbackBody } from "./validation";

const _AUTH_HEADER = "authorization";
const _BEARER_PREFIX = "Bearer ";

/** Extracts the platform-signed user JWT from the incoming `Authorization` header, if present.
 * Never forwarded back out as `Authorization` (that header carries the host `chat_api_key` on the
 * outbound leg) — threaded into `callAutomationApi` as `userToken`, which sends it on its own
 * `X-Obi-Token` header (PLAN 11.1c). Absent means the tokenless/general-only path;
 * never logged. */
function extractUserToken(request: Request): string | undefined {
  const header = request.headers.get(_AUTH_HEADER) ?? "";
  if (!header.startsWith(_BEARER_PREFIX)) return undefined;
  const token = header.slice(_BEARER_PREFIX.length).trim();
  return token || undefined;
}

const IDEMPOTENCY_HEADER = "idempotency-key";
// Resource-exhaustion ceiling, not a business-rule cap (see validation.ts) — must stay above the
// backend's own legitimate max so its real caps (chat_max_images_per_turn x chat_max_image_bytes,
// decision w-composer-images) stay authoritative, not silently pre-empted here. The per-turn image
// cap was raised 3 -> 10 on 2026-10-07 (substep 3.6.7), each still <= 3_000_000 bytes of base64:
// 10 * 3_000_000 = 30MB of image data for one turn. 40MB leaves headroom for that plus JSON/text
// history overhead while still bounding a pathologically oversized body (PLAN 7.8 fix — the
// pre-image 200_000 ceiling, set at Phase 4.5 for text-only history, was never raised when Phase 7
// added image attachments, so it 413'd almost every real screenshot/photo before reaching the backend).
const MAX_BODY_BYTES = 40_000_000;
const FEEDBACK_TIMEOUT_MS = 15_000;
// The visibility probe is a quick read; keep its timeout well under the chat path so a slow
// backend can't stall the widget's load-time cross-check (C4).
const VISIBILITY_TIMEOUT_MS = 10_000;

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
    // DEV/standalone harness only, non-authoritative (substep 8.4.2). Forwarded in snake_case so the
    // backend accepts the shape (no 400); the backend logs and ignores it in favour of the verified
    // token/note — the body never decides access (never-bend rule 2). Absent in a real session.
    simulated_context: request.simulatedContext
      ? {
          company_id: request.simulatedContext.companyId,
          slots: request.simulatedContext.slots,
        }
      : undefined,
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
  const userToken = extractUserToken(request);

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
      userToken,
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

/**
 * GET /api/chat/visibility (ADR-source-system-decides-widget-eligibility) — the source-enablement visibility probe.
 * Read-only, no request body: extracts the per-user JWT, injects the host key server-side (via
 * `callAutomationApi`), and forwards the backend's `/chat/visibility` body + status verbatim. A
 * `{"visible":false,"reason":"source_not_enabled"}` 200 and any hard failure (400/401/429/503) are
 * both passed through unchanged — the frame never coerces a hard failure into "hidden".
 */
export async function handleGetVisibility(request: Request): Promise<Response> {
  const userToken = extractUserToken(request);

  let config;
  try {
    config = readAutomationApiConfig();
  } catch (error) {
    if (error instanceof AutomationApiConfigError) {
      console.error("chat_visibility_proxy_unconfigured", { error: error.message });
      return errorResponse(503, "chat is not configured");
    }
    throw error;
  }

  let backendResponse: Response;
  try {
    backendResponse = await callAutomationApi(
      { ...config, timeoutMs: VISIBILITY_TIMEOUT_MS },
      { path: "/chat/visibility", method: "GET", userToken },
    );
  } catch (error) {
    console.error("chat_visibility_proxy_upstream_failed", {
      error: error instanceof Error ? error.message : String(error),
    });
    return errorResponse(502, "chat backend unreachable");
  }

  console.info("chat_visibility_proxy_request", { status: backendResponse.status });

  return forwardBackendJson(backendResponse);
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
