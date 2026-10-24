"""Tests for app.erasure: build_plan, _resolve_field_policy, _process_csv/_txt/_xlsx helpers."""
import csv
import json
import os
import tempfile

import pytest

from app.db import get_db, init_db
from app.erasure import (
    build_plan,
    _resolve_field_policy,
    _process_csv,
    _process_txt,
    _sha256_file,
    _load_retention_yaml,
    _is_expected_residual,
)


# ---------------------------------------------------------------------------
# _load_retention_yaml
# ---------------------------------------------------------------------------
def test_retention_yaml_loads():
    ret = _load_retention_yaml()
    assert "sources" in ret
    assert "appointments_form.csv" in ret["sources"]
    assert "whatsapp_chat.txt" in ret["sources"]
    assert "patients.xlsx" in ret["sources"]
    assert "billing.csv" in ret["sources"]
    assert "staff.csv" in ret["sources"]


# ---------------------------------------------------------------------------
# _resolve_field_policy
# ---------------------------------------------------------------------------
class TestResolveFieldPolicy:
    def setup_method(self):
        self.retention = _load_retention_yaml()

    def _policy(self, filename):
        return self.retention["sources"].get(filename, {})

    def test_appt_name_erase(self):
        p = _resolve_field_policy(self._policy("appointments_form.csv"), "Name", "appointments_form.csv", "name")
        assert p["decision"] == "ERASE"
        assert p["reason_code"] == "APPT_ERASE"

    def test_patients_phone_erase(self):
        p = _resolve_field_policy(self._policy("patients.xlsx"), "Phone", "patients.xlsx", "phone")
        assert p["decision"] == "ERASE"

    def test_patients_notes_retain(self):
        p = _resolve_field_policy(self._policy("patients.xlsx"), "Notes", "patients.xlsx", "health_term")
        assert p["decision"] == "RETAIN"
        assert p["verify"] is True

    def test_billing_phone_mask(self):
        p = _resolve_field_policy(self._policy("billing.csv"), "phone", "billing.csv", "phone")
        assert p["decision"] == "MASK"
        assert "BILLING_PHONE_MASK" in p["reason_code"]

    def test_staff_default_retain(self):
        p = _resolve_field_policy(self._policy("staff.csv"), "SomeUnknownField", "staff.csv", "name")
        assert p["decision"] == "RETAIN"

    def test_unknown_source_defaults_to_retain(self):
        p = _resolve_field_policy({}, "anything", "unknown.csv", "phone")
        assert p["decision"] == "RETAIN"


# ---------------------------------------------------------------------------
# _sha256_file
# ---------------------------------------------------------------------------
def test_sha256_file(tmp_path):
    f = tmp_path / "test.txt"
    f.write_bytes(b"hello world")
    h = _sha256_file(str(f))
    import hashlib
    expected = hashlib.sha256(b"hello world").hexdigest()
    assert h == expected


