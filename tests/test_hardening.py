"""Tests for hardening, input safety, error handling, and config/salt management."""
import io
import os
import tempfile
import pytest
from app import create_app
from app.detect import get_salt, hash_value
from app.ingest import read_source, MAX_FILE_SIZE


@pytest.fixture
def test_client(tmp_path):
    db_file = tmp_path / "test_hardening.sqlite"
    app = create_app({
        "TESTING": True,
        "DATABASE": str(db_file),
    })
    with app.test_client() as client:
        yield client


# ---------------------------------------------------------------------------
# 1. Config and Salt tests
# ---------------------------------------------------------------------------
def test_salt_from_env(monkeypatch):
    """When KAVACH_SALT is set, get_salt() returns it."""
    monkeypatch.setenv("KAVACH_SALT", "custom-secret-salt-2026")
    salt = get_salt()
    assert salt == "custom-secret-salt-2026"
    assert hash_value("test@example.com") == hash_value("test@example.com", salt="custom-secret-salt-2026")


def test_salt_file_fallback(monkeypatch, tmp_path):
    """When KAVACH_SALT is unset, salt is read from or stored in data/.salt."""
    monkeypatch.delenv("KAVACH_SALT", raising=False)
    salt1 = get_salt()
    assert isinstance(salt1, str)
    assert len(salt1) >= 16

    salt2 = get_salt()
    assert salt1 == salt2


# ---------------------------------------------------------------------------
# 2. Input Safety: Upload tests
# ---------------------------------------------------------------------------
def test_upload_bad_extension(test_client):
    """Reject unsupported file extensions (e.g. .exe, .json).
    Note: .pdf is now valid when OCR is available; use .exe which is always rejected.
    """
    data = {
        "files": (io.BytesIO(b"MZ\x90\x00this-is-a-fake-exe"), "malware.exe")
    }
    resp = test_client.post("/api/upload", data=data, content_type="multipart/form-data")
    assert resp.status_code == 400
    res = resp.get_json()
    assert "error" in res
    assert "Unsupported file extension" in res["error"] or "Only .xlsx" in res["error"]


def test_upload_empty_file(test_client):
    """Reject empty 0-byte file."""
    data = {
        "files": (io.BytesIO(b""), "empty.csv")
    }
    resp = test_client.post("/api/upload", data=data, content_type="multipart/form-data")
    assert resp.status_code == 400
    res = resp.get_json()
    assert "error" in res
    assert "empty" in res["error"].lower()


def test_upload_oversize_file(test_client):
    """Reject file exceeding 10 MB limit."""
    oversize_bytes = b"A" * (MAX_FILE_SIZE + 1024)
    data = {
        "files": (io.BytesIO(oversize_bytes), "oversize.csv")
    }
    resp = test_client.post("/api/upload", data=data, content_type="multipart/form-data")
    assert resp.status_code in (400, 413)
    res = resp.get_json()
    assert "error" in res
    assert "exceeds" in res["error"].lower() or "limit" in res["error"].lower()


def test_upload_bad_encoding(test_client):
    """Show friendly error for invalid UTF-8 encoding in CSV/TXT without stack trace."""
    bad_bytes = b"Name,Phone\n\xff\xfe\xfaInvalid\x80\x81,9876543210\n"
    data = {
        "files": (io.BytesIO(bad_bytes), "bad_encoding.csv")
    }
    resp = test_client.post("/api/upload", data=data, content_type="multipart/form-data")
    assert resp.status_code == 400
    res = resp.get_json()
    assert "error" in res
    assert "encoding" in res["error"].lower() or "utf-8" in res["error"].lower()
    # Confirm no stack trace exposed in response
    assert "Traceback" not in resp.get_data(as_text=True)


def test_upload_corrupted_xlsx(test_client):
    """Show friendly error for corrupted Excel file without stack trace."""
    corrupted_bytes = b"PK\x03\x04not-a-valid-zip-or-excel-file"
    data = {
        "files": (io.BytesIO(corrupted_bytes), "corrupted.xlsx")
    }
    resp = test_client.post("/api/upload", data=data, content_type="multipart/form-data")
    assert resp.status_code == 400
    res = resp.get_json()
    assert "error" in res
    assert "corrupted" in res["error"].lower() or "invalid" in res["error"].lower()
    assert "Traceback" not in resp.get_data(as_text=True)


def test_upload_path_traversal_sanitised(test_client, tmp_path):
    """Path traversal filename (e.g. ../../evil.csv) is sanitised to safe basename and stored safely in workspace."""
    valid_csv = b"name,phone\nAnita Reddy,9876543210\n"
    data = {
        "files": (io.BytesIO(valid_csv), "../../evil_traversal.csv")
    }
    resp = test_client.post("/api/upload", data=data, content_type="multipart/form-data")
    assert resp.status_code == 200
    res = resp.get_json()
    assert res.get("success") is True
    assert res.get("files_scanned") == 1
    # Check that file was saved as basename evil_traversal.csv, not outside workspace
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    workspace_file = os.path.join(base_dir, "data", "workspace", "evil_traversal.csv")
    assert os.path.exists(workspace_file)
    # Cleanup
    if os.path.exists(workspace_file):
        os.remove(workspace_file)


# ---------------------------------------------------------------------------
# 3. Direct Ingest Safety tests
# ---------------------------------------------------------------------------
def test_read_source_row_limit(tmp_path):
    """Files exceeding 50,000 rows raise friendly ValueError."""
    csv_file = tmp_path / "long.csv"
    with open(csv_file, "w", encoding="utf-8") as f:
        f.write("header\n")
        for i in range(15):
            f.write(f"row_{i}\n")

    # With max_rows=10, reading raises ValueError
    with pytest.raises(ValueError) as excinfo:
        list(read_source(str(csv_file), max_rows=10))
    assert "exceeds maximum limit" in str(excinfo.value)
