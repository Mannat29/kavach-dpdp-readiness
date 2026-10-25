# Progress

## Done
- Task 8: Minimalist Legal Theme with True 3D WebGL PBR Scales of Justice & Balanced Layout.
  - Replaced image slicing with an actual real 3D WebGL PBR Scales of Justice model using Three.js (stepped gold pedestal, fluted column, curved arched balance beam, hook rings, hanging suspension chains, and 3D hollow concave balance bowls with studio lighting).
  - Scaled up 3D model slightly (0.63) on Dashboard; rock-solid in-place rotation on central vertical Y-axis with zero cursor dangling or tilt.
  - Enabled the 3D rotating balance scale across all pages (`.page-container`), with a compact header badge (`220×200px`) on non-dashboard routes to completely eliminate overlap on content cards and boxes.
  - Replaced raw emojis on Data Map mode switcher buttons ("Sources → Categories" and "Person View") with clean inline SVG vector icons.
  - Styled Scanner page `.stats-strip` with matching KPI card surfaces (`.stat-item`, `.stat-title`, `.stat-number`, `.stat-item-alert`), eliminating raw unstyled text.
  - Eliminated the empty white void below the Readiness Score card by setting flex stretch on `.deductions-container` and `.deductions-list`, harmonizing card heights across the split grid.
  - Right-edge 4-dot section navigator tracking sections (Welcome, Inventory, Compliance, Resolution) with smooth scrolling.
  - Zero emojis across the entire app — all replaced with crisp SVG vector icons.
  - Snapshot test diff: empty text diff & identical element IDs across all routes.
  - All test suites passing (`python -m pytest -q`).

- Purpose Mapping (Purpose Limitation Readiness):
  - Added `purpose_answers` table in `app/schema.sql` (append-only audit trail with `superseded_by` tracking and CHECK constraint on status).
  - Created `app/purposes.py` with vocabulary/preset loading, `infer_segment()`, `get_questions()` with progress tracking and unverified preset suggestions (omitted for `aadhaar`), `record_answer()` with validation and ledger integration, and `get_history()`.
  - Added API endpoints in `app/routes.py`: `GET /api/purposes`, `GET /api/purpose-questions`, `POST /api/purpose-answers`, `GET /api/purpose-history`, and UI view `/purposes`.
  - Updated `scripts/demo_reset.py` and `POST /api/reset` to cleanly wipe `purpose_answers` on demo reset.
  - Created `/purposes` page (`templates/purposes.html`) with documentation progress bar, question cards with checkboxes, "I don't know" option, save controls, readiness aid disclaimer, and zero emojis.
  - Updated `ENABLED_PAGES` and `base.html` navigation bar to include Purposes.
  - Integrated `purposes.json` into evidence pack export (`app/ledger.py`) with manifest hashing.
  - Added full test suite in `tests/test_purposes.py` covering all 7 requirement areas.

- Flaky test fix in tests/test_ledger.py:
  - Diagnosed false positive in `test_no_raw_identifier_appears_anywhere_in_pack`: 10-digit numeric run inside 64-hex SHA-256 digest in `manifest.json` matched `_PHONE_RE`.
  - Stripped `\b[0-9a-f]{64}\b` digests before `detect_all()` scan in `test_no_raw_identifier_appears_anywhere_in_pack`.
  - Added `test_positive_control_hex_stripping_preserves_phone_detection()` to ensure genuine PII detection remains robust.
  - Full test suite passing (209 passed, 1 skipped).

- Keyed HMAC-SHA256 upgrade in app/detect.py:
  - Replaced `hashlib.sha256((salt + value).encode())` with `hmac.new(key_bytes, normalized.encode(), hashlib.sha256)` in `hash_value()`.
  - Updated docstrings and warning text: now keyed HMAC, key from KAVACH_SALT or data/.salt (git-ignored); in production the key must be kept outside the database.
  - Added `tests/test_hmac.py` (4 tests): deterministic output, differs from SHA-256 concatenation, changes when key changes, equal for same value in different formats via normalization.
  - Only `app/detect.py` and `tests/test_hmac.py` touched; no other files changed.
  - demo_reset: 5 sources, 585 findings, 36 people. pytest: 213 passed, 1 skipped. eval demo: F1 0.99. eval heldout: F1 0.88.

- Rule title fix in app/rules/rules.yaml:
  - Renamed `notice_at_collection` title from "No notice at collection points" to "No notice at CCTV collection points" to match its CCTV-only trigger. id, trigger, decision and reason_codes unchanged.

