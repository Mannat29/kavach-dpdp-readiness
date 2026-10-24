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

    # 1. Facts from Questionnaire
    facts = {
        "cctv": "no",
        "personal_phones": "no",
        "vendors": "no",
        "breach_contact": "no",
        "retention_policy": "no",
        "children_served": "no",
    }
    cur.execute("SELECT key, answer FROM questionnaire")
    for row in cur.fetchall():
        k = row["key"].strip().lower()
        if k in QUESTIONNAIRE_KEYS:
            facts[k] = row["answer"].strip().lower()

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

    cur = conn.cursor()
    cur.execute("DELETE FROM risks")

    results = []
    deductions = []

    for r in rules:
        r_id = r["id"]
        is_triggered = evaluate_condition(r["trigger"], facts)

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
                note = r["remediation"]
                deductions.append({
                    "rule_id": r_id,
                    "title": r["title"],
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
            "title": r["title"],
            "citation_hint": r["citation_hint"],
            "severity": r["severity"],
            "status": status,
            "remediation": r["remediation"],
            "verify": r.get("verify", True),
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
    """Save questionnaire answers validating the 6 yes/no keys."""
    if conn is None:
        conn = get_db()

    cur = conn.cursor()
    saved = {}
    for k, v in answers.items():
        key = k.strip().lower()
        if key in QUESTIONNAIRE_KEYS:
            ans = "yes" if str(v).strip().lower() in {"yes", "true", "1"} else "no"
            cur.execute(
                "INSERT INTO questionnaire (key, answer) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET answer = excluded.answer",
                (key, ans),
            )
            saved[key] = ans
    conn.commit()
    return saved
