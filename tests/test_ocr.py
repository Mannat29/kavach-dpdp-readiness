"""Tests for optional scanned-document and OCR ingestion."""
import io
import json
import os
import pytest
from PIL import Image, ImageDraw
import pymupdf

from app.db import get_db, init_db
from app.ingest import read_source
from app.inventory import run_entity_resolution, scan_and_ingest_file
from app.ocr import (
    ocr_available,
    resolve_tesseract_cmd,
    set_custom_ocr_runner,
)
from scripts.make_ocr_sample import create_clinic_slip, generate_synthetic_aadhaar


@pytest.fixture(autouse=True)
def reset_custom_runner():
    """Ensure custom mock runner is always reset after each test."""
    yield
    set_custom_ocr_runner(None)


def test_native_pdf_skips_ocr(tmp_path):
    """Native selectable PDF extracts directly and never invokes OCR runner."""
    pdf_path = str(tmp_path / "selectable.pdf")
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    sample_text = (
        "Patient Clinical Consultation Report\n"
        "Patient Name: Aarav Sharma\n"
        "Contact Mobile: 9876543210\n"
        "Email Address: aarav.sharma@example.com\n"
        "Diagnosis: Seasonal allergic rhinitis. Prescribed antihistamine."
    )
    page.insert_text((50, 72), sample_text, fontsize=12)
    doc.save(pdf_path)
    doc.close()

    ocr_call_count = 0

    def mock_runner(img, lang="eng"):
        nonlocal ocr_call_count
        ocr_call_count += 1
        return {"text": ["SHOULD_NOT_BE_CALLED"]}

    set_custom_ocr_runner(mock_runner)

    units = list(read_source(pdf_path))
    assert len(units) == 1
    location, text, meta = units[0]

    assert location == "page 1"
    assert meta["method"] == "native"
    assert "Aarav Sharma" in text
    assert ocr_call_count == 0, "Native PDF with sufficient text must not invoke OCR runner"


def test_image_triggers_ocr(tmp_path):
    """Image files trigger OCR recognition with location 'page 1' and method 'ocr'."""
    img_path = str(tmp_path / "receipt.png")
    img = Image.new("RGB", (600, 300), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((20, 30), "Consultation Slip", fill="black")
    img.save(img_path, format="PNG")

    def mock_runner(img, lang="eng"):
        return {
            "text": ["AAROGYA", "CLINIC", "Phone:", "9876543210"],
            "block_num": [0, 0, 0, 0],
            "line_num": [1, 1, 2, 2],
        }

    set_custom_ocr_runner(mock_runner)

    units = list(read_source(img_path))
    assert len(units) == 1
    location, text, meta = units[0]

    assert location == "page 1"
    assert meta["method"] == "ocr"
    assert "Phone: 9876543210" in text


def test_corrupt_file_rejected(tmp_path):
    """Malformed or spoofed files without valid magic bytes are rejected."""
    corrupt_pdf = str(tmp_path / "corrupt.pdf")
    with open(corrupt_pdf, "wb") as f:
        f.write(b"NOT_A_VALID_PDF_HEADER_JUST_GARBAGE_BYTES")

    with pytest.raises(ValueError, match="Unsupported or corrupted file"):
        list(read_source(corrupt_pdf))

    empty_png = str(tmp_path / "empty.png")
    with open(empty_png, "wb") as f:
        pass  # 0 bytes

    with pytest.raises(ValueError, match="empty"):
        list(read_source(empty_png))


def test_unavailable_message(tmp_path, monkeypatch):
    """When OCR is unavailable, attempting to read PDF/images raises clear error."""
    # Create valid dummy PDF file so size check passes
    pdf_path = str(tmp_path / "doc.pdf")
    with open(pdf_path, "wb") as f:
        f.write(b"%PDF-1.4 dummy content")

    monkeypatch.setattr(
        "app.ocr.ocr_available",
        lambda: {"available": False, "reason": "Tesseract binary not found"},
    )

    with pytest.raises(ValueError, match="OCR unavailable: Tesseract binary not found"):
        list(read_source(pdf_path))


def test_no_raw_pii_stored_in_db_or_ledger(tmp_path, isolate_test_database):
    """Raw OCR text is never persisted: only masked samples and salted/keyed hashes enter DB and ledger."""
    slip_path = str(tmp_path / "test_slip.png")
    create_clinic_slip(slip_path)

    raw_phone = "9876543210"
    raw_aadhaar = generate_synthetic_aadhaar(42)

    conn = get_db(isolate_test_database)
    init_db(isolate_test_database)

    # Ingest the OCR slip
    source_id = scan_and_ingest_file(slip_path, conn)
    assert source_id > 0

    run_entity_resolution(conn)

    cur = conn.cursor()

    # Verify findings table
    cur.execute("SELECT location, category, masked_sample, value_hash, meta_json FROM findings WHERE source_id = ?", (source_id,))
    findings = cur.fetchall()
    assert len(findings) > 0

    for f in findings:
        # Neither raw phone nor raw Aadhaar should appear in masked_sample or meta_json
        assert raw_phone not in f["masked_sample"]
        assert raw_aadhaar not in f["masked_sample"]
        if f["meta_json"]:
            assert raw_phone not in f["meta_json"]
            assert raw_aadhaar not in f["meta_json"]

    # Verify people table
    cur.execute("SELECT masked_name, name_hash FROM people")
    for p in cur.fetchall():
        if p["masked_name"]:
            assert raw_phone not in p["masked_name"]
            assert raw_aadhaar not in p["masked_name"]

    # Verify ledger table
    cur.execute("SELECT payload_json FROM ledger")
    for row in cur.fetchall():
        payload_str = row["payload_json"]
        assert raw_phone not in payload_str
        assert raw_aadhaar not in payload_str


def test_non_latin_ocr_tagged_low_confidence_and_no_strong_links(tmp_path, isolate_test_database):
    """Non-Latin OCR text is tagged low_confidence in meta and never creates strong entity links."""
    img_path = str(tmp_path / "hindi_slip.png")
    img = Image.new("RGB", (500, 200), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((20, 30), "Hindi Document", fill="black")
    img.save(img_path, format="PNG")

    # Mock runner returning Devanagari script text
    def mock_runner(img, lang="eng"):
        return {
            "text": ["रोगी", "का", "फ़ोन:", "9876543210"],
            "block_num": [0, 0, 0, 0],
            "line_num": [1, 1, 1, 1],
        }

    set_custom_ocr_runner(mock_runner)

    units = list(read_source(img_path))
    assert len(units) == 1
    location, text, meta = units[0]

    assert meta.get("low_confidence") is True

    # Ingest and verify entity resolution does not create a strong link
    conn = get_db(isolate_test_database)
    init_db(isolate_test_database)

    scan_and_ingest_file(img_path, conn)
    run_entity_resolution(conn)

    cur = conn.cursor()
    cur.execute("SELECT link_type FROM person_records")
    link_types = [r["link_type"] for r in cur.fetchall()]
    assert "strong" not in link_types


def test_real_tesseract_smoke_test():
    """Live smoke test with real Tesseract when installed."""
    avail = ocr_available()
    if not avail["available"]:
        pytest.skip(f"Live Tesseract unavailable: {avail['reason']}")

    demo_slip = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "demo_ocr", "clinic_slip.png"
    )
    if not os.path.exists(demo_slip):
        create_clinic_slip(demo_slip)

    units = list(read_source(demo_slip))
    assert len(units) >= 1
    _, text, meta = units[0]
    assert meta["method"] == "ocr"
    assert "9876543210" in text
