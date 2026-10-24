# Progress

## Done
- Task 5a & 5b: Breach simulator backend & interactive UI with blast-radius graph and drafts.
- Task 6a: Audit ledger, tamper demo, Evidence page, evidence pack & public verify page.
- Task 6b: Reports page and self-contained printable readiness report.
  - Compliance summary API (`GET /api/reports/summary`) with scan summary, score deductions, risks, questionnaire, rights requests, erasure receipts, breach simulations, and prioritised recommended actions (max 8, overdue requests first).
  - Printable HTML export (`GET /api/reports/export`) with print stylesheet, notices, detector accuracy benchmark, and ledger event `report_generated`.
  - Accessible Reports page (`templates/reports.html`) with "Download printable report", empty state, and no colour-only meaning.
  - "Reports" added to `ENABLED_PAGES`; 157 tests passing (`tests/test_reports.py` + full test suite).
