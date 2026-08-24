# Phase 4.6 — Fixes-backlog remediation (ingestion-relevant sub-steps only)

**Status:** ✅ done. Phase 4.6 (`PLAN.md` lines 2135–2935) closed 16 findings from an independent
audit of already-shipped Phases 0–4 (`docs/rag/fixes/`, since deleted — every finding is now fixed
and folded into this ledger). Findings on the retrieval/chat side — idempotency cache cross-
principal leak (4.6.3), rate-limiter hardening (4.6.4), the overloaded `scope` string (4.6.6),
duplicate CHECK constraint (4.6.8), pyright baseline reconciliation (4.6.9), RLS reader-role no-op
(4.6.10), and the exit gate (4.6.16) — are covered in `../retrieval/phase-4.6.md`.

## Files & folders used

```
apps/automation/app/platform/clients/
├── confluence_client.py                        HttpConfluenceClient: restrictions, groups, breaker
└── fixture_confluence_client.py                 matching fixture-backed behavior
apps/automation/app/platform/clients/tests/test_confluence_client.py
apps/automation/app/features/ingestion/application/versioning.py         rollback_to (hash restore)
apps/automation/app/features/confluence_sync/
├── application/sync_service.py                  _attachment_blocks orchestration
├── infrastructure/event_repo.py                 record_event (delivery_id fix)
└── tests/test_versioning_rollback.py, test_event_dedup.py, test_worker_sync.py, test_attachment_wiring.py
apps/automation/app/platform/db/enums.py         JobStatus comment (dead-code disposition)
apps/automation/app/platform/config/settings.py  confluence_breaker_threshold, attachment caps
```

## 4.6.1 — Confluence group-restriction fail-closed sentinel (CRITICAL)

`HttpConfluenceClient.get_restrictions`/`FixtureConfluenceGateway.get_restrictions` used to parse
only `restrictions.user.results[].accountId`, silently dropping group-only restrictions — a page
restricted **only** by a Confluence group synced as fully unrestricted. Fixed with a shared pure
resolver, `_resolve_read_restriction` (`confluence_client.py:88-117`): if a restriction record has
group entries but no resolvable user principal, it returns `[GROUP_RESTRICTED_SENTINEL]`
(`confluence_client.py:82`) — a literal string no real caller can ever be — instead of `[]`. A page
keyed by the sentinel is inaccessible to every principal-scoped caller until group-membership
expansion (4.6.2) resolves it. Both the live and fixture gateways call this one resolver.

## 4.6.2 — Confluence group-membership expansion (CRITICAL)

`_resolve_read_restriction` gained an optional `resolve_group` callable; each group on a
restriction record is resolved to real account ids and unioned into the principal list. Fail-closed
is preserved: no resolver, or a resolver that finds zero members, still returns the sentinel.
`HttpConfluenceClient._group_members`/`_fetch_group_members` (`confluence_client.py:353-399+`)
call Confluence's v1 group-membership endpoint (`GET {base}/rest/api/group/by-id/{groupId}/member`,
falling back to the deprecated name-based path), cached per-instance
(`_group_members_cache`) since the client is documented "instantiate once and reuse" per sync run.
`FixtureConfluenceGateway` gets a parallel fixture-backed resolver reading
`tests/fixtures/confluence/group_members.json`.

**Same-session update (2026-08-21, still uncommitted as of this writing) — a real bug found one
layer up.** A live sync against the real `SUPPORT` space found `get_restrictions()`'s *parent* call
— the old `GET {base}/api/v2/pages/{id}/restrictions` — returned **418** for every page (Atlassian
documents v2 restrictions as still "under construction," not a path typo), and the old
`if resp.status_code >= 400: return []` swallowed that as "no restrictions" — **fail-open**: every
synced page persisted with zero restriction rows regardless of its real Confluence ACL. Fixed by
switching to the working v1 endpoint (`GET {base}/rest/api/content/{id}/restriction`,
`confluence_client.py:319-351`) and changing the failure case to return
`[GROUP_RESTRICTED_SENTINEL]` — fail-**closed**, reusing 4.6.1's own sentinel. See `PLAN.md` §0's
2026-08-21 entries for full detail. **Still not fully closed:** the parent fetch now demonstrably
works live, but no synced real page has actually carried a group-based restriction yet, so
`_fetch_group_members`'s exact endpoint shape remains unverified against a real group-restricted
page.

