# 0003 — Feature Boundary Enforcement

Status: Accepted
Date: 2026-08-07
Governs: apps/automation (all features, platform, shared), the monorepo architecture standard

## Context

The backend was already feature-sliced, but cross-feature and cross-layer imports
reached straight into submodules (`from app.features.ingestion.application.services
import ...`). Nothing stopped a consumer from binding to another feature's internals,
so the feature boundary existed by convention only. Two architecture standards also
disagreed on the folder shape: the global standard's feature-shape backend, and the
project standard's five-folder rule (`app/features/components/platform/shared`).

## Decision

1. **Every feature exposes one public root** (`app/features/<f>/__init__.py`) that
   re-exports the symbols crossing its boundary. All external code — routes, other
   features, tests — imports through that root and never deeper. The four features
   (`confluence_sync`, `ingestion`, `retrieval`, `evaluation`) each have such a facade.

2. **The external-client capability also has a public root** (`app/platform/clients`).
   It is a small, cohesive set of client contracts and factories, so one flat root
   reads cleanly.

3. **The boundary is machine-enforced**, not documented-and-hoped. `tools/check_feature_boundaries.py`
   (stdlib `ast`, walking the full tree so function-local imports count) fails the
   build on four rules Ruff's isort cannot express:
   - (a) code outside a feature imports it only at its root;
   - (b) code inside `<f>` may deep-import `<f>`, but reaches other features at root;
   - (c) code inside `<f>` must not import its own root (self-facade ImportError trap);
   - (d) `platform/**` and `shared/**` import no features; `shared/**` imports no platform.
   Wired as `make boundaries` and gated in `make check`.

4. **Standards reconciled: backend uses `app/{features, platform, shared}`.** The
   five-folder rule's `components/` is UI-only and applies to `apps/web`, not backend
   services. Pure cross-feature primitives live in `app/shared/` (this is where
   `hashing` now sits, relocated from the `platform/` root); `platform/` holds
   technical capabilities (db, clients, config, jobs, logging).

5. **`platform/db` is deliberately not faceted.** ~40 ORM classes, enums, and DDL
   helpers are a large, intrinsically-namespaced vocabulary; collapsing them into one
   root would create a god-module and destroy the `db.enums.PageStatus` vs
   `db.models.PageSource` disambiguation. The standard mandates public entrypoints for
   *features*, not for every platform sub-capability. `platform/db` keeps full-path imports.

6. **The service version is single-sourced** at `app/__init__.py::__version__`;
   pyproject reads it via Hatchling's dynamic version and `app.main` stamps it onto
   FastAPI, resolving the prior 0.1.0/0.2.0 drift.

## Reason

A boundary a script can check is a boundary that survives contact with the next change;
one that lives only in a doc erodes on the first deadline. Facades with eager
re-exports give each feature a single, greppable public surface without a runtime cost.

## Deviations register (decisions taken during the conformance refactor)

- **[D1] Gate = no-regression, not zero, for Ruff and Pyright.** The baseline was
  already dirty (Ruff 2 errors + 25 unformatted files, Pyright 31 errors / 1 warning).
  Reformatting 25 unrelated files would bury the behavior-unchanged import diff, so the
  gate holds whole-repo counts flat and only makes *touched* files cleaner. Pre-existing
  dirt is out of scope for this refactor.
- **[D2] Committed on `main`, red state first.** The repo had zero commits; `main` is the
  natural home for its initial history, and the tag/bisect/rollback design needs linear
  history. The red baseline (`e10ee9d`, tag `pre-refactor-baseline`) is an intentional
  bisect anchor; `green-baseline` (`325dd8f`) marks the first trustworthy-green tree.
- **[D3] Facades use eager exports and never import their own root.** `from app.features.<f>
  import X` inside `<f>` raises ImportError against a half-built package. Verified no
  feature imports its own root; rule (c) guards it permanently.
- **[D4] The ingestion facade re-exports `normalization` as a module, not loose symbols.**
  Call sites use `norm.Block` / `norm.normalize_body` / `norm.content_hash` — the
  numpy.linalg pattern keeps the call-site diff to one import line.
- **[D5] `platform/db` gets no facade** — see Decision 5.
- **[D6] The `app.*` startup import graph is 46 modules** (was 45 pre-refactor). The +1 is
  the `app.shared` namespace introduced by relocating `hashing`; no feature facade leaks
  into `app.main`'s startup graph.
- **One legal cycle-breaker stays:** `confluence_sync/application/worker.py` lazily imports
  `reconciliation` inside a function to avoid a module-load cycle. It is a same-feature
  deep import (rule b permits it) and must not be hoisted.

## Paths governed

`apps/automation/app/features/**`, `apps/automation/app/platform/**`,
`apps/automation/app/shared/**`, `apps/automation/tools/check_feature_boundaries.py`,
the root `CLAUDE.md`.
