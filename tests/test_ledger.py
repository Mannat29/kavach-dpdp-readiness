"""Tests for audit ledger, tamper detection, evidence pack, and public verify."""
import io
import json
import os
import random
import zipfile
import pytest

from app import create_app
from app.db import get_db, init_db
from app.detect import detect_all
from app.inventory import scan_demo_data
from app.rights import process_intake
from app.erasure import build_plan, execute
from app.breach import simulate
from app.ledger import (
    append_ledger,
    verify_chain,
    tamper_ledger_event,
    repair_ledger_event,
    export_evidence_pack,
    GENESIS_PREV_HASH,
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


def test_chain_valid_after_normal_flow(app_with_demo):
    """1. Chain valid after normal flow (scan, intake, plan, approve, execute, breach, export)."""
    with app_with_demo.app_context():
        conn = get_db()

        # Intake request
        created = process_intake(
            [{"sender": "Ramesh Kumar", "text": "Please delete my records completely", "channel": "whatsapp"}],
            conn,
        )
        assert len(created) == 1
        req_id = created[0]["id"]

        # Ensure person is resolved to person 1 if not automatically matched
        cur = conn.cursor()
        cur.execute("SELECT person_id FROM rights_requests WHERE id = ?", (req_id,))
        if cur.fetchone()["person_id"] is None:
            cur.execute("SELECT id FROM people LIMIT 1")
            p_row = cur.fetchone()
            if p_row:
                cur.execute("UPDATE rights_requests SET person_id = ?, resolution = 'confirmed' WHERE id = ?", (p_row["id"], req_id))
                conn.commit()

        # Plan build
        plan_res = build_plan(req_id, conn)
        assert "plan_hash" in plan_res

        # Plan approve
        cur.execute("UPDATE rights_requests SET status = 'approved' WHERE id = ?", (req_id,))
        conn.commit()
        append_ledger("plan_approved", {"request_id": req_id}, conn)

        # Erasure execute
        exec_res = execute(req_id, plan_res["plan_hash"], conn)
        assert exec_res["request_id"] == req_id
        assert exec_res["plan_hash"] == plan_res["plan_hash"]

        # Breach simulate
        sim_res = simulate("owner_phone_stolen", conn=conn)
        assert sim_res["id"] is not None

        # Evidence pack export
        pack_res = export_evidence_pack(conn)
        assert pack_res["pack_id"] is not None

        # Verify chain integrity
        ver = verify_chain(conn)
        assert ver["ok"] is True
        assert ver["length"] >= 5
        assert ver["first_broken_id"] is None
        assert ver["head_hash"] is not None


def test_editing_payload_makes_verify_fail(app_with_demo):
    """2. Editing a payload makes verify fail and report that id."""
    with app_with_demo.app_context():
        conn = get_db()
        append_ledger("scan_completed", {"files": 3}, conn)
        target_id = append_ledger("questionnaire_updated", {"keys": ["q1"]}, conn)
        append_ledger("report_generated", {"type": "readiness"}, conn)

        # Directly tamper with stored payload without updating hash
        cur = conn.cursor()
        cur.execute("UPDATE ledger SET payload_json = ? WHERE id = ?", ('{"tampered":true}', target_id))
        conn.commit()

        ver = verify_chain(conn)
        assert ver["ok"] is False
        assert ver["first_broken_id"] == target_id
        assert "Hash mismatch" in ver["reason"]


def test_editing_hash_fails(app_with_demo):
    """3. Editing a hash fails."""
    with app_with_demo.app_context():
        conn = get_db()
        append_ledger("scan_completed", {"files": 2}, conn)
        target_id = append_ledger("questionnaire_updated", {"keys": ["q2"]}, conn)
        append_ledger("report_generated", {"type": "summary"}, conn)

        cur = conn.cursor()
        cur.execute("UPDATE ledger SET hash = ? WHERE id = ?", ("f" * 64, target_id))
        conn.commit()

        ver = verify_chain(conn)
        assert ver["ok"] is False
        assert ver["first_broken_id"] == target_id


def test_deleting_middle_row_fails(app_with_demo):
    """4. Deleting a middle row fails."""
    with app_with_demo.app_context():
        conn = get_db()
        id1 = append_ledger("scan_completed", {"files": 1}, conn)
        id2 = append_ledger("questionnaire_updated", {"keys": ["q1"]}, conn)
        id3 = append_ledger("report_generated", {"type": "test"}, conn)

        # Delete the middle row (id2)
        cur = conn.cursor()
        cur.execute("DELETE FROM ledger WHERE id = ?", (id2,))
        conn.commit()

        ver = verify_chain(conn)
        assert ver["ok"] is False
        # The chain breaks at id3 because its prev_hash does not match id1's hash
        assert ver["first_broken_id"] == id3
        assert "Hash chain broken" in ver["reason"]


def test_reordering_rows_fails(app_with_demo):
    """5. Reordering rows fails."""
    with app_with_demo.app_context():
        conn = get_db()
        id1 = append_ledger("scan_completed", {"files": 1}, conn)
        id2 = append_ledger("questionnaire_updated", {"keys": ["q1"]}, conn)
        id3 = append_ledger("report_generated", {"type": "test"}, conn)

        # Swap rows id2 and id3 by updating IDs
        cur = conn.cursor()
        cur.execute("UPDATE ledger SET id = 999 WHERE id = ?", (id2,))
        cur.execute("UPDATE ledger SET id = ? WHERE id = ?", (id2, id3))
        cur.execute("UPDATE ledger SET id = ? WHERE id = 999", (id3,))
        conn.commit()

        ver = verify_chain(conn)
        assert ver["ok"] is False


def test_deleting_last_row_detected_by_pack_head_hash(app_with_demo):
    """6. Deleting the LAST row is NOT detected by chain alone but IS detected when the pack's head hash is checked."""
    with app_with_demo.app_context():
        conn = get_db()
        append_ledger("scan_completed", {"files": 1}, conn)
        append_ledger("questionnaire_updated", {"keys": ["q1"]}, conn)

        pack_res = export_evidence_pack(conn)
        pack_head_hash = pack_res["head_hash"]

        # Check chain is intact before deletion
        ver_before = verify_chain(conn)
        assert ver_before["ok"] is True
        assert ver_before["head_hash"] == pack_head_hash

        # Now delete the LAST row of the ledger
        cur = conn.cursor()
        cur.execute("SELECT id, hash FROM ledger ORDER BY id DESC LIMIT 1")
        last_row = cur.fetchone()
        last_id = last_row["id"]
        assert last_row["hash"] == pack_head_hash

        cur.execute("DELETE FROM ledger WHERE id = ?", (last_id,))
        conn.commit()

        # Chain alone: the remaining entries from genesis to (N-1) have valid link hashes!
        ver_after = verify_chain(conn)
        assert ver_after["ok"] is True, "Deleting the last row is NOT detected by chain alone"

        # BUT checking against the exported evidence pack's head hash detects tampering:
        cur.execute("SELECT 1 FROM ledger WHERE hash = ?", (pack_head_hash,))
        assert cur.fetchone() is None, "The pack's head hash is no longer present in the ledger"
        assert ver_after["head_hash"] != pack_head_hash


def test_payload_guard_rejects_aadhaar(app_with_demo):
    """7. Payload guard rejects an Aadhaar-looking string."""
    with app_with_demo.app_context():
        conn = get_db()
        # 9999 4105 7058 is a valid Verhoeff Aadhaar test number
        with pytest.raises(ValueError, match="Personal data detected in ledger payload"):
            append_ledger("intake", {"aadhaar_number": "9999 4105 7058"}, conn)


def test_payload_guard_rejects_phone(app_with_demo):
    """8. Payload guard rejects a phone number."""
    with app_with_demo.app_context():
        conn = get_db()
        with pytest.raises(ValueError, match="Personal data detected in ledger payload"):
            append_ledger("intake", {"contact": "9876543210"}, conn)


def test_tamper_endpoints_return_404_without_kavach_dev(client, monkeypatch):
    """9. Tamper endpoints return 404 without KAVACH_DEV."""
    monkeypatch.delenv("KAVACH_DEV", raising=False)
    resp1 = client.post("/api/dev/tamper", json={"id": 1})
    assert resp1.status_code == 404

    resp2 = client.post("/api/dev/repair", json={})
    assert resp2.status_code == 404


def test_evidence_pack_contents_and_manifest_hashes(app_with_demo):
    """10. Evidence pack contains every listed file, manifest hashes match."""
    with app_with_demo.app_context():
        conn = get_db()
        pack = export_evidence_pack(conn)
        zip_path = pack["path"]
        assert os.path.exists(zip_path)

        with zipfile.ZipFile(zip_path, "r") as zf:
            namelist = zf.namelist()
            expected_files = [
                "manifest.json",
                "ledger.json",
                "risks.json",
                "breach_simulations.json",
                "inventory_summary.json",
                "limitations.md",
            ]
            for ef in expected_files:
                assert ef in namelist, f"Missing {ef} in evidence pack ZIP"

            # Verify manifest hashes match file contents
            manifest_bytes = zf.read("manifest.json")
            manifest = json.loads(manifest_bytes.decode("utf-8"))

            assert manifest["chain_ok"] is True
            assert manifest["head_hash"] == pack["head_hash"]
            assert isinstance(manifest["score"], int)

            for filename, expected_hash in manifest["files"].items():
                file_bytes = zf.read(filename)
                import hashlib
                computed_hash = hashlib.sha256(file_bytes).hexdigest()
                assert computed_hash == expected_hash, f"Hash mismatch for {filename}"


def test_no_raw_identifier_appears_anywhere_in_pack(app_with_demo):
    """11. No raw identifier appears anywhere in the pack (scan all text files with detect functions)."""
    with app_with_demo.app_context():
        conn = get_db()
        pack = export_evidence_pack(conn)

        with zipfile.ZipFile(pack["path"], "r") as zf:
            for name in zf.namelist():
                content = zf.read(name).decode("utf-8", errors="replace")
                findings = detect_all(content, source=name, location="pack", meta={})
                assert len(findings) == 0, f"Raw identifiers found in {name}: {[f['category'] for f in findings]}"


def test_verify_page_renders_without_personal_data_and_shows_tampering(client, app_with_demo):
    """12. /verify/<id> renders without personal data and shows broken status after tampering."""
    with app_with_demo.app_context():
        conn = get_db()
        pack = export_evidence_pack(conn)
        pack_id = pack["pack_id"]

    # Initial check: renders ok
    resp = client.get(f"/verify/{pack_id}")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Chain Intact" in html
    assert pack_id in html
    # Guard: no personal data in HTML
    findings = detect_all(html, source="verify_page", location="html", meta={})
    assert len(findings) == 0

    # Tamper with an event
    with app_with_demo.app_context():
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id FROM ledger ORDER BY id ASC LIMIT 1")
        first_id = cur.fetchone()["id"]
        tamper_ledger_event(first_id, conn)

    # After tampering: /verify/<id> shows broken status
    resp_tampered = client.get(f"/verify/{pack_id}")
    assert resp_tampered.status_code == 200
    tampered_html = resp_tampered.get_data(as_text=True)
    assert "Verification Failed" in tampered_html or "Tampering detected" in tampered_html


def test_repair_restores_ok(client, app_with_demo, monkeypatch):
    """13. Repair restores ok."""
    monkeypatch.setenv("KAVACH_DEV", "1")
    with app_with_demo.app_context():
        conn = get_db()
        append_ledger("scan_completed", {"files": 2}, conn)
        target_id = append_ledger("questionnaire_updated", {"keys": ["q1"]}, conn)

        # Tamper via endpoint
        resp_tamper = client.post("/api/dev/tamper", json={"id": target_id})
        assert resp_tamper.status_code == 200
        ver_tampered = verify_chain(conn)
        assert ver_tampered["ok"] is False

        # Repair via endpoint
        resp_repair = client.post("/api/dev/repair", json={})
        assert resp_repair.status_code == 200
        ver_repaired = verify_chain(conn)
        assert ver_repaired["ok"] is True
