# `components/` — reusable UI

Reusable, presentation-only building blocks for `frontend`, per the architecture
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
```

Add `layout/`, `forms/`, `templates/`, or other subfolders only when a real
group of reusable structures justifies them — not preemptively. `layout/` was
removed (2026-08-11, PLAN 4.7.7) when its only member, `PageShell`, lost its
last consumer (the `/chat` route was deleted — see `features/chat/FEATURES.md`).

## Current members

| Component | Consumed by | Role |
|---|---|---|
| `ui/Button` | none currently — kept as a generic primitive, cheap to keep, likely needed again | Token-styled button primitive |

Import via the `@/` alias, e.g. `import { Button } from "@/components/ui/button"`.
