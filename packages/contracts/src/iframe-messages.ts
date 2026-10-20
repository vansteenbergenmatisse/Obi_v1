/**
 * postMessage contract between the Obi loader (`obi.js`, running in the host page) and the Obi
 * `/embed` iframe frame (PLAN 11.1c, ADR-0014). Four message types exist in two directions:
 *
 *  - HOST → FRAME (three): `obi:open`, `obi:token`, `obi:clear`. The loader posts these to the
 *    iframe with the exact Obi origin as `targetOrigin` (never `"*"`); the frame's bridge accepts
 *    them only from `window.parent` and only when `event.origin` is an allowed host origin.
 *  - FRAME → HOST (one): `obi:hidden` (sync-rules Task 5, authorized by ADR-0022). The frame posts
 *    it after the server-authoritative `GET /chat/visibility` probe reports `visible:false`
 *    (source-enablement hide, ADR-0023); the loader accepts it only from its own iframe's `contentWindow`
 *    and the exact Obi origin, then `destroy()`s the widget.
 *
 * The token lives only in memory on both sides — never a cookie, localStorage, sessionStorage, or
 * the URL. The two directions are kept separate on purpose: each side validates incoming messages
 * against ONLY the set it should ever receive (`OBI_HOST_TO_FRAME_TYPES` on the frame,
 * `OBI_HIDDEN_MESSAGE_TYPE` on the host), so neither direction's string widens the other's gate.
 */

/** Host page → frame: the user opened the widget (button click). Carries no data. */
export interface ObiOpenMessage {
  type: "obi:open";
}

/** Host page → frame: hand the frame a freshly-fetched platform-signed JWT. */
export interface ObiTokenMessage {
  type: "obi:token";
  /** The raw JWT. Sent by the frame as `Authorization: Bearer <token>` on every chat POST. */
  token: string;
}

/** Host page → frame: forget the current token and clear the conversation (logout / session end). */
export interface ObiClearMessage {
  type: "obi:clear";
}

/**
 * Frame → host: the server-authoritative visibility probe (`GET /chat/visibility`) reported
 * `visible:false` for the verified context — the directed token's source system is not
 * supported (ADR-0023; the message itself was authorized by ADR-0022). Carries no data. The loader `destroy()`s
 * the widget on receipt, accepting it ONLY from its own iframe's `contentWindow` and the exact Obi
 * origin. A hard failure of the probe (400/401/429/503) is NEVER turned into this message — the
 * widget stays mounted — so an outage can't blank the widget for everyone.
 */
export interface ObiHiddenMessage {
  type: "obi:hidden";
}

/** The complete, closed set of messages Obi passes across the iframe boundary (both directions). */
export type ObiMessage = ObiOpenMessage | ObiTokenMessage | ObiClearMessage | ObiHiddenMessage;

/** The three HOST → FRAME literal type strings — the ONLY set the frame's bridge accepts as
 * incoming. `obi:hidden` is deliberately absent: it travels the other way and is validated by the
 * loader against `OBI_HIDDEN_MESSAGE_TYPE`, so it can never slip through the frame's gate. */
export const OBI_MESSAGE_TYPES = ["obi:open", "obi:token", "obi:clear"] as const;
export type ObiMessageType = (typeof OBI_MESSAGE_TYPES)[number];

/** The single FRAME → HOST literal type string — the ONLY message the loader accepts from the
 * iframe (sync-rules Task 5, ADR-0022). */
export const OBI_HIDDEN_MESSAGE_TYPE = "obi:hidden" as const;
