# Ingestion · component docs

One Markdown per ingestion component, written **before** that component is next touched. The
doc says three things and nothing else: **what it does**, **why it does it**, and **how we know
it works**. Read the component's doc (and `../ledger.md`) before any add, edit or removal; update
the doc in the same change; append the ledger entry after.

Ingestion is the workflow that turns a published Confluence page into chunks with vectors. It is
owned by two backend features:

- `backend/app/features/confluence_sync/` — stages 1–2: webhook, event ledger, job queue and
  worker, sweeps, change classification, labels to scope state.
- `backend/app/features/ingestion/` — stages 3–4: normalize, chunk, contextualize, attachments,
  embed, version, swap, garbage collection (retain 0 — rollback retired, sync rule 6 / D1).

## Files here

| file | what it holds |
|---|---|
| `_template.md` | the shape every component doc copies. Not a component; never edited to describe one. |
| `<component>.md` | one component of the ingestion workflow — what / why / how we know. Named after the component (e.g. `chunk.md`, `embed.md`, `webhook.md`). |

## The rule

- **Read before you touch.** Before changing a component, read its doc and `../ledger.md`. If the
  component has no doc yet, write it first from the current code — that is how "before we ever
  touch something" is honoured.
- **What / why / how we know.** Every doc answers exactly those three. "How we know it works"
  names the tests (by name) and the design panel the component protects — not a claim, a pointer.
- **The design page still wins.** These docs describe what the code does today; `../obi-rag-system-flow.html`
  is the source of truth for what it must do. When they disagree, the design page wins and the
  doc gets fixed.
- **Names.** Lowercase, one component per file, named for the component. No bare `today`/`latest`
  in a filename.