## 4.6.5 — `rollback_to` didn't restore `PageSource`'s cached hashes (MEDIUM-HIGH)

Location correction from the original finding: this lives in `ingestion/application/versioning.py`
(owned by `ingestion`, not `confluence_sync`). Before the fix, `rollback_to` repointed
`active_doc_version_id` but left `PageSource`'s change-detection hashes and pipeline-version stamps
at their pre-rollback values — so the next sync's freshly computed hashes could spuriously agree
with the stale cached ones, silently masking a real content change as `no_change`. Fixed:
`rollback_to` (`versioning.py:419-460`) now also copies `content_hash`, `structure_hash`,
`parser_version`, `chunker_version`, `contextualization_version`, `embedding_model`,
`embedding_dim`, `retrieval_schema_version` from the target `DocumentVersion`. Fields with no
`DocumentVersion` counterpart (`title`, `labels_hash`, `access_scope_hash`, etc.) are deliberately
left as-is — nothing correct exists to restore them to, and they self-heal on the next
reconciliation sweep. Verified by reverting the fix locally and confirming the exact masking
behavior reproduced, then passed once restored.

## 4.6.7 — Confluence client hardening batch (MEDIUM + INFO)

Three fixes to `confluence_client.py`, all in the `_get`/`_get_with_retry` request path:

1. **Consecutive-failure circuit breaker** — `_get` checks `_consecutive_failures >=
   _breaker_threshold` (new `confluence_breaker_threshold` setting, default 5) before every
   request, raising `ConfluenceCircuitBreakerOpenError` without a network call; a success resets
   the counter.
2. **Retry now covers 5xx** — `_RETRYABLE` gained `httpx.HTTPStatusError`; a 4xx is still returned
   as a normal `Response`, never raised, so only the 5xx retry gap closed.
3. **Audit log lines** — `confluence_client_5xx`/`confluence_client_4xx` before returning/raising,
   plus a `before_sleep` hook logging `confluence_client_retry` between attempts.

