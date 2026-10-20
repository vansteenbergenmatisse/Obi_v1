// Prints, as a JSON array, every name an enabled source system answers to — for `build:obi` to
// inject as `__OBI_ENABLED_SOURCES__` (ADR-source-system-decides-widget-eligibility). For each id in product_catalog.json's
// `enabled_sources`: the canonical id, the display label and every alias, normalized exactly like
// the backend's lenient `resolve_system` (case-folded, whitespace collapsed), so a partner token
// that says "Opera Cloud" is matched by the loader the same way the backend gate matches it.
// An absent `enabled_sources` means every product is enabled.
import { readFileSync } from "node:fs";

const catalog = JSON.parse(
  readFileSync(new URL("../../knowledge-base/config/product_catalog.json", import.meta.url), "utf8"),
);
const normalize = (value) => value.trim().split(/\s+/).join(" ").toLowerCase();
const ids = catalog.enabled_sources ?? Object.keys(catalog.products);
const names = new Set();
for (const id of ids) {
  const product = catalog.products[id];
  for (const name of [id, product.label, ...product.aliases]) names.add(normalize(name));
}
process.stdout.write(JSON.stringify([...names]));
