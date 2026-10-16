import { TestHostContent } from "../test-host-content";
import { tokenUrlFor } from "../token-url";

// Disabled-target stub (sync-rules Task 5, ADR-0022). Uses the DIRECTED token form (`?form=directed`)
// so the minted note carries `target_system: "quickbooks-online"` — an accounting product that is
// NOT in product_catalog.json's enabled_targets — which the loader decodes at init and refuses to
// mount. Exercised by `e2e/widget-hidden-when-target-disabled.spec.ts`.
export default function QuickbooksTestHostPage() {
  return <TestHostContent name="quickbooks" tokenUrl={`${tokenUrlFor("quickbooks")}?form=directed`} />;
}
