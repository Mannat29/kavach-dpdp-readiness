"""Tests for Task 6b: Reports page, compliance summary, and printable export."""
import datetime
import json
import pytest

from app import create_app
from app.db import get_db, init_db
from app.detect import (
    detect_phone,
    detect_email,
    detect_aadhaar,
    detect_pan,
    detect_bank_account,
)
from app.inventory import scan_demo_data
from app.rights import process_intake


@pytest.fixture
def app_empty(isolate_test_database):
    """Create test Flask app with empty DB."""
    app = create_app({"TESTING": True, "DATABASE": isolate_test_database})
    with app.app_context():
        init_db()
    return app


@pytest.fixture
def app_with_demo(isolate_test_database):
    """Create test Flask app with scanned demo data."""
    app = create_app({"TESTING": True, "DATABASE": isolate_test_database})
    with app.app_context():
        conn = get_db()
        init_db()
        scan_demo_data(conn)
    return app


def test_empty_db_summary(app_empty):
    """Empty DB returns a valid empty summary without errors."""
    client = app_empty.test_client()
    resp = client.get("/api/reports/summary")
    assert resp.status_code == 200
    data = resp.get_json()

    assert "scan_summary" in data
    scan = data["scan_summary"]
    assert scan["total_sources"] == 0
    assert scan["records"] == 0
    assert scan["distinct_people"] == 0
    assert scan["per_category_counts"] == {}
    assert scan["high_impact_sources"] == []

    assert "readiness_score" in data
    assert "score" in data
    assert "triggered_risks" in data
    assert "questionnaire" in data
    assert len(data["questionnaire"]) == 6
    for q in data["questionnaire"]:
        assert q["answer"] == "not answered"

    assert "rights_requests" in data
    assert data["rights_requests"]["open_requests"] == []
    assert data["erasure_receipts"] == []
    assert data["breach_simulations"] == []

    assert "recommended_actions" in data
    assert isinstance(data["recommended_actions"], list)
    assert len(data["recommended_actions"]) <= 8

    # Also verify empty state on HTML page
    html_resp = client.get("/reports")
    assert html_resp.status_code == 200
    html_text = html_resp.get_data(as_text=True)
    assert "reports-empty-state" in html_text or "No Scan Data Available" in html_text


def test_summary_no_raw_identifiers(app_with_demo):
    """Verify summary contains zero raw identifiers by scanning JSON with detect functions."""
    client = app_with_demo.test_client()

    # Create a rights request with proper Hinglish erase phrase
    with app_with_demo.app_context():
        conn = get_db()
        created = process_intake([
            {
                "sender": "Ramesh Kumar",
                "text": "Mera number aur details list se hata dijiye",
                "timestamp": "20/10/26, 9:05 pm",
            }
        ], conn)
        # If person not resolved, skip erasure part—we still test summary JSON
        if created and created[0].get("person_id"):
            from app.erasure import build_plan, execute
            req_id = created[0]["id"]
            plan = build_plan(req_id, conn)
            # Approve the plan before executing
            cur = conn.cursor()
            cur.execute("UPDATE rights_requests SET status = 'approved' WHERE id = ?", (req_id,))
            conn.commit()
            execute(req_id, plan["plan_hash"], conn)

        # Run a breach simulation
        from app.breach import simulate
        simulate("staff_laptop_lost", device_protected="no", conn=conn)

    resp = client.get("/api/reports/summary")
    assert resp.status_code == 200
    data = resp.get_json()

    # Convert complete summary JSON to string
    summary_json_str = json.dumps(data)

    # Scan with detect functions — no raw identifiers should appear
    phone_findings = detect_phone(summary_json_str, "report_summary", "json", {})
    email_findings = detect_email(summary_json_str, "report_summary", "json", {})
    aadhaar_findings = detect_aadhaar(summary_json_str, "report_summary", "json", {})
    pan_findings = detect_pan(summary_json_str, "report_summary", "json", {})
    bank_findings = detect_bank_account(summary_json_str, "report_summary", "json", {})

    assert len(phone_findings) == 0, f"Raw phones detected in summary: {phone_findings}"
    assert len(email_findings) == 0, f"Raw emails detected in summary: {email_findings}"
    assert len(aadhaar_findings) == 0, f"Raw Aadhaar detected in summary: {aadhaar_findings}"
    assert len(pan_findings) == 0, f"Raw PAN detected in summary: {pan_findings}"
    assert len(bank_findings) == 0, f"Raw bank account detected in summary: {bank_findings}"


