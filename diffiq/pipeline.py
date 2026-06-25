"""P0 pipeline — crawl BSE, download PDFs, extract text, store in SQLite."""

import hashlib
import logging
from pathlib import Path

import httpx
import pypdf

from diffiq.config import STOCKS, DB_PATH, PDF_CACHE_DIR, PDF_DOWNLOAD_TIMEOUT
from diffiq.crawler import fetch_manifest
from diffiq.db import (
    get_filing_by_uuid,
    get_pending_filings,
    insert_filing,
    update_filing_raw_text,
    update_filing_status,
    upsert_stock,
)
from diffiq.schema import init_db

logger = logging.getLogger(__name__)

USER_AGENT: str = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


def download_and_extract(pdf_url: str) -> str | None:
    """Download a PDF and extract its text using pypdf.

    Args:
        pdf_url: Full URL to the PDF file.

    Returns:
        Extracted text as a single string, or None on failure
        (download error, corrupted PDF, or extraction returns < 100 chars).
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
        return None

    try:
        reader = pypdf.PdfReader(resp.content)
        pages: list[str] = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
    except Exception as e:
        logger.warning("pypdf extraction failed for %s: %s", pdf_url, e)
        return None

    full_text: str = "\n".join(pages)

    if len(full_text) < 100:
        logger.info("Extracted text too short (%d chars) — likely scanned PDF", len(full_text))
        return None

    return full_text


def run_daily_pipeline() -> None:
    """P0 daily pipeline: crawl, download, extract, store.

    For each stock in the watchlist:
        1. Fetch filing manifest from BSE.
        2. Insert new filings (QUEUED status).
        3. Download and extract text from QUEUED filings.
        4. Update status to READY or ERROR_*.
    """
    logger.info("=== DiffIQ P0 Pipeline Start ===")

    # Ensure data directories exist
    PDF_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    conn = init_db(DB_PATH)

    total_new: int = 0
    total_errors: int = 0

    for stock in STOCKS:
        bse_code: str = stock["bse_code"]
        name: str = stock["name"]

        # Ensure stock is in DB
        stock_id: int = upsert_stock(conn, bse_code, name)
        logger.info("Processing %s (BSE: %s, id=%d)", name, bse_code, stock_id)

        # Fetch manifest
        manifest = fetch_manifest(bse_code)
        if not manifest:
            logger.info("  No filings returned for %s", name)
            continue

        new_count: int = 0
        for entry in manifest:
            # Skip if already in DB
            existing = get_filing_by_uuid(conn, entry["filing_uuid"])
            if existing:
                continue

            # Insert new filing
            filing_id = insert_filing(
                conn,
                stock_id,
                entry["filing_uuid"],
                entry["filing_date"],
                entry["subject"],
                entry["pdf_url"],
            )
            logger.info(
                "  New filing [%d]: %s — %s",
                filing_id,
                entry["filing_date"],
                entry["subject"][:60],
            )
            new_count += 1

            # Download and extract text
            update_filing_status(conn, filing_id, "DOWNLOADING")
            raw_text = download_and_extract(entry["pdf_url"])

            if raw_text:
                update_filing_raw_text(conn, filing_id, raw_text)
                update_filing_status(conn, filing_id, "READY")
                logger.info(
                    "    Extracted %d chars → READY", len(raw_text)
                )
            else:
                update_filing_status(
                    conn, filing_id, "ERROR_EXTRACTION",
                    "Download failed or scanned PDF (text < 100 chars)",
                )
                logger.info("    Extraction failed → ERROR_EXTRACTION")
                total_errors += 1

        total_new += new_count

    conn.close()
    logger.info(
        "=== Pipeline complete: %d new filings, %d errors ===",
        total_new,
        total_errors,
    )


def run_backlog() -> None:
    """Retry ERROR_* filings from previous runs."""
    conn = init_db(DB_PATH)
    pending = get_pending_filings(conn)
    logger.info("Backlog: %d QUEUED filings to process", len(pending))
    conn.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    run_daily_pipeline()
