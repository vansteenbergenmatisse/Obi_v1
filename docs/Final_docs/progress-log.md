# Progress log — the plain-English record of everything done

One entry per finished piece of work, in plain sentences: what we did, why, which tests ran, and
what happened. 2 to 20 sentences each — a quick read, not the full technical record.

This is a companion to `ledger.md`, not a replacement for it. `ledger.md` stays the detailed,
technical record (exact commit, exact test names, every deviation) that CLAUDE.md requires. This
file is the short version, for scanning the whole history in one sitting.

**Append-only, same as the ledger: a new entry never edits an old one.** If something reported
here turns out to have been wrong or incomplete, the fix is a new entry that says so — the
original entry stays exactly as written, even if it was wrong. That's the point: you can trust
that entry 12 hasn't quietly rewritten what entry 3 said.

Newest at the bottom.

## Entries

**0.3.1 — audited the code against the design page (2026-09-14).** We compared every one of the
192 design-page panels against what the code actually does, to catch drift before doing any more
work on top of it. No tests were run — this was a read-only audit. Result: produced 10 audit
documents (one per subsystem) covering all 192 panels, plus one extra for the app's entrypoint.

**0.3.2 — inventoried every existing test (2026-09-15).** We catalogued every test in the repo
against the panels audited above, to find out which of the "already built" panels have no test
protecting them at all. No new substep tests were written; along the way we found and fixed a bug
in a safety-check script that only worked when run from one specific folder. Result: 793 test
functions across 98 files were inventoried, and 35 built panels came back with zero test — this
became the to-do list for later work.

**0.2.8 — proved the "break it, watch it fail, fix it, watch it pass" method actually works
(2026-09-15).** Before trusting this method for real work, we ran it once on 4 existing tests:
deliberately reverted the code they protect, confirmed the tests correctly turned red, then
restored the code and confirmed green again. All 4 caught their break as expected. One real gap
was found in the process (a feature that isn't built yet) and left alone on purpose — proving the
test can catch it later, not building it now.

**1.3.1 — wrote down deferred ideas so they don't get lost (2026-09-16).** We wrote up 8 feature
ideas that are good but explicitly not being worked on now (multi-language search, cost tracking,
live streaming answers, etc.), so nobody accidentally starts on them early or forgets them. No
tests — documentation only.

**0.4.2 — fixed the design page where it disagreed with the code (2026-09-16).** The design page
is supposed to be the single source of truth, so wherever the earlier audit found it wrong, we
corrected it. No tests — documentation only, no code changed. Result: 52 panels corrected with
evidence for each; a handful of other known-wrong spots couldn't be safely auto-edited and were
left flagged instead of silently skipped.

**0.4.3 — checked the future work-list against everything found wrong so far (2026-09-16).** We
made sure every gap found in the two audits above (design-page mistakes, code the design page
never mentioned) already has a home in the plan of future work, so nothing falls through the
cracks. No tests — documentation only. Result: of 187 planned work items, 157 still made sense
as-is, 24 turned out already done, 6 needed rewriting; every one of the 60+12 gap items already
had a planned home.

**0.5.1 — built the actual test-running setup (2026-09-16).** There was no reliable way to run
database-backed tests locally before this, so we set one up: a local test database, a CI
pipeline config, a browser-test setup, and 10 new fixture pages to test against. 8 new tests
were added and 1 existing test fixed. We discovered this machine quietly points test runs at a
live cloud database instead of the local one unless told otherwise — worked around for this
substep, flagged as still broken everywhere else. We also deliberately left one already-broken,
unrelated test failing, as proof the new setup actually catches real problems.

**0.5.2 — cleaned up type-checking errors in recently-written tests (2026-09-16).** Two earlier
batches of new test files shipped with type-checking errors that had been wrongly excused as "the
same as an older file's style." We fixed all of them properly instead. No behavior changed — this
was type-annotation cleanup only. Result: whole-repo type errors dropped from 72 to 58; both test
suites stayed fully green.

**0.5.3 — wrote the missing tests for retrieval, the widget, the database, and security
(2026-09-16).** Continuing the "find every untested panel and protect it" work, we covered 13
more panels and also ran a real check against the staging cloud database to confirm access rules
actually hold live. 23 new tests were added. Partway through, a mistake connected a test run to
the live staging database instead of the local one and reset a shared password — caught, reported,
the owner rotated the password, and every following test was pinned to local-only. The live check
itself came back 6 confirmed working, 6 unconfirmable (reported honestly, not guessed at).

**0.5.4 — proved the CI pipeline actually blocks a broken change (2026-09-16).** A test suite is
only a real safety net if it's wired into something that actually stops bad code from merging, so
we deliberately broke one check, watched CI go red, fixed it, and watched CI go green again. No
new tests; one pre-existing unrelated bug (a mis-tagged test) was found and fixed because it made
the first CI run fail for the wrong reason. Result: repo got its first GitHub remote and branch
protection; the break → red → fix → green cycle ran clean.

**docs-consolidation — reorganized where documents live (2026-09-17).** At the owner's direct
request (not a planned work item), we archived old/superseded design documents, moved the ledger
to its current location, and fixed several places that pointed at a folder that no longer exists.
No tests — no code behavior changed; confirmed by running the full suite (460 + 197 tests), all
still green.

**0.5.3 re-verify (2026-09-17).** Before starting new work, we re-checked that substep 0.5.3's own
proof still holds up. No new tests; re-ran the existing suites, all green. We deliberately did NOT
re-run the live staging check from 0.5.3, because the shared password from that incident hadn't
been confirmed fixed yet — running a live check with a possibly-broken password would prove
nothing.

**0.5.4 re-verify (2026-09-17).** Same idea for the CI-gate substep: re-ran the actual break → red
→ fix → green cycle for real, because an earlier pass had only compared files and never actually
executed it. While re-checking, the same live-database mistake from 0.5.3 happened again (a direct
test command instead of the proper local-only command) — this time we fixed the root cause in the
test code itself, so it now refuses to run against anything but a local database, not just
flagging the risk again.

**Ingestion stage 1 — protected 7 already-working panels (2026-09-17).** We wrote regression tests
for the webhook handler, the event ledger, and job claiming/retry/dead-lettering — the parts that
already work today — so future changes can't quietly break them. 12 new tests across two passes
(10 first, 2 more found missing on a stricter re-check against the "one test per check" bar).
Both the fast (fakes-only) and database-backed test suites came back green; one stale citation in
the test-coverage map was corrected along the way.

**Ingestion stage 2 — protected 5 already-working panels (2026-09-17).** We wrote regression tests
for fetching a page's facts, metadata-only updates, no-change detection, handing off to the
chunker, and in-place writes — again, the parts that already work today. 3 new tests were added;
run through two parallel work-agents split so they wouldn't edit the same file at once. Both test
suites came back green (460 fakes-only + 212 database-backed tests). A stricter re-check
afterward found 2 tests were mis-named (copied an old typo instead of the correct naming) — fixed
— and caught a real slip: the fix had briefly rewritten an already-finished record of past work
instead of only adding a new one, which was reverted before it stuck. That's exactly the mistake
this log exists to make impossible to miss.

**Ingestion stage 3 — protected 5 already-working panels (2026-09-17).** We wrote regression tests
for turning a page's HTML into blocks, building parent and child chunks, adding the short context
note to each child, and the keyword search index — the parts that already work today. Four
work-agents ran at once, one per panel or shared test file, each checking whether an existing test
already proved its panel's checks before writing anything new. One panel (i3-blocks) needed
nothing at all — three older tests already covered it exactly. The other four needed 9 new tests
between them, including one genuine gap: the two-sentence context note is supposed to be capped
at 128 tokens, and nothing had ever actually checked that the cap is enforced, only that the note
itself gets written. Both the fast (fakes-only) and database-backed test suites came back green
(466 and 215 tests respectively) with no code changes anywhere — this batch only closed gaps in
what proved the code already works, it didn't have to fix anything that was broken.

**Ingestion stage 3 re-verify (2026-09-17).** Checked the batch above against its own literal
rule: one test per check, named after the panel's own id. Four of the five panels pass that
literally. The fifth, the context-note panel, doesn't quite: two of its three checks are proven by
older tests that were never renamed to match, because one of those two tests is also the only
proof on record for a completely different panel elsewhere in the system — renaming it would have
silently broken that other panel's record. Left as-is and written down plainly rather than fixed
by half-measure. Both test suites re-ran green with no changes (466 and 215 tests, same as before).

**Knowledge scopes — protected 5 already-working panels (2026-09-17).** We wrote regression tests
for adding a label, changing a label, a page's first appearance in the index, a tag update without
a re-embed, and a tagged page actually going into the index — the parts that already work today.
Five work-agents ran at once, one per panel, each checking whether an existing test already proved
its panel's checks before writing anything new. Two panels (the first-index panel and the
no-re-embed panel) needed nothing at all — their checks were already fully proven by other panels'
tests. The other three needed 4 new tests between them: one closing a real gap where adding a
label had only ever been proven to update the database row, never proven to actually make the page
findable in a search scoped to its new tag; one closing a gap where a label swap delivered as two
separate queued events (rather than one combined change) had never been exercised, even though the
underlying code treats those two delivery shapes differently; and two proving, for the first time,
that a page tagged through the real pipeline is actually searchable in its scope (and correctly
absent from a search outside it) — the only prior test for that behavior checked the database
columns directly rather than proving the page comes back from an actual search. Both the fast
(fakes-only) and database-backed test suites came back green (466 and 222 tests) with no code
changes anywhere — this batch only closed gaps in what proved the code already works.

**Knowledge scopes re-verify (2026-09-17).** Checked the batch above against its own literal
rule: one test per check, named after the panel's own id. Three of the five panels pass that
literally. Two don't, quite: the first-index panel's second check and two of the three checks on
the panel for a page actually going into the index are genuinely proven — just by tests that carry
a different panel's name, because that's where the identical behavior is already asserted more
precisely. Renaming or duplicating those tests would either break another panel's own citation or
just re-prove the same thing a second time under a new label, so both gaps were written down
plainly instead of patched over. Both test suites re-ran green with no changes (466 and 222 tests,
same as before).

**Knowledge scopes — naming gaps closed for real (2026-09-17).** Asked to fix, rather than just
disclose, the two gaps from the re-verify above: the first-index panel's second check, and two of
the three checks on the panel for a page going into the index. Two work-agents each wrote one
dedicated test carrying their own panel's name — one proving that a label added after a page's
first build only updates it in place, one proving that running a single queued sync job is what
actually drives a brand-new page through fetching, chunking and activating, and one proving the
chunks themselves (not just the page's own record) end up carrying the recognized label. Three new
tests, no code changes, both test suites green (466 and 225 tests). Every one of the five panels
in this batch now has a test named for itself proving every one of its own checks — no naming gaps
left in this batch.

**Retrieval, stage 1 — six panels protected, three drifts found (2026-09-17).** Asked to write one
regression test per check for the six panels covering how a question first arrives: the widget's
proxy route, rate/size limits, small talk, the too-vague-to-search check, idempotent replay, and the
short reply that skips search. Rather than blindly rewriting eighteen checks' worth of tests, an
audit ran first, since the coverage map already showed every panel green from earlier work. It found
ten checks already properly proven and eight with a real gap. Four of those eight were just missing
tests on code that already works correctly, and four parallel agents closed them: the proxy route now
has a test proving the browser calls its own `/api/chat` address and a test proving the streamed
reply isn't buffered before it reaches the browser; the limits check now proves an oversized image
buried in an earlier turn of a conversation gets caught, not just one on the latest turn; the
idempotent-replay check now proves two different logged-in people sharing the same replay key don't
get each other's cached answer. The other three gaps turned out to be the page's own description
being wrong, not the tests: the page says the proxy forwards requests untouched, but the code
deliberately reshapes them to match the backend's format; the page says the rate limiter falls back
to the caller's IP address behind a trusted proxy, but no such logic exists in the code at all; and
the page says small-talk replies come from the fast, cheap model, but they're actually generated by
the same model that writes full answers. None of these three were fixed in code — changing them is a
real product or security call, not a test-writing one — so all three went into the decisions log for
the owner to weigh in on. One of the four work-agents also created its own permission marker without
first checking whether this work actually belonged to a numbered plan step, which it did — a mistake
worth naming since its two sibling agents hit the same missing information and correctly stopped to
ask instead. Its actual test was checked afterward and is fine. All new and existing tests passed
together at the end: 467 backend tests without a database, 228 with one, and 29 in the browser-style
frontend suite.

**Retrieval, stage 1 — naming gaps closed for real (2026-09-17).** Asked to actually verify the
substep's own proof bar: run the two test commands, and check that every one of the six panels has
one test per check literally named after that panel, not just proven by some test somewhere. A
direct search for test names starting with each panel's id turned up real gaps: two panels (small
talk and the too-vague-to-search check) had zero tests carrying their own name anywhere, even though
every fact they claim was already correctly and thoroughly proven by tests named for other things;
the limits panel was missing a named test for its rate-limit check and its main history check; the
replay panel was missing named tests for two of its three checks. None of this meant the underlying
behavior was wrong or unproven — it meant the proof wasn't filed under the right name. Ten small,
focused tests were added, each proving exactly the one fact its check describes and named for that
check; two tests written earlier the same day (before their proper names were settled) were renamed
in place rather than duplicated, since nothing else in the repository was citing them yet by name.
Nothing else was renamed, since three of these panels' existing tests are already cited by name in
older, frozen audit snapshots, and renaming them would just make those old snapshots wrong for no
real benefit. No code changed — only tests. Both full test suites ran green afterward: 473 without a
database (six more than before), 232 with one (four more than before, plus the one long-standing
expected failure).

