# Obi widget — frontend design (apps/web)

> Scope: the floating chat widget UI only (`apps/web/src/features/chat`), not the backend
> retrieval/answer pipeline — that's [`DESIGN.md`](./DESIGN.md). This doc distills the pixel-exact
> spec that `docs/rag/PLAN.md`'s Phase 4.7 already shipped (✅ done, 2026-08-11, commits `206baab` →
> `9d7c0bf`/uncommitted 4.7.4 work) into one standalone reference, and adds two **new, not-yet-built**
> pieces raised in this session: a real image/screenshot attachment, and a dev-only placeholder
> backdrop. Source of visual truth for everything already built: `docs/rag/reference/obi-mockup/`
> (`obi-render.html` is a live, clickable copy of the original mockup).

---

## 1. Component map (as-built)

All in `apps/web/src/features/chat/ui/`, none promoted to `apps/web/src/components/` yet (each has
exactly one consumer today):

| Component | Role |
|---|---|
| `chat-session-provider.tsx` | Shared conversation state machine (D0) — mounted once in `app/layout.tsx`; `ChatPanel` and `ChatWidget` read the same live session. |
| `chat-panel.tsx` | Full-page `/chat` route root — renders `panel-body` in its "page" variant. |
| `chat-widget.tsx` | Floating widget root — `ChatLauncher` + conditional `TeaserPopup` while closed, `FloatingFrame` wrapping `panel-body` in its "widget" variant while open. |
| `use-widget-visibility.ts` | Launcher/teaser timing state machine — teaser at 3000ms after mount if closed, repeats 20000ms after each close. |
| `chat-launcher.tsx` | Closed-state circular launcher button. |
| `teaser-popup.tsx` | Proactive nudge card above the launcher. |
| `floating-frame.tsx` | Widget's open-state chrome — fixed-position overlay pinned to the right edge (not a flex sibling — see §4.1). |
| `panel-body.tsx` | Composition root shared by `ChatPanel`/`ChatWidget`: `panel-header` + `message-list` + `composer`. |
| `panel-header.tsx` | Chrome bar — mark/name + "···"/language/close icon row; owns mutually-exclusive menu state; wires restart. |
| `menu.tsx` / `menu-item.tsx` | Shared dropdown shell for both header menus. |
| `language-menu.tsx` | Six-locale stub menu. |
| `message-list.tsx` / `message-bubble.tsx` | Thread rendering. |
| `typing-indicator.tsx` | Waiting-for-first-token state. |
| `composer.tsx` | Message input + send + (stub) attach. |
| `icon-button.tsx` / `assistant-mark.tsx` | Shared primitives (icon-button is the top promotion candidate the day a second feature needs one). |

Public root: `apps/web/src/features/chat/index.ts` exports `ChatPanel`, `ChatWidget`,
`ChatSessionProvider`, and the view-model types. Nothing else imports `ui/**` directly.

---

## 2. Design tokens (as-built, `packages/design-tokens/src/tokens.ts`)

| Group | Values |
|---|---|
| `color` | `surface #f6f8fa`, `surfaceRaised #ffffff`, `surfaceSunken #f0f1f5`, `text #30313d`, `textMuted #687385`, `accent #635bff`, `accentHover #4f47e6`, `accentSecondary #8f8af7`, `accentContrast #ffffff`, `border #e6e8ee`, `success #1f7a45` / `successBg #e6f6ee` / `successBg-selected #d3f0df`, `danger #df1b41` / `dangerBg #fdf2f4` / `dangerBg-selected #fbdde4` |
| `shadow` | `sm`, `md`, `lg` (plus one-off compound shadows kept as inline arbitrary values where the mockup's shadow doesn't match the scale — launcher, composer border-glow) |
| `zIndex` | `widget`, `widgetMenu` |
| `motion` | `fast`, `base`, `slow`, `easing` |
| Font | Inter via `next/font/google`, wired app-wide in `app/layout.tsx` |

`radius`/`spacing` tokens predate this phase and are reused as-is — no new scale needed.

## 3. Motion catalogue (`apps/web/src/app/globals.css` `@keyframes`, every one has a `motion-reduce:` fallback)

