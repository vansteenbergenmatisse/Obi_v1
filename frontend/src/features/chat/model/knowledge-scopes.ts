/**
 * knowledge-scopes — the recognized RAG knowledge scopes the dev/verification scope switcher
 * (PLAN 10.8) lets a tester pick between.
 *
 * GENERATED, NOT hand-written (substep 1.2.2, panels ks-deploy / ks-widget / cm-config). This list
 * is built at import/build time from the ONE canonical allowlist,
 * `knowledge-base/config/knowledge_scopes.json` — the same file the backend reads at startup
 * (ADR-0011, PLAN 10.1) and Confluence ingestion reads for scope eligibility. There is no second
 * source of truth and no hand-maintained copy: to recognize a new scope, add one entry (with its
 * `label`) to that JSON and rebuild — nothing here changes. The reserved `classified` scope is
 * present in the JSON but filtered out below, so it is never offered by the widget and can never
 * ride on a request body (ADR-0011).
 *
 * The JSON is reached through the `@kb/*` tsconfig path alias (mirrored in `vitest.config.ts`), so
 * the relative depth to the repo-root config is written once, in the alias, not here.
 */
import scopeConfig from "@kb/config/knowledge_scopes.json";

// Reserved scope: present in the canonical file so the backend knows it, but never offered by the
// widget. Kept in sync with the backend loader's RESERVED_CLASSIFIED_SCOPE and the forbidden
// integration slug (ADR-0011).
const RESERVED_CLASSIFIED_SCOPE = "classified";

/**
 * A recognized, offerable scope's tag name. Widened to `string` now that the set is generated from
 * the JSON at build time (the runtime backend gate — not a compile-time union — is what rejects an
 * unknown scope). The exported name is unchanged from the pre-1.2.2 hand-written list, so no
 * importer changes.
 */
export type KnowledgeScope = string;

/**
 * The offerable scopes, in the JSON's order, each as `{ name, label }` — `classified` excluded.
 * `name` is the exact Confluence tag / internal scope id; `label` is the human-readable name the
 * switcher displays. Both come straight from the canonical JSON.
 */
export const KNOWLEDGE_SCOPES: readonly { name: KnowledgeScope; label: string }[] =
  scopeConfig.scopes
    .filter((scope) => scope.name !== RESERVED_CLASSIFIED_SCOPE)
    .map((scope) => ({ name: scope.name, label: scope.label }));

export const KNOWLEDGE_SCOPE_NAMES: readonly KnowledgeScope[] = KNOWLEDGE_SCOPES.map((s) => s.name);
