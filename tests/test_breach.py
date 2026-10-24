"""Tests for breach blast-radius simulator module and endpoints."""
import datetime
import json
import pytest

from app import create_app
from app.db import get_db, init_db
from app.detect import ALL_DETECTORS, detect_phone, detect_email, detect_aadhaar, detect_pan, detect_bank_account
from app.inventory import scan_demo_data
from app.breach import simulate, get_simulation, load_scenarios
from app.config import (
    BREACH_STAGE_1_DESCRIPTION,
    BREACH_STAGE_2_HOURS,
    BREACH_STAGE_2_DESCRIPTION,
    BREACH_INDIVIDUAL_NOTICE_NOTE,
)


@pytest.fixture
def app_with_demo(isolate_test_database):
    """Create test Flask app with scanned demo data in temp DB."""
    app = create_app({"TESTING": True, "DATABASE": isolate_test_database})
    with app.app_context():
        conn = get_db()
        init_db()
        scan_demo_data(conn)
    return app


@pytest.fixture
def client(app_with_demo):
    return app_with_demo.test_client()


def test_distinct_people_count_equals_direct_person_records(app_with_demo):
    """1. Distinct people count equals a direct count from person_records for each scenario."""
    with app_with_demo.app_context():
        conn = get_db()
        scenarios = ["owner_phone_stolen", "billing_laptop_ransomware", "public_form_link_leaked", "staff_laptop_lost"]
        for s in scenarios:
            res = simulate(s, conn=conn)
            affected_sources = res["affected_sources"]
            cur = conn.cursor()
            placeholders = ",".join("?" for _ in affected_sources)
            cur.execute(
                f"""SELECT COUNT(DISTINCT pr.person_id) 
                    FROM person_records pr 
                    JOIN sources s ON pr.source_id = s.id 
                    WHERE s.filename IN ({placeholders})""",
                affected_sources,
            )
            direct_count = cur.fetchone()[0]
            assert res["counts"]["people_count"] == direct_count
            assert res["counts"]["people"]["total"] == direct_count


def test_person_in_multiple_affected_sources_counted_once(app_with_demo):
    """2. A person present in several affected sources is counted once."""
    with app_with_demo.app_context():
        conn = get_db()
        # billing_laptop_ransomware affects billing.csv and patients.xlsx
        res = simulate("billing_laptop_ransomware", conn=conn)
        cur = conn.cursor()
        cur.execute(
            """SELECT pr.person_id, COUNT(DISTINCT pr.source_id) as src_count
               FROM person_records pr
               JOIN sources s ON pr.source_id = s.id
               WHERE s.filename IN ('billing.csv', 'patients.xlsx')
               GROUP BY pr.person_id
               HAVING src_count > 1"""
        )
        overlap_people = cur.fetchall()
        assert len(overlap_people) > 0, "Expected overlap of individuals across billing and patients"

        # Direct sum across sources would double-count overlapping people
        cur.execute(
            """SELECT COUNT(pr.person_id)
               FROM person_records pr
               JOIN sources s ON pr.source_id = s.id
               WHERE s.filename IN ('billing.csv', 'patients.xlsx')"""
        )
        # Verify deduplicated people count is strictly equal to unique people
        assert res["counts"]["people_count"] == 20


def test_confirmed_and_possible_reported_separately_and_sum(app_with_demo):
    """3. Confirmed + possible are reported separately and sum correctly."""
    with app_with_demo.app_context():
        conn = get_db()
        for s in ["owner_phone_stolen", "billing_laptop_ransomware", "public_form_link_leaked", "staff_laptop_lost"]:
            res = simulate(s, conn=conn)
            counts = res["counts"]
            confirmed = counts["confirmed_count"]
            possible = counts["possible_count"]
            total = counts["people_count"]

            assert confirmed == counts["people"]["confirmed"]
            assert possible == counts["people"]["possible"]
            assert confirmed + possible == total
            assert counts["range"] == f"{confirmed} - {total}"

        # owner_phone_stolen in particular has both confirmed and possible links
        ops_res = simulate("owner_phone_stolen", conn=conn)
        assert ops_res["counts"]["confirmed_count"] == 10
        assert ops_res["counts"]["possible_count"] == 5
        assert ops_res["counts"]["people_count"] == 15
        assert ops_res["counts"]["range"] == "10 - 15"


def test_ransomware_scenario_adds_availability_points(app_with_demo):
    """4. The ransomware scenario adds availability points."""
    with app_with_demo.app_context():
        conn = get_db()
        rw_res = simulate("billing_laptop_ransomware", conn=conn)
        rw_factors = {f["factor"]: f for f in rw_res["severity_factors"]}
        assert "availability_loss" in rw_factors
        assert rw_factors["availability_loss"]["points"] > 0
        assert "availability" in rw_factors["availability_loss"]["reason"].lower()

        # Non-ransomware scenario does not have availability factor
        phone_res = simulate("owner_phone_stolen", conn=conn)
        phone_factors = {f["factor"]: f for f in phone_res["severity_factors"]}
        assert "availability_loss" not in phone_factors


