import { TestHostContent } from "../test-host-content";
import { tokenUrlFor } from "../token-url";

export default function MewsTestHostPage() {
  return <TestHostContent name="mews" tokenUrl={tokenUrlFor("mews")} />;
}
