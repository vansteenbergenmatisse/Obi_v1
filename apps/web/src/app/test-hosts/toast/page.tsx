import { TestHostContent } from "../test-host-content";
import { tokenUrlFor } from "../token-url";

export default function ToastTestHostPage() {
  return <TestHostContent name="toast" tokenUrl={tokenUrlFor("toast")} />;
}
