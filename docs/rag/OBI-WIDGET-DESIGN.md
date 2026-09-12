# Obi widget — frontend design (apps/web)

> Scope: the floating chat widget UI only (`apps/web/src/features/chat`), not the backend
> retrieval/answer pipeline — that's [`DESIGN.md`](./DESIGN.md). This is the standalone as-built
> reference for the widget, kept in sync with the code (not a session-by-session log — that
> history lives in git and in `PLAN.md`'s own commit trail if it's ever needed). Rewritten
> 2026-08-11 to reflect the widget after it became the app's only chat surface. It was originally
> built from a proprietary Obi mockup export (reference art only, removed 2026-09-12); this document
> is now the as-built source of truth for the widget.

---

## 1. Component map (as-built)

All in `apps/web/src/features/chat/ui/`, none promoted to `apps/web/src/components/` yet (each has
exactly one consumer today):

| Component | Role |
|---|---|
| `chat-session-provider.tsx` | Conversation state machine + the widget's UI-copy `locale` — mounted once in `app/layout.tsx`. |
| `chat-widget.tsx` | The feature's only UI export — `ChatLauncher` + conditional `TeaserPopup` while closed, `FloatingFrame` wrapping `panel-body` while open. |
| `use-widget-visibility.ts` | Launcher/teaser timing state machine — teaser at 3000ms after mount if closed, repeats 20000ms after each close. |
| `chat-launcher.tsx` | Closed-state circular launcher button. Locale-aware title. |
| `teaser-popup.tsx` | Proactive nudge card above the launcher. Locale-aware copy. |
| `floating-frame.tsx` | Widget's open-state chrome — fixed-position overlay pinned to the right edge (not a flex sibling — see §4.1). Carries `data-obi-widget-root` so the screenshot capture (§6) can hide it during its own capture. |
| `panel-body.tsx` | Composition root: `panel-header` + `contour-background` + `message-list` + `composer`. Owns the screenshot-capture handler and the capture flash overlay. |
| `panel-header.tsx` | Chrome bar — mark/name + "···"/screenshot/language/close icon row; owns mutually-exclusive menu state; wires restart. Locale-aware labels. |
| `menu.tsx` / `menu-item.tsx` | Shared dropdown shell for both header menus. |
| `language-menu.tsx` | Real six-locale switcher — calls `useChatSession().setLocale`. |
| `contour-background.tsx` | Ambient wavy-line SVG behind the message thread. Pure decoration. |
| `message-list.tsx` / `message-bubble.tsx` | Thread rendering — greeting, empty-state suggestion chip, per-turn bubbles/citations/feedback. Locale-aware greeting/chip. |
| `typing-indicator.tsx` | Waiting-for-first-token state. |
| `composer.tsx` | Message input + send + image attachments (file-picker + clipboard-paste + screenshot, one pipeline). `forwardRef` exposing `ComposerHandle.addAttachmentFile` for the header's screenshot button. Locale-aware placeholder/footer/notice. |
| `attachment-strip.tsx` | 40×40 thumbnail preview row for composer attachments; clicking a thumbnail opens `image-lightbox.tsx`. |
| `image-lightbox.tsx` | Full-size zoomed preview overlay for a clicked attachment/screenshot thumbnail (PLAN 4.7.8) — local preview only, no analysis. |
| `icon-button.tsx` / `assistant-mark.tsx` | Shared primitives (icon-button is the top promotion candidate the day a second feature needs one). |

`../model/i18n.ts` — the widget's own six-locale UI-copy table (greeting, chip, placeholder,
footer, attachment notice, teaser, header labels). Does not translate the RAG agent's actual
answers — see §5.

Public root: `apps/web/src/features/chat/index.ts` exports `ChatWidget` and `ChatSessionProvider`
only, plus the view-model types. Nothing else imports `ui/**` directly. There is no `ChatPanel` and
no full-page `/chat` route — both were removed once the widget covered everything they did; the
widget (launcher/teaser click) is the only way to reach the conversation.

---

## 2. Design tokens (as-built, `packages/design-tokens/src/tokens.ts`)

