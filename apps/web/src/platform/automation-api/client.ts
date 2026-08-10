/**
 * Automation API client — generic technical access to the Python `apps/automation`
 * service (base URL + shared-secret auth + timeout). No chat-specific behaviour lives
 * here; that stays in `features/chat`, the client's sole consumer today.
 */

export class AutomationApiConfigError extends Error {}

export interface AutomationApiConfig {
  baseUrl: string;
  apiKey: string;
  timeoutMs: number;
}

const DEFAULT_BASE_URL = "http://localhost:8000";
const DEFAULT_TIMEOUT_MS = 120_000;

/**
 * Reads the shared secret + base URL from process env, server-side only. `CHAT_API_KEY`
 * has no default — an unconfigured secret must fail closed, mirroring the automation
 * API's own posture (`_verify_api_key` in `router.py`), not silently proceed unauthenticated.
 */
export function readAutomationApiConfig(): AutomationApiConfig {
  const apiKey = process.env.CHAT_API_KEY ?? "";
  if (!apiKey) {
    throw new AutomationApiConfigError("CHAT_API_KEY is not configured");
  }
  const baseUrl = process.env.AUTOMATION_API_BASE_URL || DEFAULT_BASE_URL;
  const parsedTimeout = Number(process.env.AUTOMATION_API_TIMEOUT_MS);
  const timeoutMs = Number.isFinite(parsedTimeout) && parsedTimeout > 0 ? parsedTimeout : DEFAULT_TIMEOUT_MS;
  return { baseUrl, apiKey, timeoutMs };
}

export interface AutomationApiRequest {
  path: string;
  method: "POST" | "PATCH";
  body: unknown;
  idempotencyKey?: string;
}

/** Issues one bounded, authenticated call to the automation API. No retries here — retrying a
 * state-mutating `POST /chat` without the caller's own `Idempotency-Key` would risk duplicate
 * side effects; the automation API owns its own retry/breaker discipline for its outbound calls. */
export async function callAutomationApi(
  config: AutomationApiConfig,
  request: AutomationApiRequest,
): Promise<Response> {
  const headers: Record<string, string> = {
    "content-type": "application/json",
    authorization: `Bearer ${config.apiKey}`,
  };
  if (request.idempotencyKey) {
    headers["idempotency-key"] = request.idempotencyKey;
  }
  return fetch(`${config.baseUrl}${request.path}`, {
    method: request.method,
    headers,
    body: JSON.stringify(request.body),
    signal: AbortSignal.timeout(config.timeoutMs),
  });
}
