"""P1 pipeline — crawl BSE, download PDFs, extract text, classify, sectionize, diff."""

import logging
from pathlib import Path
from time import sleep

from diffiq.classifier import classify_filing
from diffiq.config import STOCKS, DB_PATH, PDF_CACHE_DIR, CRAWL_DELAY_SECONDS
from diffiq.crawler import fetch_manifest
from diffiq.db import (
    get_filing_by_uuid,
    get_pending_filings,
    insert_filing,
    update_filing_raw_text,
    update_filing_status,
    update_filing_type,
    upsert_stock,
)
from diffiq.differ import run_diffs_for_filing
from diffiq.extractor import extract_and_store_sections, download_pdf_text
from diffiq.schema import init_db

logger = logging.getLogger(__name__)


def run_daily_pipeline() -> None:
    """P0 daily pipeline: crawl BSE announcements, download PDFs, extract, store.

    For each stock in the watchlist:
        1. Fetch announcements from BSE corporate announcements API.
        2. Insert new announcements (QUEUED status).
        3. Download and extract text from filings with PDF URLs.
        4. Update status to READY or ERROR_*.
    """
    logger.info("=== DiffIQ P0 Pipeline Start ===")

    # Ensure data directories exist
    PDF_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    conn = init_db(DB_PATH)

    total_new: int = 0
    total_errors: int = 0

    for stock in STOCKS:
        bse_code: str = stock.get("bse_code") or ""
        if not bse_code:
            logger.info(
                "Skipping %s (no BSE code — ETF/cash equivalent)",
                stock["name"],
            )
            continue

        symbol: str = stock["symbol"]
        name: str = stock["name"]

        # Ensure stock is in DB (use BSE code as unique identifier)
        stock_id: int = upsert_stock(conn, bse_code, name)
        logger.info("Processing %s (BSE=%s, id=%d)", name, bse_code, stock_id)

        # Fetch BSE announcements
        manifest = fetch_manifest(bse_code)
        if not manifest:
            logger.info("  No announcements returned for %s", name)
            sleep(CRAWL_DELAY_SECONDS)
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

            # Set filing type from BSE's newstype
            if entry.get("filing_type"):
                update_filing_type(conn, filing_id, entry["filing_type"])

            # Download and extract text (skip if no PDF URL)
            if not entry.get("pdf_url"):
                update_filing_status(
                    conn, filing_id, "NO_PDF", "No attachment available"
                )
                logger.info("    No PDF attachment → NO_PDF")
                continue

            update_filing_status(conn, filing_id, "DOWNLOADING")
            result = download_pdf_text(entry["pdf_url"])

            if result.text:
                update_filing_raw_text(conn, filing_id, result.text)
                update_filing_status(conn, filing_id, "READY")
                logger.info(
                    "    Extracted %d chars → READY", len(result.text)
                )

                # P1: classify → sectionize → diff
                ft = entry.get("filing_type")
                if not ft:
                    ft = classify_filing(entry.get("subject", ""))
                    update_filing_type(conn, filing_id, ft)

                extract_and_store_sections(
                    conn, filing_id, result.text, ft
                )
                run_diffs_for_filing(conn, filing_id, stock_id, ft)

                conn.commit()
            else:
                error_msg = result.error or "Unknown extraction error"
                update_filing_status(
                    conn,
                    filing_id,
                    "ERROR_EXTRACTION",
                    error_msg,
                )
                conn.commit()
                logger.info(
                    "    Extraction failed → ERROR_EXTRACTION: %s",
                    error_msg,
                )
                total_errors += 1

        total_new += new_count
        if manifest:
            sleep(CRAWL_DELAY_SECONDS)

    conn.close()
    logger.info(
        "=== Pipeline complete: %d new filings, %d errors ===",
        total_new,
        total_errors,
    )


def run_backlog() -> None:
    """Retry ERROR_* and QUEUED filings from previous runs."""
    conn = init_db(DB_PATH)
    pending = get_pending_filings(conn)
    logger.info("Backlog: %d QUEUED filings to process", len(pending))
    conn.close()


def sync() -> None:
    """Backfill all existing READY filings through classify → sectionize → differ."""
    conn = init_db(DB_PATH)

    rows = conn.execute(
        "SELECT id, stock_id, subject, raw_text, filing_type FROM filings WHERE status = 'READY'"
    ).fetchall()

    if not rows:
        logger.info("No READY filings to sync")
        conn.close()
        return

    logger.info("Syncing %d READY filings", len(rows))

    for row in rows:
        filing_id = row["id"]
        stock_id = row["stock_id"]
        filing_type = row["filing_type"]

        if not filing_type:
            filing_type = classify_filing(row["subject"] or "")
            update_filing_type(conn, filing_id, filing_type)

        raw_text = row["raw_text"]
        if not raw_text:
            continue

        existing = conn.execute(
            "SELECT COUNT(*) as cnt FROM sections WHERE filing_id = ?",
            (filing_id,),
        ).fetchone()
        if existing and existing["cnt"] == 0:
            extract_and_store_sections(conn, filing_id, raw_text, filing_type)

        run_diffs_for_filing(conn, filing_id, stock_id, filing_type)

    conn.commit()
    conn.close()
    logger.info("Sync complete")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    run_daily_pipeline()
