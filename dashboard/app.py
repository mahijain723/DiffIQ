"""DiffIQ — Streamlit Dashboard (P0)."""

import sys
from pathlib import Path

import streamlit as st

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from diffiq.config import STOCKS, DB_PATH
from diffiq.db import get_filings_for_stock, get_stock_by_bse_code, upsert_stock
from diffiq.schema import init_db

st.set_page_config(
    page_title="DiffIQ",
    page_icon="📄",
    layout="centered",
)

st.title("DiffIQ — Corporate Filing Monitor")
st.caption("Tracks BSE-listed portfolio stock filings.")

# -- Init DB on first load --
if "db_inited" not in st.session_state:
    conn = init_db(DB_PATH)
    for s in STOCKS:
        bse_code = s.get("bse_code") or s["symbol"]
        upsert_stock(conn, bse_code, s["name"])
    conn.close()
    st.session_state["db_inited"] = True


def load_filings(stock_name: str) -> list[dict]:
    """Fetch filings for a given stock from SQLite."""
    stock = next((s for s in STOCKS if s["name"] == stock_name), None)
    if not stock:
        return []
    conn = init_db(DB_PATH)
    bse_code = stock.get("bse_code") or stock["symbol"]
    row = get_stock_by_bse_code(conn, bse_code)
    if not row:
        conn.close()
        return []
    filings = get_filings_for_stock(conn, row["id"], limit=50)
    conn.close()
    return filings


# -- Stock selector --
stock_names = [s["name"] for s in STOCKS]
selected_stock = st.selectbox("Select Stock", stock_names, index=0)

stock_data = next(s for s in STOCKS if s["name"] == selected_stock)
bse_code = stock_data.get("bse_code") or "—"
st.caption(f"BSE Code: {bse_code}")

filings = load_filings(selected_stock)

# -- Summary stats --
if filings:
    total = len(filings)
    ready = sum(1 for f in filings if f["status"] == "READY")
    errors = sum(1 for f in filings if f["status"].startswith("ERROR"))
    pending = sum(1 for f in filings if f["status"] == "QUEUED")

    cols = st.columns(4)
    cols[0].metric("Total Filings", total)
    cols[1].metric("Ready", ready)
    cols[2].metric("Pending", pending)
    cols[3].metric("Errors", errors)
else:
    has_bse = bool(stock_data.get("bse_code"))
    if not has_bse:
        st.info(f"**{selected_stock}** is an ETF — no corporate filings to track.")
    else:
        st.info(
            "No filings yet. Run the pipeline first:\n\n"
            "`python -m diffiq.pipeline`"
        )

st.divider()

# -- Filing list --
if filings:
    for f in filings:
        with st.container():
            cols = st.columns([2, 3, 1, 1])
            cols[0].write(f.get("filing_date", ""))
            subject = f.get("subject", "") or ""
            cols[1].write(subject[:60] + ("..." if len(subject) > 60 else ""))
            cols[2].write(f.get("filing_type") or "—")

            status = f["status"]
            if status == "READY":
                cols[3].markdown(f"✅ {status}")
            elif status.startswith("ERROR"):
                cols[3].markdown(f"❌ {status}")
            elif status == "NO_PDF":
                cols[3].markdown(f"⏭️ {status}")
            else:
                cols[3].write(status)

            st.divider()

# -- Footer --
st.caption(
    "Data source: BSE Corporate Announcements API. "
    "Run `python -m diffiq.pipeline` to fetch new filings."
)
