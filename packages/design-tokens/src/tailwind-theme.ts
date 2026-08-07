/**
 * Maps semantic design tokens into a Tailwind theme extension.
 *
 * `apps/web` imports `tailwindTheme` and spreads it into the `theme.extend`
 * block of its Tailwind config, so Tailwind utilities (bg-surface, text-text,
 * rounded-md, p-md, ...) resolve to the token values in `tokens.ts`.
 */

import { color, spacing, radius, font } from "./tokens";

export const tailwindTheme = {
  colors: {
    surface: color.surface,
    "surface-raised": color.surfaceRaised,
    text: color.text,
    "text-muted": color.textMuted,
    accent: color.accent,
    "accent-contrast": color.accentContrast,
    border: color.border,
  },
  spacing: {
    none: spacing.none,
    xs: spacing.xs,
    sm: spacing.sm,
    md: spacing.md,
    lg: spacing.lg,
    xl: spacing.xl,
    "2xl": spacing["2xl"],
  },
  borderRadius: {
    none: radius.none,
    sm: radius.sm,
    md: radius.md,
    lg: radius.lg,
    full: radius.full,
  },
  fontFamily: {
    sans: font.sans,
    mono: font.mono,
  },
} as const;

export type TailwindTheme = typeof tailwindTheme;
