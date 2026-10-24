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


def test_api_reset_endpoint(app_client):
    """Verify POST /api/reset clears all tables and reset demo state."""
    # First scan demo data
    res_scan = app_client.post("/api/scan-demo")
    assert res_scan.status_code == 200

    inv1 = app_client.get("/api/inventory").get_json()
    assert inv1["total_sources"] > 0

    # Reset
    res_reset = app_client.post("/api/reset")
    assert res_reset.status_code == 200
    reset_data = res_reset.get_json()
    assert reset_data["success"] is True

    # Inventory must now be empty
    inv2 = app_client.get("/api/inventory").get_json()
    assert inv2["total_sources"] == 0
    assert inv2["total_records"] == 0
    assert inv2["total_findings"] == 0
    assert inv2["total_people"] == 0


def test_questionnaire_three_state_and_risk_text(app_client):
    """Verify unanswered default treated as 'no' for scoring with 'not confirmed' risk text."""
    # Initial state with no questionnaire answers
    res = app_client.get("/api/risks")
    assert res.status_code == 200
    data = res.get_json()

    # Default answers are 'unanswered'
    assert data["facts"]["breach_contact"] == "unanswered"
    assert data["facts"]["retention_policy"] == "unanswered"

    # In scoring, unanswered is treated as 'no', but title/text says 'not confirmed'
    breach_rule = next(r for r in data["rules"] if r["id"] == "breach_contact_process")
    assert breach_rule["status"] == "triggered"
    assert "not confirmed" in breach_rule["title"].lower()
    assert "no " not in breach_rule["title"].lower()

    retention_rule = next(r for r in data["rules"] if r["id"] == "retention_policy")
    assert retention_rule["status"] == "triggered"
    assert "not confirmed" in retention_rule["title"].lower()
    assert "no " not in retention_rule["title"].lower()

    # Now answer 'yes'
    app_client.post("/api/questionnaire", json={"breach_contact": "yes", "retention_policy": "yes"})
    data_yes = app_client.get("/api/risks").get_json()
    assert data_yes["facts"]["breach_contact"] == "yes"
    b_yes = next(r for r in data_yes["rules"] if r["id"] == "breach_contact_process")
    assert b_yes["status"] == "ok"
    r_yes = next(r for r in data_yes["rules"] if r["id"] == "retention_policy")
    assert r_yes["status"] == "ok"

    # Explicit 'no' restores standard 'No' risk text
    app_client.post("/api/questionnaire", json={"breach_contact": "no", "retention_policy": "no"})
    data_no = app_client.get("/api/risks").get_json()
    b_no = next(r for r in data_no["rules"] if r["id"] == "breach_contact_process")
    assert b_no["status"] == "triggered"
    assert b_no["title"] == "No breach contact/process"


