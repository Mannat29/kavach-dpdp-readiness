"""Global pytest configuration ensuring all tests use temporary databases."""
import os
import pytest
from app.db import init_db


@pytest.fixture(autouse=True)
def isolate_test_database(tmp_path, monkeypatch):
    """Isolate DB for all tests so tests never touch the real database."""
    test_db = str(tmp_path / "kavach_test_isolated.sqlite")
    monkeypatch.setenv("KAVACH_DATABASE", test_db)
    monkeypatch.setenv("KAVACH_KEEP_DB", "1")
    init_db(test_db)
    yield test_db
