import json
import logging
import os
import tempfile
from flask import Blueprint, render_template, request, jsonify, Response, send_file, abort, url_for

from app.db import get_db, init_db
from app.ingest import ALLOWED_EXTENSIONS, MAX_FILE_SIZE, MAX_ROWS
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

logger = logging.getLogger(__name__)

bp = Blueprint("main", __name__)


# ---------------------------------------------------------------------------
# Frontend Views
# ---------------------------------------------------------------------------
@bp.route("/")
@bp.route("/dashboard")
def dashboard():
    from app.ocr import ocr_available
    is_ocr = ocr_available().get("available", False)
    return render_template("dashboard.html", active_page="dashboard", ocr_available=is_ocr)


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
    from app.ledger import append_ledger
    from app.reports import get_reports_summary
    conn = get_db()
    init_db()
    append_ledger("report_generated", {"report_type": "compliance_summary"}, conn)
    summary = get_reports_summary(conn)
    return render_template("reports.html", active_page="reports", summary=summary)


@bp.route("/evidence")
def evidence():
    is_dev = os.environ.get("KAVACH_DEV") == "1"
    return render_template("evidence.html", active_page="evidence", is_dev=is_dev)


@bp.route("/purposes")
def purposes():
    return render_template("purposes.html", active_page="purposes")


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------
@bp.route("/api/upload", methods=["POST"])
def api_upload():
    """Upload multiple files to data/workspace/ (persistent), scan, and ingest. Originals are never modified."""
    files = request.files.getlist("files") or list(request.files.values())
    if not files:
        return jsonify({"error": "No files provided"}), 400

    conn = get_db()
    init_db()
    uploaded_count = 0

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    workspace_dir = os.path.join(base_dir, "data", "workspace")
    os.makedirs(workspace_dir, exist_ok=True)
    abs_workspace = os.path.abspath(workspace_dir)

    for f in files:
        if not f or not f.filename:
            continue

        # Sanitise filename and prevent path traversal
        raw_name = f.filename.replace("\\", "/")
        safe_name = os.path.basename(raw_name).strip()
        if not safe_name or safe_name in (".", ".."):
            return jsonify({"error": f"Invalid filename: '{f.filename}'."}), 400

        # Extension whitelist: only .xlsx, .csv, .txt (plus OCR formats if available)
        from app.ingest import get_allowed_extensions
        from app.ocr import ocr_available
        allowed = get_allowed_extensions()
        ext = os.path.splitext(safe_name)[1].lower()
        if ext not in allowed:
            if ocr_available().get("available"):
                msg = "Only .csv, .jpeg, .jpg, .pdf, .png, .txt, and .xlsx files are accepted."
            else:
                msg = "Only .xlsx, .csv, and .txt files are accepted."
            return jsonify({
                "error": f"Unsupported file extension '{ext}' for file '{safe_name}'. {msg}"
            }), 400

        # Upload size check per file
        f.seek(0, os.SEEK_END)
        file_size = f.tell()
        f.seek(0)
        if file_size == 0:
            return jsonify({"error": f"File '{safe_name}' is empty (0 bytes)."}), 400
        if file_size > MAX_FILE_SIZE:
            return jsonify({
                "error": f"File '{safe_name}' exceeds maximum allowed upload size of 10 MB ({file_size:,} bytes)."
            }), 400

        save_path = os.path.abspath(os.path.join(workspace_dir, safe_name))
        # Ignore and prevent path traversal
        if not save_path.startswith(abs_workspace):
            return jsonify({"error": f"Path traversal attempt rejected for '{safe_name}'."}), 400

        f.save(save_path)

        try:
            scan_and_ingest_file(save_path, conn)
            uploaded_count += 1
        except ValueError as ve:
            logger.warning("Validation error ingesting file %s: %s", safe_name, ve)
            if os.path.exists(save_path):
                try:
                    os.remove(save_path)
                except OSError:
                    pass
            return jsonify({"error": str(ve)}), 400
        except Exception as exc:
            logger.exception("Unexpected error scanning file %s: %s", safe_name, exc)
            if os.path.exists(save_path):
                try:
                    os.remove(save_path)
                except OSError:
                    pass
            return jsonify({"error": f"Could not process file '{safe_name}'. Please ensure it is a valid, uncorrupted file."}), 400

    run_entity_resolution(conn)

    summary = get_inventory_summary(conn)
    from app.ledger import append_ledger
    append_ledger("scan_completed", {"source_count": uploaded_count, "summary": summary}, conn)
    return jsonify({"success": True, "files_scanned": uploaded_count, "summary": summary})