| Group | Values |
|---|---|
| `color` | `surface #f6f8fa`, `surfaceRaised #ffffff`, `surfaceSunken #f0f1f5`, `text #30313d`, `textMuted #687385`, `accent #635bff`, `accentHover #4f47e6`, `accentSecondary #8f8af7`, `accentContrast #ffffff`, `border #e6e8ee`, `success #1f7a45` / `successBg #e6f6ee` / `successBg-selected #d3f0df`, `danger #df1b41` / `dangerBg #fdf2f4` / `dangerBg-selected #fbdde4` |
| `shadow` | `sm`, `md`, `lg` (plus one-off compound shadows kept as inline arbitrary values where the mockup's shadow doesn't match the scale — launcher, composer border-glow) |
| `zIndex` | `widget`, `widgetMenu` |
| `motion` | `fast`, `base`, `slow`, `easing` |
| Font | Inter via `next/font/google`, wired app-wide in `app/layout.tsx` |

`radius`/`spacing` tokens predate this phase and are reused as-is — no new scale needed. A few
one-off hex values that don't map cleanly to a token (`#8d8bfa` composer/chip border, `#f6f6ff`
chip hover fill, `#fdfdfe` message-thread background, `#edeff6` contour-line stroke) are kept as
arbitrary Tailwind values rather than forcing a new single-use token — same precedent as the
shadows above.

## 3. Motion catalogue (`apps/web/src/app/globals.css` `@keyframes`, every one has a `motion-reduce:` fallback)

| Keyframe | Used by | Timing |
|---|---|---|
| `menu-in` | "···"/language menu open, user-message-bubble entrance, attachment-strip entrance | 180ms ease-out |
| `feedback-pop` | Thumbs up/down selected state | 350ms ease |
| `typing-shimmer` | Typing-indicator label gradient sweep | — |
| `typing-spin` | Typing-indicator icon (`scale`+`rotate`, `0%,100%→50%: scale(1.18) rotate(90deg) opacity .75`) | 1.4s ease-in-out infinite |
| `launcher-pulse` | Launcher ring, only while the teaser is visible | — |
| `teaser-in` | Teaser popup entrance (`translateY(10px) scale(.96) → none`, deliberately springier/bouncier than `menu-in`) | 300ms `cubic-bezier(.2,.9,.3,1.2)` |
| `screenshot-flash` | Brief white overlay over the panel during a screenshot capture | 550ms ease-out forwards |

---

## 4. Pixel spec (condensed reference — the full derivation is in `PLAN.md`'s Phase 4.7 section)

### 4.1 Panel frame

Fixed-position overlay (not the mockup's flex-sibling layout — this app's pages don't resize for
the panel): pinned right edge, full height, `width: clamp(360px, 29%, 440px)`, `bg-surface-raised`,
`border-l border-border`, shadow `-4px 0 16px rgba(35,38,59,0.04)`. Its root carries
`data-obi-widget-root` (§6). Its only child, `panel-body.tsx`'s root `<section>`, is `h-full` — this
matters: the message thread below is `flex-1`, and without a definite height on this ancestor chain
`flex-1` has nothing real to grow into (see the bug note in §8).

### 4.2 Header (52px)

Flex row, `gap-sm` (10px), `padding 0 14px 0 16px`, `border-b border-border`, `bg-surface-raised`,
`z-index: widget`. `AssistantMark` 20px + name (15px/600). Icon row `margin-left: auto`, `gap` 2px,
each a 30×30 `IconButton`: **More (⋯)**, **Screenshot** (camera icon, real capture — see §6),
**Language**, **Close**.

### 4.3 Menus

Invisible full-viewport overlay closes on outside click; both menus mutually exclusive. Panel:
`absolute top-[46px] right-11`, `z-index: widget-menu`, `bg-surface-raised`, `border border-border`,
`rounded-lg`, `shadow-md`, `min-width` 200px ("···") / 190px (language), `py-1.5`, `menu-in 180ms
ease-out`. "···" items 13.5px `px-4 py-2.5`: "Developer docs"/"Support articles" (disabled stubs —
no real target page exists), "Restart conversation" (`color.danger`, real, wired to
`useChatSession().restart()`). Language items 13.5px, `justify-between gap-4`, weight 600 if active
else 400, checkmark 14px `stroke-accent` — **real**: selecting one calls `setLocale` and the check
follows the actual active locale (§5).

### 4.4 Message thread