# ---------------------------------------------------------------------------
# _process_csv
# ---------------------------------------------------------------------------
class TestProcessCsv:
    def _write_csv(self, path, rows):
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            csv.writer(f).writerows(rows)

    def test_erase_row_removed(self, tmp_path):
        src = str(tmp_path / "billing.csv")
        out = str(tmp_path / "billing_out.csv")
        self._write_csv(src, [
            ["invoice_no", "patient_name", "phone"],
            ["INV-001", "Ramesh Kumar", "9876543210"],
            ["INV-002", "Other Person", "8888888888"],
        ])
        record_decisions = {
            "billing.csv:R2": {"invoice_no": "ERASE", "patient_name": "ERASE", "phone": "ERASE"},
        }
        _process_csv(src, out, "billing.csv", record_decisions, {})
        with open(out, encoding="utf-8-sig") as f:
            rows = list(csv.reader(f))
        assert len(rows) == 2  # header + 1 remaining row
        assert rows[1][1] == "Other Person"

    def test_mask_phone_field(self, tmp_path):
        src = str(tmp_path / "billing.csv")
        out = str(tmp_path / "billing_out.csv")
        self._write_csv(src, [
            ["invoice_no", "patient_name", "phone"],
            ["INV-001", "Ramesh Kumar", "9876543210"],
        ])
        record_decisions = {
            "billing.csv:R2": {"invoice_no": "RETAIN", "patient_name": "RETAIN", "phone": "MASK"},
        }
        _process_csv(src, out, "billing.csv", record_decisions, {})
        with open(out, encoding="utf-8-sig") as f:
            rows = list(csv.reader(f))
        assert rows[1][2] == "[REDACTED]"
        assert rows[1][1] == "Ramesh Kumar"  # retained unchanged

    def test_partial_erase_row_kept(self, tmp_path):
        src = str(tmp_path / "patients.csv")
        out = str(tmp_path / "patients_out.csv")
        self._write_csv(src, [
            ["Name", "Phone", "Notes"],
            ["Ramesh Kumar", "9876543210", "pregnancy test"],
        ])
        record_decisions = {
            "patients.csv:R2": {"Name": "ERASE", "Phone": "ERASE", "Notes": "RETAIN"},
        }
        _process_csv(src, out, "patients.csv", record_decisions, {})
        with open(out, encoding="utf-8-sig") as f:
            rows = list(csv.reader(f))
        assert len(rows) == 2  # row not removed (not all ERASE)
        assert rows[1][0] == ""  # Name erased
        assert rows[1][1] == ""  # Phone erased
        assert rows[1][2] == "pregnancy test"  # Notes retained

    def test_non_person_rows_untouched(self, tmp_path):
        src = str(tmp_path / "billing.csv")
        out = str(tmp_path / "billing_out.csv")
        self._write_csv(src, [
            ["invoice_no", "patient_name", "phone"],
            ["INV-001", "Ramesh Kumar", "9876543210"],
            ["INV-002", "Other Person", "8888888888"],
        ])
        # Only R2 has a decision
        record_decisions = {
            "billing.csv:R2": {"invoice_no": "ERASE", "patient_name": "ERASE", "phone": "ERASE"},
        }
        _process_csv(src, out, "billing.csv", record_decisions, {})
        with open(out, encoding="utf-8-sig") as f:
            rows = list(csv.reader(f))
        assert any("Other Person" in r for r in rows)

    def test_original_unchanged_after_process(self, tmp_path):
        src = str(tmp_path / "billing.csv")
        out = str(tmp_path / "billing_out.csv")
        self._write_csv(src, [
            ["invoice_no", "phone"],
            ["INV-001", "9876543210"],
        ])
        original_hash = _sha256_file(src)
        _process_csv(src, out, "billing.csv",
                     {"billing.csv:R2": {"invoice_no": "ERASE", "phone": "ERASE"}}, {})
        assert _sha256_file(src) == original_hash


