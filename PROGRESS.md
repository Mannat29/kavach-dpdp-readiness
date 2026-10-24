# Progress

## Done
- Clean SQLite DB on startup unless KAVACH_KEEP_DB=1; POST /api/reset and header Reset button.
- Tests isolated to temp DBs via conftest; questionnaire tri-state with "not confirmed" risk text.
- Task 3c: UI polish — wording, verify popover, data-map labels/layout, ENABLED_PAGES nav config.
- Task 4a: Informal Request Catcher + Erasure Engine (backend + tests only).
  - `path` column on sources; uploads persist to data/workspace/ (git-ignored); originals never modified.
  - data/demo/demo_requests.txt (8 WhatsApp msgs, Ramesh Kumar = 5-file requester); scripts/seed_requests.py.
  - app/rules/intents.yaml: EN/Hinglish/Kannada-Latin keyword rules; false-positive guard (delete message/report/photo = none).
  - app/rights.py: classify_message, parse_whatsapp_text, process_intake, resolve_sender (strong/probable/ambiguous/none).
  - app/rules/retention.yaml retained fields and reason codes:
    - patients.xlsx Test Name/Notes → MEDICAL_RECORD_RETAIN (medical record retention, needs professional review (verify))
    - billing.csv invoice_no/amount/gstin/patient_name → BILLING_RETAIN (tax/accounting record retention, verify period)
    - billing.csv phone → BILLING_PHONE_MASK (phone not required for tax records; mask to reduce risk)
    - staff.csv all → STAFF_RETAIN (employment basis DPDP Act s.7(i); outside scope of customer erasure request)
  - app/erasure.py: build_plan (sha256 plan hash), execute (sha256 integrity guard, cleaned copies, residual check, receipt.json+html).
  - app/ledger.py: hash-chained audit log (ledger table); RESPONSE_DAYS=30 in config.py (TODO verify DPDP Rules 2025).
  - API: POST /api/rights/intake, GET /api/rights, GET /api/rights/<id>, confirm-identity, approve, plan-override, receipt, download, demo-text.
  - 119 tests passing (66 new: test_rights.py, test_erasure.py, test_rights_routes.py + 53 existing).

## Next: Breach simulator.