| Keyframe | Used by | Timing |
|---|---|---|
| `menu-in` | "···"/language menu open, user-message-bubble entrance | 180ms ease-out |
| `feedback-pop` | Thumbs up/down selected state | 350ms ease |
| `typing-shimmer` | Typing-indicator label gradient sweep | — |
| `typing-spin` | Typing-indicator icon (`scale`+`rotate`, `0%,100%→50%: scale(1.18) rotate(90deg) opacity .75`) | 1.4s ease-in-out infinite |
| `launcher-pulse` | Launcher ring, only while the teaser is visible | — |
| `teaser-in` | Teaser popup entrance (`translateY(10px) scale(.96) → none`, deliberately springier/bouncier than `menu-in`) | 300ms `cubic-bezier(.2,.9,.3,1.2)` |

No screenshot-flash keyframe exists (previously dropped — see §5, now reopened in §6).

---

## 4. Pixel spec (condensed reference — the full derivation is in `PLAN.md`'s Phase 4.7 section)

### 4.1 Panel frame

Fixed-position overlay (not the mockup's flex-sibling layout — this app's pages don't resize for
the panel): pinned right edge, full height, `width: clamp(360px, 29%, 440px)`, `bg-surface-raised`,
`border-l border-border`, shadow `-4px 0 16px rgba(35,38,59,0.04)`.

### 4.2 Header (52px)

Flex row, `gap-sm` (10px), `padding 0 14px 0 16px`, `border-b border-border`, `bg-surface-raised`,
`z-index: widget`. `AssistantMark` 20px + name (15px/600). Icon row `margin-left: auto`, `gap` 2px:
**More (⋯)**, **Language**, **Close** — each a 30×30 `IconButton`. No screenshot icon in the header
(that affordance lives in the composer toolbar, see §6).

### 4.3 Menus

Invisible full-viewport overlay closes on outside click; both menus mutually exclusive. Panel:
`absolute top-[46px] right-11`, `z-index: widget-menu`, `bg-surface-raised`, `border border-border`,
`rounded-lg`, `shadow-md`, `min-width` 200px ("···") / 190px (language), `py-1.5`, `menu-in 180ms
ease-out`. "···" items 13.5px `px-4 py-2.5`: "Developer docs"/"Support articles" (disabled stubs),
"Restart conversation" (`color.danger`, real, wired to `useChatSession().restart()`). Language items
13.5px, `justify-between gap-4`, weight 600 if active else 400, checkmark 14px `stroke-accent`.

### 4.4 Message thread

`flex-1 overflow-y-auto`, `padding 16px 16px 12px`, `flex flex-col gap-md`. Greeting (once, no
personalization): *"Hi there, how can I help you with Omniboost? The more details you provide, the
better."* No suggestion chip (dropped). User bubble: right-aligned, `bg-surface-sunken`, 14px,
`px-[15px] py-[9px]`, `rounded-2xl`-ish, `max-w-[82%]`, `menu-in` entrance. Bot message: no bubble
fill, 14px/1.6, `max-w-[96%]`, feedback row below (26×26 thumbs, `feedback-pop` on select).

### 4.5 Typing indicator

Flex row `gap-[9px]`, 17px `AssistantMark` on `typing-spin`, shimmering label (13.5px/500,
`typing-shimmer`), ~90-word whimsical bank (Thinking, Pondering, Mulling, …), cycles every 3800ms,
stops the instant real content arrives.

### 4.6 Composer

Outer box: `border border-[#8d8bfa]`, `rounded-xl`, `bg-surface-raised`, `p-[12px_12px_8px]`,
`flex flex-col gap-1`, shadow `0 1px 4px rgba(99,91,255,0.06)`. Textarea: 2 rows visible,
autosizing, borderless/transparent, 14px/1.5, `min-h-[42px]`, placeholder *"Ask about your
Confluence workspace…"*. Toolbar `justify-end items-center gap-[10px]`: **Attach** (28×28, disabled
stub today — see §6), **Send** (30×30 circle, `bg-accent` when non-empty, `bg-surface-sunken` when
empty — a distinct grey fill, not `disabled:opacity-50`), hover `scale-105`-ish. Footer disclaimer,
centered, 12px: *"AI may make mistakes. Verify important information."*

