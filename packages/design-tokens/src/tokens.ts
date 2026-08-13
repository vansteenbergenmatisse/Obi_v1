/**
 * Semantic design tokens for Omniboost RAG.
 *
 * These are DESIGN DECISIONS expressed as values, with no markup and no
 * product knowledge. Everything downstream (Tailwind theme, components) reads
 * from here so a single change propagates everywhere.
 *
 * Palette matches the Obi widget (Phase 4.7's source of design truth,
 * `/Users/matissevansteenbergen/Downloads/Obi chatbot UI mockups/`): a light,
 * Stripe-esque theme with an indigo accent and Inter typography.
 */

export const color = {
  /** Page / app background. */
  surface: "#f6f8fa",
  /** Raised panels, cards, headers. */
  surfaceRaised: "#ffffff",
  /** Sunken fill distinct from a raised card — e.g. the user's own message bubble, hover fills. */
  surfaceSunken: "#f0f1f5",
  /** Primary readable text on surfaces. */
  text: "#30313d",
  /** Secondary / muted text. */
  textMuted: "#687385",
  /** Interactive accent (links, focus, primary actions). */
  accent: "#635bff",
  /** Accent on hover/press. */
  accentHover: "#4f47e6",
  /** Secondary accent — paired with `accent` in two-tone marks/icons. */
  accentSecondary: "#8f8af7",
  /** Text/icon color that reads on top of the accent. */
  accentContrast: "#ffffff",
  /** Fill behind an open/inviting accent state (e.g. a clarification prompt) — never a failure. */
  accentBg: "#f6f6ff",
  /** Hairline borders and dividers. */
  border: "#e6e8ee",
  /** Positive feedback (e.g. a selected "helpful" thumbs-up). */
  success: "#1f7a45",
  /** Fill behind a selected positive-feedback control. */
  successBg: "#e6f6ee",
  /** Fill behind a selected positive-feedback control once it's the active/pressed state. */
  successFill: "#d3f0df",
  /** Negative/destructive actions (e.g. a selected "not helpful" thumbs-down, restart). */
  danger: "#df1b41",
  /** Fill behind a selected negative-feedback control. */
  dangerBg: "#fdf2f4",
  /** Fill behind a selected negative-feedback control once it's the active/pressed state. */
  dangerFill: "#fbdde4",
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

/** Elevation shadows — panels, dropdown menus, the floating launcher/teaser. */
export const shadow = {
  sm: "0 1px 4px rgba(35, 38, 59, 0.06)",
  md: "0 8px 24px rgba(35, 38, 59, 0.12)",
  lg: "0 12px 32px rgba(35, 38, 59, 0.18)",
} as const;

/** Stacking order for the floating chat widget, above ordinary page content. */
export const zIndex = {
  widget: "40",
  widgetMenu: "50",
} as const;

/** Motion durations/easing for the widget's transitions and keyframes (see `globals.css`). */
export const motion = {
  fast: "120ms",
  base: "180ms",
  slow: "300ms",
  easing: "cubic-bezier(0.16, 1, 0.3, 1)",
} as const;

/** Font families. */
export const font = {
  sans: "var(--font-sans), Inter, ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
  mono: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace",
} as const;

/** Aggregate token object, convenient for a single import. */
export const tokens = { color, spacing, radius, font, shadow, zIndex, motion } as const;

export type Tokens = typeof tokens;