**Retrieval, stage 2 — 5 panels (2026-09-17).** Protected the five panels that cover how a
question gets embedded and searched: embedding the question with the same model used for pages,
setting the per-transaction database scope (which sources and knowledge scopes are visible, plus
the HNSW search knobs), the dense (vector) search itself, the keyword (full-text) search, and the
two indexes both searches lean on. Before writing anything, checked whether the coverage sheet's
existing citations actually proved each panel's specific claims — three of the five didn't: the
dense-search and keyword-search rows both pointed at a test that only proves an unrelated, narrower
behavior (an optional customer-scope filter), never the actual distance operator, filter clause,
tsquery rewrite, or rank expression these two panels describe; the indexes row pointed at a test for
a completely different index than the two this panel names. Five people worked one panel each at
the same time, each adding tests to their own file so nobody stepped on anyone else's work — one
person extended the embedding-client tests, one extended the existing scope-setting tests, and three
wrote brand-new test files for dense search, keyword search, and the two search indexes. The
indexes tests are the most rigorous of the batch: they ask the real, freshly-migrated local database
directly whether the index exists, what method and settings it actually has, and what condition
narrows it — not just whether the Python code that describes it reads correctly. One harmless gap
was found and disclosed rather than fixed: the test suite runs with a smaller embedding size for
speed, which means the newest index test never actually exercises the special "compressed vector"
code path a production-sized embedding would use, even though the test was written to handle either
case correctly. No application code changed anywhere in this batch — every one of the five panels
already worked exactly as described; the gap was in what proved it, not in what it did. Both full
test suites ran green afterward: 489 without a database (sixteen more than before), 237 with one
(five more than before, plus the one long-standing expected failure).

**Retrieval, stage 2 — re-verify (2026-09-17).** Went back over the five panels above and checked
them against their own literal proof bar: every single fact in the design page's settings table for
each panel, not just the shorter list the original batch worked from. Found two real gaps where
something was actually unproven, not just proven under an unexpected test name: the dense-search
row cap was never checked to be passed through safely, even though the near-identical keyword-search
test already checked exactly that; and the keyword search's basic filters (which page, chunk type,
and source are allowed to match) were never exercised at all, because every test in that file
happened to call the function without a source list, so that whole branch of the code silently never
ran. Both were closed with one small, focused test each, matching the pattern already used
elsewhere in the same two files. A third case was found true but filed under an older name: the
scope-setting panel's search-speed knobs are fully proven, just by tests written before this
batch's naming convention existed — left as-is rather than renamed, since those exact test names are
already quoted in older audit documents and renaming them would make those documents wrong for
nothing gained. No application code changed. Both full test suites ran green afterward: 491 without
a database (two more than before), 237 with one (unchanged, since neither new test needed a
database).

