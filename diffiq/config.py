"""DiffIQ configuration — stock watchlist, BSE params, paths."""

from pathlib import Path

# Stock watchlist (BSE scrip codes)
STOCKS: list[dict] = [
    {"bse_code": "531456", "name": "VEDL"},
    {"bse_code": "500180", "name": "HDFCBANK"},
    {"bse_code": "543267", "name": "ENERGY"},
    {"bse_code": "540777", "name": "NEXT50IETF"},
    {"bse_code": "543072", "name": "NIFTYBEES"},
    {"bse_code": "540491", "name": "MIDCAPETF"},
    {"bse_code": "540148", "name": "GOLDBEES"},
    {"bse_code": "543627", "name": "MODEFENCE"},
    {"bse_code": "544041", "name": "MAKEINDIA"},
    {"bse_code": "543670", "name": "MASPTOP50"},
    {"bse_code": "543937", "name": "GROWW"},
    {"bse_code": "543919", "name": "METALETF"},
]

BSE_BASE_URL: str = "https://api.bseindia.com/BseIndiaAPI/api"
BSE_PDF_URL: str = "https://www.bseindia.com/xml-data/corpfiling/AttachLive"

CRAWL_DELAY_SECONDS: int = 5
PDF_DOWNLOAD_TIMEOUT: int = 120

DATA_DIR: Path = Path(__file__).resolve().parent.parent / "data"
DB_PATH: Path = DATA_DIR / "diffiq.db"
PDF_CACHE_DIR: Path = DATA_DIR / "pdfs"
