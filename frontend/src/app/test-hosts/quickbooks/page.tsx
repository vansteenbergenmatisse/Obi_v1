import { TestHostContent } from "../test-host-content";
import { tokenUrlFor } from "../token-url";

// Disabled-source stub (ADR-0023). Uses the DIRECTED token form (`?form=directed`) so the minted
// note carries `source_system: "quickbooks-online"` — an accounting product that is NOT in
// product_catalog.json's enabled_sources — which the loader decodes at init and refuses to mount.
// Exercised by `e2e/widget-hidden-when-source-disabled.spec.ts`.
export default function QuickbooksTestHostPage() {
  return <TestHostContent name="quickbooks" tokenUrl={`${tokenUrlFor("quickbooks")}?form=directed`} />;
}