def test_overdue_request_listed_first_in_recommended_actions(app_with_demo):
    """An overdue request is listed first in recommended actions (create one with a past due date)."""
    with app_with_demo.app_context():
        conn = get_db()
        cur = conn.cursor()
        past_due = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=15)).isoformat()
        cur.execute("""
            INSERT INTO rights_requests
            (intent, sender_masked, status, received_at, due_at, message_excerpt_masked)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            "erasure",
            "R**** K***",
            "received",
            (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=45)).isoformat(),
            past_due,
            "Please delete all my clinic data",
        ))
        conn.commit()

    client = app_with_demo.test_client()
    resp = client.get("/api/reports/summary")
    assert resp.status_code == 200
    data = resp.get_json()

    actions = data["recommended_actions"]
    assert len(actions) > 0
    assert len(actions) <= 8

    # The overdue request MUST be listed first (#1)
    first_action = actions[0]
    assert first_action["priority"] == 1
    assert first_action["category"] == "overdue_request"
    assert "Overdue" in first_action["title"]
    assert "overdue by" in first_action["reason"]
    assert first_action["link"] == "/rights-desk"
    assert first_action["page"] == "Rights Desk"


def test_export_contains_notices_and_constants(app_with_demo):
    """Printable HTML export contains the required notices, detector accuracy constants, and ledger event."""
    client = app_with_demo.test_client()
    resp = client.get("/api/reports/export")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["Content-Type"]

    html = resp.get_data(as_text=True)

    # Title check
    assert "<title>Kavach privacy readiness report</title>" in html

    # Business name placeholder check
    assert "[Business Name / Data Fiduciary]" in html

    # Print stylesheet check
    assert "@media print" in html

    # Not-legal-advice notice check
    assert "not constitute formal legal advice" in html

    # Citations-to-verify notice check
    assert "citations" in html.lower() and "verify" in html.lower()

    # Detector accuracy numbers check from app.config.REPORTED_ACCURACY
    assert "0.91" in html
    assert "0.85" in html
    assert "synthetic" in html.lower()

    # Verify ledger event report_generated was emitted
    with app_with_demo.app_context():
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM ledger WHERE type = 'report_generated'")
        events = cur.fetchall()
        assert len(events) >= 1
        found_export = False
        for ev in events:
            payload = json.loads(ev["payload_json"])
            if payload.get("report_type") == "printable_export":
                found_export = True
                break
        assert found_export, "Ledger event report_generated for printable_export not found"


def test_full_demo_flow_report_sections(app_with_demo):
    """After a full demo flow the report shows scan results, risks, requests, breach simulations and recommended actions."""
    client = app_with_demo.test_client()

    with app_with_demo.app_context():
        conn = get_db()

        # Intake a rights request (skip erasure if person_id not resolved)
        created = process_intake([
            {
                "sender": "Ramesh Kumar",
                "text": "Mera number aur details list se hata dijiye",
                "timestamp": "20/10/26, 9:05 pm",
            }
        ], conn)

        if created and created[0].get("person_id"):
            from app.erasure import build_plan, execute
            req_id = created[0]["id"]
            plan = build_plan(req_id, conn)
            # Approve the plan before executing
            cur = conn.cursor()
            cur.execute("UPDATE rights_requests SET status = 'approved' WHERE id = ?", (req_id,))
            conn.commit()
            execute(req_id, plan["plan_hash"], conn)

        # Simulate breach
        from app.breach import simulate
        simulate("staff_laptop_lost", device_protected="no", conn=conn)

    # Fetch summary
    resp = client.get("/api/reports/summary")
    assert resp.status_code == 200
    summary = resp.get_json()

    # Scan results present
    assert summary["scan_summary"]["total_sources"] >= 3
    assert summary["scan_summary"]["records"] > 0
    assert summary["scan_summary"]["distinct_people"] > 0
    assert len(summary["scan_summary"]["high_impact_sources"]) > 0

    # Triggered risks present
    assert len(summary["triggered_risks"]) > 0
    for r in summary["triggered_risks"]:
        assert "citation" in r
        assert "verify" in r
        assert "remediation" in r

    # Breach simulations present and marked SIMULATION
    assert len(summary["breach_simulations"]) >= 1
    sim = summary["breach_simulations"][0]
    assert sim["scenario"] == "staff_laptop_lost"
    assert sim["marked"] == "SIMULATION"
    assert "people_counts" in sim

    # Recommended actions present (max 8)
    assert 1 <= len(summary["recommended_actions"]) <= 8
    for act in summary["recommended_actions"]:
        assert "reason" in act
        assert "link" in act
        assert "page" in act

    # UI page renders with all sections and no colour-only meaning
    ui_resp = client.get("/reports")
    assert ui_resp.status_code == 200
    ui_html = ui_resp.get_data(as_text=True)
    assert "Download printable report" in ui_html
    assert "[SIMULATION]" in ui_html
    assert "[VERIFY REQUIRED]" in ui_html
