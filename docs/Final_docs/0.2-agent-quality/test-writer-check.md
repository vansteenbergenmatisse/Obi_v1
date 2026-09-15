# 0.2.8 · Prove the test writer's tests actually catch a broken build

Output location deviates from `final_docs/0.2-agent-quality/` (repo root) to
`docs/Final_docs/0.2-agent-quality/` — same owner decision recorded in ledger entry 0.3.1: this
repo's audit/proof output lives under `docs/Final_docs/`, not a root-level `final_docs/`.

All commands below run with `DATABASE_URL` pointed at the local `make up` Postgres
(`postgresql+psycopg://rag:rag@localhost:5434/omniboost_rag`, database `omniboost_rag_test`
derived by the confluence_sync conftest), exported explicitly before `uv run pytest`. This is a
workaround for this run only, not a fix: the root `.env`'s `DATABASE_URL` points at the live
Supabase pooler, and pydantic-settings' `env_file` lookup picks that up ahead of the code default,
which is the same routing gap the ledger already flagged under "Need from you" (0.3.2). A real env
var outranks `.env`, so exporting it locally is enough to run these tests against `make up`
Postgres without touching any source file — the underlying routing bug for the general suite/CI is
still open and unchanged by this check.

## Method

For each test: run it unmodified against the code as committed, then comment out or revert the one
line its docstring names, rerun with nothing else changed, confirm it now fails for that reason,
restore the line, rerun, confirm it passes again. `git status` confirms every source file involved
is byte-identical to HEAD after each cycle.

## 1 — i1-ledger, unit level

Test: `test_in1_duplicate_result_stops_before_enqueue` —
`apps/automation/app/features/confluence_sync/tests/test_event_dedup.py`. No `session` fixture;
`record_event` and `enqueue_job` are monkeypatched, so it is DB-free.

Guard checked: the `if event_id is None: return IngestResult(..., duplicate=True, ...)` early
return in `event_service.ingest_event`
(`apps/automation/app/features/confluence_sync/application/event_service.py:55-56`).

| Step | Command | Result |
|---|---|---|
| Passes today | `uv run pytest app/features/confluence_sync/tests/test_event_dedup.py::test_in1_duplicate_result_stops_before_enqueue -v` | **PASSED** (1 passed in 0.32s) |
| Guard commented out | same command | **FAILED** — `_must_not_enqueue` raises `AssertionError: must not enqueue a job for a duplicate event` because control falls through to `_enqueue_for_event` → `enqueue_job` once the early return is gone |
| Restored | same command | **PASSED** (1 passed in 0.32s); `git status --short` on the file: clean |

## 2 — i1-ledger, database level

Test: `test_same_delivery_id_different_payload_dedupes_gracefully_not_500` — same file. Takes the
real `session` fixture (local Postgres, migrations at head).

Guard checked: the targetless `.on_conflict_do_nothing()` in `event_repo.record_event`
(`apps/automation/app/features/confluence_sync/infrastructure/event_repo.py`), which absorbs a
violation on either `uq_event_ledger_payload_hash` or `ux_event_ledger_delivery_id` in one round
trip (PLAN 4.6.11). Reverted to the pre-fix `on_conflict_do_nothing(index_elements=["payload_hash"])`
found via `git log -p` on this file (commit `0a61fb4`).

| Step | Command | Result |
|---|---|---|
| Passes today | `uv run pytest app/features/confluence_sync/tests/test_event_dedup.py -v` | **PASSED**, all 3 tests in the file (`test_duplicate_delivery_is_idempotent`, `test_in1_duplicate_result_stops_before_enqueue`, `test_same_delivery_id_different_payload_dedupes_gracefully_not_500`) |
| Guard narrowed to `index_elements=["payload_hash"]` | `uv run pytest app/features/confluence_sync/tests/test_event_dedup.py::test_same_delivery_id_different_payload_dedupes_gracefully_not_500 -v` | **FAILED** — uncaught `sqlalchemy.exc.IntegrityError: ... duplicate key value violates unique constraint "ux_event_ledger_delivery_id"`, i.e. exactly the uncaught 500 PLAN 4.6.11 fixed |
| Restored | `uv run pytest app/features/confluence_sync/tests/test_event_dedup.py -v` | **PASSED**, all 3 (3 passed in 0.38s); `git status --short` on the file: clean |