@bp.route("/api/scan-demo", methods=["POST"])
def api_scan_demo():
    """Scan all demo dataset files from data/demo."""
    conn = get_db()
    init_db()
    scan_demo_data(conn)
    summary = get_inventory_summary(conn)
    from app.ledger import append_ledger
    append_ledger("scan_completed", {"demo": True, "files_scanned": len(summary.get("sources", []))}, conn)
    return jsonify({"success": True, "summary": summary})


@bp.route("/api/reset", methods=["POST"])
def api_reset():
    """Reset the database (clear all tables) and remove all files in workspace and out folders."""
    conn = get_db()
    init_db()
    cur = conn.cursor()
    cur.execute("PRAGMA foreign_keys = OFF")
    cur.execute("DELETE FROM findings")
    cur.execute("DELETE FROM person_records")
    cur.execute("DELETE FROM people")
    cur.execute("DELETE FROM sources")
    cur.execute("DELETE FROM questionnaire")
    cur.execute("DELETE FROM risks")
    cur.execute("DELETE FROM rights_requests")
    cur.execute("DELETE FROM breach_simulations")
    cur.execute("DELETE FROM ledger")
    cur.execute("DELETE FROM evidence_packs")
    cur.execute("DELETE FROM ledger_tamper_backup")
    cur.execute("DELETE FROM purpose_answers")
    try:
        cur.execute("DELETE FROM sqlite_sequence WHERE name IN ('sources', 'findings', 'people', 'person_records', 'risks', 'rights_requests', 'breach_simulations', 'ledger', 'evidence_packs', 'purpose_answers')")
    except Exception:
        pass
    cur.execute("PRAGMA foreign_keys = ON")
    conn.commit()

    # Clear workspace and out folders
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for folder_name in ["workspace", "out"]:
        target_dir = os.path.join(base_dir, "data", folder_name)
        if os.path.exists(target_dir):
            for fname in os.listdir(target_dir):
                fpath = os.path.join(target_dir, fname)
                try:
                    if os.path.isfile(fpath) or os.path.islink(fpath):
                        os.unlink(fpath)
                    elif os.path.isdir(fpath):
                        import shutil
                        shutil.rmtree(fpath)
                except OSError:
                    pass
        else:
            os.makedirs(target_dir, exist_ok=True)

    from flask import current_app
    upload_dir = current_app.config.get("UPLOAD_FOLDER")
    if upload_dir and os.path.exists(upload_dir):
        for fname in os.listdir(upload_dir):
            fpath = os.path.join(upload_dir, fname)
            try:
                if os.path.isfile(fpath):
                    os.unlink(fpath)
            except OSError:
                pass

    return jsonify({"success": True, "message": "Demo data, workspace, and outputs reset successfully."})


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
        from app.ledger import append_ledger
        append_ledger("questionnaire_updated", {"keys": list(answers.keys()), "count": len(saved)}, conn)
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


# ---------------------------------------------------------------------------
# Rights Desk API
# ---------------------------------------------------------------------------
@bp.route("/api/rights/intake", methods=["POST"])
def api_rights_intake():
    """Intake rights requests from WhatsApp chat text or a list of messages.

    Accepts JSON: {"text": "<whatsapp export text>"}  OR
                  {"messages": [{"sender": "...", "text": "...", "timestamp": "..."}]}
    Returns list of created request records.
    """
    from app.rights import parse_whatsapp_text, process_intake
    conn = get_db()
    init_db()
    data = request.get_json(silent=True) or {}

    messages = data.get("messages")
    if messages is None:
        raw_text = data.get("text", "")
        messages = parse_whatsapp_text(raw_text)

    created = process_intake(messages, conn)
    return jsonify({"success": True, "created": len(created), "requests": created})


@bp.route("/api/rights/requests", methods=["GET"])
def api_rights_list():
    """List all rights requests, optionally filtered by status or intent."""
    conn = get_db()
    init_db()
    cur = conn.cursor()

    status_filter = request.args.get("status", "").strip()
    intent_filter = request.args.get("intent", "").strip()

    query = "SELECT * FROM rights_requests WHERE 1=1"
    params = []
    if status_filter:
        query += " AND status = ?"
        params.append(status_filter)
    if intent_filter:
        query += " AND intent = ?"
        params.append(intent_filter)
    query += " ORDER BY id ASC"

    cur.execute(query, params)
    rows = cur.fetchall()
    requests_list = [dict(r) for r in rows]
    return jsonify({"requests": requests_list, "total": len(requests_list)})


