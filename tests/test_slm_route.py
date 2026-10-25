"""Tests for opt-in SLM suggestion API route (POST /api/slm/suggest)."""
import json
import pytest
from app import create_app
from app.db import get_db, init_db


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    """Create Flask test client with an isolated SQLite database."""
    db_file = str(tmp_path / "test_slm_route.db")
    monkeypatch.setenv("KAVACH_DATABASE", db_file)
    app = create_app({"TESTING": True, "DATABASE": db_file})
    with app.app_context():
        init_db(db_file)
    return app.test_client()


def _get_all_table_counts(client):
    """Query row count of all application tables in the database."""
    with client.application.app_context():
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = [row[0] for row in cur.fetchall()]
        counts = {}
        for t in tables:
            cur.execute(f"SELECT count(*) FROM {t}")
            counts[t] = cur.fetchone()[0]
        return counts


def test_slm_suggest_off_by_default(app_client, monkeypatch):
    """When SLM_MODE is off (the default), returns 200 with mode off and empty findings."""
    monkeypatch.delenv("SLM_MODE", raising=False)
    resp = app_client.post(
        "/api/slm/suggest",
        json={
            "text": "Patient has diabetes and is a 15-year-old student.",
            "filename": "clinic.xlsx",
            "column": "notes",
        },
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["mode"] == "off"
    assert data["chunk_status"] == "off"
    assert data["findings"] == []
    assert data["needs_review"] == []


def test_slm_suggest_mock_mode(app_client, monkeypatch):
    """In mock mode, returns findings for diabetes sentence and no raw text in JSON findings."""
    monkeypatch.setenv("SLM_MODE", "mock")
    text = "Client has diabetes and cannot pay fees."
    resp = app_client.post(
        "/api/slm/suggest",
        json={"text": text, "filename": "clinic.xlsx", "column": "notes"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["mode"] == "mock"
    assert data["chunk_status"] == "ok"
    assert len(data["findings"]) > 0

    # Ensure findings contain only metadata and NO raw text
    findings_dump = json.dumps(data["findings"])
    assert "diabetes" not in findings_dump
    assert "cannot pay" not in findings_dump

    for f in data["findings"]:
        assert set(f.keys()) == {"category", "start", "end", "locator"}
        assert f["locator"]["filename"] == "clinic.xlsx"
        assert f["locator"]["column"] == "notes"
        # Consumer re-slices source text using offsets
        assert text[f["start"]:f["end"]] in ("diabetes", "cannot pay")


def test_slm_suggest_bad_input(app_client):
    """Reject missing text, non-string text, or text exceeding 4000 chars with 400."""
    # Missing text
    resp = app_client.post("/api/slm/suggest", json={"filename": "notes.csv"})
    assert resp.status_code == 400
    assert "text" in resp.get_json()["error"].lower()

    # Non-string text (int)
    resp = app_client.post("/api/slm/suggest", json={"text": 12345})
    assert resp.status_code == 400

    # Non-string text (None)
    resp = app_client.post("/api/slm/suggest", json={"text": None})
    assert resp.status_code == 400

    # Non-string text (list)
    resp = app_client.post("/api/slm/suggest", json={"text": ["diabetes"]})
    assert resp.status_code == 400

    # Non-JSON / non-dict payload
    resp = app_client.post(
        "/api/slm/suggest",
        data="plain-text-not-json",
        content_type="application/json",
    )
    assert resp.status_code == 400

    # Text exceeding 4000 characters
    resp = app_client.post(
        "/api/slm/suggest",
        json={"text": "a" * 4001, "filename": "big.txt"},
    )
    assert resp.status_code == 400
    assert "4000" in resp.get_json()["error"]


def test_slm_suggest_no_database_writes(app_client, monkeypatch):
    """Never write to the database or ledger when calling /api/slm/suggest."""
    counts_before = _get_all_table_counts(app_client)

    # 1. Off mode call
    monkeypatch.delenv("SLM_MODE", raising=False)
    app_client.post(
        "/api/slm/suggest",
        json={"text": "Patient has diabetes", "filename": "clinic.xlsx"},
    )

    # 2. Mock mode call with findings
    monkeypatch.setenv("SLM_MODE", "mock")
    app_client.post(
        "/api/slm/suggest",
        json={"text": "Patient has diabetes and cannot pay", "filename": "clinic.xlsx"},
    )

    # 3. Bad input call
    app_client.post("/api/slm/suggest", json={"text": 999})

    counts_after = _get_all_table_counts(app_client)
    assert counts_before == counts_after, f"DB changed! before={counts_before}, after={counts_after}"
