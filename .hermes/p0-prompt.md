# P0 Implementation: DiffIQ Foundation

You are implementing Phase 0 (Foundation) of DiffIQ, a corporate filing change detector for Indian stocks. Follow the specification below precisely.

## Architecture Context
- Pipeline: BSE crawl → classify → extract (pypdf) → section detect → text diff → LLM verify → Streamlit dashboard
- P0 scope: BSE crawler + pypdf extractor + SQLite store + Streamlit filing list
- Single stock for P0: VEDL (BSE scrip code: 531456)
- No vector DB, no embeddings, no ChromaDB — this is a text-diff pipeline using SQLite + difflib

## Files to Create

### 1. `requirements.txt`
```
pypdf
httpx
apscheduler
streamlit
```

### 2. `diffiq/__init__.py`
Empty file.

### 3. `diffiq/config.py`
```python
from pathlib import Path

STOCKS = [
    {"bse_code": "531456", "name": "VEDL"},
]

BSE_BASE_URL = "https://api.bseindia.com/BseIndiaAPI/api"
BSE_PDF_URL = "https://www.bseindia.com/xml-data/corpfiling/AttachLive"

CRAWL_DELAY_SECONDS = 5
PDF_DOWNLOAD_TIMEOUT = 120

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "diffiq.db"
PDF_CACHE_DIR = DATA_DIR / "pdfs"
```

### 4. `diffiq/schema.py`
SQLite schema with 4 tables: stocks, filings, sections, diffs.
Use WAL mode and 64MB cache_size.

**stocks table:** id (PK), bse_code (UNIQUE), name, active (default 1)

**filings table:** id (PK), stock_id (FK→stocks), filing_uuid (UNIQUE), filing_type, filing_date, subject, pdf_url, status (default 'QUEUED'), error, raw_text, created_at, updated_at

**sections table:** id (PK), filing_id (FK→filings), header, text, chunk_hash, page_num, section_idx

**diffs table:** id (PK), stock_id (FK→stocks), filing_id_new (FK→filings), filing_id_old (FK→filings), section_id_new (FK→sections), section_id_old (FK→sections), section_header, significance, diff_text, changed (int, default 0), created_at

All timestamp fields use TEXT with default `datetime('now')`.

Include `init_db(db_path)` function that creates tables if not exist (idempotent) and returns a connection with row_factory = sqlite3.Row.

### 5. `diffiq/db.py`
SQLite helper functions. All take `conn` as first argument. Use parameterized queries, never f-strings.

Functions:
- `upsert_stock(conn, bse_code, name)` → returns stock id
- `insert_filing(conn, stock_id, filing_uuid, filing_date, subject, pdf_url)` → returns filing id
- `update_filing_status(conn, filing_id, status, error=None)`
- `update_filing_type(conn, filing_id, filing_type)`
- `get_filings_for_stock(conn, stock_id, limit=50)` → list of dicts (ORDER BY created_at DESC)
- `get_filing_by_uuid(conn, filing_uuid)` → dict or None
- `get_pending_filings(conn)` → filings with status='QUEUED'
- `get_last_filing_of_type(conn, stock_id, filing_type)` → most recent filing of that type for that stock, or None
- `insert_sections(conn, filing_id, sections_list)` where sections_list is [{header, text, chunk_hash, page_num, section_idx}]
- `get_sections(conn, filing_id)` → list of dicts ordered by section_idx
- `insert_diff(conn, diff_data)` where diff_data is a dict matching diffs columns (stock_id, filing_id_new, section_id_new, section_header, diff_text, changed)
- `get_diffs_for_stock(conn, stock_id, limit=20)` → list of dicts ORDER BY created_at DESC

### 6. `diffiq/crawler.py`
```python
import httpx

def fetch_manifest(bse_code: str) -> list[dict]:
    """
    Fetch filing manifest from BSE for a stock.
    
    API: GET {BSE_BASE_URL}/CorpFilings/w?scripcode={code}&fromdate=&todate=
    
    Returns list of dicts with keys:
    - filing_uuid: str (from the attachment filename/NSE filing code)
    - subject: str
    - filing_date: str (YYYY-MM-DD)
    - pdf_url: str (full URL to download PDF)
    
    Headers: User-Agent like a real browser
    Timeout: 30s
    Returns empty list on failure (don't crash).
    """
```

BSE response JSON structure — the API returns an array of filings. Each filing has structure like:
```json
[
  {
    "attchmntFile": "e0f6c350-171d-4712-b35b-196b77e9f5b2.pdf",
    "desc": "Auditors Report",
    "dt": "15/05/2026",
    "sr_NO": 1,
    "category": "Audit",
    ...
  }
]
```
The pdf_url is `https://www.bseindia.com/xml-data/corpfiling/AttachLive/{attchmntFile}`.
The filing_uuid is attchmntFile without the .pdf extension.
Parse dt into YYYY-MM-DD format.