### 4.7 Launcher (closed) / teaser popup

Launcher: `fixed bottom-6 right-6`, 52×52 circle, `border border-border`, `bg-surface-raised`,
shadow `0 6px 20px rgba(35,38,59,0.16)`, `AssistantMark` 24px centered, hover `scale-[1.06]`, pulses
(`launcher-pulse`) only while the teaser is visible. Teaser: `fixed bottom-[92px] right-6`,
`z-index: widget-menu`, `rounded-2xl`-ish, `shadow-lg`, `p-[14px_16px]`, `max-w-[290px]`, dismiss (×)
top-right, `teaser-in` entrance. Timing: 3000ms after mount if closed; 20000ms after each close.

---

## 5. Product decisions already locked (Phase 4.7, historical — §6 partially revises the first one)

- Mockup's exact visuals are the real Omniboost brand tokens now, app-wide, not widget-scoped.
- The floating widget is the primary surface; the full-page `/chat` route stays working but gets no
  further design investment.
- ~~Screenshot capture: dropped entirely.~~ **Reopened this session — see §6.**
- File attachment: shipped as an honest disabled stub — **also reopened, same feature as §6.**
- Language switcher: stub, no real translation. "Developer docs"/"Support articles": disabled
  stubs until real URLs exist. "Restart conversation": real.
- Assistant display name "Obi" is the mockup's placeholder, not a confirmed product decision.

---

## 6. NEW — image / screenshot attachment (this session, not yet built)

**Ask, as given:** users should be able to attach/screenshot an image; it previews above the
composer's input, at the bottom of the panel, "properly" — not a dead stub.

This directly reopens two Phase 4.7 decisions (§5): screenshot capture was dropped and file
attachment shipped as a non-functional disabled stub, both because **no backend capability exists
to receive an image** — `AnswerService`/`POST /chat` are text-in/text-out only (confirmed in
`DESIGN.md` §1/§2 and already flagged as unscoped future work in
`docs/future-ideas/IDEAS.md` idea #3, "Screenshot-grounded guidance," which explicitly calls out
privacy/consent review and a vision-capable model as prerequisites). That gap is still real — this
section proposes two ways to close the UI/UX half of it now, and is explicit about what each does
and doesn't unlock.

### 6.1 Shared UI shape (either option)

- `Composer` gains local `attachments` state: an array of `{ id, file, previewUrl }`.
- **Capture sources:** file-picker (existing paperclip button, un-stubbed) **and** clipboard-paste
  of an image (`onPaste`, reads `event.clipboardData.items`) — the paste path is what actually
  covers "screenshot" (a screenshot lands on the OS clipboard; there is no in-browser "take a
  screenshot of this tab" API without the user's explicit screen-share permission grant, which is a
  much heavier, more sensitive flow than pasting one already-taken screenshot — recommend starting
  with paste + file-picker, not a `getDisplayMedia()` capture button).
- **Preview strip:** rendered *inside* the composer's outer box, above the textarea (so it sits at
  the bottom of the panel, per the ask) — a row of 40×40 rounded thumbnails (`object-cover`), each
  with a small (×) remove button top-right, `gap-1.5`. Entrance reuses `menu-in`. Appears only when
  `attachments.length > 0`; adds `gap-1.5` to the composer's existing `flex flex-col gap-1`.
- **Send button state:** disabled while `value` is empty **and** no attachments (today it's just
  `value.trim().length > 0`) — an image-only send should be allowed to reach the client-side
  `attachments` array even before a backend exists to answer it, see 6.2/6.3.
- A single new component, `attachment-strip.tsx`, colocated in `features/chat/ui/` next to
  `composer.tsx` (its only consumer) — not promoted to `components/`.

### 6.2 Option A — client-side only, ships now, no backend change (recommended starting point)