def test_device_protected_lowers_and_raises_severity(app_with_demo):
    """5. Device_protected yes lowers and no raises severity versus unknown."""
    with app_with_demo.app_context():
        conn = get_db()
        res_unk = simulate("owner_phone_stolen", device_protected="unknown", conn=conn)
        res_yes = simulate("owner_phone_stolen", device_protected="yes", conn=conn)
        res_no = simulate("owner_phone_stolen", device_protected="no", conn=conn)

        score_unk = res_unk["severity_score"]
        score_yes = res_yes["severity_score"]
        score_no = res_no["severity_score"]

        assert score_yes < score_unk, f"Expected protected (score={score_yes}) < unknown (score={score_unk})"
        assert score_no > score_unk, f"Expected unprotected (score={score_no}) > unknown (score={score_unk})"

        # Verify reasons state the status
        yes_factor = next(f for f in res_yes["severity_factors"] if f["factor"] == "device_protected")
        assert yes_factor["points"] < 0

        unk_factor = next(f for f in res_unk["severity_factors"] if f["factor"] == "device_protection_unknown")
        assert "unknown" in unk_factor["reason"].lower()
        assert "unprotected" in unk_factor["reason"].lower()


def test_severity_factors_sum_to_total(app_with_demo):
    """6. Severity factors sum to the total."""
    with app_with_demo.app_context():
        conn = get_db()
        for s in ["owner_phone_stolen", "billing_laptop_ransomware", "public_form_link_leaked", "staff_laptop_lost"]:
            for prot in ["yes", "no", "unknown"]:
                res = simulate(s, device_protected=prot, conn=conn)
                factors_sum = sum(f["points"] for f in res["severity_factors"])
                assert factors_sum == res["severity_score"]