- Citation text updates in app/rules/retention.yaml and app/rules/rules.yaml:
  - `appointments_form.csv` & `whatsapp_chat.txt`: updated citation_hint to "DPDP Act s.8(7) and s.12(3) - erasure when purpose no longer served or on request (verify against official text)".
  - `patients.xlsx`: citation_hint updated to "Retention subject to applicable medical/clinical-establishment record rules and s.8(7) 'unless law requires retention'; verify with a professional" (removed s.7(i), verify: true).
  - `billing.csv`: citation_hint updated to "Retention period set by applicable tax/accounting law; verify the period" (removed "7 years").
  - `rules.yaml`: `aadhaar_in_chat` citation_hint updated to "s.8(5) safeguards; best practice (Aadhaar-specific rules are outside the DPDP Act)"; `breach_contact_process` updated to "s.8(6) breach intimation; s.8(9) contact point".
  - Full test suite passing: 213 passed, 1 skipped.

- Optional scanned-document ingest (OCR) — adapted from Nehar's _incoming/ocr_engine.py:
  - Created `app/ocr.py`: magic-byte format sniffing, size/page limits, encrypted/malformed PDF handling, native PDF text first (OCR only when insufficient), dark-image preprocessing, Tesseract path resolution (TESSERACT_CMD env, PATH, Windows default `C:\Program Files\Tesseract-OCR\tesseract.exe`), mockable OCR runner, `ocr_available()`, non-Latin OCR tagged `low_confidence`.
  - Added OCR constants to `app/config.py` (max file size, max pages, min native chars/words, default language "eng", Tesseract Windows default path).
  - Updated `app/ingest.py`: `get_allowed_extensions()` dynamically adds `.pdf/.png/.jpg/.jpeg` when OCR is available; `read_source()` handles OCR formats with `ValueError("OCR unavailable: <reason>")` guard.
  - Updated `app/routes.py` and `templates/dashboard.html`: dashboard passes `ocr_available` flag; file-picker accept attribute and error messages adapt dynamically.
  - Updated `app/inventory.py`: `run_entity_resolution()` skips `low_confidence` OCR findings for strong entity links; fixed `f.get("meta_json")` → `f["meta_json"]` (sqlite3.Row incompatibility).
  - Created `scripts/make_ocr_sample.py` and `data/demo_ocr/clinic_slip.png` with synthetic phone and Verhoeff-valid Aadhaar-format number. No real data.
  - Created `tests/test_ocr.py` (7 tests): native PDF skips OCR, image triggers OCR, corrupt file rejected, unavailable message, no raw PII stored, non-Latin tagged low_confidence, real-Tesseract smoke test (skipif unavailable).
  - Added `pytest.ini` with `testpaths = tests` to exclude `_incoming/test_ocr_ingestion.py` (requires uninstalled `backend` module).
  - Updated `tests/test_hardening.py::test_upload_bad_extension`: swapped `.pdf` (now a valid OCR extension) for `.exe` (always rejected), preserving the test's intent.
  - Added `pillow>=10.0`, `pymupdf>=1.23`, `pytesseract>=0.3.10` under `# optional: OCR` in `requirements.txt`.
  - Full test suite: 220 passed, 1 skipped.

- SLM module replacement from teammate's _incoming/:
  - Replaced `app/slm.py` with `_incoming/slm_nehar.py`, removing `pydantic` imports and `ModelOutput` class in favor of pure Python dict/list parsing and validation in `scan_chunk()`.
  - Replaced `tests/test_slm.py` with `_incoming/test_slm_nehar.py` (43 unit tests).
  - Deleted `contrib/slm_grounding/`.
  - Verified no disallowed dependencies (`fastapi`, `sqlalchemy`, `pydantic`, `pandas`, `backend.`) in `app/`.
  - Test suites passing: `tests/test_slm.py` (43 passed), full test suite (228 passed).



- SLM Suggest API route (POST /api/slm/suggest):
  - Added opt-in `POST /api/slm/suggest` in `app/routes.py` invoking `app.slm.scan_chunk()`.
  - Input validation: requires JSON object, non-empty string `text` <= 4000 characters; returns 400 on violations.
  - Zero DB writes, zero ledger writes, no scoring pipeline involvement. Returns 200 with mode off and empty findings by default.
  - Added `tests/test_slm_route.py` covering default off mode, mock mode findings (no raw text in JSON), 400 on bad inputs, and table row count immutability verification.
  - Tests passing: 232 passed; demo reset verified at 585 findings across 36 people.
