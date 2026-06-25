"""Tests for BSE crawler."""

import httpx
import pytest
from unittest.mock import patch, MagicMock

from diffiq.crawler import fetch_manifest, _parse_bse_date


class TestParseBseDate:
    """_parse_bse_date converts DD/MM/YYYY to YYYY-MM-DD."""

    def test_valid_date(self) -> None:
        assert _parse_bse_date("15/05/2026") == "2026-05-15"

    def test_valid_date_edge(self) -> None:
        assert _parse_bse_date("01/01/2025") == "2025-01-01"

    def test_empty_string(self) -> None:
        assert _parse_bse_date("") == ""

    def test_invalid_format(self) -> None:
        assert _parse_bse_date("2026-05-15") == ""

    def test_none(self) -> None:
        assert _parse_bse_date(None) == ""  # type: ignore[arg-type]


class TestFetchManifest:
    """fetch_manifest hits the BSE API and parses results."""

    SAMPLE_RESPONSE = [
        {
            "attchmntFile": "abc123.pdf",
            "desc": "Auditors Report",
            "dt": "15/05/2026",
            "sr_NO": 1,
        },
        {
            "attchmntFile": "def456.pdf",
            "desc": "Board Meeting Outcome",
            "dt": "10/05/2026",
            "sr_NO": 2,
        },
    ]

    @patch("diffiq.crawler.httpx.Client")
    def test_returns_list(self, mock_client: MagicMock) -> None:
        """fetch_manifest returns a list for a valid BSE code."""
        mock_instance = MagicMock()
        mock_instance.get.return_value.json.return_value = self.SAMPLE_RESPONSE
        mock_instance.get.return_value.raise_for_status.return_value = None
        mock_client.return_value.__enter__.return_value = mock_instance

        result = fetch_manifest("531456")
        assert isinstance(result, list)
        assert len(result) == 2

    @patch("diffiq.crawler.httpx.Client")
    def test_entry_structure(self, mock_client: MagicMock) -> None:
        """Each manifest entry has required keys."""
        mock_instance = MagicMock()
        mock_instance.get.return_value.json.return_value = self.SAMPLE_RESPONSE
        mock_instance.get.return_value.raise_for_status.return_value = None
        mock_client.return_value.__enter__.return_value = mock_instance

        result = fetch_manifest("531456")
        entry = result[0]
        assert "filing_uuid" in entry
        assert entry["filing_uuid"] == "abc123"
        assert "subject" in entry
        assert entry["subject"] == "Auditors Report"
        assert "filing_date" in entry
        assert entry["filing_date"] == "2026-05-15"
        assert "pdf_url" in entry
        assert "abc123.pdf" in entry["pdf_url"]

    @patch("diffiq.crawler.httpx.Client")
    def test_handles_http_error(self, mock_client: MagicMock) -> None:
        """fetch_manifest returns empty list on HTTP error."""
        mock_instance = MagicMock()
        mock_instance.get.side_effect = httpx.HTTPError("Connection error")
        mock_client.return_value.__enter__.return_value = mock_instance

        result = fetch_manifest("531456")
        assert result == []

    @patch("diffiq.crawler.httpx.Client")
    def test_handles_invalid_json(self, mock_client: MagicMock) -> None:
        """fetch_manifest returns empty list on parse failure."""
        mock_instance = MagicMock()
        mock_instance.get.return_value.json.side_effect = ValueError("bad json")
        mock_instance.get.return_value.raise_for_status.return_value = None
        mock_client.return_value.__enter__.return_value = mock_instance

        result = fetch_manifest("531456")
        assert result == []

    def test_integration_skip_if_api_down(self) -> None:
        """Live BSE API test — skip gracefully if unreachable."""
        try:
            result = fetch_manifest("531456")
            assert isinstance(result, list)
            if not result:
                pytest.skip("BSE API returned empty (may be down or no filings today)")
        except Exception:
            pytest.skip("BSE API unreachable — skipping live test")
