"""Rules engine and questionnaire module for Kavach DPDP readiness."""
import json
import os
from typing import Dict, List, Any, Optional

import yaml

from app.db import get_db

QUESTIONNAIRE_KEYS = {
    "cctv",
    "personal_phones",
    "vendors",
    "breach_contact",
    "retention_policy",
    "children_served",
}

SEVERITY_WEIGHTS = {
    "critical": 25,
    "high": 15,
    "med": 10,
    "low": 5,
}


def load_rules() -> List[Dict[str, Any]]:
    """Load the 12 rules from rules.yaml."""
    rules_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules", "rules.yaml")
    with open(rules_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def evaluate_condition(cond: Dict[str, Any], facts: Dict[str, Any]) -> bool:
    """Evaluate a structured condition over facts without using eval()."""
    if "any" in cond:
        return any(evaluate_condition(c, facts) for c in cond["any"])
    if "all" in cond:
        return all(evaluate_condition(c, facts) for c in cond["all"])

    fact_name = cond.get("fact")
    op = cond.get("operator", "==")
    target_val = cond.get("value")

    fact_val = facts.get(fact_name)

    if op == "==":
        return fact_val == target_val
    elif op == "!=":
        return fact_val != target_val
    elif op == ">":
        return fact_val is not None and fact_val > target_val
    elif op == ">=":
        return fact_val is not None and fact_val >= target_val
    elif op == "<":
        return fact_val is not None and fact_val < target_val
    elif op == "<=":
        return fact_val is not None and fact_val <= target_val
    elif op == "in":
        return fact_val in target_val
    return False


def collect_facts(conn=None) -> Dict[str, Any]:
    """Collect facts from inventory and questionnaire tables."""
    if conn is None:
        conn = get_db()

    cur = conn.cursor()

    # 1. Facts from Questionnaire (default is 'unanswered')
    facts = {
        "cctv": "unanswered",
        "personal_phones": "unanswered",
        "vendors": "unanswered",
        "breach_contact": "unanswered",
        "retention_policy": "unanswered",
        "children_served": "unanswered",
    }
    cur.execute("SELECT key, answer FROM questionnaire")
    for row in cur.fetchall():
        k = row["key"].strip().lower()
        if k in QUESTIONNAIRE_KEYS:
            val = row["answer"].strip().lower()
            if val in {"yes", "no", "unanswered"}:
                facts[k] = val

    # 2. Facts from Inventory / Findings
    cur.execute("SELECT COUNT(*) as count FROM findings WHERE category = 'health_term'")
    facts["has_health_data"] = cur.fetchone()["count"] > 0

    # Aadhaar in chat or free text
    cur.execute("""
        SELECT COUNT(*) as count 
        FROM findings f 
        JOIN sources s ON f.source_id = s.id 
        WHERE f.category = 'aadhaar' AND (s.type = 'txt' OR s.filename LIKE '%chat%' OR s.filename LIKE '%whatsapp%')
    """)
    facts["has_aadhaar_in_chat"] = cur.fetchone()["count"] > 0

    # Aadhaar source count
    cur.execute("""
        SELECT COUNT(DISTINCT f.source_id) as count 
        FROM findings f 
        WHERE f.category = 'aadhaar'
    """)
    facts["aadhaar_source_count"] = cur.fetchone()["count"]

    # Minors present in DOB findings
    cur.execute("SELECT meta_json FROM findings WHERE category = 'dob'")
    has_minors = False
    for row in cur.fetchall():
        if row["meta_json"]:
            try:
                meta = json.loads(row["meta_json"])
                if meta.get("is_minor"):
                    has_minors = True
                    break
            except json.JSONDecodeError:
                pass
    facts["has_minors"] = has_minors

    # Employee data present (staff file)
    cur.execute("SELECT COUNT(*) as count FROM sources WHERE filename LIKE '%staff%' OR filename LIKE '%employee%'")
    facts["has_employee_data"] = cur.fetchone()["count"] > 0

    # Max sources for any single person
    cur.execute("""
        SELECT person_id, COUNT(DISTINCT source_id) as s_count 
        FROM person_records 
        GROUP BY person_id 
        ORDER BY s_count DESC 
        LIMIT 1
    """)
    row = cur.fetchone()
    max_person_sources = row["s_count"] if row else 0
    facts["max_person_source_count"] = max_person_sources
    facts["data_sprawl"] = max_person_sources >= 3

    return facts


def evaluate_rules(conn=None) -> Dict[str, Any]:
    """Evaluate all 12 rules against collected facts, update risks table, and compute score."""
    if conn is None:
        conn = get_db()

    facts = collect_facts(conn)
    rules = load_rules()

    # For scoring, treat 'unanswered' questionnaire keys as 'no'
    scoring_facts = dict(facts)
    for k in QUESTIONNAIRE_KEYS:
        if scoring_facts.get(k) == "unanswered":
            scoring_facts[k] = "no"

    cur = conn.cursor()
    cur.execute("DELETE FROM risks")

    results = []
    deductions = []

    for r in rules:
        r_id = r["id"]
        is_triggered = evaluate_condition(r["trigger"], scoring_facts)

        title = r["title"]
        remediation = r["remediation"]

        # If triggered because an answer was unanswered, risk text says 'not confirmed' instead of 'none' / 'No '
        if r_id == "breach_contact_process" and facts.get("breach_contact") == "unanswered":
            title = "Breach contact/process not confirmed"
            remediation = "Breach contact/process not confirmed. Formulate a formal breach response plan and publish a designated breach point of contact to intimate the Data Protection Board and affected principals."
        elif r_id == "retention_policy" and facts.get("retention_policy") == "unanswered":
            title = "Retention policy not confirmed"
            remediation = "Retention policy not confirmed. Establish a documented retention policy to periodically erase personal data once diagnostic, billing, or statutory purposes are completed."

        # Lawful basis for employee data is positive note, not violation
        if r_id == "employee_data_lawful_basis":
            if is_triggered:
                status = "ok"
                note = "Lawful basis under s.7(i) applies; consent not required for employment records."
            else:
                status = "not_applicable"
                note = "No employee records detected."
            points = 0
        else:
            if is_triggered:
                status = "triggered"
                points = SEVERITY_WEIGHTS.get(r["severity"], 10)
                note = remediation
                deductions.append({
                    "rule_id": r_id,
                    "title": title,
                    "severity": r["severity"],
                    "points": points,
                    "reason": note,
                })
            else:
                status = "ok"
                points = 0
                note = "Condition not triggered or requirement satisfied."

        cur.execute(
            "INSERT INTO risks (rule_id, severity, status) VALUES (?, ?, ?)",
            (r_id, r["severity"], status),
        )

        results.append({
            "id": r_id,
            "title": title,
            "citation_hint": r["citation_hint"],
            "severity": r["severity"],
            "status": status,
            "remediation": remediation,
            "verify": r.get("verify", True),
            "verified": r.get("verified", False),
            "source_url": r.get("source_url", ""),
            "deduction": points,
            "note": note,
        })

    conn.commit()

    total_deductions = sum(d["points"] for d in deductions)
    readiness_score = max(0, min(100, 100 - total_deductions))

    return {
        "readiness_score": readiness_score,
        "total_deductions": total_deductions,
        "deductions": deductions,
        "rules": results,
        "facts": facts,
    }


def save_questionnaire_answers(answers: Dict[str, str], conn=None) -> Dict[str, str]:
    """Save questionnaire answers validating keys as 'yes', 'no', or 'unanswered'."""
    if conn is None:
        conn = get_db()

    cur = conn.cursor()
    saved = {}
    for k, v in answers.items():
        key = k.strip().lower()
        if key in QUESTIONNAIRE_KEYS:
            val_str = str(v).strip().lower()
            if val_str in {"yes", "true", "1"}:
                ans = "yes"
            elif val_str in {"no", "false", "0"}:
                ans = "no"
            else:
                ans = "unanswered"
            cur.execute(
                "INSERT INTO questionnaire (key, answer) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET answer = excluded.answer",
                (key, ans),
            )
            saved[key] = ans
    conn.commit()
    return saved