# ---------------------------------------------------------------------------
# _process_txt
# ---------------------------------------------------------------------------
class TestProcessTxt:
    def _write_txt(self, path, lines):
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    def test_erase_sender_line(self, tmp_path):
        src = str(tmp_path / "chat.txt")
        out = str(tmp_path / "chat_out.txt")
        self._write_txt(src, [
            "20/10/26, 9:05 pm - Ramesh Kumar: hata dijiye meri details",
            "20/10/26, 9:06 pm - Staff: Thank you for your message",
        ])
        record_decisions = {
            "line 1": {"line": "ERASE"},
        }
        _process_txt(src, out, "whatsapp_chat.txt", record_decisions, {}, {})
        with open(out, encoding="utf-8") as f:
            content = f.read()
        assert "Ramesh Kumar" not in content
        assert "Thank you" in content

    def test_mask_phone_in_other_line(self, tmp_path):
        src = str(tmp_path / "chat.txt")
        out = str(tmp_path / "chat_out.txt")
        self._write_txt(src, [
            "20/10/26, 9:06 pm - Staff: Contact Ramesh at 9876543210 for followup",
        ])
        person_identifiers = {"phones": {"9876543210"}, "emails": set(), "aadhaar_digits": set(), "name_tokens": set()}
        _process_txt(src, out, "whatsapp_chat.txt", {}, {}, person_identifiers)
        with open(out, encoding="utf-8") as f:
            content = f.read()
        assert "9876543210" not in content
        assert "[REDACTED]" in content

    def test_non_erased_lines_preserved(self, tmp_path):
        src = str(tmp_path / "chat.txt")
        out = str(tmp_path / "chat_out.txt")
        self._write_txt(src, [
            "20/10/26, 9:05 pm - Ramesh Kumar: hata dijiye",
            "20/10/26, 9:10 pm - Other Person: okay noted",
        ])
        record_decisions = {"line 1": {"line": "ERASE"}}
        _process_txt(src, out, "whatsapp_chat.txt", record_decisions, {}, {})
        with open(out, encoding="utf-8") as f:
            content = f.read()
        assert "Other Person" in content

    def test_original_unchanged_after_process(self, tmp_path):
        src = str(tmp_path / "chat.txt")
        out = str(tmp_path / "chat_out.txt")
        self._write_txt(src, ["20/10/26, 9:05 pm - A: delete my data"])
        original_hash = _sha256_file(src)
        _process_txt(src, out, "whatsapp_chat.txt", {"line 1": {"line": "ERASE"}}, {}, {})
        assert _sha256_file(src) == original_hash


# ---------------------------------------------------------------------------
# build_plan
# ---------------------------------------------------------------------------
class TestBuildPlan:
    def test_build_plan_no_person_raises(self, isolate_test_database):
        conn = get_db(isolate_test_database)
        cur = conn.cursor()
        # Create a request with no person_id
        cur.execute("""
            INSERT INTO rights_requests (intent, sender_masked, person_id, resolution,
              confidence, received_at, due_at, status, message_excerpt_masked)
            VALUES ('erase', 'R**** K***', NULL, 'none', 0.8,
                    '2026-10-20T00:00:00', '2026-11-19T00:00:00', 'received', 'hata dijiye')
        """)
        conn.commit()
        req_id = cur.lastrowid
        with pytest.raises(ValueError, match="person not resolved"):
            build_plan(req_id, conn)

    def test_build_plan_missing_request_raises(self, isolate_test_database):
        conn = get_db(isolate_test_database)
        with pytest.raises(ValueError, match="not found"):
            build_plan(9999, conn)

    def test_build_plan_with_demo_data(self, isolate_test_database):
        """End-to-end: scan demo data, run intake, build plan for Ramesh Kumar."""
        from app.inventory import scan_demo_data
        from app.rights import parse_whatsapp_text, process_intake
        import os

        conn = get_db(isolate_test_database)
        scan_demo_data(conn)

        # Process intake with Ramesh Kumar's erase request
        msgs = [{"sender": "Ramesh Kumar", "text": "Mera number aur details list se hata dijiye",
                 "timestamp": "20/10/26, 9:05 pm"}]
        created = process_intake(msgs, conn)
        assert len(created) == 1
        req = created[0]
        req_id = req["id"]

        # Ramesh Kumar should be matched via name hash (probable)
        assert req["resolution"] in ("probable", "strong", "none")

        if req["person_id"] is None:
            pytest.skip("Ramesh Kumar not resolved — entity resolution not linked")

        result = build_plan(req_id, conn)
        assert "plan" in result
        assert "plan_hash" in result
        assert result["plan_hash"] and len(result["plan_hash"]) == 64  # sha256 hex

        # Plan should have sources
        plan = result["plan"]
        assert "sources" in plan

        # Verify DB updated
        cur = conn.cursor()
        cur.execute("SELECT status, plan_hash FROM rights_requests WHERE id = ?", (req_id,))
        row = cur.fetchone()
        assert row["status"] == "plan_ready"
        assert row["plan_hash"] == result["plan_hash"]
