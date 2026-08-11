# Obi widget mockup — design-fidelity reference (Phase 4.7)

Not app code. Not linted, not tested, not deployed. A frozen copy of the user-supplied UI mockup
that Phase 4.7 (`docs/rag/PLAN.md`) rebuilds, kept here so it survives independently of the original
`~/Downloads/Obi chatbot UI mockups/` folder and so a fresh session (after `/compact-ultra` or a
context clear) can re-render and interact with the *real* mockup instead of trusting prose alone.

## Files

- `Obi Assistant.dc.html` + `support.js` — the original mockup, byte-for-byte as supplied. This is a
  proprietary prototyping-tool export: `support.js` is a small custom runtime that expects
  `window.React`/`window.ReactDOM` to already be injected by the tool's own preview iframe, so
  opening `Obi Assistant.dc.html` directly in a plain browser throws
  `dc-runtime: window.React is not available yet` — it does **not** render standalone.
- `obi-render.html` — the same mockup with two `<script>` tags added (React 18 + ReactDOM 18 UMD from
  a CDN) immediately before the `support.js` tag, nothing else changed. This *does* render and is
  fully interactive standalone. **Needs internet access** (loads React/ReactDOM from `unpkg.com`,
  and `support.js` itself dynamically loads `@babel/standalone` from `unpkg.com` to transpile the
  mockup's inline component script at runtime).
- `uploads/*.png` — the three screenshots the user originally supplied alongside the mockup.

## How to open it

```
cd docs/rag/reference/obi-mockup
python3 -m http.server 8901
# then open http://localhost:8901/obi-render.html in a browser
```

Click the circular launcher (bottom-right) to open the panel. It's the full interactive prototype —
menus, language switcher, canned keyword-matched replies, feedback thumbs, restart, teaser popup
(appears ~3s after load if the panel is closed) all work exactly as designed.

## What it is / isn't

It sits behind a fake Stripe-style "Payments" dashboard backdrop — **irrelevant, ignore it**; only
the widget (launcher → teaser → panel) matters. Its "AI" replies are hardcoded keyword-matched
strings with a randomized delay, not a real backend — only the UI shapes carry over. See
`docs/rag/PLAN.md`'s Phase 4.7 section (particularly the "Design specification" subsection) for the
exhaustive pixel-level spec extracted from this mockup, and for which parts of it are being dropped,
stubbed, or built real in the actual rebuild.
