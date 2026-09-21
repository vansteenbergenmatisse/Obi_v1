# `platform/` — application-wide technical capabilities

Generic technical access with no business rules, per the architecture standard: external
clients, auth, storage, logging, observability. Feature-specific integration logic (how a
request is validated, translated, or streamed back) stays in the owning feature; `platform/`
only provides the raw, authenticated capability to reach the external system.

## Current members

| Module | Role |
|---|---|
| `automation-api/` | Authenticated (`CHAT_API_KEY`), timeout-bounded calls to the Python `backend` service. Consumed by `features/chat/server`. |

Import via the `@/` alias, e.g. `import { callAutomationApi } from "@/platform/automation-api"`.