Wrapper: `relative flex-1 overflow-hidden bg-[#fdfdfe]`, holding the ambient contour-line SVG
(`stroke #edeff6`, `viewBox 0 0 430 900`, `pointer-events-none`, `absolute inset-0`) behind an
`absolute inset-0 overflow-y-auto` scroller (`padding 16px 16px 12px`, `flex flex-col gap-md`).
Greeting (once, no personalization): *"Hi there, how can I help you with Omniboost? The more
details you provide, the better."* Below it in the empty state, a suggestion chip — *"What can you
help me with?"* — `rounded-full border border-[#8d8bfa]`, `px-md py-sm`, hover lift/accent-border/
`#f6f6ff` fill, sends the question through the real session. User bubble: right-aligned,
`bg-surface-sunken`, 14px, `px-[15px] py-[9px]`, `rounded-2xl`-ish, `max-w-[82%]`, `menu-in`
entrance. Bot message: no bubble fill, 14px/1.6, `max-w-[96%]`, feedback row below (26×26 thumbs,
`feedback-pop` on select).

### 4.5 Typing indicator

Flex row `gap-[9px]`, 17px `AssistantMark` on `typing-spin`, shimmering label (13.5px/500,
`typing-shimmer`), ~90-word whimsical bank (Thinking, Pondering, Mulling, …), cycles every 3800ms,
stops the instant real content arrives.

### 4.6 Composer

Outer box: `border border-[#8d8bfa]`, `rounded-xl`, `bg-surface-raised`, `p-[12px_12px_8px]`,
`flex flex-col gap-1`, shadow `0 1px 4px rgba(99,91,255,0.06)`. When attachments exist, a preview
strip (40×40 rounded thumbnails, `object-cover`, small × remove button top-right, `gap-1.5`,
`menu-in` entrance) renders above the textarea. Textarea: 2 rows visible, autosizing, borderless/
transparent, 14px/1.5, `min-h-[42px]`, placeholder *"Ask about your Confluence workspace…"*.
Toolbar `justify-end items-center gap-[10px]`: **Attach image** (28×28, real — opens a file picker;
clipboard-paste of an image works anywhere in the textarea too), **Send** (30×30 circle, `bg-accent`
when non-empty-or-has-attachment, `bg-surface-sunken` when empty — a distinct grey fill, not
`disabled:opacity-50`), hover `scale-105`-ish. Sending with attachments present clears them and
shows a 4s inline notice — *"Image attachments aren't answered yet — sent as text only."* — while
any text still sends normally. Footer disclaimer, centered, 12px: *"AI may make mistakes. Verify
important information."*

### 4.7 Launcher (closed) / teaser popup

Launcher: `fixed bottom-6 right-6`, 52×52 circle, `border border-border`, `bg-surface-raised`,
shadow `0 6px 20px rgba(35,38,59,0.16)`, `AssistantMark` 24px centered, hover `scale-[1.06]`, pulses
(`launcher-pulse`) only while the teaser is visible. Teaser: `fixed bottom-[92px] right-6`,
`z-index: widget-menu`, `rounded-2xl`-ish, `shadow-lg`, `p-[14px_16px]`, `max-w-[290px]`, dismiss (×)
top-right, `teaser-in` entrance. Timing: 3000ms after mount if closed; 20000ms after each close.

---

## 5. Product decisions — current state

