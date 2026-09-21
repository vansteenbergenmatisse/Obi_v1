import { TestHostContent } from "../test-host-content";
import { tokenUrlFor } from "../token-url";

export default function OperaCloudTestHostPage() {
  return <TestHostContent name="opera-cloud" tokenUrl={tokenUrlFor("opera-cloud")} />;
}
