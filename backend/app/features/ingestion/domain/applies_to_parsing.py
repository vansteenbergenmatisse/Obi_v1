"""Parsing "Applies to" tables out of a storage-format body (panel mi-applies, 8.2.2).

The 8.2.1 authoring decision (`docs/Final_docs/5-integration-context/applies-to-authoring.md`):
a page authors its applicability as one or more standard two-column tables whose header row's
first cell reads "Applies to"; every row below is one ``field | value`` pair, one table = one
complete rule. This module lifts those tables out of the raw storage HTML **before**
normalization, so:

- the raw rule mappings go to :func:`app.features.ingestion.domain.applicability.validate_rule`
  (this module owns no vocabulary — it only finds and shapes the rows), and
- the remaining body — what normalize/chunk/content-hash see — no longer contains the table,
  so a table-only edit changes no content hash and rides the §D.0 metadata-only restamp
  route instead of a rebuild.

Normalization at the parse edge (the label precedent, ``test_tags_mixed_case_label_...``):
the header match is case-insensitive and field names/values are whitespace-trimmed and
lowercased, because the Confluence editor capitalizes — a near-miss header silently treated
as content would silently drop the whole rule. Malformed table SHAPES fail loudly here with
the same :class:`ApplicabilityValidationError` the schema raises (reasons ``malformed-table``
and ``duplicate-field``); field/value SEMANTICS stay the schema's job.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser

from app.features.ingestion.domain.applicability import ApplicabilityValidationError
from app.shared.hashing import normalize_text

# The authored marker: the header row's first cell, whitespace-normalized, case-insensitive.
_MARKER = "applies to"

_CELL_TAGS = {"td", "th"}


@dataclass(frozen=True)
class AppliesToExtraction:
    """The split body: storage HTML minus every Applies-to table, plus the raw rules.

    ``rules`` is one field→value mapping per Applies-to table, in page order — the exact
    input shape ``validate_applies_to`` takes. Empty means the page authored no record
    (the documented label-only default); it is NOT an empty record."""

    body_storage: str
    rules: list[dict[str, str]]


@dataclass
class _Table:
    start: int  # absolute offset of "<table" in the raw html
    end: int = -1  # absolute offset just past "</table...>"
    rows: list[list[str]] | None = None


class _TableParser(HTMLParser):
    """Collects every top-level table's cell texts and raw-source span.

    Only depth-1 rows/cells are structural (a table nested inside a cell flattens into
    that cell's text, and its own rows are ignored) — mirroring how the body normalizer
    flattens nested content."""

    def __init__(self, raw: str) -> None:
        super().__init__(convert_charrefs=True)
        self._raw = raw
        self._line_starts = [0]
        for match in re.finditer("\n", raw):
            self._line_starts.append(match.end())
        self.tables: list[_Table] = []
        self._depth = 0
        self._rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def _abs(self) -> int:
        line, offset = self.getpos()
        return self._line_starts[line - 1] + offset

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "table":
            if self._depth == 0:
                self.tables.append(_Table(start=self._abs()))
                self._rows = []
            self._depth += 1
            return
        if self._depth != 1:
            return
        if tag == "tr":
            self._row = []
        elif tag in _CELL_TAGS and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "table" and self._depth:
            self._depth -= 1
            if self._depth == 0 and self.tables:
                close = self._raw.find(">", self._abs())
                self.tables[-1].end = (close + 1) if close != -1 else len(self._raw)
                self.tables[-1].rows = self._rows
                self._rows = []
            return
        if self._depth != 1:
            return
        if tag in _CELL_TAGS and self._cell is not None and self._row is not None:
            self._row.append(normalize_text(" ".join(self._cell)))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self._rows.append(self._row)
            self._row = None

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)


def _fail(reason: str, message: str) -> ApplicabilityValidationError:
    return ApplicabilityValidationError(reason, message)


def _rule_from_rows(rows: list[list[str]]) -> dict[str, str]:
    """Shape one Applies-to table's data rows into a field→value mapping, loudly."""
    fields: dict[str, str] = {}
    for row in rows[1:]:  # row 0 is the header
        if not any(cell for cell in row):
            continue  # a fully blank row states no condition — nothing is dropped
        if len(row) < 2 or any(cell for cell in row[2:]):
            raise _fail(
                "malformed-table",
                f'"Applies to" rows are one field | value pair; got {row!r}',
            )
        field = row[0].lower()
        if not field:
            raise _fail("malformed-table", f'"Applies to" row has no field name: {row!r}')
        if field in fields:
            raise _fail(
                "duplicate-field",
                f'field "{field}" appears twice in one "Applies to" table — a '
                f"last-one-wins would silently drop the first condition",
            )
        fields[field] = row[1].lower()
    return fields


def extract_applies_to(storage_html: str) -> AppliesToExtraction:
    """Split a storage-format body into (body without Applies-to tables, raw rules).

    A body with no Applies-to table returns unchanged with ``rules == []`` — the
    label-only default. A table whose header matches but whose shape is malformed
    raises :class:`ApplicabilityValidationError` (never a silently dropped rule)."""
    if not storage_html:
        return AppliesToExtraction(body_storage=storage_html, rules=[])
    parser = _TableParser(storage_html)
    try:
        parser.feed(storage_html)
        parser.close()
    except ApplicabilityValidationError:
        raise
    except Exception:
        # The body normalizer is lenient on broken HTML (it falls back to stripped
        # text), so stay consistent — unless the broken body plausibly carries an
        # Applies-to table, in which case dropping it would silently widen the rule.
        if _MARKER in storage_html.lower():
            raise _fail(
                "malformed-table",
                'the body failed to parse but appears to contain an "Applies to" '
                "table — fix the page rather than lose the rule",
            ) from None
        return AppliesToExtraction(body_storage=storage_html, rules=[])

    rules: list[dict[str, str]] = []
    spans: list[tuple[int, int]] = []
    for table in parser.tables:
        rows = table.rows or []
        if not rows or not rows[0] or rows[0][0].lower() != _MARKER:
            continue  # a content table — none of our business
        rules.append(_rule_from_rows(rows))
        spans.append((table.start, table.end if table.end != -1 else len(storage_html)))

    if not spans:
        return AppliesToExtraction(body_storage=storage_html, rules=[])
    body = storage_html
    for start, end in reversed(spans):
        body = body[:start] + body[end:]
    return AppliesToExtraction(body_storage=body, rules=rules)
