# `components/` — reusable UI

Reusable, presentation-only building blocks for `apps/web`, per the architecture
standard. Everything here is **content-free and rule-free**: it renders what it
is told to, styled through semantic tokens from `@omniboost/design-tokens` (never
arbitrary hex/px). Business rules, data fetching, and domain state live in
`features/`.

## What belongs here

A component earns a place in `components/` only when it is **reused across more
than one route or feature**. The placement rule (from the standard):

- Used once → keep it beside its route or feature.
- Repeated across pages/routes → `components/`.
- Feature-specific despite reuse → `features/<feature>/ui/`.

## Layout

```
components/
  ui/        Primitives: button, input, badge, … (button.tsx today)
  layout/    Page-level structure: page-shell.tsx today
```

Add `forms/`, `templates/`, or other subfolders only when a real group of
reusable structures justifies them — not preemptively.

## Current members

| Component | Consumed by | Role |
|---|---|---|
| `ui/Button` | home route, `features/chat` composer | Token-styled button primitive |
| `layout/PageShell` | home route, chat route | Centered max-width page column |

Import via the `@/` alias, e.g. `import { Button } from "@/components/ui/button"`.
