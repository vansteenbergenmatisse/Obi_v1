# <component name>

- **Workflow:** retrieval
- **Owning code:** `backend/app/features/<feature>/<path>` (the module(s) that own this component)
- **Design panel:** <the panel on `obi-rag-system-flow.html` this component maps to>
- **Status:** Implemented | Implemented, needs changing | Planned | Unverified | Decision needed

## What it does

One or two paragraphs. The behaviour, in plain English: inputs, what it produces, where it sits
in the retrieval workflow. No code walkthrough — describe the contract, not the lines.

## Why it does it

Why this component exists and why it works this way. The rule or design decision behind it (cite
the project rule or ADR when there is one). What would break if it were removed or done
differently.

## How we know it works

Not a claim — pointers. Name the tests that cover it (`test_<stage>_<behavior>`), the level they
run at (unit / database / live / eval), and the design panel they protect. For a change that
moves retrieval, name the before-and-after gold-set number. Note any acceptance line that is
asserted, and any gap that is not yet proven.
