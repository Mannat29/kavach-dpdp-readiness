"""Tests for Purpose mapping (purpose limitation readiness)."""
import hashlib
import json
import os
import zipfile
import pytest

from app import create_app
from app.db import get_db, init_db
from app.ledger import check_payload_guard, export_evidence_pack, verify_chain
from app.purposes import (
    get_history,
    get_questions,
    infer_segment,
    load_preset,
    load_vocabulary,
    record_answer,
)
from scripts.demo_reset import reset_demo


@pytest.fixture
def app_with_demo(tmp_path, monkeypatch):
    """Create Flask test client with isolated SQLite database and scanned demo data."""
    db_file = str(tmp_path / "test_purposes.sqlite")
    monkeypatch.setenv("KAVACH_DATABASE", db_file)
    monkeypatch.setenv("KAVACH_KEEP_DB", "1")
    app = create_app({"TESTING": True, "DATABASE": db_file})
    init_db(db_file)

    with app.app_context():
        from app.inventory import scan_demo_data
        scan_demo_data(get_db(db_file))

    return app


def test_questions_generated_from_demo_data(app_with_demo):
    """1. Open questions are generated from demo findings, ordered by finding count descending."""
    with app_with_demo.app_context():
        conn = get_db()
        data = get_questions(conn)
        questions = data["questions"]
        progress = data["progress"]

        assert len(questions) > 0
        assert progress["total"] == len(questions)
        assert progress["answered"] == 0

        # Ordered by finding count descending
        counts = [q["finding_count"] for q in questions]
        assert counts == sorted(counts, reverse=True)

        # Aadhaar questions must omit preset suggestion
        for q in questions:
            if q["category"] == "aadhaar":
                assert q["suggested_default"] == []

            # Options must include vocabulary + 'I don't know'
            option_ids = [opt["id"] for opt in q["options"]]
            assert "unknown" in option_ids
            assert "appointment_booking" in option_ids


def test_invalid_purpose_id_rejected(app_with_demo):
    """2. Invalid purpose ID and invalid segments are rejected."""
    client = app_with_demo.test_client()

    # Invalid purpose ID via API
    resp = client.post(
        "/api/purpose-answers",
        json={
            "source_id": 1,
            "header": "Name",
            "category": "name",
            "segment": "patient",
            "purpose_ids": ["non_existent_purpose_xyz"],
            "unknown": False,
        },
    )
    assert resp.status_code == 400
    assert "Unknown purpose id" in resp.get_json()["error"]

    # Invalid segment via API
    resp_seg = client.post(
        "/api/purpose-answers",
        json={
            "source_id": 1,
            "header": "Name",
            "category": "name",
            "segment": "unrecognized_segment",
            "purpose_ids": ["appointment_booking"],
            "unknown": False,
        },
    )
    assert resp_seg.status_code == 400
    assert "Invalid segment" in resp_seg.get_json()["error"]

    # Direct function call validation
    with app_with_demo.app_context():
        conn = get_db()
        with pytest.raises(ValueError, match="Unknown purpose id"):
            record_answer(1, "Name", "name", "patient", ["fake_purpose"], conn=conn)

        with pytest.raises(ValueError, match="Invalid segment"):
            record_answer(1, "Name", "name", "alien_segment", ["appointment_booking"], conn=conn)


def test_superseding_keeps_history(app_with_demo):
    """3. Answering again supersedes prior active answer while keeping full history."""
    with app_with_demo.app_context():
        conn = get_db()

        # First answer
        res1 = record_answer(1, "Name", "name", "patient", ["appointment_booking"], conn=conn)
        hist1 = get_history(1, "Name", "name", conn=conn)
        assert len(hist1) == 1
        assert hist1[0]["superseded_by"] is None
        assert hist1[0]["purpose_id"] == "appointment_booking"

        # Second answer supersedes the first
        res2 = record_answer(1, "Name", "name", "patient", ["medical_care"], conn=conn)
        hist2 = get_history(1, "Name", "name", conn=conn)
        assert len(hist2) == 2

        active = [h for h in hist2 if h["superseded_by"] is None]
        superseded = [h for h in hist2 if h["superseded_by"] is not None]

        assert len(active) == 1
        assert active[0]["purpose_id"] == "medical_care"
        assert len(superseded) == 1
        assert superseded[0]["purpose_id"] == "appointment_booking"
        assert superseded[0]["superseded_by"] == active[0]["id"]


