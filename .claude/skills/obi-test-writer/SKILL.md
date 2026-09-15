---
name: obi-test-writer
description: Write a rock-solid test for one Obi behavior: a regression test for something that works, or a failing test for something to build. Use before any implementation and for every "Protect" item in the plan.
allowed-tools: Read, Write, Edit, Grep, Glob, Bash(uv run pytest:*), Bash(pnpm:*)
---
# /obi-test-writer

Input: the behavior in one sentence, the design panel id, the substep id, the level (unit, database, browser, eval).

Rules
1. One behavior per test function. Name test_<stage>_<behavior>; stage is one of in1 in2 in3 in4 tags rt1 rt2 rt3 rt4 rt5 widget data sec eval.
2. Docstring, first line: "panel <id> · substep <id>"; second line: the acceptance sentence being proved.
3. Deterministic: no network, no sleep, no wall clock (freeze time), no unseeded randomness. Never call a real API.
4. Fakes, and only these: FixtureConfluenceGateway over tests/fixtures/confluence; the deterministic fake embedder; FakeReranker (input order preserved); a scripted Claude client returning canned JSON per prompt name. Add a fixture page instead of mocking a Confluence response inline.
5. Level rules:
   - unit: no `session` fixture, no database; pure functions and services with fakes.
   - database: no pytest marker — this suite registers none. Place the test in the feature's `tests/` next to a `conftest.py` that provides the `session` fixture (see `app/features/confluence_sync/tests/conftest.py`: the autouse `_configure_test_engine` points at the local test Postgres and migrates to head, and `_truncate` clears tables per test). Real local Postgres; migrations at head; roles rag and rag_reader; policies on; reader tests set app.allowed_sources and app.allowed_knowledge_scopes explicitly with set_config.
   - browser: Playwright; a stub host page under the frontend test fixtures; assert on the DOM and on network requests, never on a real platform.
   - eval: not a pytest; a gold case with expected outcome, required passages, essential facts, forbidden claims.
6. Assert the acceptance line: the outcome, the rows, the ids, the status code, the log line. Never assert private state or call order.
7. Every lock and every refusal gets its negative case: the forbidden path returns zero rows, 401, or a refusal with the named reason.
8. Regression tests pass on the current code before anything changes. New-behavior tests fail on the current code for the stated reason, then pass after the change.
9. Fixture pages available: one per tag (obi-mews-test, obi-toast-test, obi-general-test), two provider labels, classified, no recognized label, with a PDF attachment, group-restricted, empty.

Skeleton (unit or database). Database tests take the `session` fixture from the feature's conftest; unit tests take only fakes — neither uses a pytest marker:

    # database: request the `session` fixture (feature conftest wires the test DB).
    # unit: drop `session`, take only fakes.
    def test_in1_ledger_dedups_redelivery(fixture_gateway, session):
        """panel i1-ledger · substep 0.5.2
        Same delivery id, different payload: the second insert returns None and creates no job."""
        # arrange
        # act
        # assert

Output: the test file path (next to the feature it covers), the test code, and the exact command to run it.