**Retrieval, stage 3 — page-level access list, one panel (2026-09-17).** This is one panel
(`r3-acl`, "a restricted page never reaches the reranker; a group-restricted page is readable by
its members") inside a larger six-panel batch; the other five panels are being handled separately
and are not covered by this entry. The coverage sheet already marked this panel green, citing four
existing tests — but those tests only check the underlying yes/no permission function by itself,
never the actual retrieval pipeline the panel's own wording is about: whether a forbidden page's
text is ever handed to the reranker, and whether a page shared with several people (the way a
Confluence group turns into a list of individual names once it's expanded) is actually readable by
one of them. Neither fact had a dedicated test. Added two new tests that build the real retrieval
pipeline with its database calls faked out: one proves a page restricted to one person never gets
its text sent to the reranker, and never comes back in the results, for someone else asking; the
other restricts a page to three people (standing in for an expanded group) and proves one of them
gets the page back, with its text actually sent to the reranker along the way. Both tests passed
immediately, with no code changes, confirming this panel already works exactly as designed — only
the missing test was closed, not any behavior. The coverage sheet's citation for this panel was
corrected to point at the new tests instead of the old, too-narrow ones.

**Retrieval, stage 3 — a forgotten scope leaks nothing, one panel (2026-09-17).** This is one panel
(`r3-deny`) inside the same six-panel batch as the entry above; the other five panels are being
handled separately. The panel's point: if a bug ever drops the line of code that tells the database
which source a question is allowed to read, the database itself must return nothing rather than
everything — the safety net behind the app-level check. A test with exactly the right name,
`test_rls_default_deny_on_reader_role`, already existed and already proved this for an explicit
empty scope, a wrong scope, and a matching scope. But every one of those still called the
"set the scope" instruction at least once, just with an empty or wrong value — none of them
reproduced the panel's actual worry, which is that instruction never running at all. Strengthened
the existing test by adding one more check first: open a brand-new database connection as the
read-only role, skip the scope instruction entirely, and confirm the answer is still zero rows.
It passed immediately, with no code changed, confirming the safety net was already solid — only the
exact failure mode the panel describes had never been reproduced by name. The coverage sheet had
been citing a different test about a related but separate app-level check (making sure two
customers' tagged content never crosses once both scopes are actually set); corrected it to point
at the panel's own named test instead. The live version of this same check (`verify-isolation`
against a real hosted database) is a by-hand script, not a test, and was not run here — the local
database test above stands in for it, matching a note already logged for the previous panel's
neighbor in this batch.

**Retrieval, stage 3 — the read-only database role, one panel (2026-09-17).** This is one panel
(`r3-reader`, the `rag_reader` role Obi's retrieval reads through) inside the same six-panel batch
as the two entries above; the other five panels are being handled separately. The panel makes three
promises: the role can only log in and read, never create databases or roles or bypass row security;
it can read the tables it needs today, plus any table added later, without a fresh grant each time;
and the code that opens a reader connection always points at the dedicated reader address, not the
all-powerful writer one. The coverage sheet already marked this panel green, but its one cited test
only proved the "tables added later" half. Nobody had ever asked the database itself, in a test,
whether the role actually carries those five safety attributes — every other test only ever relies
on them working, never checks them directly. Likewise nobody had proven the plain "read a table that
already existed before the role was created" case, as opposed to the after-the-fact case that was
already covered. Added two new database tests for those two gaps, run against a disposable
throwaway database so they never touch the shared one other tests use: both passed immediately, with
no code changed, confirming the role has always had exactly the attributes and grants promised. The
third promise, about the reader connection pointing at the right address, turned out to already be
fully proven by three tests written earlier — so no new behavior needed proving there, just one more
small test added alongside them so this exact panel is named directly rather than only implied. No
part of the actual system changed; only test coverage was added, and the coverage sheet's entry for
this panel was updated to list all four tests now proving it instead of just the one.

**Retrieval, stage 3 — only permitted candidates move on, one panel (2026-09-17).** This is one
panel (`r3-torerank`) inside the same six-panel batch as the entries above; the other five are being
handled separately. The panel makes two promises about the hand-off from the permission checks to
the scoring model: only up to a fixed number of candidates (75) that already passed all three
permission checks move on to be scored, and the actual text for those candidates is fetched right
after, in the very same database transaction and under the very same access rules the searches
themselves used — never a second connection, and never a wider or narrower view of what the person
may see. The coverage sheet already marked this panel green, citing a real database test — but that
test only proved the permission-check half of the story, never the "at most 75" cap or the
"same transaction, same rules" hand-off; neither had ever actually been tested anywhere. Wrote two
new tests that build the real search logic with fake stand-ins for the database calls, so the exact
values passed between steps can be checked directly: one feeds in more candidates than the cap
allows, restricts one of them, and confirms the restricted one is dropped and exactly the cap's worth
of the right ones survive; the other confirms the code opens the database only once for the whole
search and that the text-fetching step is handed the identical access rules the search itself used.
To make sure these tests actually catch a real break and are not just rubber stamps, the underlying
code was temporarily broken two different ways — once removing the cap, once weakening the access
rules passed to the text fetch — and both times the new tests failed for exactly that reason, then
passed again once the code was put back. No part of the actual system was changed; only test
coverage was added, and the coverage sheet's entry for this panel was updated to point at the new
tests instead of the old one, which is now understood to prove a different, narrower part of the
story.

**Retrieval, stage 3 — groups expanded at sync time, one panel (2026-09-17).** This is the sixth and
last panel (`r3-groups`) in the same batch as the four entries above (`r3-source` is being handled
separately). The panel makes three promises about how a Confluence group restriction on a page turns
into real access control: group membership is looked up through Confluence's own group-member
endpoint, once per group, and reused for the rest of that sync run rather than refetched for every
page; a group whose membership cannot be looked up (the request fails, or nobody comes back) makes
the page closed to everyone rather than accidentally open, using a stand-in value no real person
could ever hold; and the page's stored access list ends up with exactly one row per actual person,
never more than one for the same person even if they reached the list two different ways (say, being
named directly and also being a member of a restricted group). Reading the existing tests against
these three promises, the first two were already proven thoroughly — including, importantly, a test
that checks the stand-in value for an unreachable group genuinely blocks every real person from
seeing the page, not just that the value gets saved correctly. The third promise had never been
tested anywhere: the code that saves the access list does quietly drop duplicate names before
writing rows, but nothing ever fed it a duplicate and counted the rows saved — every existing test
only checked the resulting set of names, and a set in the underlying tool used to check results
already hides duplicates by nature, so it could never have caught a miss here. Wrote one new
database test that hands the syncing code a duplicate name on purpose and counts the actual rows
saved for that page, confirming there are two, not three. It passed immediately with no code
changes, confirming the save step already worked correctly; the gap was only in what proved it. This
subagent's own copy of the shared "work is in progress" marker file was found deleted partway through
the work — a sibling subagent finishing its own panel in this same six-way batch removed it, since
several panels share that one file — and was recreated to keep going; this is a known rough edge
in running six panels at once that is not yet fixed at the tooling level, only worked around here.
No part of the actual system was changed; only test coverage was added, and the coverage sheet's
entry for this panel was updated to cite the new test alongside the ones that already proved the
first two promises.

**Retrieval, stage 3 — source row security, one panel (2026-09-17).** This is the last of the six
panels in this batch (`r3-source`), closing it out; the other five are each covered by their own
entry above. The panel's point: a question's search must only ever see rows from the Confluence
source it actually came from — no source set at all should return nothing, the right source should
return everything the reader is allowed to see, and a made-up or mismatched source should also
return nothing. The underlying database rule that enforces this already worked correctly; nothing in
the code changed. Three new database tests were added next to the existing "a forgotten scope leaks
nothing" test (itself strengthened separately by the `r3-deny` panel above, in the same file): one
confirms no source set returns zero rows, one confirms the matching source returns every row the
reader is allowed to see, and one confirms a source that doesn't match anything returns zero rows.
All three passed immediately against the current database rules. This panel's own subagent finished
its work first but deliberately held off writing this entry, since writing a shared six-panel batch's
record from only one panel's view risked getting the other five wrong — it was written here instead,
once all six panels had reported back and the batch record for `p0-s0_5-reg-retrieval-stage-3` could
be completed correctly. The coverage sheet's row for this panel is now filled in and ticked.

The next batch to protect was retrieval stage 4: the Cohere reranker, the "is the best passage too
weak" gate, and the hand-off of the top-k passages to the answer stage. Before spawning the three
subagents the plan called for, the coverage sheet was checked first, and all three panels already
showed a passing, cited test from earlier work — the three test files involved were not touched by
anything done in this session, they were already sitting in the repo, committed. Rather than trust
that at face value, each panel was read fresh from the design page and checked line by line against
what its cited tests actually prove, because a couple of earlier "yes" rows in this same sheet had
turned out to be citing the wrong test once someone actually looked. Two of the three held up exactly:
the hand-off panel's one check was fully covered by its own already-well-named test, and the "too
weak" panel's two testable checks (comparing the top score to the threshold, and never refusing on a
weak score or no candidates when the question came with an image) were both already solidly proven
by seven existing tests. The reranker panel had a real, if narrow, gap: the code retries a failed
call with a short backoff before giving up, but nothing in the test suite ever made a call actually
fail once and then succeed on the second try — the one existing test that touches retries deliberately
turns retries off to test something else instead. One small new test closes that gap: it makes the
first call return "too many requests," the second succeed, and checks that the retry happened, the
backoff delay was the expected one, and the final answer was correct. The full backend test suite was
run afterward exactly as the batch's own instructions require — 497 unit tests and 243 database tests,
one new xfail unrelated to this work, all green. One honest loose end, disclosed rather than fixed:
most of this batch's pre-existing tests aren't named after their panel the way newer tests are, only
the hand-off panel's test is. They were left alone rather than renamed, because renaming them would
make an older frozen audit document, which quotes their exact names, wrong for no real benefit — the
same call already made once before for a different panel earlier in this same file.

**p0-s0_5-reg-retrieval-stage-5 — protected the last 7 panels of "Answer" (2026-09-17).** This batch
covers the whole answer stage: building the numbered evidence block the model reads, the model call
that writes the answer, the check that strips any sentence citing a number that doesn't exist,
streaming the finished answer back to the widget and logging the trace row, refusing when nothing
survives the citation checks, the separate call that describes an attached image, and the thumbs
up/down endpoint. All seven panels were already working; this was purely about adding the tests that
pin that down, so nothing quietly breaks later. Four `obi-implementer` subagents ran at the same time,
grouped by which test file each panel would land in so no two agents edited the same file at once: one
for the evidence block, one for the answer-generation and image-analysis calls together (both live in
the same client file), one for the citation-number check, and one for streaming, the no-citations
refusal, and the feedback endpoint together (all three converge on the same two files). Between them
they added 14 new tests and attached a "which panel does this protect" note to roughly 15 tests that
already existed but weren't labeled that way. One check almost fell through the cracks: "only the
newest turn's image ever gets analyzed" wasn't proven by any of the four agents, because it fell just
outside the file each one was assigned. Caught it after they all finished and closed it directly with
one more test, rather than spinning up a fifth agent for a single check. One process hiccup, disclosed
honestly: this session didn't set up the shared "work in progress" marker file before handing out the
four jobs, the way an earlier ingestion batch learned to do — so one agent watched a sibling's cleanup
step delete the marker out from under it mid-task and had to put it back to keep going. Nothing was
lost or corrupted, but the next batch like this should set the marker up front instead of leaving each
agent to manage its own. Also flagged and left alone: one of the test files already had six unrelated
pre-existing type-checker errors (some old test stand-ins missing a method the real code requires) —
checked they were exactly the same before and after this batch's edits, then left them for someone to
clean up separately, since fixing them wasn't this batch's job. No application code was touched
anywhere — every panel's behavior already matched what the design page says. Full suite run afterward:
507 unit tests and 247 database tests, one pre-existing unrelated xfail, all green.

**Protect: The widget — 8 panels (2026-09-17).** Wrote regression tests for the 8 widget panels the
design page marks "already works": the launcher and its teaser, the chat panel's layout, the composer,
which platform the widget thinks it's in, the proxy route that adds the server key, the six-locale copy
table, the page screenshot, and how a streamed answer renders. Learned from the marker-race problem the
previous retrieval batch hit: this time the coordinating session created the "work in progress" marker
itself, in all three places a subagent's shell might look for it, before handing out any work, and took
it down itself once every agent was back — no agent had to recreate a marker that vanished mid-task.
Ran 7 agents at once, one per panel, except two panels (the chat panel's layout and the screenshot
capture) shared an agent because both live in the same test file. Two panels needed zero new tests —
the launcher's teaser timing and the screenshot's hide-during-capture behavior were already proven by
tests written earlier, just not tests that happen to be named after those two panel ids. The other six
panels got 19 new tests between them: the composer's screenshot-button attachment path and its "images
don't carry over to the next turn" rule; which platform the widget is in getting set once at mount and
sent on every request; the chat panel mounting exactly one session provider; the proxy route wiring both
its endpoints and never leaking the server key to the browser; a brand-new test file proving all six
locales have every required piece of copy; and the streamed-answer rendering for tokens, missing-URL
citations, and the refusal banner together with its hand-off link and feedback thumbs. Two real gaps got
found and written down instead of silently fixed: the composer's design text claims a 5 MB image size
limit that no code anywhere actually enforces, so no test was written for something untrue; and this
substep's own instructions said to verify with the two backend `make` commands, which turned out to
only ever run the Python test suite and never touch this frontend work at all — caught by the batch
verifier, so the real proof run afterward was the frontend test runner directly: 23 files, 182 tests,
all green. The two named backend commands were still run as instructed and are also green (507 and
247 tests). No application code changed; every panel's behavior already matched what it says.

**Protect: The widget — naming gaps closed for real (2026-09-17).** Asked to check the substep's own
literal bar again — one test per check, actually named after the panel id, not just proven somewhere —
so this pass audited every touched file by grepping for the panel-id-prefixed test names directly,
rather than trusting the "green" from the previous entry at face value. Found the bar genuinely unmet
for five of the eight panels: the launcher's two checks, one check each on the composer, which-platform,
and proxy panels, and all three of the screenshot panel's checks were correct and covered, but only by
tests that predate this batch's naming convention and don't literally carry the panel's own id in their
name. Closed all eight with one small test added alongside each existing one, using five agents running
at once, one per panel. While auditing, the grep tool itself turned up something odd: it found zero
matches in the brand-new locale-copy test file even though reading the file plainly showed the right
test names in it. Traced it to a single stray invisible character — a null byte — accidentally written
into a string inside one of that file's tests instead of a plain space, which is why command-line search
tools treated the whole file as binary data rather than text. The test still technically passed since
that byte is legal inside a string, but it wasn't what was meant and it made the file invisible to normal
searching, so it was fixed directly rather than left in. Every file touched by this pass and the last one
was then checked byte-by-byte for the same mistake; nothing else was found. Ran the full frontend suite
again afterward together with the same two backend commands as before: all three green, 191 frontend
tests now (up nine from the previous count). The 5 MB image-size gap noted in the last entry stands
unchanged — this pass was about test naming, not that open question.

**Protect: The relational database — 4 panels (2026-09-17).** Four tables sit behind ingestion and
sync — the delivery ledger, the stable per-page document row, the record of each reconciliation
sweep, and who's allowed to see a restricted page — and this pass made sure each one's existing
guarantees stay proven by tests, one agent per table working at the same time since none of them
touch the same test file. The delivery ledger needed nothing new: its two uniqueness rules and its
status list were already fully covered by three tests written earlier. Along the way that agent
noticed the design page claims the ledger records who triggered each delivery in an `actor` column,
but no such column exists in the real table — only a similar field used for logging, never saved to
the database — flagged as a question for the owner rather than fixed. The document table's existing
tests proved the behavior (one row survives every rebuild of a page) but never the two structural
rules behind it — that a page can't have two document rows, and that the reference to the page's
source is allowed to be briefly unsatisfied within one transaction — so three new tests were added
proving both directly. The reconciliation-run table's one existing test only checked the numbers a
sweep function handed back in memory, never what actually got saved to the database row itself — three
new tests now re-read the saved row after a sweep and check its scope, kind, status, and counts are
right, that a space-only sweep is tagged differently from a full one, and that a sweep which hits an
error is honestly marked failed rather than silently marked done. The page-restriction table already
had tests proving the two easy directions (a restricted page has one row per allowed person, an open
page has none) and half of the harder rule (that changing who's allowed rewrites the rows) — but
nothing proved the other half, that an unrelated update to a page leaves those rows alone when
access hasn't actually changed, so one new test was added confirming that. No application code needed
to change anywhere — every rule was already true today, this pass only closed gaps in what proved it.
Ran the two named backend commands once for the whole batch after every agent finished: both green,
507 and 254 tests (seven more database tests than before, all new).

**The vector database — the nearest 75, one panel (2026-09-17).** This is one panel (`vd-nearest`,
"the 75 pieces whose numbers are closest to the question's numbers") inside a larger eight-panel
batch protecting the vector database; the other seven panels are being handled separately by other
agents at the same time. The panel names three checks: the dense-search query orders candidates by
cosine distance and caps the result at the nearest 75, row security filters before that cap is
applied rather than after, and ties on distance break deterministically by page id. Two of the three
already had a dedicated, real-Postgres test from an earlier substep — the tie-break test and the
row-security-before-the-limit test — both re-run here and still green, so they were not rewritten.
The third had a real gap: nothing proved the `LIMIT 75` itself actually truncates a larger result set
down to the 75 nearest rows rather than an arbitrary 75 — the existing row-security test happens to
use a 75-row cap but only ever returns 60 rows, so it never exercises that boundary, and the only
other test touching the row cap is a unit-level one that just checks the SQL text, never a real
result set. Added one new test that seeds 80 chunks at 80 distinct cosine distances and runs the
real query against a local Postgres database: it checks that exactly 75 rows come back, that they
are exactly the 75 nearest of the 80 (the 5 farthest correctly excluded), and that the single nearest
chunk lands first. It passed immediately, with no code change, confirming the query already behaves
exactly as the panel describes — only the missing proof was added. The coverage-map row for this
panel was updated to note three citing tests instead of two. Ran only this file's three tests
locally (green); the whole-batch `make test-unit`/`make test-db` run happens once, centrally, after
all seven panels' agents finish.

**The vector database — the text that becomes a vector, one panel (2026-09-17).** This is one panel
(`vd-text`, "the text that becomes a vector") inside the same eight-panel batch protecting the vector
database; the other seven panels were handled separately by other agents at the same time. The panel
names three checks: the input is page title + heading path + context note + child text, composed in
that order; the result is about 400 tokens; and the verbatim child text is kept separately, for
citations. The coverage map cited exactly one pre-existing test for this whole panel with no "and
more" marker, so it was read closely first: it proved the context note is prepended ahead of the
untouched child text, but never checked that the title and heading path actually show up in the
composed string, never measured how big the result gets, and never checked that the verbatim child
text is also stored in its own column rather than just sitting at the end of one shared string.
Three new tests were added, one per check. The first builds a chunk with a distinct title, heading
path and a canned context note and checks all four pieces appear in exactly that order, ending with
the untouched child text. The second builds a real ~400-token chunk the same way the chunking code's
own tests do, runs it through the same composition step with the AI-written note turned off (so it's
fast and deterministic), and checks the total lands between 400 and 450 tokens once the short title
prefix is added — "about 400" once you count the small addition on top. The third runs the real
ingestion pipeline against a fixture page on a local Postgres database and checks that every stored
chunk's embedded text ends with its own separately-stored citation text, unchanged, while the two are
not simply identical — proving the original wording is both kept whole and kept in its own place, not
just glued onto the end of a longer string. No code changed; all three checks were already true, this
only closed the gap in what proved them. The coverage-map row was updated to list all three new
tests across both files. Ran only this panel's three new tests plus the seven existing tests in the
same file, unaffected — all green, against a real local Postgres pinned explicitly, never the shared
project one; the whole-batch `make test-unit`/`make test-db` run happens once, centrally, after all
seven panels' agents finish.

**The vector database — the keyword side, one panel (2026-09-17).** This is one panel (`vd-keyword`,
"the word index that lives next to the vector and catches exact strings the numbers might miss")
inside the same eight-panel vector-database batch; the other seven panels were handled separately by
other agents at the same time. The panel names three checks: the `tsv` column is built from
`to_tsvector('english', title || heading path || text)`, a GIN index named `ix_chunk_tsv_gin` exists
over it, and a keyword query OR-joins the question's words and ranks matches by `ts_rank`. The one
pre-existing test that cited this panel only proved a much weaker claim — that a real word ("access")
in an indexed page's text was findable at all — not the exact construction formula, not the index's
existence, and not the OR-join/ranking shape. All three checks got their own new, dedicated test:
one that recomputes each real child chunk's tsvector fresh from Postgres and asserts it matches the
stored one byte-for-byte, one that checks `pg_indexes` for the named index using the gin method over
the `tsv` column, and one that seeds three chunks (one with only the word "alpha", one with only
"beta", one repeating both) and calls the real keyword-search function with the question "alpha
beta": both single-word chunks came back (proving the words are OR-joined, since an AND query would
have matched neither on its own) and the chunk repeating both words ranked first (proving the order
comes from `ts_rank`, not insertion order). All three passed immediately with no code change — the
column, the index and the query already worked exactly as the panel describes; only the missing
proof was added. One of the three tests deliberately re-proves, under this panel's own name, a
construction formula an earlier substep's `i3-tsv` panel already proved under its own name for the
same underlying code — the same "two panels, two dedicated names" choice this batch already made
for a few other panels, rather than leaving the newer panel's check unproven by name. The
coverage-map row for this panel was updated to name all three new tests. Ran only this panel's three
new tests plus the eleven pre-existing tests already living in the same two files (fourteen passed,
pointed explicitly at the local Postgres so as not to repeat an earlier incident where a direct test
run reached toward the live database); the whole-batch `make test-unit`/`make test-db` run happens
once, centrally, after all seven panels' agents finish.

Closed two more panels from the same "Protect: the vector database" batch together, since the
coverage map cited the same one test for both: the HNSW index (`vd-hnsw`) and row security covering
vectors too (`vd-rls`). That shared test only proved the reader database role can resolve Postgres's
`halfvec` type — it said nothing about the index's own name, its halfvec-and-cosine shape, its build
settings, or whether a hidden row's vector can ever sneak into a nearest-neighbor search result.
Wrote six new tests, three per panel, each reading the real local Postgres catalogs directly rather
than trusting the Python model code: one confirms the index is named exactly
`ix_chunk_embedding_hnsw`; one confirms it casts to `halfvec` with the cosine operator class above
pgvector's 2000-dimension cap (this test suite deliberately runs at a much smaller 256-dimension
embedding for speed, which falls under that cap and builds the plain, non-halfvec branch instead —
an already-known, already-documented trade-off elsewhere in this repo, not a new problem, so the
test checks whichever branch actually applies rather than assuming the production number); and one
confirms the build settings are exactly m=16, ef_construction=200. For row security: one confirms
the vector column really does live on the `chunk` table itself; one confirms both the source and
knowledge-scope security rules are registered on that table for every read; and the last one seeds
two rows — one on an allowed source, one on a forbidden source placed deliberately closer to the
search query than the allowed one — and proves that querying as the read-only database role, with a
raw hand-written nearest-neighbor query rather than the app's own retrieval code, still never
returns the forbidden row. All six checks were already true; nothing in the application changed,
only the missing tests were added. The coverage-map rows for both panels now name their own three
tests each. Ran this file's nine tests (six new plus three already there) against the local
Postgres — all green; the whole-batch test run happens once, centrally, after all seven panels'
agents finish.

**The vector database — vectors swap with the page, one panel (2026-09-17).** This is one panel (`vd-swap`, "new chunks and vectors go in switched off, one transaction flips the switch, the old ones go dark at once") inside the same eight-panel batch protecting the vector database; the other seven panels were handled separately by other agents at the same time. The panel names three checks: new chunks and their vectors are inserted inactive, one transaction flips the version pointer, and the old vectors go inactive at once (leaving the search index) while their rows are only deleted once two more versions have superseded them. The one pre-existing test citing this panel proved the swap's end result — exactly one active version, with every active chunk belonging to it — but never separately proved any of the three checks by name. Three new tests were added, one per check. The first attaches a small SQLAlchemy hook around a rebuild that watches every new chunk row the moment it is about to be written, and confirms every single one already carries "inactive" at that moment — before the switch that turns the new version on ever runs. The second forces a failure to happen right after the switch has already run inside the job's own database transaction, but before that transaction is allowed to commit, and confirms the old version and its chunks are still exactly as they were — proving the old-off and new-on halves of the switch are genuinely one all-or-nothing step, not two separate writes that could land apart. The third rebuilds a page once and checks the previous version's chunk rows directly: same rows, same vectors, but flipped off at once — while confirming (without re-testing it here, since another panel already owns and proves this in its own tests) that those rows are not deleted yet, only after two further rebuilds age them out. All three passed immediately with no code change — the swap already worked exactly as the panel describes; only the missing proof was added. The coverage-map row for this panel was updated to name the new tests. Ran only this file's own tests (20 passed, plus one pre-existing, unrelated expected-failure test unaffected) against a real local Postgres pinned explicitly, never the shared project one; the whole-batch `make test-unit`/`make test-db` run happens once, centrally, after all seven panels' agents finish.

**The vector database — chunk.embedding, one panel (2026-09-17).** This is one panel (`vd-column`) inside the same eight-panel batch protecting the vector database; the other seven panels were handled separately by other agents at the same time. The panel names three checks: the embedding column is a nullable vector(3072); only child chunks ever carry one (never parents); and it lives on the same row as the chunk's text, tags, scope state, and keyword index. All three already had dedicated, panel-id-named tests from an earlier batch, but reading them showed the "same row" test only checked the tags and keyword-index columns alongside the embedding — it never actually looked at the row's text columns, and "scope state" isn't its own column at all (it's the same thing as "tags," a fact already noted elsewhere in this log). Rather than write a new test for one already-covered check, the existing test was strengthened with two more assertions so it genuinely checks every named field on the same row. Nothing about the check itself was wrong — the code already puts all these fields on one row — only the test's coverage was thin. No application code changed; ran the file's three tests against local Postgres, all green.

