"""Section extractor — splits filing text into logical sections.

Also handles PDF download and text extraction (moved from pipeline.py
for single-responsibility — extraction belongs with the extractor).
"""

import io
import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

import httpx
import pypdf

from diffiq.config import PDF_DOWNLOAD_TIMEOUT
from diffiq.db import insert_sections

logger = logging.getLogger(__name__)

USER_AGENT: str = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


@dataclass
class ExtractionResult:
    """Result of downloading and extracting text from a PDF.

    Attributes:
        text: Extracted text on success, None on failure.
        error: Human-readable error description on failure, None on success.
    """
    text: str | None
    error: str | None


def download_pdf_text(pdf_url: str) -> ExtractionResult:
    """Download a PDF and extract its text using pypdf.

    Args:
        pdf_url: Full URL to the PDF file.

    Returns:
        ExtractionResult with text on success, or error description on failure.
    """
    try:
        with httpx.Client(timeout=PDF_DOWNLOAD_TIMEOUT) as client:
            resp = client.get(
                pdf_url,
                headers={"User-Agent": USER_AGENT},
            )
            resp.raise_for_status()
    except httpx.HTTPError as e:
        logger.warning("PDF download failed: %s — %s", pdf_url, e)
        return ExtractionResult(text=None, error=f"Download failed: {e}")

    try:
        reader = pypdf.PdfReader(io.BytesIO(resp.content))
        pages: list[str] = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
    except Exception as e:
        logger.warning("pypdf extraction failed for %s: %s", pdf_url, e)
        return ExtractionResult(text=None, error=f"Corrupted PDF: {e}")

    full_text: str = "\n".join(pages)

    if len(full_text) < 100:
        logger.info(
            "Extracted text too short (%d chars) — likely scanned PDF",
            len(full_text),
        )
        return ExtractionResult(text=None, error="Scanned PDF (text < 100 chars)")

    return ExtractionResult(text=full_text, error=None)

SECTION_HEADERS: dict[str, list[str]] = {
    "AUDIT_REPORT": [
        r"Independent\s+Auditor'?s?\s+Report",
        r"Opinion",
        r"Basis\s+for\s+Opinion",
        r"Emphasis\s+of\s+Matter",
        r"Key\s+Audit\s+Matters",
        r"Management'?s?\s+Responsibility",
        r"Other\s+Matter",
    ],
    "FINANCIAL_RESULT": [
        r"(?:Profit|Loss)\s+(?:for|before|after)",
        r"Balance\s+Sheet",
        r"Statement\s+of\s+(?:Profit|Loss|Cash)",
        r"Notes\s+to\s+(?:Accounts|Financial)",
        r"Revenue",
        r"Expenses",
        r"Cash\s+Flow",
    ],
    "RPT": [
        r"Related\s+Party\s+(?:Transactions?|Disclosures?)",
        r"Details\s+of\s+Related\s+Party",
        r"Loans?\s+to\s+Related",
    ],
    "PROMOTER_CHANGE": [
        r"Shareholding\s+Pattern",
        r"Promoter(?:s|'s)?\s+(?:Holding|Pledge|Shareholding)",
        r"Statement\s+of\s+(?:Holding|Shares)",
    ],
}

GENERIC_PATTERNS: list[str] = [
    r"^\d+\.\s+",
    r"^[A-Z][A-Z\s/]{4,}$",
]


def _compile_group_patterns(patterns: list[str]) -> re.Pattern | None:
    """Compile a list of patterns into a single alternation regex."""
    if not patterns:
        return None
    joined = "|".join(f"(?:{p})" for p in patterns)
    return re.compile(joined, re.IGNORECASE | re.MULTILINE)


def _extract_by_headers(text: str, patterns: list[str]) -> list[dict[str, Any]]:
    """Split text at each section header match.

    Each section gets {header, text, page_num: 0, section_idx}.
    """
    header_re = _compile_group_patterns(patterns)
    if not header_re:
        return []

    matches = list(header_re.finditer(text))
    if not matches:
        return []

    sections: list[dict[str, Any]] = []

    for i, match in enumerate(matches):
        header = match.group(0).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()

        sections.append({
            "header": header,
            "text": content,
            "page_num": 0,
            "section_idx": i,
        })

    return sections


def extract_sections(
    raw_text: str, filing_type: str | None = None
) -> list[dict[str, Any]]:
    """Split filing text into logical sections based on filing type.

    Args:
        raw_text: The full extracted PDF text.
        filing_type: One of AUDIT_REPORT, FINANCIAL_RESULT, RPT,
                     PROMOTER_CHANGE, ROUTINE, or None.

    Returns:
        List of section dicts with keys: header, text, page_num, section_idx.
    """
    if not raw_text or not raw_text.strip():
        return [{
            "header": "Body",
            "text": raw_text or "",
            "page_num": 0,
            "section_idx": 0,
        }]

    patterns = SECTION_HEADERS.get(filing_type or "") if filing_type else None
    if patterns:
        sections = _extract_by_headers(raw_text, patterns)
        if sections:
            return sections

    generic_sections = _extract_by_headers(raw_text, GENERIC_PATTERNS)
    if generic_sections:
        return generic_sections

    return [{
        "header": "Body",
        "text": raw_text.strip(),
        "page_num": 0,
        "section_idx": 0,
    }]


def extract_and_store_sections(
    conn: sqlite3.Connection,
    filing_id: int,
    raw_text: str,
    filing_type: str | None = None,
) -> list[dict[str, Any]]:
    """Extract sections and store them in the database.

    Args:
        conn: SQLite connection.
        filing_id: Filing ID.
        raw_text: Full extracted text.
        filing_type: Filing type for section header selection.

    Returns:
        The list of section dicts that were stored.
    """
    sections = extract_sections(raw_text, filing_type)
    insert_sections(conn, filing_id, sections)
    logger.debug(
        "Stored %d sections for filing %d", len(sections), filing_id
    )
    return sections
