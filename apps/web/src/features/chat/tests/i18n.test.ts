import { describe, expect, it } from "vitest";
import { LOCALES, LOCALE_LABELS, getCopy } from "../model/i18n";

/**
 * panel w-i18n · substep p0-s0_5-reg-the-widget
 * Covers: greeting, suggestion chips, placeholder, footer, teaser, menus, banners.
 * Does not cover: the answer text — the model decides that.
 */

// Required copy keys grouped by the panel's "Covers" categories. Every locale must supply a
// non-empty value for every key below with no silent fallback to another locale's string.
const REQUIRED_STRING_KEYS = {
  greeting: ["greetingPre", "greetingPost"],
  placeholder: ["placeholder"],
  footer: ["footer"],
  teaser: ["teaser"],
  menus: ["docs", "support", "restart", "more", "language"],
  banners: ["clarifyingLabel", "handoffCta", "imageDisclosure", "imageAnalysisLabel"],
} as const;

const REQUIRED_STRING_KEY_LIST = Object.values(REQUIRED_STRING_KEYS).flat();

// Keys that would let this table govern the streamed answer's own content rather than static
// widget chrome. None of these may ever appear on WidgetCopy — the model decides answer text.
const ANSWER_GOVERNING_KEYS = [
  "answer",
  "answerText",
  "response",
  "responseText",
  "modelAnswer",
  "assistantAnswer",
  "streamedAnswer",
  "reply",
];

describe("i18n copy table", () => {
  it("w_i18n_six_locales_are_defined_with_labels", () => {
    expect(LOCALES).toHaveLength(6);
    expect([...LOCALES].sort()).toEqual(["de", "en", "es", "fr", "it", "nl"]);
    for (const locale of LOCALES) {
      expect(LOCALE_LABELS[locale]).toBeTruthy();
      expect(typeof LOCALE_LABELS[locale]).toBe("string");
    }
  });

  it("w_i18n_every_locale_has_every_required_copy_key", () => {
    for (const locale of LOCALES) {
      const copy = getCopy(locale);
      for (const key of REQUIRED_STRING_KEY_LIST) {
        const value = copy[key as keyof typeof copy];
        expect(value, `${locale}.${key} must be a non-empty string`).toBeTypeOf("string");
        expect((value as string).trim().length, `${locale}.${key} must not be empty`).toBeGreaterThan(0);
      }
    }
  });

  it("w_i18n_every_locale_has_suggestion_chips", () => {
    for (const locale of LOCALES) {
      const { suggestions } = getCopy(locale);
      expect(suggestions).toHaveLength(3);
      for (const chip of suggestions) {
        expect(typeof chip).toBe("string");
        expect(chip.trim().length).toBeGreaterThan(0);
      }
    }
  });

  it("w_i18n_no_locale_silently_falls_back_to_another_locales_copy", () => {
    // Cross-locale collision on every required key would indicate a shared/fallback string
    // rather than a per-locale translation; assert each locale's full required-key bundle is
    // distinct from every other locale's.
    const bundles = LOCALES.map((locale) => {
      const copy = getCopy(locale);
      return REQUIRED_STRING_KEY_LIST.map((key) => copy[key as keyof typeof copy]).join(" ");
    });
    const unique = new Set(bundles);
    expect(unique.size).toBe(LOCALES.length);
  });

  it("w_i18n_does_not_govern_answer_text", () => {
    const enKeys = Object.keys(getCopy("en"));
    for (const forbidden of ANSWER_GOVERNING_KEYS) {
      expect(enKeys).not.toContain(forbidden);
    }
  });
});
