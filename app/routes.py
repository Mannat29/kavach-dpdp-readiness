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
def index():
    return render_template("scanner.html")


@bp.route("/scanner")
def scanner():
    return render_template("scanner.html")


@bp.route("/data-map")
def data_map():
    return render_template("data_map.html")


@bp.route("/rights-desk")
def rights_desk():
    return render_template("rights_desk.html")


@bp.route("/breach-simulator")
def breach_simulator():
    return render_template("breach_simulator.html")


@bp.route("/risk-analysis")
def risk_analysis():
    return render_template("risk_analysis.html")


@bp.route("/reports")
def reports():
    return render_template("reports.html")


@bp.route("/evidence")
def evidence():
    return render_template("evidence.html")


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


@bp.route("/api/questionnaire", methods=["POST"])
def api_questionnaire():
    """Save answers for the 6 yes/no questionnaire keys."""
    data = request.get_json(silent=True) or {}
    answers = data.get("answers", data)
    conn = get_db()
    init_db()
    saved = save_questionnaire_answers(answers, conn)
    facts = collect_facts(conn)
    return jsonify({"success": True, "saved": saved, "facts": facts})


@bp.route("/api/risks", methods=["GET"])
def api_risks():
    """Evaluate 12 rules, readiness score, and deductions."""
    conn = get_db()
    init_db()
    results = evaluate_rules(conn)
    return jsonify(results)