**Same-session addendum (2026-08-21, uncommitted as of this writing) — a fourth bug found running
the first real live sync (the "Base" folder, 9 pages; see `PLAN.md` §0).** `list_space_pages`'s and
`_fetch_group_members`'s cursor pagination both doubled the `/wiki` context path on every page past
the first: `f"{self._base}{next_link}"` when `next_link` (Confluence's `_links.next`) is already a
site-root-relative path that itself starts with `/wiki` — `.../wiki/wiki/api/v2/pages?...` → 404.
Only surfaces once a space/group has more than one page of results, which is exactly why it was
never caught: every existing test mocked a single-page response. Fixed both call sites
(`confluence_client.py`) with `httpx.URL(self._base).join(next_link)` — resolves a root-relative
ref against the origin instead of naively concatenating, and passes an already-absolute link
through unchanged. Two new regression tests reproduce the double-prefix via a mocked multi-page
`_links.next` and assert the exact request path seen (they fail on the pre-fix code): `make check`
(repo root) → **401 passed** (was 399), `make boundaries` clean, ruff/pyright unchanged at baseline.

## 4.6.11 — Event dedup ignored `delivery_id` collisions (LOW)

`event_repo.py::record_event`'s `ON CONFLICT DO NOTHING` named only the `payload_hash` index, so a
same-`delivery_id`/different-hash redelivery still hit the separate `ux_event_ledger_delivery_id`
partial-unique index uncaught, raising an `IntegrityError`. Fixed by dropping `index_elements`
entirely — a target-less `ON CONFLICT DO NOTHING` absorbs a violation on *either* unique constraint
in one round trip (Postgres semantics: no target means any unique/exclusion violation on the
table). Verified by reverting locally and confirming the exact uncaught `IntegrityError` reproduced.

## 4.6.13 — Dead-code disposition: `attachment_extraction.py`, then wired in this session

At 4.6.13 (2026-08-11), `ingestion/domain/attachment_extraction.py` (`extract_attachment`) was
confirmed fully built and tested but with **zero production call sites** — attachment content was
tracked for change detection (`attachment_manifest_hash`) but never chunked/embedded/searchable.
Deliberate "park, don't wire" disposition at the time; the "PARKED" note was written into
`FEATURES.md` at 4.6.15.

**This changed in the current session (2026-08-21, uncommitted as of this writing) — the user
asked to close the last open item from the (now-deleted) `docs/rag/fixes/` audit.** Design,
confirmed with the user before writing code: reuse the existing `Chunk` table (no migration). Each
attachment's extracted text is wrapped as `norm.Block`s under a title-keyed heading path
(`["Attachments", title]`, `attachment_to_blocks`, `attachment_extraction.py:128-150`) and merged
into the page's `blocks` on any rebuild, flowing through the *exact same* section/chunk/diff/
embedding-reuse pipeline as page body text — inheriting the page's RLS/ACL for free via the
existing `page_id` FK.

- **`sync_service.py::_attachment_blocks`** (`sync_service.py:187-233`) — downloads and extracts
  every attachment's text on a rebuild (deterministic order, sorted by attachment id), fails soft
  per-attachment (oversized/unreachable/unparseable is skipped and logged, never fails the whole
  sync), capped by `confluence_attachment_max_per_page` (default 200) and
  `confluence_attachment_max_bytes` (default 20 MB, `settings.py:49-50`) — enforced both from
  cheap pre-download metadata (`fileSize`) and via streaming self-abort in
  `download_attachment` so a lied `Content-Length` can't bypass it.
- **`content_hash`/`structure_hash` deliberately stay body-only** (`sync_service.py:135-143`) —
  folding attachment content into them would make `classify()`'s next-sync comparison permanently
  disagree with what's persisted, spuriously reclassifying every subsequent sync as `body_changed`.
- `ChangeClass.attachment_changed` is deliberately **not** a rebuild trigger on its own (see
  [phase-1.md](./phase-1.md#5-what-the-sync-handler-decides-applicationsync_servicepy)) —
  attachment-only edits are picked up at the next rebuild-triggering event, a disclosed limitation.
- **Tests** (`confluence_sync/tests/test_attachment_wiring.py`, 9 new tests): real text/CSV/
  markdown attachment content becomes searchable; PDF/XLSX placeholders degrade to zero chunks, not
  a crash; attachment chunks inherit the page's ACL/source; re-syncing an unchanged page stays a
  true `no_change`; an unchanged attachment reuses its embedding across a body-driven rebuild;
  oversized/unfetchable attachments are skipped without failing the sync.
- Real API research before writing the client code: the real download link
  (`downloadLink`/`_links.download`) 302-redirects **cross-host** to a signed
  `api.media.atlassian.com` URL; confirmed httpx does not forward the Basic Auth header across that
  redirect (no credential leak).

**One residual risk disclosed, not silently accepted:** the byte cap bounds the compressed download
only — `pypdf`/`python-docx`/`openpyxl` decompress ZIP-based formats in memory, so a malicious/
corrupt attachment could still trigger a decompression-bomb-style memory spike during parsing;
accepted given attachments originate from a single authenticated Confluence tenant, not arbitrary
internet uploads.

## Not this file

- 4.6.3 (idempotency cache leak), 4.6.4 (rate-limiter hardening), 4.6.6 (overloaded `scope`
  string), 4.6.8 (duplicate CHECK constraint), 4.6.9 (pyright baseline), 4.6.10 (RLS reader no-op),
  4.6.12 (`refusal_reason` observability), 4.6.14/4.6.15 (doc-drift batches), 4.6.16 (exit gate) —
  all retrieval/chat-side or cross-cutting doc work, `../retrieval/phase-4.6.md`.
