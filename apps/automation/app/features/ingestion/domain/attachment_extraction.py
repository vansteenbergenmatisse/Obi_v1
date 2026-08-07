"""Attachment text extraction with native-first parsing and conditional-OCR gating (pure-ish).

Text formats (txt/markdown/csv/html) are parsed with the standard library — no dependencies, fully
offline. Office/PDF formats use optional libraries (``pypdf``, ``python-docx``, ``openpyxl``); when
a library is absent the attachment is *skipped* with a recorded method rather than crashing
ingestion. OCR is never run eagerly: a PDF whose native text extraction comes back empty, or an
image, is flagged ``needs_ocr`` so the application layer can decide whether to invoke the
(paid) multimodal/OCR path. Extraction from bytes is deterministic; the only I/O is the optional
lazy imports.
"""

from __future__ import annotations

import csv
import io
import re
from collections.abc import Callable
from dataclasses import dataclass

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t]+")
_MIN_NATIVE_PDF_CHARS = 20  # below this, treat a PDF page layer as scanned → needs OCR


@dataclass
class ExtractionResult:
    text: str
    method: str  # text | csv | markdown | html | pdf | docx | xlsx | image | skipped
    needs_ocr: bool = False


def extract_attachment(
    *,
    filename: str,
    media_type: str | None,
    data: bytes,
    pdf_text_fn: Callable[[bytes], str] | None = None,
) -> ExtractionResult:
    """Extract readable text from one attachment. Never raises on unsupported/absent parsers."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    mt = (media_type or "").lower()

    if mt.startswith("image/") or ext in {"png", "jpg", "jpeg", "gif", "tiff", "bmp", "webp"}:
        return ExtractionResult(text="", method="image", needs_ocr=True)

    if mt == "text/csv" or ext == "csv":
        return ExtractionResult(text=_from_csv(data), method="csv")
    if mt == "text/html" or ext in {"html", "htm"}:
        return ExtractionResult(text=_strip_html(_decode(data)), method="html")
    if mt == "text/markdown" or ext in {"md", "markdown"}:
        return ExtractionResult(text=_decode(data).strip(), method="markdown")
    if mt.startswith("text/") or ext in {"txt", "text", "log"}:
        return ExtractionResult(text=_decode(data).strip(), method="text")

    if mt == "application/pdf" or ext == "pdf":
        text = (pdf_text_fn or _pdf_native)(data).strip()
        needs_ocr = len(text) < _MIN_NATIVE_PDF_CHARS
        return ExtractionResult(text=text, method="pdf", needs_ocr=needs_ocr)

    if ext == "docx" or "wordprocessingml" in mt:
        text = _docx_native(data)
        return ExtractionResult(text=text, method="docx" if text else "skipped")
    if ext in {"xlsx", "xlsm"} or "spreadsheetml" in mt:
        text = _xlsx_native(data)
        return ExtractionResult(text=text, method="xlsx" if text else "skipped")

    return ExtractionResult(text="", method="skipped")


def _decode(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def _from_csv(data: bytes) -> str:
    rows = csv.reader(io.StringIO(_decode(data)))
    return "\n".join(" | ".join(cell.strip() for cell in row) for row in rows if any(row))


def _strip_html(html: str) -> str:
    text = _TAG_RE.sub(" ", html)
    return _WS_RE.sub(" ", text).replace(" \n", "\n").strip()


def _pdf_native(data: bytes) -> str:  # pragma: no cover - exercised only when pypdf is installed
    try:
        from pypdf import PdfReader  # pyright: ignore[reportMissingImports]
    except Exception:
        return ""
    try:
        reader = PdfReader(io.BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception:
        return ""


def _docx_native(data: bytes) -> str:  # pragma: no cover - exercised only when python-docx present
    try:
        import docx  # pyright: ignore[reportMissingImports]
    except Exception:
        return ""
    try:
        document = docx.Document(io.BytesIO(data))
        return "\n".join(p.text for p in document.paragraphs if p.text)
    except Exception:
        return ""


def _xlsx_native(data: bytes) -> str:  # pragma: no cover - exercised only when openpyxl present
    try:
        from openpyxl import load_workbook
    except Exception:
        return ""
    try:
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        lines: list[str] = []
        for ws in wb.worksheets:
            for row in ws.iter_rows(values_only=True):
                cells = [str(c) for c in row if c is not None]
                if cells:
                    lines.append(" | ".join(cells))
        return "\n".join(lines)
    except Exception:
        return ""
