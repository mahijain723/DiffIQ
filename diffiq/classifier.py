"""Filing type classifier — regex-based subject matching."""

import logging
import re
import sqlite3

from diffiq.db import get_filings_for_stock, update_filing_type

logger = logging.getLogger(__name__)

PATTERNS: list[tuple[str, str]] = [
    ("AUDIT_REPORT", r"\baudit"),
    ("FINANCIAL_RESULT", r"(?=.*\bresult(?:s)?\b)(?=.*\b(?:quarter(?:ly)?|half\s*year(?:ly)?|annual|standalone|consolidated|financial)\b)"),
    ("RPT", r"\b(?:related\s*party|rpt)\b"),
    ("PROMOTER_CHANGE", r"\b(?:promoter|pledge|shareholding\s*pattern)\b"),
    ("BOARD_OUTCOME", r"\bboard\b.*\b(?:meeting|outcome|resolution)\b"),
]


def classify_filing(subject: str, raw_text: str | None = None) -> str:
    """Classify a filing by its subject line using regex patterns.

    First match wins; returns ROUTINE if no pattern matches.

    Args:
        subject: The filing subject line.
        raw_text: Unused; reserved for future content-based classification.

    Returns:
        A filing type string: AUDIT_REPORT, FINANCIAL_RESULT, RPT,
        PROMOTER_CHANGE, BOARD_OUTCOME, or ROUTINE.
    """
    if not subject:
        return "ROUTINE"

    subject_lower = subject.lower()

    for filing_type, pattern in PATTERNS:
        if re.search(pattern, subject_lower):
            logger.debug("Classified as %s: %s", filing_type, subject[:60])
            return filing_type

    return "ROUTINE"


def classify_pending_filings(conn: sqlite3.Connection) -> int:
    """Classify all filings where filing_type is NULL.

    Args:
        conn: SQLite connection.

    Returns:
        Number of filing records updated.
    """
    rows = conn.execute(
        "SELECT id, subject FROM filings WHERE filing_type IS NULL"
    ).fetchall()

    count = 0
    for row in rows:
        filing_type = classify_filing(row["subject"] or "")
        update_filing_type(conn, row["id"], filing_type)
        count += 1

    if count:
        logger.info("Classified %d pending filings", count)

    return count