**The vector database — the question vector, one panel (2026-09-17).** This is one panel (`vd-question`) inside the same eight-panel batch protecting the vector database; the other seven panels were handled separately by other agents at the same time. The panel names three checks: a rewritten question is embedded through the exact same model used for the page's own child text; that embedding is always exactly one vector of 3072 numbers; and it's compared against child (never parent) vectors using cosine distance. Two of the three checks were already proven, but only by borrowing another panel's tests under a different name; the third — that the comparison specifically targets child vectors by cosine distance — had never been pinned down on its own, only implied by a different panel's test of the SQL text rather than a real result. Three new tests were added, one per check, confirming: retrieval and ingestion build their embedding client the exact same way; a single question always comes back as one 3072-number vector; and the nearest-neighbor search orders results using the cosine operator against child rows only. All three checks were already true; nothing in the application changed, only the missing proof was added, and the coverage-map row for this panel now names all three new tests. Ran the touched files' tests directly (no database needed, this is unit-level) — 18 passed, all green; the whole-batch `make test-unit`/`make test-db` run happens once, centrally, after all seven panels' agents finish.

## p0-s0_5-reg-code-map · Protect: Code map — 5 panels (2026-09-18)

Wrote the regression net for the five "Code map" panels that already work today — `cm-root`,
`cm-docs`, `cm-contracts`, `cm-tokens`, `cm-infra` — so later phases that change code next to them
can't silently break them. One obi-implementer subagent per panel ran in parallel, each writing to
its own new test file (no shared files, no collisions); the shared docs (coverage-map rows, the
batch section, the ledger and this log) were all written centrally afterward by a single writer.
Every subagent read its panel's checks from `tools/panel.py` and added one deterministic test per
check, named after the panel id.

14 new unit tests total: cm-root (3 — settings read, reader engine fails closed without
`DATABASE_READER_URL` in production, HybridRetriever built with embedder/reranker/scope flag),
cm-docs (3 — ADRs 0001/0002/0003 name the stack, retrieval core, and feature boundaries),
cm-contracts (3 — chat.yaml is the source of truth, the six chat types are defined, the note/iframe
artifacts are present and wired), cm-tokens (2 — the design tokens hold colors/type/Tailwind mapping
and encode a light theme with an indigo accent and Inter), and cm-infra (3 — the pgvector image is
pinned, the compose is the local/test DB, and "production is Supabase" is a documented claim). No
production code was touched anywhere — every check was already true; this batch only proved it.

Several honest disclosures came out of writing the tests, none of them a failing test: cm-root's
fail-closed raise actually lives one module down and the fail-open set is `{local,test,dev,ci}` not
just "local"; ADR 0002 spells out "Reciprocal Rank Fusion" and never uses the acronym "RRF"
(asserted the full phrase); the two artifacts the cm-contracts panel still labels "Planned" already
exist and are wired (the design page's label is stale); the cm-tokens values are hex/font stacks
rather than the literal words "indigo"/"light"/"Inter" (asserted the values, mapped them in the
test); and the cm-infra image is pinned by digest as `pg16` with 0.8.5 only in a comment, while
"production is Supabase" stays an open/red claim in decisions.md rather than a verified fact — the
test asserts where it's written, not that it's true. All disclosures are recorded in the ledger and
the coverage-map batch section for a future design-review pass.

Verified centrally after all five returned: `make test-unit` 530 passed (up from 516, the 14 new
tests), `make test-db` 286 passed + 1 xfailed (unchanged — every new test is unit-level), and `make
boundaries` clean. All five coverage-map rows are filled and ticked; cm-root and cm-contracts were
repointed from real-but-not-panel-named tests to the new dedicated `test_cm_*` files so every
citation is literally named for its own panel. Nothing is committed yet.

## p0-s0_5-reg-system-overview · Protect: System overview — 3 panels (2026-09-18)

Wrote the regression net for the three "System overview" panels that already work today —
`ov-confluence` (Confluence, the source of truth), `ov-corpus` (the Postgres corpus), and
`ov-widget` (the Obi widget) — so later phases that change code next to them can't silently break
them. One obi-implementer subagent per panel ran in parallel, each writing to a different test file
(the Confluence client tests, the db-index tests, and the frontend chat tests — no shared files, no
collisions). The shared docs (the three coverage-map rows, the batch section, the ledger and this
log) were written centrally afterward by a single writer to avoid a three-way write race. Every
subagent read its panel's checks from `tools/panel.py` and added one deterministic test per check,
named after the panel id.

Nine new tests total, three per panel. `ov-confluence` got three unit tests over an `httpx`
MockTransport: what the client reads (page meta, storage-format body, labels, restrictions,
attachments), which API version each endpoint uses, and the client's timeout / 5xx-retry /
circuit-breaker-after-five-failures behaviour. `ov-corpus` got three database tests that query the
live Postgres catalog (never `models.py` text), reusing the index-test file's own disposable-engine
fixture: the engine is PostgreSQL 16 with pgvector and full-text search, the dense index is HNSW
cosine m=16/ef_construction=200, and the keyword index is GIN over tsvector. `ov-widget` got three
vitest+jsdom tests: the widget takes its scope from the mount config, it calls its own same-origin
`/api/chat` proxy route rather than the automation backend directly, and the proxy injects the
server key and streams the answer back without the browser ever seeing the key. No production code
was touched anywhere — every check was already true; this batch only proved it.

Three honest disclosures came out of writing the tests, none of them a failing test. The
`ov-confluence` panel's "APIs used" line lists labels under v1, but the live client actually reads
labels from the v2 pages endpoint (`/api/v2/pages/{id}/labels`) — the test asserts the real v2 path
and flags the drift for a future design-review pass (only the attachment *download* link is the v1
path the panel names). The `ov-corpus` dense-index test branches on the model's configured dimension
because the test suite pins `EMBEDDING_DIM=256`, under pgvector's halfvec threshold, so a stock
`make test-db` builds the plain `vector_cosine_ops` branch rather than the production
`halfvec_cosine_ops(3072)` branch — the same nuance already disclosed for `r2-indexes`/`vd-hnsw`.
And the three `ov-widget` steps were already indirectly proven under adjacent panel ids
(`w-scope`, `r1-proxy`, `w-proxy`); dedicated `ov_widget_*` tests were added anyway per the
substep's "one test per check named after its panel id" rule, none a verbatim duplicate. Also noted:
the frontend `pnpm lint` isn't wired in this repo (`next lint` drops into an interactive setup
prompt), pre-existing and not introduced here; frontend typecheck is clean.

Verified centrally after all three subagents returned: `make test-unit` 533 passed (289 deselected),
`make test-db` 289 passed + 1 xfailed (pre-existing, unrelated), and the ov-widget frontend vitest
suite green separately (29 files / 236 tests passed). ruff/pyright clean on both touched backend
files, tsc clean on the three touched frontend files. All three coverage-map rows are now filled and
ticked, `ov-confluence` repointed from its old group-restriction test to the new dedicated
`test_ov_confluence_*` tests so every citation is literally named for its own panel. Nothing is
committed yet.

## 2026-09-18 · The 0.5 questions answered and the plan amendments implemented

The owner amended the action plan (0.1.1, the 0.5.3 widget batch, 0.6.1, 2.4.3, 3.2.6, 7.1.1) and
answered every open question the 0.5 regression phase had raised. This entry implements those
answers. First the verification that prompted it: a panel-by-panel reconciliation of all 91 built
panels found the net is real — every panel has a filled, green coverage-map row backed by a test
that exists on disk, no missing tests and nothing faked green — with only smaller issues to fix.

The freeze gate (0.1.1) was finally done, honestly and late. The plan's starting commit is
`bf7fece` (2026-09-14); the tag and branch `pre-target-2026-09-14` were placed on that commit, not
on today's HEAD, because a tag on today's commit would be a lie about where the plan began. The
tag's test state was captured in a fresh worktree and written to `docs/snapshot/README.md`: 428
tests pass and 166 database tests error for lack of a provisioned database — recorded as-is rather
than spinning up Postgres to produce a prettier number. The tag and branch are local only; there is
no git remote yet.

Two design-page-vs-code drifts were closed the way the owner chose. For r1-limits, the design page
claimed a trusted-proxy X-Forwarded-For rate-limit fallback that the code never had; the owner
decided to drop the claim and keep `request.client.host`, since the real proxy hop count is a
hosting fact fixed later in 7.1.1 and a guessed count would make the limit spoofable. The panel
today-line was corrected and a regression test now pins that a forged X-Forwarded-For header changes
nothing; the `TRUSTED_PROXY_HOPS` setting (default 0) belongs to substep 3.2.6. For r1-small, the
design page said the small-talk greeting comes from Haiku while the code used the answer model; the
owner said it does not matter and could be Haiku, so the design page wins — `generate_small_talk`
now runs on `settings.routing_model` (Haiku) while grounded answers keep the answer model, with the
test rewritten to assert the split.

0.6.1 was implemented: `docs/plan/decisions.md` is now the one canonical decisions file, carrying
the fifteen settled calls (2026-09-14), the four calls added on 2026-09-18 (the version-only body
fetch, the never-garbage-collected failed version, the widget jsdom test level, and the r1-limits IP
key), and four open lines including the new trusted-proxy-hops default. This reversed an
earlier-in-session move of that list into the regression folder; the regression file now defers to
the canonical one. The 0.5.3 widget batch dropped to seven panels because w-scope is `change`, not
built — a Close item for it was added to the Phase 3 stage 1 close list, and the widget test level
was relabelled jsdom, with `make test-ui` run once (the mount smoke passes). Four cited tests that
protected a panel but named it nowhere gained a panel-id docstring, satisfying the naming rule.

The questions the owner could not answer yet — a shared auth service to sign the note, a real
platform signing key, a real per-person identity flow, and the four missing ADRs for cm-docs — were
written into `docs/future-ideas.md` as deferred, blocked-on-owner items rather than left as silent
gaps. One thing was re-verified and found still open: the `final_docs/` versus `docs/Final_docs/`
path drift the owner thought was fixed is not — the action plan still points at
`final_docs/0.3-synopsis-of-today/` and `docs/design/…` paths that do not exist on disk, which
should be corrected in a dedicated pass.

Verification: `make boundaries` clean, `make test-unit` 535 passed (up from 533 by the two new
tests), `make test-ui` 1 passed, and ruff/format/pyright clean on every touched backend file.
`make test-db` was not re-run because no database-level code changed. Nothing is committed yet.

## p4-s4_2-7 · 4.2.7 · The composer image cap (2026-09-18)

The owner confirmed decision w-composer-images and asked to build it now, so the composer's image cap moved from the old 4-images / 5 MB limit to at most 3 images per turn, each at most 3 MB. There was no build substep for it — the composer already exists and Phase 4's 4.2.x batch covers the frame/loader/bridge, not the composer's caps — so a new substep p4-s4_2-7 ("The composer image cap") was added to the action plan and pulled forward from Phase 4 during the 0.5 freeze, with the owner's go-ahead.

Backend: the two Settings defaults dropped to 3 and 3_000_000 (decimal 3 MB), with the comment updated to cite the decision. The /chat endpoint already rejected over-limit turns with a 400 on every turn (not just the newest), and the widget proxy already forwards that 400 as-is, so no endpoint or proxy code changed — only the cap values did.

Frontend: composer.tsx now caps at 3 and adds a per-image byte check (MAX_IMAGE_BYTES = 3_000_000) that refuses an oversized image before it is ever attached or sent, and it shows a user-facing error instead of silently dropping extras. Two new i18n strings (imageTooLarge, imageTooMany) were added across all six locales; the error renders as an accessible alert line using the semantic text-danger token.

Tests were written first and failed for the right reason: a new backend settings-default test (asserting 3 / 3_000_000, which failed at 4) and two composer tests (the old "caps at 4 and ignores extras" test rewritten to expect cap 3 plus the limit error, and a new oversized-image test). After the change all passed: composer 17/17, settings 8/8, the full backend unit suite 536 passed, the full web suite 237 passed, tsc exit 0, boundaries clean, ruff/pyright clean on the touched backend files.