@bp.route("/api/rights/requests/<int:request_id>", methods=["GET"])
def api_rights_detail(request_id: int):
    """Get a single rights request by id."""
    conn = get_db()
    init_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM rights_requests WHERE id = ?", (request_id,))
    row = cur.fetchone()
    if not row:
        return jsonify({"error": f"Request {request_id} not found"}), 404
    return jsonify(dict(row))


@bp.route("/api/rights/requests/<int:request_id>/approve", methods=["POST"])
def api_rights_approve(request_id: int):
    """Approve a rights request (status plan_ready -> approved)."""
    conn = get_db()
    init_db()
    cur = conn.cursor()
    cur.execute("SELECT status FROM rights_requests WHERE id = ?", (request_id,))
    row = cur.fetchone()
    if not row:
        return jsonify({"error": f"Request {request_id} not found"}), 404
    if row["status"] not in ("plan_ready", "received", "identity_pending"):
        return jsonify({"error": f"Cannot approve request in status '{row['status']}'"}), 400
    cur.execute("UPDATE rights_requests SET status = 'approved' WHERE id = ?", (request_id,))
    conn.commit()
    from app.ledger import append_ledger
    append_ledger("plan_approved", {"request_id": request_id}, conn)
    return jsonify({"success": True, "request_id": request_id, "status": "approved"})


@bp.route("/api/rights/requests/<int:request_id>/plan", methods=["POST"])
def api_rights_build_plan(request_id: int):
    """Build an erasure plan for a request."""
    from app.erasure import build_plan
    conn = get_db()
    init_db()
    try:
        result = build_plan(request_id, conn)
        return jsonify({"success": True, **result})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@bp.route("/api/rights/requests/<int:request_id>/execute", methods=["POST"])
def api_rights_execute(request_id: int):
    """Execute an approved erasure plan. Body: {confirm_hash: <plan_hash>}."""
    from app.erasure import execute
    conn = get_db()
    init_db()
    data = request.get_json(silent=True) or {}
    confirm_hash = data.get("confirm_hash", "")
    if not confirm_hash:
        return jsonify({"error": "confirm_hash is required"}), 400
    try:
        receipt = execute(request_id, confirm_hash, conn)
        return jsonify({"success": True, "receipt": receipt})
    except (ValueError, RuntimeError) as e:
        return jsonify({"error": str(e)}), 400


@bp.route("/api/rights/classify", methods=["POST"])
def api_rights_classify():
    """Classify a single message text. Body: {text: '...'}."""
    from app.rights import classify_message
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")
    result = classify_message(text)
    return jsonify(result)


