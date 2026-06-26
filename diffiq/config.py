"""DiffIQ configuration — stock watchlist, BSE params, paths.

WARNING: This file is committed to the repo. Do NOT add secrets (API keys,
passwords, tokens) here. Use .env for sensitive values.
"""

from pathlib import Path

# Stock watchlist with BSE scrip codes.
# Only actual corporate entities file announcements on BSE.
# ETFs (NEXT50IETF, NIFTYBEES, etc.) are kept for dashboard display but
# won't return filings from the BSE corporate announcements API.
STOCKS: list[dict] = [
    {"symbol": "VEDL", "name": "VEDL", "bse_code": "500295"},
    {"symbol": "HDFCBANK", "name": "HDFCBANK", "bse_code": "500180"},
    {"symbol": "GROWW", "name": "GROWW", "bse_code": "544603"},
    {"symbol": "ENERGY", "name": "ENERGY", "bse_code": "544604"},
    # ETFs — trade on BSE but no corporate filings
    {"symbol": "NEXT50IETF", "name": "NEXT50IETF", "bse_code": ""},
    {"symbol": "NIFTYBEES", "name": "NIFTYBEES", "bse_code": ""},
    {"symbol": "MIDCAPETF", "name": "MIDCAPETF", "bse_code": ""},
    {"symbol": "GOLDBEES", "name": "GOLDBEES", "bse_code": ""},
    {"symbol": "MODEFENCE", "name": "MODEFENCE", "bse_code": ""},
    {"symbol": "MAKEINDIA", "name": "MAKEINDIA", "bse_code": ""},
    {"symbol": "MASPTOP50", "name": "MASPTOP50", "bse_code": ""},
    {"symbol": "METALETF", "name": "METALETF", "bse_code": ""},
    {"symbol": "PWL", "name": "PWL", "bse_code": ""},
    {"symbol": "LIQUIDCASE", "name": "LIQUIDCASE", "bse_code": ""},
]

# BSE API endpoints
BSE_API_BASE: str = "https://api.bseindia.com/BseIndiaAPI/api"
BSE_PDF_BASE: str = "https://www.bseindia.com/xml-data/corpfiling/AttachLive"

PDF_DOWNLOAD_TIMEOUT: int = 120
CRAWL_DELAY_SECONDS: int = 5

DATA_DIR: Path = Path(__file__).resolve().parent.parent / "data"
DB_PATH: Path = DATA_DIR / "diffiq.db"
PDF_CACHE_DIR: Path = DATA_DIR / "pdfs"
