# DiffIQ — Corporate Filing Change Detector

**Not a chatbot. A differential analysis engine for BSE corporate filings.**
Surfaces only what changed — related party transaction creep, audit report language shifts, promoter pledge changes.

> **Status: P0 Working** — BSE crawler → PDF download → pypdf text extraction → SQLite store → Streamlit dashboard

## How it works

```
BSE Corp Announcements API → Download PDF → Extract text (pypdf) → SQLite → Streamlit Dashboard
```

1. **Crawl** BSE corporate announcements for portfolio stocks daily
2. **Download** PDF attachments via httpx
3. **Extract** text using pypdf (pure Python, ~2s install, zero model download)
4. **Store** in SQLite with filing metadata (date, type, status)
5. **View** in Streamlit dashboard with filing list and status indicators

## Stack

| Package | Size | Why |
|---------|------|-----|
| `bse` | ~50KB | Wraps BSE API with session handling & throttling |
| `pypdf` | 6MB | PDF text extraction (pure Python) |
| `httpx` | 500KB | HTTP client for PDF downloads |
| `streamlit` | 15MB | Dashboard UI |
| `sqlite3` | stdlib | Filing + text storage |

**Total install:** ~22MB, ~10 seconds.

## Usage

```bash
# Install
pip install -r requirements.txt

# Run pipeline (crawl BSE → download → extract → store)
python -m diffiq.pipeline

# Start dashboard
streamlit run dashboard/app.py
```

## Stock Watchlist

Corporate stocks tracked on BSE:
- **VEDL** (500295) — Vedanta Ltd
- **HDFCBANK** (500180) — HDFC Bank
- **GROWW** (544603) — Billionbrains Garage Ventures
- **ENERGY** (544604) — Mirae Asset Nifty Energy ETF

ETFs (NEXT50IETF, NIFTYBEES, etc.) are shown in the dashboard but have no corporate filings to track.

## Architecture

See [`engineering_memory.md`](engineering_memory.md) for full architecture decisions (gitignored).

## License

AGPL v3 — see LICENSE file.
