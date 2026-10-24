"""Tests for frontend-supporting JSON endpoints."""
import pytest
from app import create_app
from app.db import init_db


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    """Create Flask test client with an isolated SQLite database."""
    db_file = str(tmp_path / "test_api_routes.db")
    monkeypatch.setenv("KAVACH_DATABASE", db_file)
    app = create_app({"TESTING": True, "DATABASE": db_file})
    init_db(db_file)
    return app.test_client()


def test_api_findings_empty_and_populated(app_client):
    """Test GET /api/findings on empty DB and after demo scan with filters."""
    # Empty DB
    res = app_client.get("/api/findings")
    assert res.status_code == 200
    data = res.get_json()
    assert data["total"] == 0
    assert data["findings"] == []

    # Populate with demo data
    scan_res = app_client.post("/api/scan-demo")
    assert scan_res.status_code == 200

    # Fetch all findings
    res = app_client.get("/api/findings")
    assert res.status_code == 200
    data = res.get_json()
    assert data["total"] > 0
    assert len(data["findings"]) == data["total"]
    assert "source_category_counts" in data
    assert "category_counts" in data

    # Filter by category
    res_cat = app_client.get("/api/findings?category=phone")
    assert res_cat.status_code == 200
    data_cat = res_cat.get_json()
    assert data_cat["total"] > 0
    assert all(f["category"] == "phone" for f in data_cat["findings"])

    # Filter by source filename
    res_src = app_client.get("/api/findings?source=staff.csv")
    assert res_src.status_code == 200
    data_src = res_src.get_json()
    assert data_src["total"] > 0
    assert all(f["source_name"] == "staff.csv" for f in data_src["findings"])


def test_api_questionnaire_get_and_post(app_client):
    """Test GET and POST on /api/questionnaire."""
    # Initial GET
    res = app_client.get("/api/questionnaire")
    assert res.status_code == 200
    data = res.get_json()
    assert "answers" in data
    assert "facts" in data

    # POST new answers
    post_res = app_client.post("/api/questionnaire", json={
        "cctv": "yes",
        "retention_policy": "no"
    })
    assert post_res.status_code == 200
    post_data = post_res.get_json()
    assert post_data["success"] is True
    assert post_data["facts"]["cctv"] == "yes"

    # GET verifies persisted answers
    res2 = app_client.get("/api/questionnaire")
    assert res2.status_code == 200
    data2 = res2.get_json()
    assert data2["answers"].get("cctv") == "yes"
    assert data2["facts"]["cctv"] == "yes"


def test_html_views_render(app_client):
    """Verify all 8 navigation views render correctly with Kavach branding and legal banner."""
    routes = [
        ("/", "Dashboard – Kavach"),
        ("/dashboard", "Dashboard – Kavach"),
        ("/scanner", "Scanner – Kavach"),
        ("/data-map", "Data Map – Kavach"),
        ("/rights-desk", "Rights Desk – Kavach"),
        ("/breach-simulator", "Breach Simulator – Kavach"),
        ("/risk-analysis", "Risk Analysis – Kavach"),
        ("/reports", "Reports – Kavach"),
        ("/evidence", "Evidence – Kavach"),
    ]
    for url, expected_title in routes:
        res = app_client.get(url)
        assert res.status_code == 200, f"Route {url} failed with status {res.status_code}"
        html = res.get_data(as_text=True)
        assert expected_title in html
        assert "Readiness aid, not legal advice. Citations pending verification." in html
        assert "Kavach" in html

