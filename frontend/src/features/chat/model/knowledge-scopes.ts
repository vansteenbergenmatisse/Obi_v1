/**
 * knowledge-scopes — the recognized RAG knowledge scopes the dev/verification scope switcher
 * (PLAN 10.8) lets a tester pick between.
 *
 * CANONICAL SOURCE: `config/knowledge_scopes.json` at the repo root — the ONE place the backend
 * (ADR-0011, PLAN 10.1) reads to decide which scope a Confluence label maps to. This list mirrors
 * that file's `name`s so the widget can render a switcher without importing a repo-root JSON into
 * the Next client bundle (which Next forbids across the app-root boundary). It is NOT a second
 * source of truth: `tests/knowledge-scopes.test.ts` reads the canonical file and fails the build
 * if the two ever drift, so this copy can never silently diverge — the canonical file stays
 * authoritative. To recognize a new scope, add it to the canonical JSON first, then here.
 */

export const KNOWLEDGE_SCOPES = [
  { name: "obi-general-test", label: "General" },
  { name: "obi-mews-test", label: "Mews" },
  { name: "obi-operacloud-test", label: "Opera Cloud" },
  { name: "obi-toast-test", label: "Toast" },
] as const;

export type KnowledgeScope = (typeof KNOWLEDGE_SCOPES)[number]["name"];

export const KNOWLEDGE_SCOPE_NAMES: readonly KnowledgeScope[] = KNOWLEDGE_SCOPES.map((s) => s.name);
