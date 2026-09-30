/**
 * Obi · Confluence → backend webhook bridge.
 *
 * One trigger handler for the eight subscribed avi:confluence events. The event is a doorbell,
 * not a payload: the backend worker refetches page state and re-decides on its own, so this
 * handler only normalizes identity fields, filters to pages in the allowed space, signs the
 * exact body string with HMAC-SHA256, and POSTs it. Receiver contract:
 * backend/app/features/confluence_sync/server/webhook.py (flat-shape parse in schemas/events.py).
 *
 * Delivery semantics this code leans on:
 *  - Forge redeliveries carry the identical event payload, so delivery_id (a hash over event
 *    fields only — never wall clock) is deterministic and the backend's event-ledger dedup
 *    treats a redelivery as a duplicate. Wall-clock time is used only as a last-resort
 *    timestamp fallback.
 *  - The backend enqueue is idempotent and its worker version-guards, so duplicates are safe.
 *  - 4xx from the backend is terminal (retrying an unaccepted body is a retry storm); network
 *    errors and 5xx request a Forge retry (max 4, exponential backoff).
 *
 * Never logged: the secret, the signature, the body.
 */

import { fetch } from "@forge/api";
import { InvocationError, InvocationErrorCode } from "@forge/events";
import { createHash, createHmac } from "node:crypto";

const TARGET_URL =
  "https://obi-backend-production.up.railway.app/confluence/events";

// Space "SupOnb" (URL alias "omnidoc") on omniboost.atlassian.net. Forwarding is limited to this
// space in code because manifest filter expressions are unproven for label events (which may
// carry no `content` at all). The backend would also reject foreign pages via its label +
// source_scope gates — this filter just cuts the noise at the source.
const ALLOWED_SPACE_ID = 701857803;

// avi: product event → the receiver's subscribed event_type vocabulary
// (schemas/events.py — note the receiver's name is label_deleted, not label_removed).
const EVENT_MAP = {
  "avi:confluence:created:page": "page_created",
  "avi:confluence:updated:page": "page_updated",
  "avi:confluence:moved:page": "page_moved",
  "avi:confluence:trashed:page": "page_trashed",
  "avi:confluence:restored:page": "page_restored",
  "avi:confluence:deleted:page": "page_deleted",
  "avi:confluence:added:label": "label_added",
  "avi:confluence:removed:label": "label_deleted",
};

function toInt(value) {
  if (typeof value === "number" && Number.isFinite(value)) {
    return Math.trunc(value);
  }
  if (typeof value === "string" && /^\d+$/.test(value)) {
    return parseInt(value, 10);
  }
  return null;
}

function toIsoTimestamp(event, content) {
  // Prefer the event's own clock (stable across redeliveries); wall clock only as last resort.
  for (const candidate of [event?.eventCreatedDate, content?.version?.when]) {
    if (typeof candidate === "string" && !Number.isNaN(Date.parse(candidate))) {
      return new Date(candidate).toISOString();
    }
  }
  return new Date().toISOString();
}

export async function handleEvent(event, _context) {
  const eventType = EVENT_MAP[event?.eventType];
  if (!eventType) {
    console.log(`skip: unmapped eventType ${event?.eventType}`);
    return;
  }

  // Label events carry exactly one of content|space|template; space/template labels have no
  // content. Page events always carry content. Either way: pages only (kills whiteboards,
  // blogposts, databases, space labels).
  const content = event?.content;
  if (!content || content.type !== "page") {
    console.log(`skip: ${eventType} not on a page`);
    return;
  }

  const spaceId = toInt(content?.space?.id);
  if (spaceId !== ALLOWED_SPACE_ID) {
    console.log(`skip: ${eventType} space ${spaceId} not allowed`);
    return;
  }

  const pageId = toInt(content?.id);
  if (pageId === null) {
    console.error(`skip: ${eventType} missing content.id`);
    return;
  }

  const cfVersion = toInt(content?.version?.number); // null when absent (e.g. deleted:page)
  const status = typeof content?.status === "string" ? content.status : null;
  const labelName =
    typeof event?.label?.name === "string" ? event.label.name : null;
  const eventTimestamp = toIsoTimestamp(event, content);
  const actorAccountId =
    typeof event?.atlassianId === "string" ? event.atlassianId : null;

  // Deterministic across Forge redeliveries: derived only from event fields, never wall clock,
  // so a redelivery hashes identically and the backend ledger dedups it.
  const deliveryId = createHash("sha256")
    .update(
      [
        event.eventType,
        pageId,
        cfVersion ?? "",
        labelName ?? "",
        event?.eventCreatedDate ?? "",
      ].join("|"),
      "utf8",
    )
    .digest("hex");

  const isLabelEvent = eventType.startsWith("label_");
  const body = isLabelEvent
    ? {
        event_type: eventType,
        page_id: pageId,
        space_id: spaceId,
        label: labelName,
        event_timestamp: eventTimestamp,
        delivery_id: deliveryId,
        actor_account_id: actorAccountId,
      }
    : {
        event_type: eventType,
        page_id: pageId,
        cf_version: cfVersion,
        space_id: spaceId,
        status: status,
        event_timestamp: eventTimestamp,
        delivery_id: deliveryId,
        actor_account_id: actorAccountId,
      };

  // Serialize exactly once; the signed string IS the sent string (raw-body HMAC contract).
  const bodyString = JSON.stringify(body);

  const secret = process.env.CONFLUENCE_WEBHOOK_SECRET;
  if (!secret) {
    // Config error: retrying cannot help; fail loudly, terminally.
    console.error("CONFLUENCE_WEBHOOK_SECRET is not set; dropping event");
    return;
  }

  const signature = createHmac("sha256", secret)
    .update(bodyString, "utf8")
    .digest("hex");

  let response;
  try {
    response = await fetch(TARGET_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": `sha256=${signature}`,
      },
      body: bodyString,
    });
  } catch (err) {
    console.error(
      `network error delivering ${eventType} page=${pageId}: ${err?.message}`,
    );
    return requestRetry(event);
  }

  if (response.status >= 500) {
    console.error(
      `backend ${response.status} for ${eventType} page=${pageId}; will retry`,
    );
    return requestRetry(event);
  }

  if (!response.ok) {
    // 4xx is terminal: retrying an unaccepted body only makes a retry storm. A 401 here means
    // the secret in Forge and Railway diverged; a 503 means the backend secret is unset.
    console.error(
      `backend ${response.status} for ${eventType} page=${pageId}; dropped`,
    );
    return;
  }

  console.log(
    `delivered ${eventType} page=${pageId} version=${cfVersion} status=${response.status}`,
  );
}

function requestRetry(event) {
  const retryCount = event?.retryContext?.retryCount ?? 0;
  // Exponential backoff with jitter: ~30s, 60s, 120s, 240s (cap 900s; Forge caps at 4 retries).
  const base = Math.min(900, 30 * 2 ** retryCount);
  const retryAfter = Math.min(900, base + Math.floor(Math.random() * 15));
  return new InvocationError({
    retryAfter,
    retryReason: InvocationErrorCode.FUNCTION_RETRY_REQUEST,
  });
}
