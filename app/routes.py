import json
import os
import tempfile
from flask import Blueprint, render_template, request, jsonify

from app.db import get_db, init_db
from app.inventory import (
    scan_and_ingest_file,
    run_entity_resolution,
    get_inventory_summary,
    scan_demo_data,
)
from app.rules import (
    evaluate_rules,
    save_questionnaire_answers,
    collect_facts,
)

bp = Blueprint("main", __name__)


# ---------------------------------------------------------------------------
# Frontend Views
# ---------------------------------------------------------------------------
@bp.route("/")
@bp.route("/dashboard")
def dashboard():
    return render_template("dashboard.html", active_page="dashboard")


@bp.route("/scanner")
def scanner():
    return render_template("scanner.html", active_page="scanner")


@bp.route("/data-map")
def data_map():
    return render_template("data_map.html", active_page="data_map")


@bp.route("/rights-desk")
def rights_desk():
    return render_template("rights_desk.html", active_page="rights_desk")


@bp.route("/breach-simulator")
def breach_simulator():
    return render_template("breach_simulator.html", active_page="breach_simulator")


@bp.route("/risk-analysis")
def risk_analysis():
    return render_template("risk_analysis.html", active_page="risk_analysis")


@bp.route("/reports")
def reports():
    return render_template("reports.html", active_page="reports")


@bp.route("/evidence")
def evidence():
    return render_template("evidence.html", active_page="evidence")


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------
@bp.route("/api/upload", methods=["POST"])
def api_upload():
    """Upload multiple files, scan to temporary directory, ingest and clean up."""
    files = request.files.getlist("files") or list(request.files.values())
    if not files:
        return jsonify({"error": "No files provided"}), 400

    conn = get_db()
    init_db()
    uploaded_count = 0

    with tempfile.TemporaryDirectory() as tmpdir:
        for f in files:
            if f and f.filename:
                safe_name = os.path.basename(f.filename)
                tmp_path = os.path.join(tmpdir, safe_name)
                f.save(tmp_path)
                scan_and_ingest_file(tmp_path, conn)
                uploaded_count += 1
        run_entity_resolution(conn)

    summary = get_inventory_summary(conn)
    return jsonify({"success": True, "files_scanned": uploaded_count, "summary": summary})


@bp.route("/api/scan-demo", methods=["POST"])
def api_scan_demo():
    """Scan all demo dataset files from data/demo."""
    conn = get_db()
    init_db()
    scan_demo_data(conn)
    summary = get_inventory_summary(conn)
    return jsonify({"success": True, "summary": summary})


@bp.route("/api/inventory", methods=["GET"])
def api_inventory():
    """Get per-source summary and overall inventory counts."""
    conn = get_db()
    init_db()
    summary = get_inventory_summary(conn)
    return jsonify(summary)


@bp.route("/api/people", methods=["GET"])
def api_people():
    """Get list of resolved people with counts of records and sources."""
    conn = get_db()
    init_db()
    cur = conn.cursor()
    cur.execute("SELECT id, label, masked_name FROM people ORDER BY id")
    people_rows = cur.fetchall()

    people = []
    for p in people_rows:
        pid = p["id"]
        cur.execute(
            "SELECT COUNT(*) as r_count, COUNT(DISTINCT source_id) as s_count FROM person_records WHERE person_id = ?",
            (pid,),
        )
        cnt = cur.fetchone()
        people.append({
            "id": pid,
            "label": p["label"],
            "masked_name": p["masked_name"],
            "record_count": cnt["r_count"],
            "source_count": cnt["s_count"],
        })
    return jsonify({"people": people, "total_people": len(people)})


