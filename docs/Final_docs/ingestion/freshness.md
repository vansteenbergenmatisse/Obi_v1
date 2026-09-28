# The freshness target

- **Workflow:** ingestion
- **Owning code:** `backend/app/platform/config/settings.py` (`Settings.freshness_target_seconds`)
- **Design panel:** no dedicated freshness panel exists — the target is referenced inside `i2-gone`
  (a deactivated page's chunks stop appearing "within the freshness target") and `e-monitor`
  (index age is tracked "against the freshness target") on `obi-rag-system-flow.html`
- **Status:** Implemented (setting defined; substep 2.0.1). The measurement it will be checked
  against (the live 2.5.3 proof) and the monitoring (e-monitor) are Planned.

## What it does

The freshness target is the defined number of seconds between an editor clicking Publish in
Confluence and that change being searchable in the vector store, when the webhook is up. It is a
single integer setting, `Settings.freshness_target_seconds`, default **60**, env-overridable like
every other field on the `Settings` model (`FRESHNESS_TARGET_SECONDS`). It produces no behaviour of
its own — it is the one number every freshness proof reads instead of hardcoding a literal. The
daily sweep is the safety net that catches anything the webhook missed within a day; that fallback
timing is a separate concern wired in later substeps, not here.

This substep defines the number and proves it is the single source. It does **not** wire the number
into runtime behaviour (sweep scheduling, monitoring, or the deactivation-latency check named in
`i2-gone`). Those are later substeps.

## Why it does it

The owner resolved a conflict in `docs/plan/decisions.md` on 2026-09-24: the earlier
`freshness-target` row carried ≤ 20 s as an aspirational target, while the action plan's 2.0.1
prompt asked for a 60 s default. The resolution is **"60 s SLA, keep 20 s as the aim"** — 60 s is
the tested bound that the setting and every freshness test encode, and ≤ 20 s stays the aspiration
(retained in `decisions.md`, not deleted). Exposing it as a setting rather than a literal means the
live freshness proof (substep 2.5.3) and the e-monitor telemetry cannot silently drift from the
recorded decision: change the number in one place and every check follows. This honours project
rule 11 (no number without a home) and rule 12 (never invent numbers — this one is owner-confirmed).

## How we know it works

Tests in `backend/app/features/confluence_sync/tests/test_freshness_target.py` (unit level; no
session fixture, no database, no network). Each names the panel it protects in its docstring.

- `test_data_freshness_target_defaults_to_sixty_seconds` (panel `e-monitor`) — asserts the declared
  field default is 60 and a constructed `Settings()` reads 60. Reading the field default means "the
  code default", independent of any deployment `.env`.
- `test_data_freshness_target_is_env_overridable` (panel `e-monitor`) — sets
  `FRESHNESS_TARGET_SECONDS=45` and asserts `Settings().freshness_target_seconds == 45`, proving it
  is a real BaseSettings field, not a module-level constant.
- `test_data_freshness_target_is_the_single_source_freshness_tests_read` (panel `i2-gone`) — asserts
  the field exists, is typed `int`, and is exposed on the settings object, establishing the
  single-source convention later freshness proofs read.

**Not yet proven / out of scope here:** the number is defined but not yet *measured* against a real
publish-to-searchable delay — that is the live timed proof in substep 2.5.3 (panels `tg-edit`,
`tg-add`, `tg-remove`, `tg-rebuild`, `e-monitor`). The e-monitor telemetry that compares index age
to this target is Planned.
