/**
 * ChatPanel — the chat feature's root UI and public surface.
 *
 * This is what routes render. It composes `PanelBody` in its "page" variant (PLAN 4.7.3) —
 * everything below it is internal to the feature; only this component is re-exported from the
 * feature root. Reads the ambient `ChatSessionProvider` mounted once in `app/layout.tsx`
 * (PLAN 4.7.4, architecture decision D0) rather than mounting its own, so this page and the
 * floating `ChatWidget` always share one live conversation instead of running two independent,
 * contradictory ones.
 */
"use client";

import { PanelBody } from "./panel-body";

export function ChatPanel() {
  return <PanelBody variant="page" />;
}