## 3 — tg-deactivate

**Level deviation, recorded and reasoned rather than silently substituted:** the task asked for
this cycle at unit level. `tg-deactivate`'s target (`versioning.deactivate_page`,
`apps/automation/app/features/ingestion/application/versioning.py:402`) is an ORM mutation over a
real `Session` — it calls `session.get`/`session.execute(update(...))` against `PageSource`,
`DocumentVersion` and `Chunk`. `.claude/skills/obi-test-writer/SKILL.md` rule 5 defines unit level
as "no `session` fixture, no database; pure functions and services with fakes," and rule 4 limits
fakes to four named external-system doubles (Confluence gateway, embedder, reranker, Claude client)
— none of which stand in for a database session. A hand-rolled fake `Session` would not faithfully
exercise a real `UPDATE`/constraint, and every other versioning.py function of this shape
(`_activate`, `rollback_to`) is exercised at database level elsewhere in this repo — there is no
existing unit-level pattern for this module to follow. Database level is therefore the faithful
choice; this is the same "say so explicitly and propose the smallest DB-level alternative" escape
hatch `/obi-test-writer` was asked for and is documented here rather than left implicit.

Test: `test_delete_marks_the_active_version_superseded` — panel `tg-deactivate` · substep 2.5 —
`apps/automation/app/features/confluence_sync/tests/test_worker_sync.py`. Takes the real `session`
fixture. **Pre-existing in the working tree, uncommitted, before this check started** (it was not
authored as part of this substep) — used as-is since it already matches the panel/substep citation
the skill's own skeleton requires and exercises exactly the target behavior.

Gap checked: the panel's target is "page_status updated, active version supersed, chunks inactive."
`deactivate_page` today updates `page_status` and sets `Chunk.is_active = False`, but never touches
`DocumentVersion.state` or `ps.active_doc_version_id` — confirmed missing by cross-referencing
`_activate` (`versioning.py:334`) and `rollback_to` (`versioning.py:431`), which both do supersede
the outgoing version the same way this one should.

| Step | Command | Result |
|---|---|---|
| Fails today | `uv run pytest app/features/confluence_sync/tests/test_worker_sync.py -v` | **FAILED** for the stated reason — `AssertionError: assert <DocState.active: 'active'> == <DocState.superseded: 'superseded'>`; the other 8 tests in the file **PASSED** |
| Minimal stub added | same command | **PASSED**, all 9 tests in the file (9 passed in 1.17s). Stub: inside `deactivate_page`, before the existing `Chunk` update, `session.execute(update(DocumentVersion).where(DocumentVersion.id == ps.active_doc_version_id).values(state=DocState.superseded, superseded_at=_now()))` |
| Stub removed | `uv run pytest app/features/confluence_sync/tests/test_worker_sync.py::test_delete_marks_the_active_version_superseded -v` | **FAILED** again, identical `AssertionError`; `git status --short` on `versioning.py`: clean (matches HEAD, confirmed with `git diff --stat`) |

`tg-deactivate`'s implementation gap (the missing supersede) is **not** fixed by this check — the
stub was added and removed solely to prove the test can catch it; substep 2.2.4 is the substep that
actually builds the target.

## 4 — a test that could not be broken this way

`test_before_and_after_precision_ndcg` — substep **3.1.6 · Before and after** (`docs/Final_docs`
action plan, level `eval`, "Already works · protect it"). Proof for this substep is "two rows in
`docs/plan/baseline.md`": Precision@5 and NDCG@10 on the gold v0 held-out set, recorded before and
after a retrieval-affecting change. Per `.claude/skills/obi-test-writer/SKILL.md` rule 5, `eval` is
explicitly **not a pytest** — it is a `make eval` run against a gold case set producing a score,
compared against a prior score recorded in a markdown file. There is no single boolean pass/fail
tied to one source line to comment out: breaking it would mean regressing retrieval quality broadly
enough to move an aggregate metric, not reverting one guard. The revert-and-rerun method in this
check only applies to pytest-level regression/new-behavior tests (unit, database, browser); it does
not extend to `eval`-level checks by the skill's own level rules.