@bp.route("/api/rights/demo-text", methods=["GET"])
def api_rights_demo_text():
    """Return the contents of data/demo/demo_requests.txt."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    demo_path = os.path.join(base_dir, "data", "demo", "demo_requests.txt")
    if not os.path.exists(demo_path):
        return jsonify({"error": "demo_requests.txt not found"}), 404
    with open(demo_path, encoding="utf-8") as f:
        text = f.read()
    return jsonify({"text": text, "path": demo_path})


# Aliases using /api/rights/<id> pattern (spec-compliant)
@bp.route("/api/rights/<int:request_id>", methods=["GET"])
def api_rights_get(request_id: int):
    """Get a single rights request by id with countdown and data locations."""
    conn = get_db()
    init_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM rights_requests WHERE id = ?", (request_id,))
    row = cur.fetchone()
    if not row:
        return jsonify({"error": f"Request {request_id} not found"}), 404

    import datetime
    result = dict(row)

    # Countdown seconds until due_at
    if row["due_at"]:
        try:
            due = datetime.datetime.fromisoformat(row["due_at"])
            if due.tzinfo is not None:
                now = datetime.datetime.now(datetime.timezone.utc)
            else:
                now = datetime.datetime.now()
            result["countdown_seconds"] = max(0, int((due - now).total_seconds()))
        except (ValueError, TypeError):
            result["countdown_seconds"] = None

    # Data locations per source if person resolved
    if row["person_id"]:
        cur.execute("""
            SELECT s.filename, s.type, COUNT(*) as record_count
            FROM person_records pr
            JOIN sources s ON pr.source_id = s.id
            WHERE pr.person_id = ?
            GROUP BY s.id
        """, (row["person_id"],))
        result["data_locations"] = [dict(r) for r in cur.fetchall()]
    else:
        result["data_locations"] = []

    return jsonify(result)


@bp.route("/api/rights/<int:request_id>/reject", methods=["POST"])
def api_rights_reject(request_id: int):
    """Reject a rights request."""
    conn = get_db()
    init_db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM rights_requests WHERE id = ?", (request_id,))
    if not cur.fetchone():
        return jsonify({"error": f"Request {request_id} not found"}), 404
    cur.execute("UPDATE rights_requests SET status = 'rejected' WHERE id = ?", (request_id,))
    conn.commit()
    from app.ledger import append_ledger
    append_ledger("request_rejected", {"request_id": request_id, "reason": "Administrative rejection"}, conn)
    return jsonify({"success": True, "request_id": request_id, "status": "rejected"})


@bp.route("/api/rights/<int:request_id>/confirm-identity", methods=["POST"])
def api_rights_confirm_identity(request_id: int):
    """Confirm identity for a rights request in identity_pending status.

    Body: {detail: <a value on file, e.g. last 4 digits of phone>}
    On success transitions status to received (or plan_ready if plan exists).
    """
    conn = get_db()
    init_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM rights_requests WHERE id = ?", (request_id,))
    row = cur.fetchone()
    if not row:
        return jsonify({"error": f"Request {request_id} not found"}), 404
    if row["status"] != "identity_pending":
        return jsonify({"error": f"Request is not in identity_pending status (current: {row['status']})"}), 400

    new_status = "plan_ready" if row["plan_json"] else "received"
    cur.execute(
        "UPDATE rights_requests SET status = ?, resolution = 'strong' WHERE id = ?",
        (new_status, request_id)
    )
    conn.commit()
    from app.ledger import append_ledger
    append_ledger({"event": "identity_confirmed", "request_id": request_id}, conn)
    return jsonify({"success": True, "request_id": request_id, "status": new_status})


@bp.route("/api/rights/<int:request_id>/plan-override", methods=["POST"])
def api_rights_plan_override(request_id: int):
    """Override a field decision in the plan. Body: {record_key, field, decision}."""
    from app.erasure import plan_override
    conn = get_db()
    init_db()
    data = request.get_json(silent=True) or {}
    record_key = data.get("record_key", "")
    field = data.get("field", "")
    decision = data.get("decision", "")
    if not (record_key and field and decision):
        return jsonify({"error": "record_key, field, and decision are required"}), 400
    try:
        result = plan_override(request_id, record_key, field, decision, conn)
        return jsonify({"success": True, **result})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@bp.route("/api/rights/<int:request_id>/receipt", methods=["GET"])
def api_rights_receipt(request_id: int):
    """Return receipt.json for an executed request."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    receipt_path = os.path.join(base_dir, "data", "out", str(request_id), "receipt.json")
    if not os.path.exists(receipt_path):
        return jsonify({"error": "Receipt not found. Has the request been executed?"}), 404
    with open(receipt_path, encoding="utf-8") as f:
        receipt = json.load(f)
    return jsonify(receipt)


@bp.route("/api/rights/<int:request_id>/download", methods=["GET"])
def api_rights_download(request_id: int):
    """Download a zip of cleaned files + receipt for an executed request."""
    import io
    import zipfile
    from flask import send_file
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir = os.path.join(base_dir, "data", "out", str(request_id))
    if not os.path.exists(out_dir):
        return jsonify({"error": "No output found. Has the request been executed?"}), 404

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname in os.listdir(out_dir):
            fpath = os.path.join(out_dir, fname)
            if os.path.isfile(fpath):
                zf.write(fpath, fname)
    buf.seek(0)
    return send_file(
        buf,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"erasure_request_{request_id}.zip",
    )


# ---------------------------------------------------------------------------
# Breach Blast-Radius Simulator Endpoints
# ---------------------------------------------------------------------------
@bp.route("/api/breach/scenarios", methods=["GET"])
def api_breach_scenarios():
    """List available breach scenarios."""
    from app.breach import load_scenarios
    scenarios = load_scenarios()
    return jsonify({"scenarios": scenarios})


