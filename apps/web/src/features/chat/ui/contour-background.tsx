/**
 * ContourBackground — the message thread's ambient wavy-line decoration (a pixel-exact copy of
 * the original Obi mockup's body SVG, `stroke: #edeff6`; the mockup was reference art and has been
 * removed — the as-built widget doc is `docs/rag/OBI-WIDGET-DESIGN.md`).
 *
 * Pure decoration, no state, no behavior — feature-internal, used once by `panel-body.tsx`.
 * `pointer-events: none` so it never intercepts clicks/scroll from the message list above it.
 */
export function ContourBackground() {
  return (
    <svg
      viewBox="0 0 430 900"
      preserveAspectRatio="xMidYMin slice"
      className="pointer-events-none absolute inset-0 h-full w-full"
      fill="none"
      stroke="#edeff6"
      strokeWidth={1}
      aria-hidden="true"
    >
      <path d="M-10 30 C 70 8, 150 52, 230 28 S 380 6, 440 34" />
      <path d="M-10 78 C 90 52, 170 104, 260 74 S 390 50, 440 82" />
      <path d="M-10 128 C 60 102, 160 152, 250 124 S 400 98, 440 130" />
      <path d="M-10 180 C 100 152, 180 206, 270 176 S 390 150, 440 184" />
      <path d="M-10 234 C 70 206, 170 258, 260 228 S 400 202, 440 236" />
      <path d="M-10 290 C 90 262, 180 314, 270 284 S 390 258, 440 292" />
      <path d="M-10 348 C 60 320, 160 372, 250 342 S 400 316, 440 350" />
      <path d="M-10 408 C 100 380, 190 432, 280 402 S 390 376, 440 410" />
      <path d="M-10 470 C 70 442, 170 494, 260 464 S 400 438, 440 472" />
      <path d="M-10 534 C 90 506, 180 558, 270 528 S 390 502, 440 536" />
      <path d="M-10 600 C 60 572, 160 624, 250 594 S 400 568, 440 602" />
      <path d="M-10 668 C 100 640, 190 692, 280 662 S 390 636, 440 670" />
      <path d="M-10 738 C 70 710, 170 762, 260 732 S 400 706, 440 740" />
      <path d="M-10 810 C 90 782, 180 834, 270 804 S 390 778, 440 812" />
    </svg>
  );
}