def test_unknown_status_stored(app_with_demo):
    """4. Answering unknown=True stores status='unknown' and purpose_id=NULL."""
    with app_with_demo.app_context():
        conn = get_db()
        res = record_answer(1, "DOB", "dob", "patient", unknown=True, conn=conn)
        assert res["status"] == "unknown"

        hist = get_history(1, "DOB", "dob", conn=conn)
        assert len(hist) == 1
        assert hist[0]["status"] == "unknown"
        assert hist[0]["purpose_id"] is None
        assert hist[0]["superseded_by"] is None


def test_ledger_event_no_raw_pii_and_verify_chain(app_with_demo):
    """5. Ledger event contains no raw PII, passes check_payload_guard, and chain verifies."""
    with app_with_demo.app_context():
        conn = get_db()
        record_answer(
            source_id=1,
            header="Phone",
            category="phone",
            segment="patient",
            purpose_ids=["appointment_booking"],
            answered_by="compliance_officer",
            conn=conn,
        )

        cur = conn.cursor()
        cur.execute("SELECT * FROM ledger ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()

        assert row["type"] == "purpose_answered"
        payload = json.loads(row["payload_json"])

        # Payload guard check
        check_payload_guard(payload)

        # Expected keys only
        assert set(payload.keys()) >= {"source_filename", "field_header", "category", "segment", "purpose_ids", "status"}
        assert payload["status"] == "confirmed"
        assert payload["purpose_ids"] == ["appointment_booking"]

        # Chain verification
        verification = verify_chain(conn)
        assert verification["ok"] is True


def test_evidence_pack_contains_purposes_json_and_manifest_hash_matches(app_with_demo):
    """6. Evidence pack export contains purposes.json and its manifest hash matches."""
    with app_with_demo.app_context():
        conn = get_db()

        # Add a confirmed answer
        record_answer(1, "Email", "email", "patient", ["appointment_booking"], conn=conn)

        pack = export_evidence_pack(conn)
        zip_path = pack["path"]
        assert os.path.exists(zip_path)

        with zipfile.ZipFile(zip_path, "r") as zf:
            namelist = zf.namelist()
            assert "purposes.json" in namelist
            assert "manifest.json" in namelist

            manifest_bytes = zf.read("manifest.json")
            manifest = json.loads(manifest_bytes.decode("utf-8"))

            assert "purposes.json" in manifest["files"]

            # Verify hash match
            purposes_bytes = zf.read("purposes.json")
            computed_hash = hashlib.sha256(purposes_bytes).hexdigest()
            assert computed_hash == manifest["files"]["purposes.json"]

            # Content verification
            purposes_data = json.loads(purposes_bytes.decode("utf-8"))
            assert len(purposes_data) >= 1
            entry = [e for e in purposes_data if e["field_header"] == "Email"][0]
            assert entry["purpose_id"] == "appointment_booking"
            assert entry["status"] == "confirmed"


def test_demo_reset_clears_purpose_answers(app_with_demo):
    """7. Demo reset clears purpose_answers table."""
    with app_with_demo.app_context():
        conn = get_db()
        record_answer(1, "Name", "name", "patient", ["appointment_booking"], conn=conn)

        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as cnt FROM purpose_answers")
        assert cur.fetchone()["cnt"] > 0

    client = app_with_demo.test_client()
    resp = client.post("/api/reset")
    assert resp.status_code == 200

    with app_with_demo.app_context():
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as cnt FROM purpose_answers")
        assert cur.fetchone()["cnt"] == 0
