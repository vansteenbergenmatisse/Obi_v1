/**
 * postMessage contract between the Obi loader (`obi.js`, running in the host page) and the Obi
 * `/embed` iframe frame (PLAN 11.1c, ADR-0014). Exactly THREE message types exist — no others.
 *
 * The loader posts these to the iframe with the exact Obi origin as `targetOrigin` (never `"*"`);
 * the frame's bridge accepts them only from `window.parent` and only when `event.origin` is an
 * allowed host origin. The token lives only in memory on both sides — never a cookie, localStorage,
 * sessionStorage, or the URL.
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

/** The complete, closed set of messages Obi passes across the iframe boundary. */
export type ObiMessage = ObiOpenMessage | ObiTokenMessage | ObiClearMessage;

/** The three literal message-type strings, for exhaustive runtime checks on both sides. */
export const OBI_MESSAGE_TYPES = ["obi:open", "obi:token", "obi:clear"] as const;
export type ObiMessageType = (typeof OBI_MESSAGE_TYPES)[number];
