/**
 * Chat feedback route handler — a thin entrypoint.
 *
 * It only composes the `chat` feature's exported server handler and unwraps the dynamic
 * route param; the proxy behavior lives in `features/chat/server`.
 */
import type { NextRequest } from "next/server";
import { handlePatchFeedback } from "@/features/chat/server";

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ traceId: string }> },
): Promise<Response> {
  const { traceId } = await params;
  return handlePatchFeedback(request, traceId);
}
