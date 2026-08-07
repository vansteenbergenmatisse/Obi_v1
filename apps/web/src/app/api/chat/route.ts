import { NextResponse } from "next/server";

/**
 * Chat route handler — Phase 1 STUB.
 *
 * In Phase 4 this handler becomes a thin proxy: it validates the inbound
 * `ChatRequest` (from `@omniboost/contracts`) and forwards it to the Python
 * automation API's `POST /chat`, streaming the Server-Sent Events response
 * (start / token / citations / done) straight back to the browser. No business
 * logic lives here — the RAG runtime is owned by `apps/automation`.
 *
 * Until then it returns 501 so the contract and error shape are exercised
 * without pretending the runtime exists.
 */
export function POST() {
  return NextResponse.json(
    { error: "chat runtime lands in Phase 4" },
    { status: 501 },
  );
}