### 7. `diffiq/pipeline.py`
```python
import logging

logger = logging.getLogger(__name__)

def run_daily_pipeline():
    """
    P0: Minimal pipeline that:
    1. Initializes DB
    2. For each stock in config.STOCKS:
       a. Fetch manifest from BSE
       b. For each new filing (not in DB by uuid):
          - Insert filing with status QUEUED
          - Download PDF
          - Extract text via pypdf
          - If text > 100 chars: update status to READY
          - If text <= 100 chars: update status to ERROR_EXTRACTION
    3. Log summary
    """
```

The download + extract step should be a separate function `download_and_extract(pdf_url, filing_id, conn)` that:
- Downloads PDF via httpx.get (120s timeout)
- Reads with pypdf.PdfReader
- Extracts text from all pages
- Concatenates with newlines
- Stores in raw_text field of filings table
- Returns text or raises on failure

### 8. `dashboard/app.py`
Minimal Streamlit app for P0:

```python
import streamlit as st
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from diffiq.schema import init_db
from diffiq.db import get_filings_for_stock, upsert_stock
from diffiq.config import STOCKS, DB_PATH

st.set_page_config(page_title="DiffIQ", layout="centered")
st.title("DiffIQ — Corporate Filing Monitor")

# Stock selector
stock_names = [s["name"] for s in STOCKS]
selected = st.selectbox("Select Stock", stock_names)

# Look up stock info
stock = next(s for s in STOCKS if s["name"] == selected)
conn = init_db(DB_PATH)
upsert_stock(conn, stock["bse_code"], stock["name"])
filings = get_filings_for_stock(conn, stock["bse_code"])  # need a version that takes bse_code or stock_id

# Show filings
if not filings:
    st.info("No filings found. Run the pipeline first.")
else:
    for f in filings:
        with st.container():
            cols = st.columns([2, 3, 1, 1])
            cols[0].write(f["filing_date"])
            cols[1].write(f["subject"][:60] + ("..." if len(f.get("subject","")) > 60 else ""))
            cols[2].write(f["filing_type"] or "")
            cols[3].write(f["status"])
            st.divider()
```

Wait — `get_filings_for_stock` in db.py takes stock_id, not bse_code. Fix: query the stock id first, or make the dashboard get it properly.

### 9. `tests/test_crawler.py`
```python
import pytest

def test_fetch_manifest_returns_list():
    """fetch_manifest returns a list (possibly empty) for a valid BSE code."""
    from diffiq.crawler import fetch_manifest
    result = fetch_manifest("531456")
    assert isinstance(result, list)

def test_fetch_manifest_structure():
    """Each manifest entry has required keys."""
    from diffiq.crawler import fetch_manifest
    result = fetch_manifest("531456")
    if result:
        entry = result[0]
        assert "filing_uuid" in entry
        assert "subject" in entry
        assert "filing_date" in entry
        assert "pdf_url" in entry
        assert entry["filing_date"].count("-") == 2  # YYYY-MM-DD
```

Note: The live BSE API test may fail or time out. Make the tests robust — if the BSE API is unreachable, skip with a clear message rather than failing hard.

### 10. `tests/test_db.py`
```python
import pytest
from diffiq.schema import init_db
from diffiq.db import upsert_stock, insert_filing, get_filings_for_stock

@pytest.fixture
def conn():
    """In-memory SQLite for testing."""
    conn = init_db(":memory:")
    yield conn
    conn.close()

def test_upsert_stock(conn):
    stock_id = upsert_stock(conn, "531456", "VEDL")
    assert stock_id is not None

def test_insert_and_query_filing(conn):
    stock_id = upsert_stock(conn, "531456", "VEDL")
    fid = insert_filing(conn, stock_id, "test-uuid", "2026-06-25", "Test Filing", "https://example.com/test.pdf")
    assert fid is not None
    filings = get_filings_for_stock(conn, stock_id)
    assert len(filings) == 1
    assert filings[0]["filing_uuid"] == "test-uuid"
```

### 11. `tests/__init__.py`
Empty file.

## Important Rules

1. Do not include references to ponytail, karpathy, opencode, AI agent, or any internal tooling names in generated code, docstrings, or comments.
2. All Python files must have proper type hints on function signatures.
3. All functions need docstrings explaining what they do.
4. Use pathlib.Path for all file paths.
5. Use logging (not print) for pipeline output.
6. Use httpx, not requests.
7. SQL queries must be parameterized (never f-string interpolation).
8. After creating all files, run: `pip install -r requirements.txt` and `python -m pytest tests/ -v`
9. Commit all changes with message "P0: foundation — BSE crawler, pypdf extractor, SQLite store, Streamlit dashboard"