Attach + preview + remove all work for real. On send, if attachments are present, the message goes
out as **text only** (attachments dropped) and the composer shows a small inline notice near the
attachment strip: *"Image attachments aren't answered yet — sent as text only."* This is honest
about the real capability (matches this repo's existing pattern for the language-switcher and
"Developer docs" stubs — visible and real where it can be, explicit about the gap where it can't),
ships entirely inside `apps/web`, and needs no new endpoint, no vision model, no security review.

### 6.3 Option B — real vision-grounded feature (its own backend phase, not a UI pass)

The image is actually sent and actually answered against. This requires, in `apps/automation`:
a new field on the `POST /chat` contract (base64 or a pre-signed upload + reference), a
vision-capable model call in `rag_agent`, a decision on whether/how a screenshot participates in
retrieval grounding at all (per IDEAS.md #3: "ground the screenshot against known UI states/docs
rather than freeform description" is explicitly unsolved), and — because this is now a genuinely
new user-input-to-LLM surface — a pass under `securing-http-and-llm-endpoints` (upload size caps,
content-type validation, PII/screenshot-privacy handling, cost/abuse caps) before it ships. This is
plan-scale work (its own numbered phase in `PLAN.md`, its own acceptance criteria), not something
to build ad hoc alongside a widget UI pass — consistent with how every other backend capability in
this repo got built.

**Resolved with the user (2026-08-11): 6.2.** Shipped — `attachment-strip.tsx` (new component) +
`composer.tsx` changes: file-picker and clipboard-paste both add images (capped at 4, `image/*`
only), 40×40 thumbnail previews with a remove button render above the textarea, Send is enabled
with an attachment alone, and on send any attachments are cleared with a 4s inline notice
("Image attachments aren't answered yet — sent as text only.") while text (if any) still goes
through. Client-side only, no `apps/automation` change. 6.3 (the real vision-grounded pipeline)
stays exactly as scoped above — a future `PLAN.md` phase promoted out of `IDEAS.md` #3, not built
now.

---

## 7. NEW — dev-only placeholder backdrop (this session, not yet built)

**Ask, as given:** a placeholder "host page" to the left of the widget, for visual context (mirrors
the mockup's own fake Stripe dashboard sitting beside the panel) — one component, not a real
feature, safe to delete later.

**Proposed shape:** one file, `apps/web/src/app/dev-preview-backdrop.tsx` — a purely decorative,
static block (a few skeleton cards/rows, `bg-surface`/`border-border` tokens, no state, no data, no
behavior) rendered on the homepage (`app/page.tsx`) only, replacing today's centered
"Omniboost RAG" copy while this is in use, or rendered alongside it. Per the architecture standard,
this is correctly a route-owned, used-once block that lives beside its route — **not** a feature (it
owns no behavior/rules/state) and **not** promoted to `components/` (one consumer). A one-line
comment marks it as a temporary visual aid, e.g.:

```tsx
// Dev-only visual backdrop so the floating widget previews in context, not on a blank page.
// Safe to delete — no behavior, no data, not part of the product.
```

**Resolved with the user (2026-08-11): homepage.** Shipped — `dev-preview-backdrop.tsx`, rendered by
`app/page.tsx`, replacing the old bare hero. A pre-existing, unrelated bug surfaced while building
this: this repo's named `max-w-*` scale resolves against the `spacing` token scale, not Tailwind's
default (`max-w-md` computed to `16px`, not `28rem`) — already worked around everywhere else in the
widget with bracket values (e.g. `message-bubble.tsx`'s `max-w-[82%]`); fixed the homepage's one
occurrence the same way (`max-w-[28rem]`). The underlying scale mismatch is not fixed globally —
flagging it here, not silently expanding this task into a config audit.

---

## 8. Status

Everything in §1-7 is **built and shipped**. §6 shipped as 6.2 (client-side attach/preview/paste,
no backend change); 6.3 (real vision-grounded pipeline) remains future, unscoped work per
`IDEAS.md` #3. §7 shipped on the homepage. Verified: `pnpm --filter web test` — 113 passed (was
106); `tsc --noEmit` clean; `pnpm --filter web build` clean; live-browser-verified (teaser/launcher
in context on the homepage backdrop, file-picker attach + thumbnail preview + remove + send-drops-
with-notice all confirmed against the real running widget, zero console errors).