@bp.route("/api/people/<int:person_id>", methods=["GET"])
def api_person_detail(person_id: int):
    """Get all records and masked samples across sources for a single person."""
    conn = get_db()
    init_db()
    cur = conn.cursor()
    cur.execute("SELECT id, label, masked_name, name_hash FROM people WHERE id = ?", (person_id,))
    person = cur.fetchone()
    if not person:
        return jsonify({"error": f"Person {person_id} not found"}), 404

    cur.execute(
        """SELECT pr.source_id, pr.record_key, pr.link_type, pr.link_confidence, s.filename as source, s.type as source_type
           FROM person_records pr
           JOIN sources s ON pr.source_id = s.id
           WHERE pr.person_id = ?
           ORDER BY s.id, pr.record_key""",
        (person_id,),
    )
    record_rows = cur.fetchall()

    records = []
    for r in record_rows:
        cur.execute(
            """SELECT location, category, masked_sample, confidence, meta_json
               FROM findings
               WHERE source_id = ? AND record_key = ?""",
            (r["source_id"], r["record_key"]),
        )
        findings = []
        for f in cur.fetchall():
            meta = json.loads(f["meta_json"]) if f["meta_json"] else None
            findings.append({
                "location": f["location"],
                "category": f["category"],
                "masked_sample": f["masked_sample"],
                "confidence": f["confidence"],
                "meta": meta,
            })
        records.append({
            "source": r["source"],
            "source_type": r["source_type"],
            "record_key": r["record_key"],
            "link_type": r["link_type"],
            "link_confidence": r["link_confidence"],
            "findings": findings,
        })

    return jsonify({
        "id": person["id"],
        "label": person["label"],
        "masked_name": person["masked_name"],
        "record_count": len(records),
        "records": records,
    })


@bp.route("/api/findings", methods=["GET"])
def api_findings():
    """Get detected findings with optional source and category filters."""
    conn = get_db()
    init_db()
    cur = conn.cursor()

    source_param = request.args.get("source", "").strip()
    category_param = request.args.get("category", "").strip().lower()
    limit_param = request.args.get("limit", "").strip()

    query = """
        SELECT f.id, f.source_id, f.record_key, f.location, f.category,
               f.masked_sample, f.confidence, f.meta_json,
               s.filename as source_name, s.type as source_type
        FROM findings f
        JOIN sources s ON f.source_id = s.id
        WHERE 1=1
    """
    params = []

    if source_param:
        if source_param.isdigit():
            query += " AND f.source_id = ?"
            params.append(int(source_param))
        else:
            query += " AND s.filename = ?"
            params.append(source_param)

    if category_param:
        query += " AND f.category = ?"
        params.append(category_param)

    query += " ORDER BY f.id ASC"

    if limit_param and limit_param.isdigit():
        query += f" LIMIT {int(limit_param)}"

    cur.execute(query, params)
    rows = cur.fetchall()

    from app.inventory import SENSITIVE_CATEGORIES

    findings = []
    for r in rows:
        meta = json.loads(r["meta_json"]) if r["meta_json"] else None
        is_sensitive = r["category"] in SENSITIVE_CATEGORIES or (meta and meta.get("is_minor"))
        findings.append({
            "id": r["id"],
            "source_id": r["source_id"],
            "source_name": r["source_name"],
            "source_type": r["source_type"],
            "record_key": r["record_key"],
            "location": r["location"],
            "category": r["category"],
            "masked_sample": r["masked_sample"],
            "confidence": r["confidence"],
            "meta": meta,
            "is_sensitive": bool(is_sensitive),
        })

    # Also compute aggregate category counts per source
    cur.execute("""
        SELECT f.source_id, f.category, COUNT(*) as cnt
        FROM findings f
        GROUP BY f.source_id, f.category
    """)
    source_cat_counts = {}
    for r in cur.fetchall():
        s_id = str(r["source_id"])
        if s_id not in source_cat_counts:
            source_cat_counts[s_id] = {}
        source_cat_counts[s_id][r["category"]] = r["cnt"]

    # Compute overall category counts
    cur.execute("""
        SELECT category, COUNT(*) as cnt
        FROM findings
        GROUP BY category
        ORDER BY cnt DESC
    """)
    category_counts = {r["category"]: r["cnt"] for r in cur.fetchall()}

    return jsonify({
        "findings": findings,
        "total": len(findings),
        "source_category_counts": source_cat_counts,
        "category_counts": category_counts,
    })


@bp.route("/api/questionnaire", methods=["GET", "POST"])
def api_questionnaire():
    """Get or save answers for the 6 yes/no questionnaire keys."""
    conn = get_db()
    init_db()
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        answers = data.get("answers", data)
        saved = save_questionnaire_answers(answers, conn)
        facts = collect_facts(conn)
        return jsonify({"success": True, "saved": saved, "facts": facts})
    else:
        cur = conn.cursor()
        cur.execute("SELECT key, answer FROM questionnaire")
        answers = {row["key"]: row["answer"] for row in cur.fetchall()}
        facts = collect_facts(conn)
        return jsonify({"answers": answers, "facts": facts})


@bp.route("/api/risks", methods=["GET"])
def api_risks():
    """Evaluate 12 rules, readiness score, and deductions."""
    conn = get_db()
    init_db()
    results = evaluate_rules(conn)
    return jsonify(results)
