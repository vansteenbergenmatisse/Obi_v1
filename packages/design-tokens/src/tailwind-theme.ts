/**
 * Maps semantic design tokens into a Tailwind theme extension.
 *
 * `frontend` imports `tailwindTheme` and spreads it into the `theme.extend`
 * block of its Tailwind config, so Tailwind utilities (bg-surface, text-text,
 * rounded-md, p-md, ...) resolve to the token values in `tokens.ts`.
 */

import { color, spacing, radius, font, shadow, zIndex, motion } from "./tokens";

export const tailwindTheme = {
  colors: {
    surface: color.surface,
    "surface-raised": color.surfaceRaised,
    "surface-sunken": color.surfaceSunken,
    text: color.text,
    "text-muted": color.textMuted,
    accent: color.accent,
    "accent-hover": color.accentHover,
    "accent-secondary": color.accentSecondary,
    "accent-contrast": color.accentContrast,
    "accent-bg": color.accentBg,
    border: color.border,
    success: color.success,
    "success-bg": color.successBg,
    "success-fill": color.successFill,
    danger: color.danger,
    "danger-bg": color.dangerBg,
    "danger-fill": color.dangerFill,
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
  boxShadow: {
    sm: shadow.sm,
    md: shadow.md,
    lg: shadow.lg,
  },
  zIndex: {
    widget: zIndex.widget,
    "widget-menu": zIndex.widgetMenu,
  },
  transitionDuration: {
    fast: motion.fast,
    base: motion.base,
    slow: motion.slow,
  },
  transitionTimingFunction: {
    widget: motion.easing,
  },
} as const;

export type TailwindTheme = typeof tailwindTheme;