@bp.route("/api/breach/simulate", methods=["POST"])
def api_breach_simulate():
    """Execute a breach blast-radius simulation.
    
    Body JSON:
    - scenario (str, required)
    - aware_at (str ISO timestamp, optional)
    - device_protected (str: 'unknown'|'yes'|'no', optional)
    - sources (list of str, required if scenario == 'custom')
    """
    conn = get_db()
    init_db()
    data = request.get_json(silent=True) or {}
    scenario = data.get("scenario")
    if not scenario:
        return jsonify({"error": "scenario is required"}), 400

    aware_at = data.get("aware_at")
    device_protected = data.get("device_protected", "unknown")
    sources = data.get("sources")

    from app.breach import simulate
    try:
        result = simulate(
            scenario=scenario,
            aware_at=aware_at,
            device_protected=device_protected,
            sources=sources,
            conn=conn,
        )
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Simulation failed: {str(e)}"}), 500


@bp.route("/api/breach/<int:sim_id>", methods=["GET"])
def api_breach_get(sim_id: int):
    """Retrieve an existing breach simulation by ID."""
    conn = get_db()
    init_db()
    from app.breach import get_simulation
    sim = get_simulation(sim_id, conn)
    if not sim:
        return jsonify({"error": f"Breach simulation {sim_id} not found"}), 404
    return jsonify(sim)


@bp.route("/api/breach/<int:sim_id>/recipients", methods=["GET"])
def api_breach_recipients(sim_id: int):
    """Retrieve recipient list for a simulation."""
    conn = get_db()
    init_db()
    from app.breach import get_simulation
    sim = get_simulation(sim_id, conn)
    if not sim:
        return jsonify({"error": f"Breach simulation {sim_id} not found"}), 404
    return jsonify({
        "simulation_id": sim_id,
        "scenario": sim["scenario"],
        "recipients": sim["recipients"],
        "total_count": len(sim["recipients"]),
        "disclaimer": sim.get("recipients_disclaimer", "The tool cannot send anything. Notices must be sent manually."),
    })


@bp.route("/api/breach/<int:sim_id>/export", methods=["GET"])
def api_breach_export(sim_id: int):
    """Export single printable HTML page with all drafts and checklist, no raw PII."""
    import html
    conn = get_db()
    init_db()
    from app.breach import get_simulation
    sim = get_simulation(sim_id, conn)
    if not sim:
        return jsonify({"error": f"Breach simulation {sim_id} not found"}), 404

    scenario_title = html.escape(sim.get("scenario_title", sim.get("scenario", "Breach Simulation")))
    aware_at = html.escape(str(sim.get("aware_at", "N/A")))
    severity = html.escape(str(sim.get("severity", "unknown")).upper())
    counts = sim.get("counts", {})
    records_count = html.escape(str(counts.get("records_count", 0)))
    people_range = html.escape(str(counts.get("range", counts.get("people_count", 0))))
    confirmed_count = html.escape(str(counts.get("confirmed_count", 0)))
    possible_count = html.escape(str(counts.get("possible_count", 0)))

    checklist_items = sim.get("first_hour_checklist", [])
    checklist_html = "".join(
        f'<li><label><input type="checkbox" /> {html.escape(step)}</label></li>'
        for step in checklist_items
    )

    drafts = sim.get("drafts", {})
    board_intimation = html.escape(drafts.get("board_intimation", "No draft available"))
    detailed_report = html.escape(drafts.get("board_detailed_report", "No draft available"))
    individual_notice = html.escape(drafts.get("individual_notice", "No draft available"))

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Kavach Incident Simulation Pack - {scenario_title}</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      line-height: 1.6;
      color: #1f2937;
      margin: 0;
      padding: 24px;
      background: #f9fafb;
    }}
    .container {{
      max-width: 900px;
      margin: 0 auto;
      background: #ffffff;
      padding: 32px;
      border-radius: 8px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }}
    .banner {{
      background: #fee2e2;
      border: 1px solid #ef4444;
      color: #991b1b;
      padding: 12px 16px;
      border-radius: 6px;
      font-weight: 700;
      text-align: center;
      margin-bottom: 24px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}
    .print-btn {{
      background: #2563eb;
      color: #ffffff;
      border: none;
      padding: 10px 18px;
      border-radius: 6px;
      cursor: pointer;
      font-size: 14px;
      font-weight: 500;
      float: right;
    }}
    .print-btn:hover {{
      background: #1d4ed8;
    }}
    .meta-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
      padding: 16px;
      background: #f3f4f6;
      border-radius: 6px;
    }}
    .meta-label {{
      font-weight: 600;
      color: #4b5563;
      font-size: 12px;
      text-transform: uppercase;
    }}
    .meta-val {{
      font-size: 16px;
      font-weight: 600;
      color: #111827;
      margin-top: 4px;
    }}
    h1 {{
      font-size: 24px;
      margin-top: 0;
      color: #111827;
    }}
    h2 {{
      font-size: 18px;
      border-bottom: 2px solid #e5e7eb;
      padding-bottom: 8px;
      margin-top: 32px;
      color: #111827;
    }}
    .checklist {{
      list-style: none;
      padding: 0;
    }}
    .checklist li {{
      padding: 8px 0;
      border-bottom: 1px solid #f3f4f6;
    }}
    .checklist label {{
      cursor: pointer;
      display: flex;
      align-items: flex-start;
    }}
    .checklist input {{
      margin-right: 12px;
      margin-top: 4px;
    }}
    pre {{
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      padding: 16px;
      border-radius: 6px;
      white-space: pre-wrap;
      word-wrap: break-word;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 13px;
      color: #334155;
    }}
    .disclaimer-box {{
      margin-top: 32px;
      padding: 16px;
      background: #fef3c7;
      border: 1px solid #f59e0b;
      border-radius: 6px;
      font-size: 13px;
      color: #92400e;
    }}
    @media print {{
      body {{
        background: #ffffff;
        padding: 0;
      }}
      .container {{
        box-shadow: none;
        padding: 0;
        width: 100%;
        max-width: none;
      }}
      .print-btn {{
        display: none;
      }}
      .banner {{
        border-color: #000000;
        color: #000000;
        background: #eeeeee;
      }}
      h2 {{
        page-break-after: avoid;
      }}
      pre {{
        page-break-inside: avoid;
        border: 1px solid #cccccc;
      }}
    }}
  </style>
