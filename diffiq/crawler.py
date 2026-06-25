"""BSE filing manifest crawler.

Fetches the list of corporate filings for a stock from BSE's public API.
BSE does not require authentication.
"""

import logging
from datetime import datetime
from typing import Any

import httpx

from diffiq.config import BSE_BASE_URL, BSE_PDF_URL

logger = logging.getLogger(__name__)

USER_AGENT: str = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

HEADERS: dict[str, str] = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.bseindia.com/corporates/ann.html",
}


def fetch_manifest(bse_code: str) -> list[dict[str, Any]]:
    """Fetch filing manifest from BSE for a stock.

    Hits the BSE CorpFilings API endpoint which returns corporate
    announcements for the given scrip code.

    Args:
        bse_code: BSE scrip code (e.g. '531456' for VEDL).

    Returns:
        List of filing dicts with keys:
            filing_uuid: unique identifier from the PDF filename.
            subject:     filing description/title.
            filing_date: date string in YYYY-MM-DD format.
            pdf_url:     full URL to download the PDF.
        Returns empty list on any failure (network, parse, etc.).
    """
    url = f"{BSE_BASE_URL}/CorpFilings/w"
    params = {"scripcode": bse_code, "fromdate": "", "todate": ""}

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(url, params=params, headers=HEADERS)
            resp.raise_for_status()
            data: list[dict] = resp.json()
    except httpx.HTTPError as e:
        logger.warning("BSE API error for %s: %s", bse_code, e)
        return []
    except (ValueError, TypeError) as e:
        logger.warning("BSE API parse error for %s: %s", bse_code, e)
        return []

    filings: list[dict[str, Any]] = []
    for entry in data if isinstance(data, list) else []:
        attchmnt: str | None = entry.get("attchmntFile") or entry.get("ATTACHMENT")
        if not attchmnt:
            continue

        # Parse date — BSE format is DD/MM/YYYY
        raw_date: str = entry.get("dt") or entry.get("DATE") or ""
        parsed_date = _parse_bse_date(raw_date)

        filing_uuid: str = attchmnt.replace(".pdf", "").strip()

        filings.append({
            "filing_uuid": filing_uuid,
            "subject": (entry.get("desc") or entry.get("DESCRIPTION") or "").strip(),
            "filing_date": parsed_date,
            "pdf_url": f"{BSE_PDF_URL}/{attchmnt}",
        })

    logger.info(
        "Fetched %d filings for BSE code %s", len(filings), bse_code
    )
    return filings


def _parse_bse_date(raw_date: str) -> str:
    """Convert BSE date format (DD/MM/YYYY) to YYYY-MM-DD.

    Returns empty string if parsing fails.
    """
    if not raw_date:
        return ""
    try:
        return datetime.strptime(raw_date.strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        logger.debug("Unparseable BSE date: %s", raw_date)
        return ""
