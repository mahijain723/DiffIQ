"""Tests for section-aligned text differ."""

from unittest.mock import patch

import pytest
from diffiq.differ import (
    align_sections,
    diff_section,
    find_prior_filing,
    run_diffs_for_filing,
)
from diffiq.schema import init_db


class TestDiffer:
    def test_find_prior(self) -> None:
        conn = init_db(":memory:")
        conn.execute(
            "INSERT INTO stocks (id, bse_code, name) VALUES (1, '500295', 'VEDL')"
        )
        conn.execute(
            """INSERT INTO filings (id, stock_id, filing_uuid, filing_date, subject, pdf_url, status, filing_type)
               VALUES (1, 1, 'u1', '2026-01-01', 'Audit 2025', 'https://ex.com/1.pdf', 'READY', 'AUDIT_REPORT')"""
        )
        conn.execute(
            """INSERT INTO filings (id, stock_id, filing_uuid, filing_date, subject, pdf_url, status, filing_type)
               VALUES (2, 1, 'u2', '2026-06-01', 'Audit 2026', 'https://ex.com/2.pdf', 'READY', 'AUDIT_REPORT')"""
        )

        prior = find_prior_filing(conn, 1, "AUDIT_REPORT", 2)
        assert prior is not None
        assert prior["id"] == 1

        conn.close()

    def test_no_prior(self) -> None:
        conn = init_db(":memory:")
        conn.execute(
            "INSERT INTO stocks (id, bse_code, name) VALUES (1, '500295', 'VEDL')"
        )
        conn.execute(
            """INSERT INTO filings (id, stock_id, filing_uuid, filing_date, subject, pdf_url, status, filing_type)
               VALUES (1, 1, 'u1', '2026-01-01', 'Audit 2025', 'https://ex.com/1.pdf', 'READY', 'AUDIT_REPORT')"""
        )

        prior = find_prior_filing(conn, 1, "FINANCIAL_RESULT", 1)
        assert prior is None

        conn.close()

    def test_no_prior_when_only_one(self) -> None:
        conn = init_db(":memory:")
        conn.execute(
            "INSERT INTO stocks (id, bse_code, name) VALUES (1, '500295', 'VEDL')"
        )
        conn.execute(
            """INSERT INTO filings (id, stock_id, filing_uuid, filing_date, subject, pdf_url, status, filing_type)
               VALUES (1, 1, 'u1', '2026-01-01', 'Audit 2025', 'https://ex.com/1.pdf', 'READY', 'AUDIT_REPORT')"""
        )

        prior = find_prior_filing(conn, 1, "AUDIT_REPORT", 1)
        assert prior is None

        conn.close()

    def test_section_alignment(self) -> None:
        new_sections = [
            {"header": "Opinion", "text": "In our opinion...", "section_idx": 0},
            {"header": "Basis for Opinion", "text": "We conducted...", "section_idx": 1},
        ]
        old_sections = [
            {"header": "Opinion", "text": "In our opinion (old)...", "section_idx": 0},
            {"header": "Basis for Opinion", "text": "We conducted (old)...", "section_idx": 1},
        ]

        aligned = align_sections(new_sections, old_sections)
        assert len(aligned) == 2
        assert aligned[0][1] is not None
        assert aligned[0][1]["header"] == "Opinion"
        assert aligned[1][1] is not None
        assert aligned[1][1]["header"] == "Basis for Opinion"

    def test_alignment_no_match(self) -> None:
        new_sections = [
            {"header": "New Section", "text": "Brand new content here", "section_idx": 0},
        ]
        old_sections = [
            {"header": "Opinion", "text": "In our opinion...", "section_idx": 0},
        ]

        aligned = align_sections(new_sections, old_sections)
        assert len(aligned) == 1
        assert aligned[0][1] is None

    def test_diff_changed(self) -> None:
        old_text = "The company reported a profit of Rs. 100 Cr."
        new_text = "The company reported a profit of Rs. 150 Cr."

        diff_text, changed = diff_section(new_text, old_text)
        assert changed is True
        assert "Rs. 100 Cr" in diff_text
        assert "Rs. 150 Cr" in diff_text

    def test_diff_unchanged(self) -> None:
        text = "The company reported a profit of Rs. 100 Cr."
        diff_text, changed = diff_section(text, text)
        assert changed is False

    def test_empty_diff(self) -> None:
        diff_text, changed = diff_section("", "")
        assert changed is False

    def test_run_diffs_no_prior(self) -> None:
        conn = init_db(":memory:")
        conn.execute(
            "INSERT INTO stocks (id, bse_code, name) VALUES (1, '500295', 'VEDL')"
        )
        conn.execute(
            """INSERT INTO filings (id, stock_id, filing_uuid, filing_date, subject, pdf_url, status, filing_type)
               VALUES (1, 1, 'u1', '2026-01-01', 'Audit 2026', 'https://ex.com/1.pdf', 'READY', 'AUDIT_REPORT')"""
        )

        changed = run_diffs_for_filing(conn, 1, 1, "AUDIT_REPORT")
        assert changed == 0

        conn.close()

    def test_run_diffs_with_prior(self) -> None:
        conn = init_db(":memory:")
        conn.execute(
            "INSERT INTO stocks (id, bse_code, name) VALUES (1, '500295', 'VEDL')"
        )
        conn.execute(
            """INSERT INTO filings (id, stock_id, filing_uuid, filing_date, subject, pdf_url, status, filing_type)
               VALUES (1, 1, 'u1', '2026-01-01', 'Audit 2025', 'https://ex.com/1.pdf', 'READY', 'AUDIT_REPORT')"""
        )
        conn.execute(
            """INSERT INTO sections (filing_id, header, text, section_idx)
               VALUES (1, 'Opinion', 'Old opinion text', 0)"""
        )
        conn.execute(
            """INSERT INTO sections (filing_id, header, text, section_idx)
               VALUES (1, 'Basis', 'Old basis text', 1)"""
        )

        conn.execute(
            """INSERT INTO filings (id, stock_id, filing_uuid, filing_date, subject, pdf_url, status, filing_type)
               VALUES (2, 1, 'u2', '2026-06-01', 'Audit 2026', 'https://ex.com/2.pdf', 'READY', 'AUDIT_REPORT')"""
        )
        conn.execute(
            """INSERT INTO sections (filing_id, header, text, section_idx)
               VALUES (2, 'Opinion', 'New opinion text with changes and additional content to make the diff longer than one hundred characters in total output', 0)"""
        )
        conn.execute(
            """INSERT INTO sections (filing_id, header, text, section_idx)
               VALUES (2, 'Basis', 'Old basis text', 1)"""
        )

        changed = run_diffs_for_filing(conn, 2, 1, "AUDIT_REPORT")
        assert changed >= 1

        diff_rows = conn.execute(
            "SELECT * FROM diffs WHERE filing_id_new = 2"
        ).fetchall()
        assert len(diff_rows) >= 1

        conn.close()
