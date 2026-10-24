"""Tests for rules engine, questionnaire, readiness score, and API endpoints."""
import os
import pytest
from app import create_app
from app.db import init_db, get_db
from app.rules import (
    load_rules,
    evaluate_rules,
    save_questionnaire_answers,
    collect_facts,
    QUESTIONNAIRE_KEYS,
)
from app.inventory import scan_demo_data


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    """Create Flask test client with an isolated SQLite database."""
    db_file = str(tmp_path / "test_routes.db")
    monkeypatch.setenv("KAVACH_DATABASE", db_file)
    app = create_app({"TESTING": True, "DATABASE": db_file})
    init_db(db_file)
    return app.test_client()


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    """Isolate standalone DB calls."""
    db_file = str(tmp_path / "test_rules.db")
    monkeypatch.setenv("KAVACH_DATABASE", db_file)
    init_db(db_file)
    yield db_file


def test_12_rules_loaded():
    """Verify exactly 12 rules exist in rules.yaml with all required fields."""
    rules = load_rules()
    assert len(rules) == 12

    required_fields = {"id", "title", "citation_hint", "trigger", "remediation", "severity", "verify"}
    for r in rules:
        for f in required_fields:
            assert f in r, f"Rule {r.get('id')} missing field {f}"
        assert r["verify"] is True
        assert r["severity"] in {"low", "med", "high", "critical"}


def test_employment_rule_lawful_basis():
    """Verify employee data processing lawful basis s.7(i) does NOT demand consent (positive note)."""
    conn = get_db()
    scan_demo_data(conn)

    results = evaluate_rules(conn)
    emp_rule = next(r for r in results["rules"] if r["id"] == "employee_data_lawful_basis")

    # Appears as positive / "ok" finding without consent demand
    assert emp_rule["status"] == "ok"
    assert emp_rule["deduction"] == 0
    assert "s.7(i)" in emp_rule["citation_hint"]
    # Ensure it did not add deductions to readiness score
    assert not any(d["rule_id"] == "employee_data_lawful_basis" for d in results["deductions"])


def test_questionnaire_rule_triggers_and_score():
    """Verify rules fire and clear as questionnaire answers change, updating readiness score."""
    conn = get_db()
    scan_demo_data(conn)

    # Initially cctv is 'no' -> notice_at_collection rule should be 'ok'
    save_questionnaire_answers({"cctv": "no"}, conn)
    res1 = evaluate_rules(conn)
    notice_rule1 = next(r for r in res1["rules"] if r["id"] == "notice_at_collection")
    assert notice_rule1["status"] == "ok"
    score1 = res1["readiness_score"]

    # Now set cctv to 'yes' -> notice_at_collection rule must trigger
    save_questionnaire_answers({"cctv": "yes"}, conn)
    res2 = evaluate_rules(conn)
    notice_rule2 = next(r for r in res2["rules"] if r["id"] == "notice_at_collection")
    assert notice_rule2["status"] == "triggered"
    assert notice_rule2["deduction"] == 10  # med severity = 10 points
    score2 = res2["readiness_score"]

    # Score must decrease by exactly 10 points
    assert score2 == score1 - 10


def test_retention_policy_questionnaire():
    """Verify retention policy rule triggers on 'no' and resolves on 'yes'."""
    conn = get_db()

    save_questionnaire_answers({"retention_policy": "no"}, conn)
    res_no = evaluate_rules(conn)
    r_no = next(r for r in res_no["rules"] if r["id"] == "retention_policy")
    assert r_no["status"] == "triggered"

    save_questionnaire_answers({"retention_policy": "yes"}, conn)
    res_yes = evaluate_rules(conn)
    r_yes = next(r for r in res_yes["rules"] if r["id"] == "retention_policy")
    assert r_yes["status"] == "ok"


def test_minors_parental_consent_rule():
    """Verify minors parental consent rule triggers under s.9 children."""
    conn = get_db()

    save_questionnaire_answers({"children_served": "yes"}, conn)
    res = evaluate_rules(conn)
    minors_rule = next(r for r in res["rules"] if r["id"] == "minors_parental_consent")
    assert minors_rule["status"] == "triggered"
    assert minors_rule["severity"] == "critical"
    assert minors_rule["deduction"] == 25
    assert "s.9" in minors_rule["citation_hint"]


def test_questionnaire_exactly_6_keys():
    """Verify exactly 6 questionnaire keys are supported."""
    assert len(QUESTIONNAIRE_KEYS) == 6
    expected_keys = {"cctv", "personal_phones", "vendors", "breach_contact", "retention_policy", "children_served"}
    assert QUESTIONNAIRE_KEYS == expected_keys


def test_api_endpoints(app_client):
    """Test all JSON endpoints via Flask client."""
    # 1. POST /api/scan-demo
    res = app_client.post("/api/scan-demo")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True

    # 2. GET /api/inventory
    res = app_client.get("/api/inventory")
    assert res.status_code == 200
    inv = res.get_json()
    assert inv["total_sources"] == 5
    assert inv["total_people"] > 0

    # 3. GET /api/people
    res = app_client.get("/api/people")
    assert res.status_code == 200
    people_data = res.get_json()
    assert len(people_data["people"]) > 0

    # 4. GET /api/people/1
    res = app_client.get("/api/people/1")
    assert res.status_code == 200
    person1 = res.get_json()
    assert person1["id"] == 1
    assert "records" in person1
    assert len(person1["records"]) > 0

    # 5. POST /api/questionnaire
    q_payload = {
        "cctv": "yes",
        "personal_phones": "no",
        "vendors": "no",
        "breach_contact": "yes",
        "retention_policy": "yes",
        "children_served": "no",
    }
    res = app_client.post("/api/questionnaire", json=q_payload)
    assert res.status_code == 200
    q_data = res.get_json()
    assert q_data["success"] is True
    assert q_data["saved"]["cctv"] == "yes"

    # 6. GET /api/risks
    res = app_client.get("/api/risks")
    assert res.status_code == 200
    risks_data = res.get_json()
    assert "readiness_score" in risks_data
    assert "deductions" in risks_data
    assert "rules" in risks_data
    assert len(risks_data["rules"]) == 12
