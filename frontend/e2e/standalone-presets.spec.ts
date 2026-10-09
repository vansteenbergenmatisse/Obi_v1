/**
 * Browser test (substep 8.4.1, panel mi-presets). Drives the real floating widget on the main
 * site and proves the standalone preset selector's two user-visible guarantees (§D.8):
 *   - switching presets starts a FRESH chat (the prior conversation is cleared), and
 *   - the simulated test context is clearly distinguished from real configuration (a visible
 *     "simulated test context" marker).
 *
 * No backend is involved: `page.route` fulfils `POST /api/chat` with a canned SSE stream, so the
 * sent question lands in the thread deterministically; selecting a different preset then clears it.
 * `next dev` (the playwright webServer) runs with NODE_ENV=development, so the dev-only selector
 * renders — exactly the standalone environment the presets exist for.
 */
import { expect, test } from "@playwright/test";

function sse(events: Array<Record<string, unknown>>): string {
  return events.map((event) => `data: ${JSON.stringify(event)}\n\n`).join("");
}

const CANNED_ANSWER = "Here is your answer [1].";
const CANNED_STREAM = sse([
  { type: "start", conversationId: "c-presets" },
  { type: "token", delta: CANNED_ANSWER },
  {
    type: "done",
    answer: CANNED_ANSWER,
    citations: [
      { id: "1", pageId: "p-1", title: "Setup guide", url: "https://example.com/setup" },
    ],
    traceId: "t-presets",
    refused: false,
  },
]);

test("switching presets starts a fresh chat and keeps the simulated-context marker visible", async ({
  page,
}) => {
  await page.route("**/api/chat", async (route) => {
    await route.fulfill({ status: 200, contentType: "text/event-stream", body: CANNED_STREAM });
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Open assistant" }).click();

  // The simulated-context marker is visible, clearly distinguishing the test harness from a real
  // customer configuration.
  const marker = page.getByTestId("simulated-context-marker");
  await expect(marker).toBeVisible();
  await expect(marker).toContainText("Simulated test context");

  const selector = page.getByRole("combobox", { name: "Simulated test context preset" });

  // Pick a preset, then ask a question so the thread holds a conversation.
  await selector.selectOption("pos-to-pms");
  const input = page.getByRole("textbox", { name: "Message" });
  await input.fill("Why are Toast room charges missing in Mews?");
  await input.press("Enter");
  await expect(page.getByText("Why are Toast room charges missing in Mews?")).toBeVisible();

  // Switching to another preset starts a fresh chat: the prior conversation is gone.
  await selector.selectOption("three-system");
  await expect(page.getByText("Why are Toast room charges missing in Mews?")).toHaveCount(0);

  // The marker is still shown and reflects the new simulated selection.
  await expect(marker).toBeVisible();
  await expect(selector).toHaveValue("three-system");
});

test("mi-contract · 8.4.2: the widget carries the selected preset's simulated context on the chat request", async ({
  page,
}) => {
  // The dev harness threads the chosen preset's company_id + three slots onto the outgoing
  // request as the NON-AUTHORITATIVE `simulatedContext` (the verified token/note stays the only
  // authority — never-bend rules 2–3). With no preset selected the field is absent (a legacy /
  // real session is byte-identical to today).
  let firstBody: Record<string, unknown> | undefined;
  let secondBody: Record<string, unknown> | undefined;
  let seen = 0;
  await page.route("**/api/chat", async (route) => {
    const payload = route.request().postDataJSON() as Record<string, unknown>;
    seen += 1;
    if (seen === 1) firstBody = payload;
    else secondBody = payload;
    await route.fulfill({ status: 200, contentType: "text/event-stream", body: CANNED_STREAM });
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Open assistant" }).click();

  const input = page.getByRole("textbox", { name: "Message" });

  // No preset yet: the outgoing request carries no simulatedContext. `exact` matches only the
  // rendered message bubble, not the sr-only "You: …" aria-live announcement that also holds it.
  await input.fill("First question with no preset");
  await input.press("Enter");
  await expect(page.getByText("First question with no preset", { exact: true })).toBeVisible();
  await expect.poll(() => firstBody !== undefined).toBe(true);
  expect(firstBody?.simulatedContext).toBeUndefined();

  // Select a preset, then ask: the request now carries that preset's company_id + slots.
  const selector = page.getByRole("combobox", { name: "Simulated test context preset" });
  await selector.selectOption("pos-to-pms");
  await input.fill("Second question under the Toast→Mews preset");
  await input.press("Enter");
  await expect(
    page.getByText("Second question under the Toast→Mews preset", { exact: true }),
  ).toBeVisible();
  await expect.poll(() => secondBody !== undefined).toBe(true);
  expect(secondBody?.simulatedContext).toEqual({
    companyId: "preset-pos-to-pms",
    slots: { pos: "toast", pms: "mews", accounting: null },
  });
});
