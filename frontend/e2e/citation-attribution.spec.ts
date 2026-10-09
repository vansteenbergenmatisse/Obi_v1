/**
 * Browser test (substep 8.3.4, panel mi-attrib). Drives the real floating widget on the main
 * site and asserts that per-slot source attribution the BACKEND assembled renders on a citation.
 *
 * No backend is involved: `page.route` fulfils `POST /api/chat` with a canned SSE stream whose
 * `citations` carry an `attribution` enum value — exactly the shape the backend now sends
 * (substep 8.3.4). This mirrors the test-level rule "assert on the DOM and on network requests,
 * never on a real platform": the widget only RENDERS what the stream carries, it never infers or
 * recomputes eligibility, so a mocked stream is a faithful stand-in for the backend decision.
 */
import { expect, test } from "@playwright/test";

type WireCitation = {
  id: string;
  pageId: string;
  title: string;
  url: string;
  attribution?: string;
};

function sse(events: Array<Record<string, unknown>>): string {
  return events.map((event) => `data: ${JSON.stringify(event)}\n\n`).join("");
}

function streamFor(answer: string, citations: WireCitation[]): string {
  return sse([
    { type: "start", conversationId: "c-attrib" },
    { type: "token", delta: answer },
    { type: "citations", citations },
    { type: "done", answer, citations, traceId: "t-attrib", refused: false },
  ]);
}

async function ask(
  page: import("@playwright/test").Page,
  question: string,
  body: string,
): Promise<void> {
  await page.route("**/api/chat", async (route) => {
    await route.fulfill({ status: 200, contentType: "text/event-stream", body });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Open assistant" }).click();
  const input = page.getByRole("textbox", { name: "Message" });
  await input.fill(question);
  await input.press("Enter");
}

test("a pair guide renders its backend-assembled attribution on the citation", async ({ page }) => {
  await ask(
    page,
    "How do I connect Toast to Mews?",
    streamFor("Open the integrations panel [1].", [
      {
        id: "1",
        pageId: "p-pair",
        title: "Toast + Mews setup",
        url: "https://example.com/pair",
        attribution: "pair",
      },
    ]),
  );

  await expect(page.getByRole("link", { name: /Toast \+ Mews setup/ })).toBeVisible();
  const badge = page.locator('[data-attribution="pair"]');
  await expect(badge).toBeVisible();
  await expect(badge).toHaveText("For your integration");
});

test("a general guide renders the general attribution and a slot guide its named slot", async ({
  page,
}) => {
  await ask(
    page,
    "What is Obi?",
    streamFor("Obi answers from your docs [1]. Set up your POS [2].", [
      { id: "1", pageId: "p-gen", title: "Overview", url: "https://example.com/gen", attribution: "general" },
      { id: "2", pageId: "p-pos", title: "POS setup", url: "https://example.com/pos", attribution: "pos" },
    ]),
  );

  await expect(page.locator('[data-attribution="general"]')).toHaveText("General guide");
  await expect(page.locator('[data-attribution="pos"]')).toHaveText("For your POS");
});

test("a citation with no attribution renders no attribution badge (unchanged from before)", async ({
  page,
}) => {
  await ask(
    page,
    "What is the refund policy?",
    streamFor("See the policy [1].", [
      { id: "1", pageId: "p-plain", title: "Refund policy", url: "https://example.com/plain" },
    ]),
  );

  await expect(page.getByRole("link", { name: /Refund policy/ })).toBeVisible();
  await expect(page.locator("[data-attribution]")).toHaveCount(0);
});
