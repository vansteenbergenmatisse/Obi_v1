/**
 * Browser test (substep 9.3.1, panels mi-contract / mi-gate, ADR-directed-source-target-routing-labels Option A). Drives the REAL
 * embed frame on the `/test-hosts/connection-switch` page and proves that switching the directed
 * `source → target` connection via a silent token renewal RESETS the open thread — no answer built
 * for one connection bleeds into another.
 *
 * No backend is involved: `page.route` fulfils `POST /api/chat` with a canned SSE stream (the same
 * pattern as `citation-attribution.spec.ts`). The test only drives the bridge/session wiring and
 * asserts on the DOM, never on a real platform.
 */
import { expect, test } from "@playwright/test";

function sse(events: Array<Record<string, unknown>>): string {
  return events.map((event) => `data: ${JSON.stringify(event)}\n\n`).join("");
}

const ANSWER_TEXT = "Toast to Mews connection answer.";
const ANSWER_STREAM = sse([
  { type: "start", conversationId: "c-switch" },
  { type: "token", delta: ANSWER_TEXT },
  { type: "citations", citations: [] },
  { type: "done", answer: ANSWER_TEXT, citations: [], traceId: "t-switch", refused: false },
]);

test("switching the directed connection resets the embed thread", async ({ page }) => {
  await page.route("**/api/chat", async (route) => {
    await route.fulfill({ status: 200, contentType: "text/event-stream", body: ANSWER_STREAM });
  });

  await page.goto("/test-hosts/connection-switch");

  // Open the panel and hand it connection A (Toast → Mews), then hold a conversation under it.
  await page.getByTestId("open").click();
  await page.getByTestId("connection-a").click();

  const input = page.getByRole("textbox", { name: /message/i });
  await input.fill("How do I connect Toast to Mews?");
  await input.press("Enter");

  // `.first()`: the answer also renders into an sr-only aria-live region, so the text matches two
  // nodes — either one proves the turn landed.
  await expect(page.getByText("How do I connect Toast to Mews?").first()).toBeVisible();
  await expect(page.getByText(ANSWER_TEXT, { exact: false }).first()).toBeVisible();

  // Silent renewal into a DIFFERENT connection (Opera Cloud → Toast) — a partner switch. The
  // thread must be torn down so no prior-connection answer survives the switch.
  await page.getByTestId("connection-b").click();

  await expect(page.getByText("How do I connect Toast to Mews?")).toHaveCount(0);
  await expect(page.getByText(ANSWER_TEXT, { exact: false })).toHaveCount(0);
  // A switch is not a logout: the composer stays open on a fresh, empty thread.
  await expect(page.getByRole("textbox", { name: /message/i })).toBeVisible();
});
