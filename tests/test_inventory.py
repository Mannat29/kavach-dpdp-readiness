"""Tests for Inventory, Entity Resolution, and Ingestion."""
import json
import os
import sqlite3
import pytest

from app.db import init_db, get_db
from app.detect import detect_dob
from app.inventory import (
    make_record_key,
    mask_name,
    scan_demo_data,
    get_inventory_summary,
    run_entity_resolution,
)


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    """Use an isolated SQLite database for each test."""
    db_file = str(tmp_path / "test_kavach.db")
    monkeypatch.setenv("KAVACH_DATABASE", db_file)
    init_db(db_file)
    yield db_file


def test_make_record_key():
    """Verify record_key format: source + sheet/row for tabular, line number for chat."""
    assert make_record_key("patients.xlsx", "Patients/R2/C3") == "patients.xlsx:Patients/R2"
    assert make_record_key("billing.csv", "R10/C2") == "billing.csv:R10"
    assert make_record_key("whatsapp_chat.txt", "line 42") == "line 42"


def test_mask_name():
    """Verify masked name format like 'Person 07 (R**** K***)'."""
    assert mask_name("Ramesh Kumar") == "R**** K****"
    assert mask_name("Priya Sharma") == "P**** S****"
    assert mask_name("A") == "A"
    assert mask_name("") == "****"


def test_dob_minor_detection_and_no_raw_storage():
    """Verify DOB detector computes is_minor (< 18) and never stores raw date."""
    # Person born in 2015 is minor (< 18)
    minor_findings = detect_dob("2015-05-15", "test.csv", "R2/C5", {"header": "DOB"})
    assert len(minor_findings) == 1
    f_minor = minor_findings[0]
    assert f_minor["meta"]["is_minor"] is True
    # Ensure raw DOB is not exposed in finding dict
    assert "2015-05-15" not in f_minor.values()

    # Person born in 1980 is adult (>= 18)
    adult_findings = detect_dob("1980-01-01", "test.csv", "R3/C5", {"header": "DOB"})
    assert len(adult_findings) == 1
    f_adult = adult_findings[0]
    assert f_adult["meta"]["is_minor"] is False
    assert "1980-01-01" not in f_adult.values()


def test_demo_people_resolve_to_12_clusters():
    """Verify the 12 known shared people resolve to 12 clusters on the demo set."""
    conn = get_db()
    scan_demo_data(conn)

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pt_path = os.path.join(base_dir, "data", "demo", "people_truth.json")
    with open(pt_path, encoding="utf-8") as f:
        people_truth = json.load(f)

    cur = conn.cursor()
    cur.execute("""
        SELECT pr.person_id, s.filename as source, pr.record_key
        FROM person_records pr
        JOIN sources s ON pr.source_id = s.id
    """)
    pred_mapping = {(row["source"], row["record_key"]): row["person_id"] for row in cur.fetchall()}

    resolved_person_ids = set()
    for person in people_truth:
        records = person["records"]
        # Find which predicted person_id the first record resolved to
        first_key = (records[0]["source"], records[0]["record_key"])
        assert first_key in pred_mapping, f"Record {first_key} was not resolved"
        cluster_id = pred_mapping[first_key]
        resolved_person_ids.add(cluster_id)

        # All records for this person must resolve to the EXACT SAME cluster
        for r in records[1:]:
            r_key = (r["source"], r["record_key"])
            assert r_key in pred_mapping, f"Record {r_key} was not resolved"
            assert pred_mapping[r_key] == cluster_id, (
                f"Record {r_key} of person {person['name']} resolved to {pred_mapping[r_key]} "
                f"instead of {cluster_id}"
            )

    # Exactly 12 distinct clusters must represent the 12 known shared people
    assert len(resolved_person_ids) == 12


def test_different_people_not_merged():
    """Verify two people sharing no identifiers are not merged."""
    conn = get_db()
    cur = conn.cursor()

    # Create dummy source
    cur.execute("INSERT INTO sources (filename, type, record_count) VALUES ('test.csv', 'csv', 2)")
    source_id = cur.lastrowid

    # Person A findings: Name A, Phone A
    cur.execute(
        """INSERT INTO findings (source_id, record_key, location, category, masked_sample, value_hash, confidence)
           VALUES (?, 'test.csv:R2', 'R2/C1', 'name', 'A****', 'hash_name_a', 0.9)""",
        (source_id,),
    )
    cur.execute(
        """INSERT INTO findings (source_id, record_key, location, category, masked_sample, value_hash, confidence)
           VALUES (?, 'test.csv:R2', 'R2/C2', 'phone', 'XXXXXX1111', 'hash_phone_a', 0.95)""",
        (source_id,),
    )

    # Person B findings: Name B, Phone B (no shared identifiers)
    cur.execute(
        """INSERT INTO findings (source_id, record_key, location, category, masked_sample, value_hash, confidence)
           VALUES (?, 'test.csv:R3', 'R3/C1', 'name', 'B****', 'hash_name_b', 0.9)""",
        (source_id,),
    )
    cur.execute(
        """INSERT INTO findings (source_id, record_key, location, category, masked_sample, value_hash, confidence)
           VALUES (?, 'test.csv:R3', 'R3/C2', 'phone', 'XXXXXX2222', 'hash_phone_b', 0.95)""",
        (source_id,),
    )
    conn.commit()

    run_entity_resolution(conn)

    cur.execute("SELECT person_id FROM person_records WHERE record_key = 'test.csv:R2'")
    p_a = cur.fetchone()["person_id"]
    cur.execute("SELECT person_id FROM person_records WHERE record_key = 'test.csv:R3'")
    p_b = cur.fetchone()["person_id"]

    assert p_a != p_b, f"Person A ({p_a}) and Person B ({p_b}) sharing no identifiers were merged!"


def test_scan_demo_twice_same_counts():
    """Verify scanning demo dataset twice does not duplicate rows."""
    conn = get_db()
    scan_demo_data(conn)
    summary1 = get_inventory_summary(conn)

    # Scan again
    scan_demo_data(conn)
    summary2 = get_inventory_summary(conn)

    assert summary1["total_sources"] == summary2["total_sources"]
    assert summary1["total_records"] == summary2["total_records"]
    assert summary1["total_findings"] == summary2["total_findings"]
    assert summary1["total_people"] == summary2["total_people"]


def test_inventory_sensitive_flags():
    """Verify inventory summary identifies sensitive categories."""
    conn = get_db()
    scan_demo_data(conn)
    summary = get_inventory_summary(conn)

    # patients.xlsx contains health_term and aadhaar -> sensitive
    patients_src = next(s for s in summary["sources"] if s["filename"] == "patients.xlsx")
    assert patients_src["has_sensitive"] is True
    assert "aadhaar" in patients_src["categories_present"]
    assert "health_term" in patients_src["categories_present"]
