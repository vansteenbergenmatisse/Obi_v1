import type { Config } from "tailwindcss";
import { tailwindTheme } from "@omniboost/design-tokens/tailwind-theme";

/**
 * Tailwind config for apps/web.
 *
 * The theme extension is sourced from `@omniboost/design-tokens` so every
 * utility (bg-surface, text-text, rounded-md, p-md, ...) resolves to a
 * semantic token value. This is referenced from `globals.css` via `@config`.
 */
const config: Config = {
  content: [
    "./src/app/**/*.{ts,tsx}",
    "./src/features/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: tailwindTheme.colors,
      spacing: tailwindTheme.spacing,
      borderRadius: tailwindTheme.borderRadius,
      fontFamily: tailwindTheme.fontFamily,
    },
  },
  plugins: [],
};

export default config;