</head>
<body>
  <div class="container">
    <button class="print-btn" onclick="window.print()">Print / Save PDF</button>
    <div class="banner">DRAFT, SIMULATION &mdash; REVIEW BEFORE SENDING &mdash; NOT LEGAL ADVICE</div>

    <h1>Breach Response Simulation Pack</h1>
    <p>This document contains simulated incident blast-radius analysis, the initial first-hour response checklist, and statutory notification draft templates generated for review.</p>

    <div class="meta-grid">
      <div>
        <div class="meta-label">Scenario</div>
        <div class="meta-val">{scenario_title}</div>
      </div>
      <div>
        <div class="meta-label">Assessed Severity</div>
        <div class="meta-val">{severity}</div>
      </div>
      <div>
        <div class="meta-label">Compromised Records</div>
        <div class="meta-val">{records_count}</div>
      </div>
      <div>
        <div class="meta-label">Affected People (Range)</div>
        <div class="meta-val">{people_range}</div>
      </div>
      <div>
        <div class="meta-label">Confirmed / Possible</div>
        <div class="meta-val">{confirmed_count} / {possible_count}</div>
      </div>
      <div>
        <div class="meta-label">Awareness Time</div>
        <div class="meta-val">{aware_at}</div>
      </div>
    </div>

    <h2>1. First-Hour Incident Checklist</h2>
    <ul class="checklist">
      {checklist_html}
    </ul>

    <h2>2. Draft: Section 8(6) Board Intimation</h2>
    <pre>{board_intimation}</pre>

    <h2>3. Draft: Rule 7 Detailed Report Skeleton</h2>
    <pre>{detailed_report}</pre>

    <h2>4. Draft: Notice to Affected Individuals</h2>
    <pre>{individual_notice}</pre>

    <div class="disclaimer-box">
      <strong>Important Readiness Notice:</strong>
      All content generated is a simulation and draft. Kavach does not dispatch regulatory notices or individual communications. All drafts must be reviewed, verified against technical forensic findings, and authorized by counsel or the Data Protection Officer before dispatch.
    </div>
  </div>
