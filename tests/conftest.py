"""Shared test fixtures — reduces boilerplate across all test files."""

import pytest
from diffiq.schema import init_db


@pytest.fixture
def db():
    """In-memory SQLite database for testing.

    Every test gets a clean database. No cleanup needed — the connection
    is closed and the in-memory DB disappears after the test.
    """
    conn = init_db(":memory:")
    yield conn
    conn.close()