def test_custom_scenario_two_sources_and_unknown_source_rejected(client):
    """7. Custom scenario with two sources works and an unknown source name is rejected with 400."""
    # Custom scenario with two valid sources
    resp = client.post(
        "/api/breach/simulate",
        json={"scenario": "custom", "sources": ["billing.csv", "staff.csv"]},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["scenario"] == "custom"
    assert "billing.csv" in data["affected_sources"]
    assert "staff.csv" in data["affected_sources"]
    assert data["counts"]["records_count"] == 25  # 15 billing + 10 staff

    # Custom scenario with an unknown source name
    resp_err = client.post(
        "/api/breach/simulate",
        json={"scenario": "custom", "sources": ["non_existent_records.csv"]},
    )
    assert resp_err.status_code == 400
    err_data = resp_err.get_json()
    assert "not found in database" in err_data.get("error", "").lower() or "unknown" in err_data.get("error", "").lower()


def test_drafts_contain_no_raw_identifiers_and_have_header(app_with_demo):
    """8. Drafts contain no raw identifiers (scan drafts with detect functions) and have DRAFT/SIMULATION header."""
    with app_with_demo.app_context():
        conn = get_db()
        for s in ["owner_phone_stolen", "billing_laptop_ransomware", "public_form_link_leaked", "staff_laptop_lost"]:
            res = simulate(s, conn=conn)
            drafts = res["drafts"]
            assert len(drafts) == 3
            for dname, dtext in drafts.items():
                # Header assert
                assert "DRAFT, SIMULATION, review before sending" in dtext, f"{dname} missing required header"

                # Detectors assert
                for detector in ALL_DETECTORS:
                    findings = detector(dtext, "draft", "test", {})
                    assert len(findings) == 0, f"Detector {detector.__name__} found raw PII in {dname}: {findings}"


def test_clocks_stage_2_deadline_exactly_72h(app_with_demo):
    """9. Clocks: stage 2 deadline is exactly aware_at + 72 h."""
    with app_with_demo.app_context():
        conn = get_db()
        test_aware = datetime.datetime(2026, 10, 24, 10, 30, 0, tzinfo=datetime.timezone.utc)
        res = simulate("owner_phone_stolen", aware_at=test_aware.isoformat(), conn=conn)

        clocks = res["clocks"]
        deadline_str = clocks["stage_2"]["deadline"]
        deadline_dt = datetime.datetime.fromisoformat(deadline_str)

        expected_deadline = test_aware + datetime.timedelta(hours=72)
        assert deadline_dt == expected_deadline
        assert clocks["stage_2"]["hours_limit"] == 72


def test_simulating_twice_creates_two_rows_and_ledger_entries(app_with_demo):
    """10. Simulating twice creates two rows and both appear in the ledger log."""
    with app_with_demo.app_context():
        conn = get_db()
        res1 = simulate("owner_phone_stolen", conn=conn)
        res2 = simulate("staff_laptop_lost", conn=conn)

        cur = conn.cursor()
        cur.execute("SELECT id, scenario FROM breach_simulations ORDER BY id")
        rows = cur.fetchall()
        assert len(rows) >= 2
        sim_ids = [r["id"] for r in rows]
        assert res1["id"] in sim_ids
        assert res2["id"] in sim_ids

        # Check ledger
        cur.execute("SELECT event_json FROM ledger ORDER BY id")
        ledger_rows = cur.fetchall()
        breach_events = []
        for lr in ledger_rows:
            ev = json.loads(lr["event_json"])
            if ev.get("event") == "breach_simulated":
                breach_events.append(ev)

        assert len(breach_events) >= 2
        assert all(ev.get("simulation") is True for ev in breach_events)


def test_api_get_scenarios(client):
    """11. GET /api/breach/scenarios returns all preconfigured scenarios."""
    resp = client.get("/api/breach/scenarios")
    assert resp.status_code == 200
    data = resp.get_json()
    scenarios = data.get("scenarios", [])
    scenario_ids = [s["id"] for s in scenarios]
    assert "owner_phone_stolen" in scenario_ids
    assert "billing_laptop_ransomware" in scenario_ids
    assert "public_form_link_leaked" in scenario_ids
    assert "staff_laptop_lost" in scenario_ids
    assert "custom" in scenario_ids

    # Verify each has first_hour_checklist with 6-8 items
    for s in scenarios:
        checklist = s.get("first_hour_checklist", [])
        assert 6 <= len(checklist) <= 8, f"Scenario {s['id']} checklist has {len(checklist)} items"


def test_api_get_simulation_by_id(client):
    """12. GET /api/breach/<id> retrieves simulation or 404."""
    # First create one
    post_resp = client.post("/api/breach/simulate", json={"scenario": "public_form_link_leaked"})
    assert post_resp.status_code == 200
    sim_id = post_resp.get_json()["id"]

    get_resp = client.get(f"/api/breach/{sim_id}")
    assert get_resp.status_code == 200
    sim_data = get_resp.get_json()
    assert sim_data["id"] == sim_id
    assert sim_data["scenario"] == "public_form_link_leaked"
    assert "clocks" in sim_data
    assert "drafts" in sim_data

    # Non-existent ID returns 404
    err_resp = client.get("/api/breach/999999")
    assert err_resp.status_code == 404


def test_api_recipients_endpoint_and_disclaimer(client):
    """13. GET /api/breach/<id>/recipients returns recipients and non-dispatch disclaimer."""
    post_resp = client.post("/api/breach/simulate", json={"scenario": "staff_laptop_lost"})
    sim_id = post_resp.get_json()["id"]

    rec_resp = client.get(f"/api/breach/{sim_id}/recipients")
    assert rec_resp.status_code == 200
    rec_data = rec_resp.get_json()
    assert rec_data["simulation_id"] == sim_id
    assert len(rec_data["recipients"]) == 10
    assert "cannot send" in rec_data["disclaimer"].lower()

    for r in rec_data["recipients"]:
        assert "label" in r
        assert "status" in r
        assert r["status"] in {"confirmed", "possible"}
        assert "phone_present" in r
        assert "email_present" in r


def test_api_export_html_printable_and_no_raw_pii(client):
    """14. GET /api/breach/<id>/export returns printable HTML without raw PII."""
    post_resp = client.post("/api/breach/simulate", json={"scenario": "owner_phone_stolen"})
    sim_id = post_resp.get_json()["id"]

    exp_resp = client.get(f"/api/breach/{sim_id}/export")
    assert exp_resp.status_code == 200
    assert "text/html" in exp_resp.content_type
    html = exp_resp.get_data(as_text=True)

    assert "Breach Response Simulation Pack" in html
    assert "DRAFT, SIMULATION" in html
    assert "window.print()" in html
    assert "@media print" in html

    # Verify no raw PII in exported HTML
    for det in [detect_phone, detect_email, detect_aadhaar, detect_pan, detect_bank_account]:
        findings = det(html, "export", "test", {})
        assert len(findings) == 0, f"{det.__name__} found PII in export HTML: {findings}"


def test_severity_note_is_present_on_simulation(app_with_demo):
    """15. Severity includes disclaimer that it is Kavach's estimate, not a legal threshold."""
    with app_with_demo.app_context():
        conn = get_db()
        res = simulate("owner_phone_stolen", conn=conn)
        assert res["severity_note"] == "Severity is Kavach's own estimate to help prioritise, not a legal threshold."


def test_categories_flag_high_impact_and_counts(app_with_demo):
    """16. Categories breakdown counts records and distinct people, and flags high impact."""
    with app_with_demo.app_context():
        conn = get_db()
        res = simulate("owner_phone_stolen", conn=conn)
        cats = res["counts"]["categories"]
        assert "phone" in cats
        assert cats["phone"]["records"] > 0
        assert cats["phone"]["people"] > 0
        assert cats["phone"]["is_high_impact"] is False

        assert "aadhaar" in cats
        assert cats["aadhaar"]["is_high_impact"] is True

        assert "health_term" in cats
        assert cats["health_term"]["is_high_impact"] is True
