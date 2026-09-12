import { TestHostContent } from "../test-host-content";
import { tokenUrlFor } from "../token-url";

export default function NoneTestHostPage() {
  return <TestHostContent name="none" tokenUrl={tokenUrlFor("none")} />;
}