| Piece | Status |
|---|---|
| Mockup's exact visuals | Real Omniboost brand tokens, app-wide, not widget-scoped. |
| Only chat surface | The floating widget. The old full-page `/chat` route was removed — it added no value once the widget existed everywhere and duplicated the same conversation. |
| Screenshot capture | **Real** — a real DOM capture (`html-to-image`) of the page behind the widget, landing in the same attachment pipeline as any other image, including the real click-to-zoom below. Only the *analysis* is unbuilt (no vision-capable backend — see §6). |
| File/paste image attachment | **Real** capture, preview, remove, and click-to-zoom (`image-lightbox.tsx`, PLAN 4.7.8). Honest stub on send (dropped as text-only, with a notice) — no vision backend exists yet. |
| Suggestion chip | **Real** — "What can you help me with?" (adapted from the mockup's Stripe-only "My verification status," which had no Confluence equivalent) sent through the real session. |
| Language switcher (6 locales) | **Real for the widget's own UI copy only** — greeting, chip, placeholder, footer, teaser, header labels. Does **not** change what language the RAG agent answers in; that's the model's own behavior against `apps/automation`, unscoped backend work. Translations are direct/unreviewed, same quality bar as the mockup's own six-locale table. |
| "Developer docs"/"Support articles" | Disabled stubs until real URLs exist. |
| "Restart conversation" | Real. |
| Assistant display name "Obi" | Still the mockup's placeholder, not a confirmed product decision. |

---

## 6. Screenshot capture — how it works

Header icon between "More" and "Language" (§4.2). On click, `panel-body.tsx`'s `handleScreenshot`:
hides the widget's own root (found via `[data-obi-widget-root]`, set on `floating-frame.tsx`) so the
capture doesn't include the widget itself, captures `document.body` to a PNG `Blob` via
`html-to-image`'s `toBlob`, wraps it in a `File`, and hands it to the composer through
`ComposerHandle.addAttachmentFile` (the composer is a `forwardRef` for exactly this reason) — from
there it's indistinguishable from a file-picked or pasted image: same thumbnail, same removable
chip, same click-to-zoom preview (`image-lightbox.tsx`, PLAN 4.7.8), same honest "not answered yet"
notice on send. A `screenshot-flash` keyframe briefly whites out the panel during the capture,
mirroring the mockup's own flash.

**Why a real capture instead of the mockup's fake one:** the mockup fakes an instant, canned
"Screenshot: Payments page.png" attach with no actual pixels — asked to build something real
instead. **Why not `getDisplayMedia()`:** that API requires the user to explicitly grant a
screen-share permission and pick a source each time — a much heavier flow than a one-click
affordance; `html-to-image`'s DOM-to-canvas approach needs no permission prompt at all.

**What's still not real:** the analysis half. Nothing reads the captured image yet — same gap as
any other image attachment (§5). A real version needs, in `apps/automation`: a vision-capable model
call, a decision on whether/how a screenshot participates in retrieval grounding at all, and a
`securing-http-and-llm-endpoints` pass (upload caps, content-type validation, PII/privacy handling,
cost/abuse caps) before it ships. **That's `docs/rag/PLAN.md` Phase 7** (scoped 2026-08-11,
superseding `docs/future-ideas/IDEAS.md` #3's original "Screenshot-grounded guidance" framing) —
not UI work, and not started.

---

## 7. Dev-only placeholder backdrop

`apps/web/src/app/dev-preview-backdrop.tsx`, rendered by `app/page.tsx` in place of a bare hero — a
static, stateless skeleton block so the floating widget previews in visual context (mirrors the
mockup's own fake dashboard sitting beside its panel). Route-owned, one consumer, marked "safe to
delete" in its own doc comment; not a feature, not promoted to `components/`.

---

## 8. Known gaps / debt (disclosed, not silently carried)

- **Test suite not re-run** since the contour-background/suggestion-chip pass and the
  screenshot/real-i18n/`/chat`-removal pass — both were verified only by `tsc --noEmit` +
  `pnpm --filter web build`, per explicit instruction to skip the test gate for those two passes.
  `chat-panel.test.tsx` was deleted along with `ChatPanel` — its characterization coverage
  (streaming, citations, refusal, error, feedback, restart, abort-on-unmount) has no replacement.
  `language-menu.test.tsx`, `chat-launcher.test.tsx`, and `message-list.test.tsx` now fail because
  those components read `useChatSession()` (for `locale`) without those tests providing a
  `ChatSessionProvider`. Fix all of this before trusting the widget as done by this repo's normal
  bar (`CLAUDE.local.md` §2).
- **A real layout bug shipped and was only caught live**, not by any test: making the
  message-thread wrapper's children absolutely-positioned (to layer the contour background behind
  the scrollable content) meant they stopped contributing to the wrapper's auto height. Without a
  definite height anywhere up the ancestor chain, the wrapper — and everything inside it — collapsed
  to zero height and was clipped, so only the header and composer were visible, bunched at the top.
  Fixed by giving `panel-body.tsx`'s root section `h-full` (§4.1) so `flex-1` has a real height to
  grow into. Caught by opening the widget in a real browser, not by `tsc`/`build`/any unit test.
- Not committed as of this writing.

## 9. Status

`tsc --noEmit` and `pnpm --filter web build` clean, including the layout fix above. Confirmed live
in a real browser: greeting, suggestion chip, contour background, composer, and footer all render
in the correct order (greeting/chip at top of the thread, composer + footer at the bottom) and are
all visible; screenshot capture attaches a real thumbnail; language menu really switches the
widget's copy across all six locales; no console errors. No automated test run covers this state
end to end — see §8.
