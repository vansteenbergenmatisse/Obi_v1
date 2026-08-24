# Confluence Fixture Corpus

A small but representative set of JSON fixtures shaped like Confluence Cloud
REST API v2 responses. It exists to exercise every downstream code path in the
sync, ingestion, and evaluation pipelines without a live Confluence instance and
without a database. Everything here is pure files plus `loader.py`.

## Layout

```
confluence/
  page-<id>.json            current version of each page
  versions/                 historical snapshots for change-detection tests
    page-1001-v1.json
    page-1001-v2.json
    page-1001-v3.json       identical to current page-1001.json
  labels/page-<id>.json     page -> labels (for labels_hash)
  restrictions/page-<id>.json   page -> read restrictions (for access_scope_hash)
  attachments/
    page-<id>.json          per-page attachment manifest
    *.txt / *.csv / *.md    tiny real attachment files
    PLACEHOLDER-BINARIES.txt binary formats the parser must degrade gracefully on, not shipped as real binaries
  manifest.json             machine-readable index of the whole corpus
  loader.py                 pure filesystem + json access
  README.md                 this file
```

## Spaces

- Space `100` (ENG, Engineering) — pages 1001, 1002, 1003
- Space `200` (HR, People Operations) — pages 2001, 2002, 2003

## Page mapping table

| Page | Space | Parent | Status   | Versions | Labels | Restrictions | Attachments | What it tests |
|------|-------|--------|----------|----------|--------|--------------|-------------|---------------|
| 1001 | ENG   | none   | current  | 1,2,3    | yes    | no           | txt, csv    | Root page; full storage-format body (H1-H3, paragraphs, bulleted list, table, code macro, info panel, link); multi-version change detection; labels_hash; real text attachments |
| 1002 | ENG   | 1001   | current  | 5        | no     | yes          | md + pdf/xlsx placeholders | Nested child; warning macro + table; read restrictions (users+groups) for access_scope_hash; mixed real/placeholder attachments |
| 1003 | ENG   | 1002   | archived | 2        | no     | no           | none        | Archived status must be excluded/flagged by ingestion; deeper nesting (grandchild) |
| 2001 | HR    | none   | current  | 4        | no     | no           | none        | Second space root; policy content with note macro and table |
| 2002 | HR    | 2001   | current  | 1        | yes    | yes          | none        | Restricted child in second space; both labels_hash and access_scope_hash on one page; code macro |
| 2003 | HR    | none   | trashed  | 1        | no     | no           | none        | Trashed status must be skipped entirely by ingestion |

## Version history of page 1001 (change detection)

- **v1** — initial. Access SLA reads "up to three business days". No info panel.
- **v2** — edits the "Getting Access" text (SLA now "one business day") and adds
  the info panel linking to the Deployment Runbook. Diff should detect an edited
  section plus an added section.
- **v3** — adds a new "Troubleshooting" H2 (with H3 subsections) and the
  Key Contacts / info-panel ordering is preserved. Diff should detect an added
  section. v3 equals the current `page-1001.json`.

Use these to test that change detection distinguishes edited-text vs
added-section vs moved-section, and that content hashing produces different
hashes per version.

## Status coverage

- `current` — 1001, 1002, 2001, 2002 (ingested)
- `archived` — 1003 (should be excluded or flagged)
- `trashed` — 2003 (should be skipped)

## Attachments

Real, parseable files: `welcome-checklist.txt`, `team-roster.csv`,
`rollback-notes.md` — these are indexed end-to-end (downloaded, extracted, chunked, embedded,
searchable; `test_attachment_wiring.py`) via `FixtureConfluenceGateway.download_attachment`
resolving the manifest's `file` field to a real on-disk fixture. Binary formats (PDF, XLSX) appear
in the manifests as placeholders pointing at `PLACEHOLDER-BINARIES.txt` instead of a real binary —
this exercises the "attachment present, parser invoked, gracefully degrades to no chunk" path
(`extract_attachment` fails closed to empty text on non-PDF bytes under a `.pdf` name, never
raises), not real PDF/XLSX text extraction. `pypdf`/`python-docx`/`openpyxl` (the `attachments`
optional-dependency group) are real, installed, and wired into the live sync path
(`ingestion/domain/attachment_extraction.py`) — they are just not exercised against a genuine
binary anywhere in this fixture corpus, a disclosed gap, not an unimplemented one.

## Programmatic access

```python
from tests.fixtures.confluence import loader

loader.list_pages()                 # manifest page index
loader.load_page("1001")            # current version
loader.load_page("1001", version=1) # historical snapshot
loader.load_labels("1001")          # or None
loader.load_restrictions("1002")    # or None
loader.load_attachments("1001")     # or None
loader.fixtures_dir()               # Path to this directory
```