</body>
</html>"""
    return Response(html_content, mimetype="text/html")


# ---------------------------------------------------------------------------
# Ledger, Evidence Pack, Dev Tamper, and Public Verify Endpoints
# ---------------------------------------------------------------------------
@bp.route("/api/ledger")
def api_ledger():
    """Return paged audit ledger events with short hashes."""
    conn = get_db()
    cur = conn.cursor()

    type_filter = request.args.get("type", "").strip()
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (ValueError, TypeError):
        page = 1
    try:
        per_page = max(1, min(100, int(request.args.get("per_page", 20))))
    except (ValueError, TypeError):
        per_page = 20
    offset = (page - 1) * per_page

    query_count = "SELECT COUNT(*) as c FROM ledger"
    query_events = "SELECT id, ts, type, payload_json, prev_hash, hash FROM ledger"
    params = []

    if type_filter:
        query_count += " WHERE type = ?"
        query_events += " WHERE type = ?"
        params.append(type_filter)

    cur.execute(query_count, params)
    total = cur.fetchone()["c"]

    query_events += " ORDER BY id DESC LIMIT ? OFFSET ?"
    cur.execute(query_events, params + [per_page, offset])
    rows = cur.fetchall()

    events = []
    for r in rows:
        try:
            payload = json.loads(r["payload_json"])
        except Exception:
            payload = {}
        h = r["hash"] or ""
        ph = r["prev_hash"] or ""
        events.append({
            "id": r["id"],
            "ts": r["ts"],
            "type": r["type"],
            "payload": payload,
            "hash": h,
            "short_hash": h[:12] if h else "",
            "prev_hash": ph,
            "short_prev_hash": ph[:12] if ph else "",
        })

    # Available event types for UI dropdown
    cur.execute("SELECT DISTINCT type FROM ledger ORDER BY type")
    all_types = [t_row["type"] for t_row in cur.fetchall()]

    return jsonify({
        "events": events,
        "total": total,
        "page": page,
        "per_page": per_page,
        "types": all_types,
    })


@bp.route("/api/ledger/verify")
def api_ledger_verify():
    """Verify integrity of audit ledger hash chain."""
    from app.ledger import verify_chain
    conn = get_db()
    result = verify_chain(conn)
    return jsonify(result)


@bp.route("/api/dev/tamper", methods=["POST"])
def api_dev_tamper():
    """Tamper with a stored ledger event payload (dev only)."""
    if os.environ.get("KAVACH_DEV") != "1":
        return jsonify({"error": "Dev mode not enabled"}), 404

    from app.ledger import tamper_ledger_event
    conn = get_db()
    data = request.get_json(silent=True) or {}
    event_id = data.get("id")
    if event_id is None:
        cur = conn.cursor()
        cur.execute("SELECT id FROM ledger ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "No ledger events exist to tamper"}), 400
        event_id = row["id"]
    else:
        try:
            event_id = int(event_id)
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid event ID"}), 400

    try:
        res = tamper_ledger_event(event_id, conn)
        return jsonify(res)
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@bp.route("/api/dev/repair", methods=["POST"])
def api_dev_repair():
    """Restore tampered ledger event payload from backup (dev only)."""
    if os.environ.get("KAVACH_DEV") != "1":
        return jsonify({"error": "Dev mode not enabled"}), 404

    from app.ledger import repair_ledger_event
    conn = get_db()
    data = request.get_json(silent=True) or {}
    event_id = data.get("id")
    if event_id is not None:
        try:
            event_id = int(event_id)
        except (ValueError, TypeError):
            event_id = None

    try:
        res = repair_ledger_event(event_id, conn)
        return jsonify(res)
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@bp.route("/api/evidence/export", methods=["POST"])
def api_evidence_export():
    """Export evidence pack ZIP containing audit ledger, manifest, and summaries."""
    from app.ledger import export_evidence_pack
    conn = get_db()
    pack_meta = export_evidence_pack(conn)
    pack_id = pack_meta["pack_id"]
    return jsonify({
        "success": True,
        "pack_id": pack_id,
        "head_hash": pack_meta["head_hash"],
        "chain_ok": pack_meta["chain_ok"],
        "score": pack_meta["score"],
        "download_url": url_for("main.api_evidence_download", pack_id=pack_id),
        "verify_url": url_for("main.public_verify", pack_id=pack_id),
    })


@bp.route("/api/evidence/download/<pack_id>")
def api_evidence_download(pack_id: str):
    """Download exported evidence pack ZIP."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT path FROM evidence_packs WHERE pack_id = ?", (pack_id,))
    row = cur.fetchone()
    if not row or not os.path.exists(row["path"]):
        return jsonify({"error": f"Evidence pack {pack_id} not found"}), 404

    return send_file(
        row["path"],
        as_attachment=True,
        download_name=f"evidence_{pack_id}.zip",
        mimetype="application/zip",
    )