Security: this is an LLM-CALL surface (the vision call's abuse control). The change strengthens C3 (input validation — tighter caps, still enforced server-side on every turn with a 400) and C10 (cost/abuse — a smaller cost surface). C6 image-byte PII redaction remains the pre-existing, disclosed gap (ADR-0009; the composer shows the imageDisclosure). The new client-side byte check is a UX nicety, not a security control — the authoritative enforcement stays the backend 400, which was preserved as defense in depth.

Deviations worth naming: the per-panel Playwright browser test is deferred to Phase 4 proper (widget-test-level decision), so coverage here is jsdom component plus backend unit; next lint cannot run headlessly in this environment (interactive prompt), a pre-existing condition, so lint was not re-run (tsc and vitest both pass); brief.py was run under the automation venv python because bs4 is absent from the system python3; and the hardcoded color and px literals the fe token-lint flags in composer.tsx are the file's pre-existing pixel-exact styling, untouched by this change. Nothing is committed yet.

## ci-tiktoken-core · Make tiktoken a core dependency (fix the first CI run) (2026-09-18)

The first-ever CI run (PR #3) fired end-to-end — proving the CI path works — but went red on four tests in test_chunking.py and test_contextualizer.py. The failures were not from substep 4.2.7 (its backend and composer tests passed on CI too); they were exact-token-count assertions (child.tokens == 400, parent/child counts, overlap) that only hold under tiktoken.

Root cause: tiktoken was an optional dependency (the `tokenizers` extra). CI installs only `.[dev]`, and the 0.5.1 Makefile/CI split had dropped the `--extra tokenizers` that the freeze-time proof used, so the runner had no tiktoken and TokenCounter fell back to its char/word heuristic — producing 399 instead of 400 and different chunk splits. Locally tiktoken was present (0.13.0), which is why the same tests were green here.

The owner confirmed tiktoken is the intended tokenizer, so the fix makes it a core dependency (moved tiktoken>=0.8 from the optional extra into [project].dependencies), ensuring production, CI and local all count tokens the same way. The redundant `tokenizers` extra is kept so the documented `--extra tokenizers` command still resolves. uv.lock was refreshed.

Verification: the four previously-failing tests pass locally (TokenCounter().backend reports "tiktoken"). The real proof is the CI re-run on this push, since tiktoken cannot easily be removed locally to reproduce the red. Production does not exist yet (staging only, per decision live-0.5.3-cm-infra), so switching the tokenizer backend has no live index to re-embed. Nothing else changed.

## Session maintenance — .env DB-routing, action-plan path drift, 3 ADRs, and CI green (2026-09-18)

Alongside substep 4.2.7 and the tiktoken CI fix (their own entries above), this session cleared four owner-raised items that are NOT action-plan substeps, so they are narrated here and kept in their canonical homes rather than forced into the ledger as substep entries.

.env DB-routing (option b): `make test` and `make migrate` now pin the local DB URL the way `test-db` already does, so bare targets can no longer reach live Supabase. `reingest` stays live-by-design and `eval` still inherits `.env` by design (it needs a populated store). Recorded as resolved in future-ideas.md. Commit 923294d.

Action-plan path drift: the action plan referenced a pre-rename doc layout, so 51 stale references were rewritten to their real docs/Final_docs/ locations. No-target and root-level references were deliberately left and documented in the commit: the repo-root final_docs/0.5-regression-tests/ (correct as-is), final_docs/1.1-move/, docs/archive/, docs/synopsis/, docs/release/, docs/embedding/datahub.md, and the 0.3-synopsis README refs (the renamed dir has no README). Commit cefc961.

Four missing ADRs (cm-docs): three were written — ADR-0015 (change-detection fingerprints), ADR-0016 (scope-state materialized as tags, no separate column), ADR-0017 (edge-token verification). The fourth, label-gated ingestion, was deliberately NOT written: the shipped code contradicts never-bend rule #5 (there is no published+tag indexing gate; deactivation is driven by Confluence status and loss of source-scope root coverage, not by knowledge-scope tag loss; `classified` is a forbidden config-validation slug, not a page-delete trigger). That code-vs-design conflict is recorded as decision-needed in decisions.md (live-0.5.3-cm-docs) and future-ideas.md (cm-docs-adrs); the owner chose to just note it for now, so no code or design-page change was made. Commit 7f08f2a.

CI outcome: PR #3 (github.com/vansteenbergenmatisse/Obi_v1/pull/3) now passes end-to-end — the obi four-level check is green (2m27s, run 35345743740) after the tiktoken fix. This is the first time CI has run and passed on this repo. The first run (35345037971) went red on 4 chunk/token tests for the tiktoken reason above, not for anything in 4.2.7.

## Doc reconciliation after the 4.2.7 / CI work + a 6-item verification (2026-09-18)

The owner asked to (a) update every doc that should reflect this session's work and (b) re-verify a 6-item 0.5 checklist. The verification grid: tag+branch exist and the frozen tag's recorded build proof holds (428 passed / 166 no-DB errors, not re-run fresh); the 0.4 delta + design-page corrections are in place (54 correction rows); decisions.md is populated (39 rows); the test-writer break→fail→fix→pass proof exists (substep 0.2.8) and was re-demonstrated by 4.2.7's own tests; CI is green and the required check is live-confirmed. Two came back partial: the 0.3 "ten synopses + test/infra inventories" are NOT merged under one dir — the ~10 per-area synopses live in docs/Final_docs/0.3-code-vs-design-audit-2026-09-14/ and the two inventories in docs/Final_docs/0.3-synopsis-2026-09-16/, and the stated path 0.3-synopsis-of-today/ no longer exists; and "every regression item ticked" is true for the in-repo suite but six needs-live rows are deliberately red/deferred (owner-acknowledged in decisions.md).

The verification surfaced stale docs, which were then updated. The design page's r1-limits Images row and a summary-table image row were corrected from "4 per turn, 5 MB" to "3 per turn, 3 MB" to match the code shipped in 4.2.7, and the brief was regenerated. decisions.md: the w-composer-images row is marked implemented (substep 4.2.7). The coverage-map cm-docs row (which still said "no such ADR exists") was annotated to note ADR-0015/0016/0017 are now written. The ledger's open "w-composer 5 MB / count" Need-from-you item got a dated resolution line pointing at 4.2.7. ci-gate-proof.md gained an addendum recording the first real end-to-end CI run on PR #3 (run 35345037971 red on the tiktoken gap → fix → run 35345743740 green), with branch protection re-verified live.

A more important find during the audit: ADR-0016 (scope-state materialized as tags, no column), written earlier this session, overstated its case. The design page targets a scope_state ENUM (ok/conflict/classified/unlabeled) and a fuller classification model on panels i2-labels/i2-gone/tg-classified that the code does not build at all (grep-verified: no enum, no column, none of the four state values), and no prior ADR — including ADR-0011 — ratified using tags instead of the enum. So ADR-0016 documents an unratified code-vs-design divergence, the same delta family as the deliberately-unwritten label-gated-ingestion ADR. ADR-0016 now carries an explicit open-reconciliation caveat, and docs/plan/delta.md (previously _pending_) now logs three rows for this delta (i2-labels scope_state enum, i2-gone/tg-classified deactivation+classified, and the rule-#5 index gate). Per the owner's earlier "just note it" call, no code or design target was changed for it.

Two items were deliberately left and are flagged rather than silently changed: the w-proxy body-cap of 30 MB (design + brief) is code that was NOT changed this session, so its now-loose "four 5 MB images" rationale was left as-is (tightening the body cap to match 3×3 MB would be a code change and the owner's call); and merging/renaming the split 0.3 synopsis dirs into one is a doc-restructuring decision left for the owner.

## Merged the two 0.3 directories into one (2026-09-18)

Follow-up to the verification grid's item 2 (which had come back partial). At the owner's request the two 0.3 directories were consolidated. `test-suite-inventory.md` and `infrastructure-inventory.md` were `git mv`'d from `docs/Final_docs/0.3-synopsis-2026-09-16/` into `docs/Final_docs/0.3-code-vs-design-audit-2026-09-14/`, which already held the ten per-area code-vs-design synopses. That directory is now the single 0.3 home: ten synopses + the test-suite inventory + the infrastructure inventory, all together.

The audit dir was chosen as the survivor because its per-file synopses (widget.md, rag_agent.md, …) are cited by exact filename ~31 times across the append-only ledger and the frozen 0.4-design-review docs; moving them would have broken historical links I may not rewrite. Moving only the two inventory files touched far fewer references. The old `0.3-synopsis-2026-09-16/` directory is retained as two redirect stubs (`README.md`, `test-suite-inventory.md`) so the append-only ledger (lines 68, 75) and the frozen `0.4-design-review/plan-corrections.md` reference still resolve, rather than editing append-only history to repoint them. Editable references (the action plan, the `docs/Final_docs/README.md` index, and `coverage-map.md`) were repointed to the merged location; both dir READMEs now describe the merge. No synopsis or inventory content was altered — only their location.

## 1.1.1 · Move the folders — frontend / backend / knowledge-base (2026-09-18)

Phase 1 begins: the code was restructured into three top folders that say what each part is — `frontend/` (was `apps/web`), `backend/` (was `apps/automation`), and a new `knowledge-base/` holding the DB `schema/` (models, roles, policies), `migrations/` (the alembic tree + ini), `config/` (the tag list), `seed/` (the curated seed script) and `local/` (the pgvector compose). The point is to reach the final layout so every later change lands in it and nothing moves twice, and eventually to split the three into separate repos. It was done as one `git mv`-based restructure: 404 renames plus the config/prose files that name a path, plus two new files. The proof is the Phase-0 regression suite: `verify-before.md` and `verify-after.md` in `final_docs/1.1-move/` show the behavior levels (536 unit, 289 db with 1 xfail, 1 e2e, the 237-test frontend jsdom suite, and eval) identical before and after; the break-it check confirms the move is load-bearing (reverting one import to the old `app.platform.db` path fails collection with `ModuleNotFoundError`, restoring it passes).

The exploration up front used a dozen parallel read-only agents to inventory every file that names an old path and to map what each folder does; the actual move and edits were done by one hand, sequentially, so the "renames-only" `git diff -M` stays provable. The full inventory and the honest list of what changed vs the plan text live in `final_docs/1.1-move/inventory.md`.

The move was not the pure rename the spec text imagined, and the deviations are recorded rather than hidden. The biggest: the DB layer imported the backend's own config (`from app.platform.config import get_settings` in `engine.py` and `models.py`), so moving it as-is would have made `knowledge-base` depend on `backend` — exactly what the 1.1.2 one-way rule forbids. With the owner's go-ahead (the "self-contained schema settings" option), a small `knowledge-base/schema/settings.py` now reads the four DB-relevant values (`database_url`, `database_reader_url`, `env`, `embedding_dim`) from the same env vars and `.env` files the backend reads, so the two never diverge (verified live: `EMB_DIM` resolves to 3072 from `.env`, and to the test 256 under the suite's `conftest`). That settings reader is deliberately uncached: the DB engine is already cached, and leaving the settings uncached means the existing test fixtures — which clear the engine caches after pointing `DATABASE_URL` at a per-test database — just work, without any test needing to know a settings cache exists. That single decision is what turned an 84-test database failure back to green.

Other necessary edits: the db tests moved to `backend/tests/schema/` (kept in the collected suite rather than orphaned in knowledge-base); repo-root `parents[N]` path math dropped one level everywhere it reached past the old `apps/automation` into the repo root (the tag-list path also gained its new `knowledge-base/config` home), and the frontend's two file-reading tests had their `../` depth and target adjusted; `alembic.ini`/`env.py` were repointed at `schema` and read the URL from the new settings, so migrations run from `knowledge-base/migrations` with no `app` on the path; the backend depends on the schema package as an editable path dependency (not a uv workspace, to keep the single `backend/.venv` and pyright's `venvPath` unchanged), with `schema` pinned first-party in ruff so import order stayed stable. Bringing the touched files clean under ruff actually lowered the whole-repo counts (45→19 ruff errors, 11→0 unformatted; pyright unchanged at 57) — no count rose. Two things were intentionally left: the design page, action plan, ledger and other authoritative or append-only docs still name the old paths and were not rewritten (the "empty grep" proof is therefore over code/config only), and one self-deleting migration note at `CLAUDE.md:55` stays until substep 1.1.3 rewrites the structure section. The work is complete and fully verified but not yet committed — the commit and PR wait for the owner's go-ahead.

## 1.1.2 · One dependency direction (2026-09-18)

With the folders in place, the second half of the restructure adds the checker that keeps them honest: the dependency arrow may only point `frontend → backend → knowledge-base`, never back. Rather than write a new tool, the existing ADR-0003 feature-boundary checker (`backend/tools/check_feature_boundaries.py`) was extended with a second, repo-root pass: a small data table names the forbidden imports per Python folder (knowledge-base must not import `app`/`features`/`platform`/`shared`; backend must not import `frontend`), and a lightweight regex scans the frontend's TypeScript import specifiers so none reaches into `backend/` or a `.py` file. The four original intra-backend feature rules are untouched and still run. Because 1.1.1 already decoupled the DB layer from the backend's config, the tree was clean the moment the rule was switched on.

Four tests in `backend/tests/tools/test_boundaries.py` prove it — one per rule, each writing a rule-breaking temp file into the real folder and asserting the checker fails and names that file, plus a clean-tree positive case. The checker is now wired into `make test-unit` (via a `boundaries` prerequisite), so a wrong-way import fails the unit level and, because CI runs `make test-unit`, fails CI too — previously the checker only ran in `make check` locally. The CI collected-test floor was bumped 621→625 for the four new tests (830 now collected). `make test-unit` is green at 540 passed; the break-it check confirmed the rule bites (neutering the frontend→backend detection reddened its test, restoring it went green).

The decision of record is a new ADR-0018 (per the rule that changing an ADR needs a new one); ADR-0003's stale `apps/automation` paths were corrected to `backend` in passing. Finally, since both 1.1.1 and 1.1.2 are green, the `sc-kb` panel was flipped from "change" to "built" — that flip was the whole content of the Phase-4 `close: One knowledge base` item, so it is done early here rather than left as a stale status. Like 1.1.1, the work is verified but uncommitted, pending the owner's go-ahead to commit both substeps.

## Consolidated the two final-docs directories into one (2026-09-18)

The repo had a confusing pre-existing split: the capital-F `docs/Final_docs/` (ledger, progress-log, the design-page + action-plan HTML, the brief, and phases 0.2–0.4) and a separate lowercase root `final_docs/` that held only the newest phase evidence (`0.5-regression-tests/`, and the `1.1-move/` records added this session). At the owner's request this was consolidated into **one home, `docs/Final_docs/`** — chosen as the survivor because the tooling (`panel.py`/`brief.py` design-page discovery), the `agent_guard.py` write-guard (`^docs/Final_docs/`), and ~34 of the 36 layout references already point there, so the low-risk direction was to move the two evidence folders in rather than relocate everything out.

`0.5-regression-tests/` was `git mv`'d and `1.1-move/` (still untracked) was plain-`mv`'d into `docs/Final_docs/`; the empty root `final_docs/` was removed. Editable references to the lowercase `final_docs/` path were repointed to `docs/Final_docs/` (CLAUDE.md's "single home for 0.5" line, `docs/plan/decisions.md`, `docs/future-ideas.md`, `docs/snapshot/README.md`, the action-plan HTML, and the moved folders' own internal cross-references). No tool, guard, or code path changed (they already targeted `docs/Final_docs/`), and `make test-unit` stayed green at 540.

Two append-only files were deliberately NOT edited: `ledger.md` and `progress-log.md`. The 1.1.1 and 1.1.2 ledger entries therefore still name the records as `final_docs/1.1-move/{inventory,verify-before,verify-after}.md`, and older entries name `final_docs/0.5-regression-tests/`; **those paths are now `docs/Final_docs/1.1-move/…` and `docs/Final_docs/0.5-regression-tests/…`** — this note is the remap rather than a rewrite of history (the same discipline used for the earlier 0.3-directory merge).

## 1.1.1-fix · knowledge-base gets its own standalone test suite (2026-09-21)

The 1.1.1 move left one loose end, recorded openly in its own ledger entry: the schema and migration tests were parked in `backend/tests/schema/` "to stay in the collected suite" rather than moved next to the code they cover, so `knowledge-base/` had no tests of its own. This follow-up fix closes that gap without weakening the 1.1.2 one-way boundary rule (nothing under `knowledge-base/` may import `app`, `features`, `platform` or `shared`).

All ten files were `git mv`'d into a new `knowledge-base/tests/`. Two were already boundary-clean: `test_models_constraints.py` moved verbatim, and `test_s_anon_public_grant.py` needed only its `_KB_ROOT` path recomputed. The other eight imported `from app.platform.config import get_settings`/`Settings` — moving those as-is would have broken `make boundaries` — so each was swapped to the knowledge base's own `schema.settings.get_kb_settings`/`KbSettings`, the same settings object production `schema/engine.py` and Alembic `env.py` already use. The risky one, `test_engine_reader_role.py`, monkeypatches the engine module's `get_settings` and asserts both the offline-env writer fallback and the `ReaderRoleMisconfiguredError` fail-closed path; because `KbSettings` exposes exactly the fields the engine reads (`env`, `database_url`, `database_reader_url`, `is_offline_env()`), all eleven cases pass unchanged — no assertion was altered.

Two honest, disclosed adaptations. First, `_KB_ROOT` path math: six files computed the repo layout as `parents[3] / "knowledge-base"` on the assumption they lived at `backend/tests/schema/`; from `knowledge-base/tests/` the knowledge-base root is simply `parents[1]`, so each was recomputed. Second, `get_kb_settings()` is deliberately uncached (it re-reads the environment on every call), so the ten `get_settings.cache_clear()` calls the five migration/index db-fixtures made — a relic of the backend's lru_cached settings — were removed; the lru_cached `engine_mod.get_engine.cache_clear()` calls stayed. Behavior is identical: the Alembic `env.py` `get_settings()` sees each fixture's per-test `DATABASE_URL` directly.

The knowledge base now stands alone. Its `pyproject.toml` gained `alembic` as a real dependency (its migrations project needs it, not just a borrowed backend venv), a `dev` extra with pytest, and a `[tool.pytest.ini_options]` block (testpaths, the `db` marker, `--strict-markers`) mirroring the backend. A standalone `knowledge-base/.venv` is created with `uv venv` + `uv pip install -e ".[dev]"`. The root `Makefile` now runs the KB suite in both `make test-unit` (its 17 non-db tests) and `make test-db` (its 18 db tests, against the same local compose Postgres, with a combined exit status), and CI installs the KB venv and runs the same.

The CI coverage floor was rebalanced correctly rather than left to rot. The move drops the backend collect count from 830 to 795 and adds 35 to the knowledge base; the combined total is unchanged at 830. Counting only the backend against the old floor would eventually hide a KB-side deletion (a false pass) and the split itself risked dropping below the floor (a false fail), so the CI step now sums both trees (`backend + knowledge-base`) against the same 625 minimum from substep 0.5.1.

Proof: `make boundaries` green; the break-it check injected `import app` into a KB test and `make boundaries` failed naming `knowledge-base/tests/test_models_constraints.py:1`, then went green once removed. `make test-db` ran backend (271 db passed) then the KB suite (18 db passed) and tore Postgres down. `make test-unit` ran backend (523 non-db passed) then the KB suite (17 non-db passed). `make check` is green (794 passed + 1 xfailed). Ruff and Pyright are clean on every touched file. Like 1.1.1 and 1.1.2, the work is verified but uncommitted pending the owner's go-ahead.

## 1.1 · Commit the three-folder move + close the make-check KB gap (2026-09-21)

With everything above verified, the owner gave the go-ahead to commit. Substeps 1.1.1 (the folder move), 1.1.2 (the one-way boundary rules) and 1.1.1-fix (the knowledge-base test suite) had all been built on a single uncommitted working tree, and their edits overlap heavily — the `Makefile`, `.github/workflows/ci.yml`, the ledger and the two `pyproject.toml` files were each touched by more than one substep. Because no intermediate states were ever committed, they cannot be faithfully split into per-substep commits after the fact, so they went in as one commit, **c627c75** on branch `feat/rag-phase-3.5`: 466 files (411 renames, 22 adds, 2 deletes, 31 modifies), with no venvs or caches staged. The three prior ledger entries keep their original `uncommitted` status per the append-only rule; a new commit-of-record entry names c627c75 as their commit, since a commit cannot contain its own hash.

Before committing, the one real residual from 1.1.1-fix was closed: `make check`'s umbrella `test` target had stayed backend-only, so a developer running the documented pre-commit gate locally would not have caught a broken knowledge-base test. The fix is a single recipe line — the `test` target now runs `cd knowledge-base && DATABASE_URL=… uv run pytest` after the backend suite — so `make check` (which is `boundaries` then `test`) now covers both trees. It was verified two ways: `make -n check` prints boundaries → backend pytest → knowledge-base pytest, and a real `make check` ran green end to end (backend 794 passed + 1 xfailed, then knowledge-base 35 passed). This Makefile change is part of c627c75.

Finally, a whole-tree cruft sweep (fanned out to an agent) confirmed the repo carries zero tracked build, cache, or editor junk and no leftovers from the three-folder move — no `apps/`, no emptied `backend/tests/schema/`, no dangling package markers. The only superseded document still sitting outside `docs/_archive/` was `docs/OBI-RAG-SYSTEM-A-Z.md`, a pre-Phase-0 reference whose source documents had already been archived; it was `git mv`'d into `docs/_archive/rag-legacy-pre-phase0/` to match, following the repo's archive-never-delete convention. Every other near-empty file (the 0.3 redirect stubs, the agent-research placeholder, the two future-ideas lists, the snapshot README) was checked and kept as intentional. CLAUDE.md was left untouched at the owner's request — its structure rewrite (substep 1.1.3) and stale layout lines remain the owner's to make. This ledger/progress-log update and the archive move are committed in a follow-up commit.

## 1.1 · Correction — c627c75 did touch CLAUDE.md (2026-09-21)

Correction to the entry directly above. A fan-out record-integrity double-check caught that the claim "CLAUDE.md left untouched" — made in this progress-log, in the ledger's commit-of-record entry, and in the c627c75 commit message — is not accurate. Commit c627c75 does change one line of CLAUDE.md: a broken documentation path on the 0.5 regression-home bullet was corrected from `final_docs/0.5-regression-tests/` to `docs/Final_docs/0.5-regression-tests/`. That fix was part of substep 1.1.1's "CLAUDE.md: path strings only" sweep, which the 1.1.1 spec explicitly allows, so it is legitimate work — but the blanket word "untouched" was wrong. What the record meant, and what remains true, is narrower and still holds: the substep-1.1.3 structure rewrite was not done, and the two stale layout lines (the "config/" line and the self-deleting move note) are still present for the owner to handle. The commit message itself is left as-is rather than rewriting an unpushed commit's history; this note and the matching ledger entry are the correction of record.

## 1.1 · Remove the empty root tests/ scaffold (2026-09-21)

At the owner's request, after a harmlessness double-check, the repo-root `tests/` folder was removed. It held a single file, `TESTING.md` — a testing-strategy doc, no actual test code. The check confirmed it was safe: no build step runs it (the backend's `testpaths=["app","tests"]` resolves against the backend rootdir, i.e. `backend/tests`, not the repo root; knowledge-base has its own `tests`; nothing in the Makefile, CI, Turbo, or workspace config references root `tests/`), and the doc it contained was stale anyway, still naming `apps/web`/`apps/automation` and a `pnpm --filter web` command that no longer exists. The only live reference, a line in `README.md`'s directory tree, was removed in the same commit; the remaining references are append-only history in the 1.1-move records and the 0.3 audit and were left as frozen history. One thing worth not losing silently: that folder had been the reserved home for cross-application / integration / end-to-end tests spanning frontend, backend and a real Postgres — those tests don't exist yet, so with the folder gone that home is now unassigned and will need a deliberate location if cross-part e2e is ever built or the repos are split. Separately flagged but not fixed here: the rest of the README's directory-tree block still describes the pre-1.1.1 layout, which needs a broader, deliberate README refresh rather than a silent one.

## 1.1.3 · CLAUDE.md, the skills, the agents and the design page follow (2026-09-21)

The last piece of Phase 1's move is the documentation catching up with the new folders. Going in, the substep read as a big path-cleanup sweep across CLAUDE.md, four skills, three agents, the Makefile and fifteen design-page panels. A fresh fan-out audit found almost all of that was already true: the skills, agents and root Makefile carry zero `apps/web`/`apps/automation` strings, and the fifteen named panels already show the new paths, with the three "one X" separation-of-concerns panels (frontend, backend, knowledge-base) already marked `built`. The only stale old-path string left anywhere in scope was a single self-deleting HTML comment at line 55 of CLAUDE.md. So rather than re-run work that was already done, this substep records that honestly and does only what genuinely remained.

The real edit is to CLAUDE.md alone. Its "Where things go" section was rewritten from the old flat feature list into a disk-accurate three-root tree: `backend/` (with everything under `app/` — `main.py`, the five `features/`, `platform/`, `shared/` — plus `scripts/`, `tools/`, `tests/`), `knowledge-base/` (`schema/`, `migrations/versions/`, `config/`, `seed/`, `local/`), and `frontend/` (`src/features/chat` and `src/features/embed`, the thin `src/app/api/chat` route, and `src/components`). The two stale lines were removed — the line-55 move-note comment and the line-57 "After the Phase 1 move" paragraph — and two smaller path errors were corrected along the way: the config bullet now points at `knowledge-base/config/`, and the eval-dataset path now reads `backend/app/features/evaluation/`. One deliberate deviation from the substep's literal wording: it wrote the backend paths as `backend/features/…`, but on disk they live under `app/`, so the accurate `backend/app/features/…` form is used — writing the shorter form would recreate the exact "agent chases a dead path" problem this substep exists to kill.

The owner's second request — make CLAUDE.md actively guide where new work lands — was folded in as a new "Where a new file goes" subsection: a six-step ordered decision list that routes any new file first to the data layer, then to frontend UI, then to a backend feature, then to platform, then to shared, and never lets a feature-owned concept be duplicated outside its public root. CLAUDE.md ends at 129 lines, well under the 200-line ceiling.

The design page was not edited — no panel commands were run and the brief was not regenerated, because the panels were already correct and re-running the commands would either be no-ops or, for the three panels with empty "today" lines, invent text that doesn't belong. So the list of panels flipped this substep is: none.

Proof: `grep -rn "apps/web\|apps/automation" CLAUDE.md .claude/ Makefile` returns nothing; `wc -l CLAUDE.md` is 129; `python3 backend/tools/panel.py sc-kb` prints a today line containing `knowledge-base/`; `python3 backend/tools/panel.py --list` shows the three separation-of-concerns panels as `built`; `make boundaries` is clean. The full `make check` suite was not re-run because the change touches only CLAUDE.md, a doc imported by no code — there is no runtime surface to exercise. The step-4 fresh-session check is being run by the owner in a new Claude Code session (a within-session subagent isn't a true fresh `/context` session); the two answers go into `docs/Final_docs/1.1-move/claude-md-check.md`, which is pending that run at the time this entry is written. Like the rest of Phase 1, the work is verified but uncommitted pending the owner's go-ahead.

## 1.1.3 · Break-it proof that the structure rules are actually enforced (2026-09-21)

On the owner's triple-check request, the documented structure wasn't just re-read — it was tested by breaking it. Seven throwaway probe files were planted, one per rule CLAUDE.md states, run through the real `make boundaries` gate, and then deleted (a shell trap guaranteed removal even on error). Two probes that follow the rules passed as expected: a knowledge-base file importing its own `schema` package, and one feature importing another feature at its public root. Five probes that violate a rule were each rejected with the exact message for that rule: a knowledge-base file importing `app`, a frontend `.ts` reaching into `backend/`, a feature deep-importing another feature instead of its root, `platform` importing a feature, and a feature importing its own root. `make boundaries` was green before and after, and `git status` afterward showed only the 1.1.3 doc edits — no probe files leaked onto disk or into git.

The exercise also settled the one open question from the rewrite. The substep's Proof text expects a fresh session to answer "backend/features/ingestion", but that folder does not exist on disk — `ls backend/features` errors, and the code actually lives at `backend/app/features/ingestion`, with migrations at `knowledge-base/migrations/versions/`. The proof wording predates the `app/` nesting; CLAUDE.md is deliberately written to the accurate deeper paths, because naming the shorter non-existent path is exactly the "agent chases a dead path" failure this substep exists to prevent. A clean-context reader given only CLAUDE.md independently answered with those same real paths, so the soft routing guidance reads correctly to a fresh agent and the hard boundary gate backstops any wrong placement. No production or test code changed and nothing was committed; this is a verification-only record.

## 1.2.1 · The tag map (2026-09-21)

The tag file (`knowledge-base/config/knowledge_scopes.json`) is the one place that names every knowledge scope, and because a scope decides what a person may see, a bad entry has to stop the backend before it can leak. This substep added that startup gate. The loader `backend/app/platform/config/knowledge_scopes.py` now validates the file in four ordered rules, each raising with a message that names the offending entry: every entry must be lowercase, no duplicates, the general scope (`obi-general-test`) must be present, and the reserved `classified` scope must be present. A failure raises before `create_app()` finishes, so a malformed file exits the process non-zero rather than serving one request under the wrong permissions — the fail-fast path already runs through `Settings.knowledge_scope_set`, touched at startup by both `platform_registry` and the answer-service build.

Two design decisions shaped the loader. First, it no longer silently lowercases entries the way the old code did; an uppercase slug is now rejected, exactly as panel `ks-validate` requires ("uppercase slugs are rejected at startup"). Second, `classified` is a reserved scope: it must be present in the file so the backend knows it, but it is excluded from the set the loader returns. That keeps the blast radius at zero — every existing consumer of `knowledge_scope_set` still sees the same four recognized scopes it saw before, a request body of `knowledge_scope: "classified"` stays an unknown-scope 400 at the chat gate, and `platforms.py` already forbids mapping `classified` to any integration. `GET /health` now lists `sorted(settings.knowledge_scope_set)`, which lists the four recognized scopes and never `classified`.

Adding `classified` to the JSON reached across a root boundary: the frontend drift test (`frontend/src/features/chat/tests/knowledge-scopes.test.ts`) asserts the widget's scope list equals the canonical file's names exactly, so a new entry would have failed the frontend build. That was in scope — the substep explicitly calls `classified` "a scope the widget must never offer" — so the drift test was updated to exclude `classified` before comparing and to assert the widget never contains it; the widget's own TS list stayed the four offerable scopes. The frontend suite is green (3 tests).

Proof, all at unit level. Six tests in `test_knowledge_scopes.py` pass: `"Toast"` fails and the message contains Toast; a duplicate fails and names it; a file without the general scope fails; a file without classified fails; the `/health` payload lists the four scopes and not classified; the real committed file loads to exactly the four recognized scopes. These six replace the five older tests, two of which contradicted the new design (the old test expected uppercase to be lowercased, not rejected). To confirm the new tests are meaningful, the loader and `main.py` were reverted with `git stash` and the tests re-run: the five new-behaviour tests failed and only the pre-existing general-scope check passed. The break-it check was run for real: injecting `"Toast"` into the committed file made `create_app()` raise at startup with exit code 1 and the message `knowledge scope 'Toast' must be lowercase`; the file was restored from a backup and the app boots again, `/health` returning the four scopes. `make boundaries` is clean and the full backend unit suite (524 passed, 272 db-deselected) is green, which is the real evidence that excluding `classified` changed no downstream behaviour.

On security: the only endpoint touched is `GET /health`, a PUBLIC-READ liveness probe. It exposes non-secret data — the env name (already exposed) and the public scope tag identifiers — and deliberately omits `classified`. Rate limiting, input validation and timeouts are not required for a small fixed-payload probe that makes no outbound call. Panels `ks-validate`, `tg-config` and `cm-config` were flipped to built and the brief regenerated; `ks-edit` was left as-is since it is a how-to panel unchanged by this work. Like the rest of Phase 1, the work is verified but uncommitted pending the owner's go-ahead.

## 1.2.2 · The widget list is generated · 2026-09-21

The widget's dev/verification scope switcher stopped being a hand-written mirror of the tag list and is now generated from the one canonical file at build time. Before this, `frontend/src/features/chat/model/knowledge-scopes.ts` held a hand-typed array of the four offerable scopes, kept honest only by a drift test that read the canonical JSON and compared. Two lists that must agree can drift; one cannot. So the array was replaced with an import of `knowledge-base/config/knowledge_scopes.json` (reached through a new `@kb/*` tsconfig path alias, mirrored in `vitest.config.ts`), filtered to drop the reserved `classified` scope, exporting the same `KNOWLEDGE_SCOPES` / `KnowledgeScope` / `KNOWLEDGE_SCOPE_NAMES` names so no importer changed. The drift test is deleted — there is nothing left to drift.

Two owner decisions shaped this substep and were put to the owner rather than guessed. First, the label: the canonical JSON had only `name` + `description`, but the widget list needs a human-readable `label` ("Opera Cloud", not "obi-operacloud-test"). The owner chose to add a `label` field to every entry in `knowledge_scopes.json` and make that file the single canonical allowlist for Confluence ingestion, backend scopes, and widget display — no frontend override map, no second list. So each entry now carries `name` + `label` + `description`; the backend loader still reads only `name` and is unaffected. Second, the test level: substep 1.2.2's panel marks the level `browser`, but the project's 18-September widget-batch decision treats jsdom component tests as the browser/component stand-in until Phase 4. The owner chose to do BOTH.

Five jsdom component tests (`knowledge-scopes.test.tsx`) prove the list is generated from the JSON (every offerable entry, in order, as `{name, label}`), that the `ScopeMenu` renders each entry's label, that `classified` is never in the DOM and never selectable (so can never ride a request body), and — via a deterministic module mock, not a disk mutation — that a new JSON entry appears with no widget code change while a fresh `classified` entry is still filtered out. One Playwright smoke (`e2e/scope-list.spec.ts`) proves the same in the real Next build: it opens the widget on the main site `/`, opens the scope switcher (enabled for the suite via `NEXT_PUBLIC_SHOW_SCOPE_SWITCHER`), and asserts the menu shows exactly the JSON labels minus `classified`. The break-it check was run for real: removing the `classified` filter from the exported list made the never-classified tests fail; restoring it turned them green again.

Everything verified. `pnpm build` from `frontend/` is green with no `experimental.externalDir` flag — Next resolved the JSON import from outside the app root through the `@kb` alias unaided, which had been the main open risk. `make test-ui` passes both browser tests (the existing mount smoke and the new scope-list smoke); the full frontend vitest suite is 240 passed; typecheck clean; `make check` is green (backend 795 passed + 1 xfail, knowledge-base 35 passed), confirming the added `label` field is inert to the backend loader. Ruff and pyright are clean on the one touched backend file (a docstring that no longer claims a drift test guards the widget list).

Two deliberate deviations, stated plainly. Playwright "test 3" as literally worded ("a temp entry … shows up after a rebuild") was not implemented as a live dev-server rebuild — that mutates a tracked repo file mid-test and leans on unverified cross-app-root Next hot-reload, both against the determinism rule — so the "follows JSON" proof is the deterministic jsdom module-mock test instead. And the panels `ks-deploy` / `ks-widget` / `w-scope` were not flipped, because their own Close substeps (2.5 / 3.2) own that flip; only `cm-config`'s today line was updated (it was already `built`) and the brief regenerated.

Finally, the owner asked whether Confluence ingestion is implemented this phase. It is not: the label→scope resolver already reads the same canonical file, but there is no "published AND carries an approved label ⇒ index" gate — a page with zero recognized labels is still indexed with empty tags (a confirmed existing delta). Per the owner's instruction, the ingestion requirements (eligible only with ≥1 approved label; no approved label → not ingested; multiple approved labels → ingest once and associate with every matching scope; unrelated labels never become scopes; `platforms.json` still gates per-platform access; plus the tests to add) were recorded verbatim in the substep that owns that gate — `p2-s2_2-4`, "2.2.4 · Label-gated membership, unconditional" — in the action plan, and cross-referenced in `docs/plan/delta.md`, rather than pretending the scraper behavior exists. Verified but uncommitted, pending the owner's go-ahead.

## 1.2.2 · The widget list is generated — correction after a triple-check · 2026-09-21

The owner asked me to triple-check the work against the panel's literal "Check it" acceptance list, so I re-ran the evidence live and tightened the browser suite rather than trusting my earlier notes. The most valuable change: the browser test for "classified in no request body" is now a real proof, not an argument. It intercepts the outgoing `POST /api/chat` in the browser, selects the Toast scope in the switcher, sends a message, and asserts the captured request body carries `knowledgeScope: "obi-toast-test"` and contains no `classified` anywhere. Together with "the switcher shows exactly the JSON entries minus classified," that is two genuine browser tests; `make test-ui` runs three green (these two plus the pre-existing mount smoke).

Two acceptance lines do not hold literally, and I want to be exact about why. First, "against the stub host page": the scope switcher lives inside the `/embed` iframe, and that iframe only opens when it receives an `obi:open` message from an allow-listed embedding origin. The local registry allows `localhost:3000/3100`, but Playwright drives `127.0.0.1:3100` — a different origin — so the panel never opens on a `/test-hosts/*` page. I therefore run against the main site `/`, which mounts the widget directly with no iframe and no origin gate. Making the stub host page work would mean changing the Playwright harness (baseURL to localhost plus pointing the dev server at the local platform registry), which is outside this substep; I've flagged it for the owner.

Second, "a temp entry added to the JSON shows up after a rebuild." I did not hand-wave this — I wrote the live-rebuild browser test, ran it, and it failed: after writing a new entry to the canonical JSON and navigating fresh, `next dev` did not serve the new scope (a 30-second timeout). The dev server does not recompile the out-of-app-root `@kb` JSON module on change. So a browser rebuild test cannot be made reliable, and I removed it; the "follows JSON" fact stays proven deterministically in the jsdom companion, which mocks the JSON module and confirms a new entry appears (and a fresh `classified` is still filtered). The `pnpm build` half of that line is green. The canonical JSON was restored cleanly after the experiment (five scopes, no leftover temp entry, verified).

Everything else re-confirmed: the break-it check (remove the `classified` filter → the never-classified tests fail; restore → green), typecheck clean, the jsdom suite 5/5, and `make check` green from the earlier run. Net honest status against the panel: facts (b) and (c) are met at the browser level, fact (d) is met at the jsdom level with `pnpm build` green, but the literal "three browser tests against the stub host page" is not met — two browser tests against `/`, for the concrete origin-gating and dev-server-recompile reasons above. Still uncommitted, pending the owner's go-ahead.

## 1.2.2 · Correction 2 — the real reason the live-rebuild browser test failed · 2026-09-21

My earlier correction stated, as if verified, that `next dev` does not recompile the external `@kb` JSON. That was wrong, and I only found out by instrumenting it instead of asserting. I started an isolated dev server, confirmed a known scope label ("Opera Cloud") is compiled into the client chunk, then injected a probe scope into the canonical JSON. The dev server recompiled in ~150ms and the probe label reached the compiled output on the first check. So the dev server watches and rebuilds that out-of-app-root module fine.

The actual reason the Playwright test failed is a test-authoring bug, not a dev-server limitation. The test wrote the new entry to the JSON and then immediately navigated with `page.goto("/")`, racing the file-watcher's recompile, and asserted the new menu item was visible with a 30-second timeout. Playwright's `toBeVisible` auto-retry re-queries the DOM of the page that is already loaded; it does not reload. So once the page loaded the pre-edit bundle, the new scope could never appear, and the assertion timed out on a stale page. A correct version would reload the page in a loop until the recompiled bundle serves the new item, or wait for the compile before navigating. It remains out of the suite by the owner's "jsdom proof only" choice — but the honest reason is fragility and that choice, not an inability to recompile. The probe entry was restored cleanly.

## 1.2.2 · Correction 3 — the live-rebuild browser test is fixed · 2026-09-21

With the real cause understood (a stale page that never reloads, not a dev-server limitation), the fix was small and the live-rebuild browser test is back in the suite. Three changes make it reliable: the browser HTTP cache is disabled over CDP so each reload fetches the freshly recompiled chunk; after writing a temp scope into the canonical JSON the test re-navigates in a retry loop (`expect(async () => { ...open switcher...; await expect(tempItem).toBeVisible({ timeout: 1000 }); }).toPass({ timeout: 30000 })`) instead of navigating once and waiting on a stale page; and the JSON is restored in `finally`. The scope-list file runs in serial mode so the first two tests read the switcher before the mutation window.

It passes, and I ran `make test-ui` twice to check for flakiness: four tests green both times (the mount smoke plus the three scope-list browser tests), with the rebuild test steady at about three seconds. The canonical JSON was clean after both runs — five scopes, no leftover temp entry. Typecheck is clean. So all three browser-test facts the panel names are now met at the browser level against `/`: the switcher shows exactly the JSON entries minus classified, classified is in no DOM node and no request body, and a temp entry added to the JSON shows up after a rebuild. The jsdom suite stays as the fast deterministic companion. The one line still not literal is "against the stub host page," which is blocked by the `/embed` iframe's origin allow-list versus Playwright's 127.0.0.1 origin — the owner chose to keep the tests against the main site `/`. Still uncommitted.

## 1.2.3 · The platform list — 2026-09-21

This substep gives Obi the one file that says which platforms may call it and which knowledge scopes each integration may see, validated at startup, and moves that file to sit beside the tag list. It was not a from-scratch build: an earlier Phase-11.1c effort already had a platform loader (`backend/app/platform/config/platforms.py`) and a `config/platforms.json` at the repo root, wired into live token verification and the embed frame's CSP. So the real job was to relocate the file under `knowledge-base/config/` (beside `knowledge_scopes.json`), harden its startup validation to the plan's six ordered rules, and add the two accessors the plan names — without regressing the live embed work.

A blast-radius pass first (via a read-only subagent) surfaced one important fact: the "ADR-0014" the code cites for these rules is a mislabel — ADR-0014 is about database row security, and no ADR actually binds the platform registry. The rules live only in the file's own README, the loader docstring, and the action plan, so the plan is authoritative. That dissolved the worry about overstepping an ADR.

The loader now enforces, in order and each naming the offending entry: every mapped tag exists in the tag map; `classified` is never mappable; the general scope is added by the loader and must never be hand-listed; `lifetime_minutes` sits within 1..1440; every signing alg is on the allow-list (RS256, ES256); and outside local, a registry with zero active platforms stops startup. It exposes `allowed_scopes_for(integration)` (a set, general included) and `platform_for(issuer)` (the active entry, or None). The existing `by_issuer` / `scopes_for` stay for the live token verifier and auth context, which are not rewired here — switching token verification to active-only is Phase-4 work.

The relocated real file adds `datahub` as the first (and only) active platform, matching the owner's confirmed rollout order (Data Hub first; Mews and Toast follow; Opera Cloud inactive), with TODO placeholders for its issuer/JWKS until Phase 4.x. Its domains are left empty rather than the plan example's `"TODO"` string, so a placeholder can't leak into the live CSP allow-list. The plan example's empty issuers were not used because the registry is keyed by issuer and empty strings would collide. Both `platforms.json` and `platforms.local.json` moved together, and every path reference (backend and frontend default-path climbs, settings/conftest comments, `.env.example`, the contracts token-claims description, and three frontend docstrings) was updated so the repo stays honest about where the file lives.

Tests come first: twelve unit tests in `test_platforms.py` — the nine the substep names (one per rule plus the real-file-loads, allowed-scopes-adds-general, and inactive-not-served cases) and three kept to preserve the existing-API coverage the token verifier and auth context rely on. They failed for the right reasons before the loader changes and pass after. The new "general never hand-listed" rule meant stripping hand-listed `obi-general-test` from the local override and from two consumer fixtures (the loader still appends it, so their assertions are unchanged).

The break-it check ran live: injecting `classified` into the mews integration and booting with `ENV=production` aborts the backend non-zero with `integration mews: 'classified' is never mappable`; restoring the line boots clean, logging `active_platforms=["datahub"]` (a new boot log line added for the plan's hand-back). Two things bit during verification and are disclosed in the ledger: an ill-judged `git checkout` briefly reverted the rewritten file to stale git-index content (git mv had staged the old file), which I caught and recreated; and `make check` initially failed at collection because the owner's root `.env` sets `PLATFORMS_PATH` to an absolute path in a different, stale checkout whose file still hand-listed general — the old lenient loader had masked that leak. The suite is now pinned hermetic (`conftest` sets `PLATFORMS_PATH=""`) so it no longer depends on a developer's `.env`.

Final state: `make check` green (boundaries OK; backend 800 passed, 1 xfailed; knowledge-base 35 passed), frontend typecheck clean and its 240 unit tests green (including the embed/CSP tests that read the moved file), ruff and pyright clean on every touched file. Panel `cm-config`'s today line and the brief were updated; `em-backend` / `em-token` (Phase-4 token verification) and `em-kb` (waits on 1.2.3 and 4.1.2) were deliberately not flipped. Heads-up for the owner: any local `.env` / `.env.local` whose `PLATFORMS_PATH` points at the old repo-root `config/` path should move to `knowledge-base/config/`, and the browser e2e (`scope-list.spec.ts`, run by hand) may need the same update.

## Phase-1 completion-gate — reconciling the three failing gate lines (2026-09-21)

The Phase-1 gate has six "done when" lines. A first multi-agent verification pass found three of them failing, so this pass fixed them — but first, at the owner's request, a fleet of six read-only agents assessed whether each fail was really the *work* falling short or the *gate wording* being wrong. That distinction turned out to matter: two of the three "fails" were mostly the gate over-reaching, and one was a genuinely broken set of docs.

The genuinely-broken part was fixed in the repo. Five live operational documents still told a reader to `cd apps/automation` or pointed at `apps/web/...` — paths the 1.1.1 rename deleted, so anyone following them today would fail. Three runbooks (`chat-api-key-rotation`, `supabase-vector-store-cutover`, `phase-13.1-apply-reader-rls-supabase`) and two plan files (`plan/delta.md`, `plan/decisions.md`) had their path strings corrected `apps/web`→`frontend`, `apps/automation`→`backend` (the unrelated `platform/automation-api` segment was left untouched). Two design-page code-map panels had stale *today* lines — `em-button` still named `apps/web/...` and `cm-retrieval` pointed at `platform/db/engine.py`, a file that no longer exists — both were corrected through `panel.py` (which only writes the today line and status, nothing else), and the brief was regenerated. The fresh-session scaffold (`claude-md-check.md`), which had sat empty, was filled with the answers a genuinely context-free subagent gave when handed only `CLAUDE.md`: ingestion → `backend/app/features/ingestion`, migrations → `knowledge-base/migrations/versions`, both correct. That is recorded as a *provisional* pass, honestly flagged: a subagent is the closest proxy available inside a working session, but it is not the owner opening a real `/context` session, which is still owed.

The rest was the gate wording being stricter than what was actually built, and — importantly — stricter than the project's own rules allow. The leftover-path grep, read literally, still fails because `apps/web`/`apps/automation` appear across `docs/adr/`. But those ADRs are decisions of record; CLAUDE.md says changing one needs a *new* ADR, and ADR-0010 already refused to amend ADR-0007 in place precisely to preserve that history. Editing 59 "Governs:" pointer lines and the 26-occurrence repository-separation record would break that rule to satisfy a grep. The honest fix is the gate, not the ADRs: the same 1.1.1 substep's own inventory grep already excludes all of `docs/`, so the Proof grep's narrower exclude is simply an internal inconsistency in the design doc. Likewise, "verify tables identical line for line" was never meant literally — the move brings its ~80 touched files clean under ruff/pyright per CLAUDE.md, so lint counts *improved* (45→19 errors, 11→0 unformatted, pyright unchanged), a fact already disclosed in the ledger; only the behavior rows were ever meant to match, and they do, verbatim. And "code-map panels show new paths" is met by 1.1.3's actual text, which scopes the requirement to today lines — the stale panel *titles* and Code-locations tables are HTML body content the substep never asked to touch and `panel.py` cannot edit. These three are recorded as decision-needed rows in `docs/plan/decisions.md` for the owner to ratify on the design page, and `verify-before.md`'s own header was tightened to match; the design page itself was not edited, since its gate text is the owner's authoritative spec.

After the fixes, `git grep` shows zero stale-path hits in every code root and everywhere outside `docs/`; the only remaining hits are the two sanctioned categories (the immutable ADRs and the non-authoritative backlog under `docs/embedding`, `docs/snapshot`, `docs/future-ideas/IDEAS.md`, which CLAUDE.md marks "not authoritative until reviewed"). `make test-unit` stayed green (backend 529 passed, knowledge-base 17 passed) and `make boundaries` exits 0 — the changes were documentation and panel today-lines only, so nothing in code moved. Two gate items remain owner-only and were deliberately not done here: merging PR #3 into `main` (still open; its CI is red on a re-runnable Postgres infra flake in `make test-db`, not a code failure), and running the true fresh `/context` session to replace the provisional answers. Nothing was committed, per the Phase-1 commit-only-when-asked convention.

Follow-up the same day: the owner chose option A on both open gate lines, so the two amendments were applied to the design page itself, not just recorded. The Phase-1 "done when" gate lines and the 1.1.1 Proof/See text were re-scoped — "identical line for line" became "identical on every behavior row" (the lint row governed by ADR-0003 D1's no-rise floor), and the leftover-path grep's exclude widened from just `docs/archive`+`final_docs` to all of `docs/`, matching the same substep's own inventory grep. With that, gate 2 reads clean: code and config are already at zero, and the only remaining hits are the immutable ADR record and the non-authoritative backlog. Beyond the today-line scope the 1.1.3 substep actually required, the three stale panel titles were corrected too (`apps/web: the widget` → `frontend: the widget`, and the alembic/infra titles to their knowledge-base homes), with the two historical "renamed from apps/web / apps/automation" today-lines verified intact — a bulk find-replace was deliberately avoided so those history phrases could not be corrupted. The deep per-panel "Code locations" tables still name old paths and are left as a small noted residual, since they live inside the grep-excluded design page and outside the literal gate. These design-page edits were made only because the owner explicitly asked for A on both; the page is the authoritative spec and its gate wording is not changed unilaterally.

## Phase-4 embed security-hardening pass — S1: embed lifecycle & logout (2026-09-22)

This is the first implementation slice of the owner-requested security audit loop over the Obi embed (see `docs/Final_docs/phase-4-embed-security/`). It is a hardening pass, not a numbered action-plan substep, and is recorded as `SEC-S1` so the record stays honest about the distinction. The research wave that opened the loop found the backend auth core sound but surfaced four real frontend embed-lifecycle gaps, all of which this slice closes, test-first.

The headline fix: `obi:clear` was not a real logout. It only hid the panel and nulled the in-memory token, but the conversation, its id, and any in-flight answer stream lived on the always-mounted chat provider — so re-opening showed the old thread, and an answer generated under the pre-logout token could still land in it. The bridge that receives host messages now lives inside the chat provider (as a small `EmbedBridge` child), so `obi:clear` can call the session's `restart()`, which aborts the in-flight stream and clears the messages and conversation id before the panel closes. A re-open now starts an empty thread. Two supporting gaps went with it: a token fetch already in flight when the session is cleared or re-pointed could resurrect the cleared token when it resolved late — now a module-scoped epoch counter, bumped on every lifecycle boundary, makes a stale fetch drop its token instead of posting it; and a silent token renewal that crossed into a different company or integration left the old conversation in place — the bridge now decodes the (display-only, never trust-bearing) integration and company claims and resets the conversation when a renewal changes them, while a backend 401 now drives a subscribed handler that clears stale UI. A small robustness fix rounds it out: the `obi:token` message's token field is now runtime-checked as a non-empty string before being stored, not merely TypeScript-narrowed.

An important boundary was kept sharp: the client-side claim decode exists only to tell whether a renewal changed scope and to show identity; it is never used for authorization. The backend `TokenVerifier` remains the sole authority on what a token means, and the decoded values are held in memory beside the token and never persisted. The `onUnauthorized` handler only clears stale UI — the fixed host→frame message contract is unchanged, so the frame cannot itself request a fresh token.

Nine new tests were written first and verified to fail before the fix, then pass after: four in the iframe-bridge suite (the token-field guard, an ignored unknown message type, and the scope-change callback firing only on a genuine scope-changing replacement), two in the loader suite (the cleared/re-pointed in-flight fetch being dropped), and three in a new embed-frame component suite (clear wipes the thread and re-open is empty with a reset conversation id; clear aborts an in-flight stream so a late completion never lands; a 401 clears the thread). Verified independently in the main window, not taken on the implementer's word: `pnpm --filter web test` 249 passed (up from the 240 baseline), `pnpm --filter web typecheck` clean, and — because the change restructured the embed frame's React tree — the full Playwright embed suite re-run, 4 passed. `make boundaries` stays green as no backend code moved. Honest note: the repo has no `next lint` config set up (pre-existing), so the strict-TypeScript typecheck is the enforced gate here, and it is clean on every touched file.

## Phase-4 embed security-hardening pass — S2: production config trust guard (2026-09-22)

The research wave found that nothing in code stopped a test or placeholder platform being trusted in production — isolation depended entirely on which config file an operator pointed the app at. A production process loading `platforms.local.json` would happily trust its `test-*` issuers and fetch their signing keys from `localhost`, and any localhost domain on an active entry would flow straight into the embed frame's `frame-ancestors` CSP. This slice (`SEC-S2`) closes both, and fixes a smaller inconsistency in how the two apps decide what "production" even is.

The backend platform loader now, when it is not running in an offline/local/dev/test/ci environment, refuses any active platform that is not a real third-party trusted issuer: its issuer and JWKS must be https on a real host, never a `TODO`/`PLACEHOLDER` string, never `localhost`/`127.0.0.1`, never a `.local` host, and none of its CSP domains may be localhost. Each rejection raises at startup naming the offending entry, so a misconfiguration fails fast and loud rather than silently trusting a test key. The guard is threaded through a single new `offline` parameter that the settings layer computes from the same environment signal it already uses; the one and only non-test caller is that settings property (confirmed by grep), so production enforcement is guaranteed while the permissive default keeps other features' test fixtures working untouched. On the frontend, the CSP builder now strips localhost domains before they can reach `frame-ancestors` outside local/dev, and fails closed (403) if that leaves no domains. And the two apps' notions of "offline/local" were aligned — `development` is now treated the same on both sides — with a contract test on each side pinning the value sets so they cannot silently drift apart again.

This surfaced a real, expected consequence worth stating plainly: the committed platform file has `datahub` marked active with a `TODO` placeholder issuer and JWKS. Under the old loader that was inert; under the new guard it correctly makes a non-offline deployment fail to start. That is the vulnerability closing, not a regression — but it means the owner must, before any real deploy, either give `datahub` its real issuer/JWKS/domains from the Data-Hub team or set it inactive. The values were deliberately not invented (the project rule against fabricating connection/key values), and the blocker is recorded in the ledger under "need from you" so it is not a deploy-time surprise. One judgment call is flagged for the coming audit wave: the `development` alignment was made in the permissive direction (treated as offline, matching the already-offline `dev`), on the reasoning that a real production deployment uses `ENV=production` or leaves it unset — neither of which is in the offline set, so the guard still fires — and only a deployment mislabeled `development` would be affected.

Verified independently in the main window, test-first throughout: thirteen tests added or updated across the backend registry, the settings contract, and the frontend CSP. `make test-unit` — backend 538 passed (up from 529), knowledge-base 17 passed, boundaries clean; `pnpm --filter web test` 253 passed (up from 249); `pnpm --filter web typecheck` clean; ruff and pyright clean on every touched backend file. One existing test (`test_platforms_real_file_loads`) was updated rather than weakened — it now loads the committed file in offline mode and its docstring records that the active `datahub` placeholder is correctly rejected in production.
