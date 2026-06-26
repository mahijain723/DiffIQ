"""DiffIQ — Streamlit Dashboard (P1)."""

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from diffiq.config import STOCKS, DB_PATH
from diffiq.db import (
    get_diffs_for_stock,
    get_filings_for_stock,
    get_portfolio_summary,
    get_sections,
    get_stock_by_bse_code,
    upsert_stock,
)
from diffiq.schema import init_db

st.set_page_config(
    page_title="DiffIQ",
    page_icon="📄",
    layout="centered",
)

st.title("DiffIQ — Corporate Filing Monitor")
st.caption("Tracks BSE-listed portfolio stock filings.")

if "db_inited" not in st.session_state:
    conn = init_db(DB_PATH)
    for s in STOCKS:
        bse_code = s.get("bse_code") or s["symbol"]
        upsert_stock(conn, bse_code, s["name"])
    conn.close()
    st.session_state["db_inited"] = True

# ── Portfolio Overview Grid ──────────────────────────────────────
st.subheader("Portfolio Overview")

conn = init_db(DB_PATH)
summary = get_portfolio_summary(conn)
conn.close()

if summary:
    cols = st.columns(len(summary))
    for i, stock in enumerate(summary):
        with cols[i]:
            total = stock["total_filings"]
            ready = stock["ready_count"]
            errors = stock["error_count"]

            # Card wrapper
            st.markdown(
                f"<div style='border:1px solid #e0e0e0; border-radius:8px; "
                f"padding:12px; text-align:center; background:#fafafa;'>"
                f"<strong style='font-size:1.1rem;'>{stock['name']}</strong><br>"
                f"<span style='color:#888; font-size:0.8rem;'>{stock['bse_code']}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

            st.metric("Total Filings", total)

            inner = st.columns(2)
            inner[0].metric("Ready", ready)
            inner[1].metric("Errors", errors)

            if stock["latest_filing_date"]:
                st.caption(f"Latest: {stock['latest_filing_date']}")
            if stock["latest_subject"]:
                st.text(stock["latest_subject"][:50])

            st.divider()
else:
    st.info("No corporate stocks found.")

st.divider()


def load_filings(stock_name: str) -> list[dict]:
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


stock_names = [s["name"] for s in STOCKS]
selected_stock = st.selectbox("Select Stock", stock_names, index=0)

stock_data = next(s for s in STOCKS if s["name"] == selected_stock)
bse_code = stock_data.get("bse_code") or "—"
st.caption(f"BSE Code: {bse_code}")

filings = load_filings(selected_stock)

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

if filings:
    conn = init_db(DB_PATH)
    stock_row = get_stock_by_bse_code(conn, bse_code)
    stock_id = stock_row["id"] if stock_row else None

    for f in filings:
        fid = f["id"]
        subject = f.get("subject", "") or ""
        filing_type_label = f.get("filing_type") or "—"
        status = f["status"]

        with st.expander(
            f"{f['filing_date']} | {subject[:80]}{'...' if len(subject) > 80 else ''}",
            expanded=False,
        ):
            cols = st.columns([1, 1, 1, 1])
            cols[0].markdown(f"**Type:** {filing_type_label}")
            cols[1].markdown(f"**Status:** {status}")
            cols[2].markdown(f"**ID:** {fid}")
            cols[3].markdown(f"[PDF]({f.get('pdf_url', '')})")

            if f.get("error"):
                st.error(f"Error: {f['error']}")

            if status == "READY":
                sections = get_sections(conn, fid)
                if sections:
                    st.markdown(f"**Sections ({len(sections)})**")

                    if stock_id:
                        diffs = {
                            d["section_header"]: d
                            for d in get_diffs_for_stock(conn, stock_id, limit=100)
                            if d["filing_id_new"] == fid
                        }
                    else:
                        diffs = {}

                    for sec in sections:
                        header = sec["header"]
                        sec_text = sec.get("text", "")
                        has_diff = header in diffs and diffs[header].get("changed")

                        badge = " 🔄 Changed" if has_diff else ""
                        with st.expander(
                            f"**{header}**{badge}",
                            expanded=bool(has_diff),
                        ):
                            preview = sec_text[:500]
                            st.text(preview + ("..." if len(sec_text) > 500 else ""))

                            if has_diff:
                                st.markdown("**Diff**")
                                st.code(
                                    diffs[header].get("diff_text", "")[:2000],
                                    language="diff",
                                )

    conn.close()

st.caption(
    "Data source: BSE Corporate Announcements API. "
    "Run `python -m diffiq.pipeline` to fetch new filings."
)
