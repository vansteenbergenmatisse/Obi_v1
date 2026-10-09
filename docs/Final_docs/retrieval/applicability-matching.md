# Applicability matching (deterministic, §D.4)

- **Workflow:** retrieval
- **Owning code:** `backend/app/features/retrieval/domain/applicability_match.py` (exported from the feature root: `match_applicability`, `derive_connections`, `CustomerContext`, `ConnectionRecord`, `MatchResult`)
- **Design panel:** `mi-match` (section 05.2 · Multi-integration context)
- **Status:** Unverified (coded and unit/db-proven; since 8.3.1 the retrieval SQL mirrors this predicate — see `eligibility-filtering.md` — and since 8.3.4 the matched reason is collapsed to per-slot citation attribution, but no live token carries slots yet, so no live question flows through it)

## What it does

One pure, deterministic function decides whether a chunk's stamped applicability record
matches this customer's verified integration context:
`match_applicability(context, payload, catalog) → MatchResult`. The `payload` is the exact
JSON shape substep 8.2.2 stamps on `chunk.applicability` (`applies_to_payload` — one dict
per rule, OR between rules); the `context` carries the three §D.13 slots (one canonical
catalog id or None each, mirroring the gate's `AuthContext` slot fields), the host-platform
key, and any real connection records (none at launch — the token cannot express one).

The semantics: within one rule every condition ANDs **on the same actual connection** —
both role sides and every required flow direction must hold on one connection the customer
actually has, never on "both products exist somewhere in the account". Between rules: OR,
first match wins. Launch pairs derive from filled slots only — POS+PMS gives the POS–PMS
connection (both §D.2 directions), PMS+Accounting gives the PMS–Accounting connection, and
a direct POS–Accounting pair is **never** derived from three filled slots: it needs a real
connection record (§D.13/O1). When a rule is blocked only by configuration the context does
not carry (an empty slot, an unknown platform, an unverifiable variant, an inexpressible
connection record), `MatchResult.missing` names it so the answer layer can serve the
applicable general guidance and ask — a known-but-different configuration reports nothing
to ask for. Every decision carries an inspectable reason slug (`general`, `slot:<role>`,
`platform-interface:<role>`, `connection:<type>`, `workflow`, or the failure slug per rule).
A chunk with no record (NULL `applicability`) keeps label-only behavior and never reaches
the matcher — that compatibility default is encoded in SQL by 8.3.1.

## Why it does it

§D.4 is the design of record: a guide for "Toast connected to Mews" must only surface for a
customer who actually has that connection. The matcher is deliberately a pure function
(no I/O, no clock) in the retrieval domain layer because the panel places the eligibility
predicate in the retrieval feature: 8.3.1 mirrors this exact predicate inside the
database/vector-search function before the result limit, and 8.3.4 surfaces the reason
slugs as per-slot citation attribution — one reference semantics, two consumers. Workflow
bindings (`same-instance`/`same-property`) hold by construction for slot-derived
connections (one company token, one property, one product per slot); with bindings present,
real records cannot satisfy a workflow rule until the richer §D.1 context record carries
instance/property data — never-broaden. Removing the same-connection AND would re-open the
Mews/Xero cross-match; deriving the POS–Accounting pair from slots would invent a
connection the customer may not have.

## How we know it works

Unit (`backend/app/features/retrieval/tests/test_applicability_match.py`, 17 tests, panel
mi-match, run in `make test`): the three design-page negatives red-first then green —
`test_rt2_match_mews_xero_cross_match_impossible`,
`test_rt2_match_products_existing_somewhere_never_satisfy_a_connection_rule`,
`test_rt2_match_three_slots_never_derive_a_pos_accounting_pair` — plus one positive per
level (general, software, platform-interface, connection, workflow), explicit-any binding
to the actual connection, OR-between-rules, the real-record unlock of the direct pair,
direction-enabled-on-the-same-connection, incomplete-context ask-never-broaden, variant
unverifiable-never-assumes, and derive-from-filled-slots-only. Each mechanism was inverted
one at a time (break-it) and its test went red, then green on restore.

Database (`test_applicability_match_db.py`,
`test_rt2_match_stamped_jsonb_payload_round_trips_through_the_matcher`): a chunk stamped
with the exact `applies_to_payload` JSONB round-trips through real local Postgres and
matches the right context, never the Mews/Xero cross context — proving the stored shape
and the matcher share one vocabulary.

Since 8.3.1 the retrieval SQL consumes the predicate (the `_ELIGIBILITY_CLAUSE` in
`search_repo.py` mirrors it; `test_eligibility_filter_db.py`'s oracle test proves SQL and
matcher agree payload-by-payload, and the gold-set before/after numbers are recorded in
`docs/plan/baseline.md`).

Since 8.3.4 (panel mi-attrib) the matched reason is surfaced as per-slot citation
attribution: `attribution_for_reason` (same module, exported from the feature root alongside
the `AttributionValue` literal) collapses the single reason the matcher already selected to
the Citation contract enum — `general`; a named slot `pos`/`pms`/`accounting` (from a `slot:` or
`platform-interface:` reason); or `pair` (from a `connection:`/`workflow` reason — the
connection wins over its member slots, pair > slot). It never re-evaluates matching: the
retriever computes the reason ONCE while building the rerank inputs (8.3.2) and reuses it for
both the rerank YAML and the attribution, carrying the value on `RetrievedHit.attribution`;
`answer_service` copies it onto `Citation.attribution`, and the `/chat` wire includes it only
when present (a label-only page or the no-context path stays absent — byte-compatible with
pre-8.3.4, OpenAPI drift test green). A no-match or any failure slug maps to None. The value is
only ever one of the five fixed enum strings, so it can carry nothing beyond the customer's own
context (rule 10 — proven by `test_attribution.py::test_sec_attrib_never_leaks_beyond_the_
customers_own_context`). Unit proof: `backend/app/features/retrieval/tests/test_attribution.py`
(7 tests, drives the real matcher then maps the reason) and
`test_answer_service.py::test_rt3_answer_carries_each_hits_attribution_onto_its_citation` /
`::test_rt3_answer_leaves_attribution_absent_for_a_label_only_hit`;
`test_mi_attrib_wire.py` pins the wire serialization. Browser proof (panel mi-attrib): the
widget renders the attribution as a muted per-citation badge
(`frontend/.../message-bubble.tsx`) — `e2e/citation-attribution.spec.ts` (Playwright, mocked
`/api/chat` SSE) and `message-bubble.test.tsx`'s attribution block. Not yet proven: no live
token exercises it (Phase A).

**Worked-example end-to-end coverage (8.5.1, panel mi-match).** The deterministic matcher's
central promise — a connection rule matches only a connection the customer ACTUALLY has, never
"both products exist somewhere" — is now proven end to end against the §D.9 examples in
`backend/app/features/retrieval/tests/test_worked_examples_db.py`. Example 5 models the
Toast/OperaCloud + Mews/QuickBooks property as a `CustomerContext` carrying two real
`ConnectionRecord`s (Toast↔OperaCloud, Mews↔QuickBooks) and empty slots, and asserts that a
Toast/Mews pair guide — both directions — and the three-system workflow are NEVER returned by the
live retriever, while the two real connection guides are. Example 4 proves the Toast→QuickBooks
honesty clause: three filled slots never derive a direct POS–Accounting pair. These fail loudly
if cross-matching regresses.
