/**
 * Semantic design tokens for Omniboost RAG.
 *
 * These are DESIGN DECISIONS expressed as values, with no markup and no
 * product knowledge. Everything downstream (Tailwind theme, components) reads
 * from here so a single change propagates everywhere.
 *
 * Palette is intentionally neutral for Phase 1. Brand tokens are out of scope
 * for this task; when the Omniboost brand is applied, only the values below
 * change, not their names.
 */

export const color = {
  /** Page / app background. */
  surface: "#0b0d10",
  /** Raised panels, cards, message bubbles. */
  surfaceRaised: "#15181d",
  /** Primary readable text on surfaces. */
  text: "#e8eaed",
  /** Secondary / muted text. */
  textMuted: "#9aa0a6",
  /** Interactive accent (links, focus, primary actions). */
  accent: "#4f8cff",
  /** Text/icon color that reads on top of the accent. */
  accentContrast: "#0b0d10",
  /** Hairline borders and dividers. */
  border: "#262b31",
} as const;

/** 4px base spacing scale. Keys are the design step, values are CSS lengths. */
export const spacing = {
  none: "0",
  xs: "0.25rem", // 4px
  sm: "0.5rem", // 8px
  md: "1rem", // 16px
  lg: "1.5rem", // 24px
  xl: "2rem", // 32px
  "2xl": "3rem", // 48px
} as const;

/** Corner radii. */
export const radius = {
  none: "0",
  sm: "0.25rem",
  md: "0.5rem",
  lg: "0.75rem",
  full: "9999px",
} as const;

/** Font families. */
export const font = {
  sans: "ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
  mono: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace",
} as const;

/** Aggregate token object, convenient for a single import. */
export const tokens = { color, spacing, radius, font } as const;

export type Tokens = typeof tokens;