@bp.route("/verify/<pack_id>")
def public_verify(pack_id: str):
    """Public verification page: standalone clean page showing integrity and readiness status."""
    from app.ledger import verify_chain
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM evidence_packs WHERE pack_id = ?", (pack_id,))
    pack = cur.fetchone()
    if not pack:
        abort(404)

    # Live integrity check
    chain_status = verify_chain(conn)

    # Check whether the head_hash at export is still present in the chain
    cur.execute("SELECT id, hash FROM ledger WHERE hash = ?", (pack["head_hash"],))
    head_hash_row = cur.fetchone()
    head_hash_in_chain = head_hash_row is not None

    # Count completed erasure requests
    cur.execute("SELECT COUNT(*) as c FROM rights_requests WHERE status = 'executed'")
    erasures_count = cur.fetchone()["c"]

    # Count breach simulations run
    cur.execute("SELECT COUNT(*) as c FROM breach_simulations")
    breach_count = cur.fetchone()["c"]

    is_intact = bool(chain_status["ok"] and head_hash_in_chain)

    return render_template(
        "public_verify.html",
        pack=pack,
        chain_status=chain_status,
        head_hash_in_chain=head_hash_in_chain,
        is_intact=is_intact,
        erasures_count=erasures_count,
        breach_count=breach_count,
    )


# ---------------------------------------------------------------------------
# Reports API
# ---------------------------------------------------------------------------
@bp.route("/api/reports/summary", methods=["GET"])
def api_reports_summary():
    """Return compliance readiness report summary."""
    from app.reports import get_reports_summary
    conn = get_db()
    init_db()
    summary = get_reports_summary(conn)
    return jsonify(summary)


@bp.route("/api/reports/export", methods=["GET"])
def api_reports_export():
    """Return self-contained printable HTML compliance readiness report."""
    from app.ledger import append_ledger
    from app.reports import get_reports_summary, generate_printable_report_html
    conn = get_db()
    init_db()
    summary = get_reports_summary(conn)
    html_content = generate_printable_report_html(summary, conn)
    append_ledger("report_generated", {"report_type": "printable_export"}, conn)
    return Response(html_content, mimetype="text/html; charset=utf-8")


# ---------------------------------------------------------------------------
# Purpose Mapping API
# ---------------------------------------------------------------------------
@bp.route("/api/purposes", methods=["GET"])
def api_purposes():
    """Return controlled purpose vocabulary."""
    from app.purposes import load_vocabulary
    return jsonify(load_vocabulary())


@bp.route("/api/purpose-questions", methods=["GET"])
def api_purpose_questions():
    """Return open questions for undocumented purposes with progress."""
    from app.purposes import get_questions
    conn = get_db()
    init_db()
    return jsonify(get_questions(conn))


@bp.route("/api/purpose-answers", methods=["POST"])
def api_purpose_answers():
    """Record an answer for a field purpose question."""
    from app.purposes import record_answer
    conn = get_db()
    init_db()
    data = request.get_json(silent=True) or {}
    source_id = data.get("source_id")
    header = data.get("header") if "header" in data else data.get("field_header")
    category = data.get("category")
    segment = data.get("segment")
    purpose_ids = data.get("purpose_ids")
    unknown = bool(data.get("unknown", False))
    answered_by = data.get("answered_by", "user")

    if source_id is None or header is None or category is None or segment is None:
        return jsonify({"error": "Missing required fields: source_id, header, category, segment"}), 400

    try:
        res = record_answer(
            source_id=int(source_id),
            header=str(header),
            category=str(category),
            segment=str(segment),
            purpose_ids=purpose_ids,
            unknown=unknown,
            answered_by=str(answered_by),
            conn=conn,
        )
        return jsonify({"success": True, **res})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@bp.route("/api/purpose-history", methods=["GET"])
def api_purpose_history():
    """Return answer history for a field."""
    from app.purposes import get_history
    conn = get_db()
    init_db()
    source_id = request.args.get("source_id", type=int)
    header = request.args.get("header") or request.args.get("field_header") or ""
    category = request.args.get("category", "")
    if source_id is None:
        return jsonify({"error": "source_id is required"}), 400
    history = get_history(source_id, header, category, conn)
    return jsonify({"history": history})

