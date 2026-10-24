# Progress

## Done
- Task 5a & 5b: Breach simulator backend & interactive UI with blast-radius graph and drafts.
- Task 6a: Audit ledger, tamper demo, Evidence page, evidence pack & public verify page.
  - Append-only hash chain in `app/ledger.py` with canonical JSON, 64-zero genesis, and personal data detect guard.
  - Verification API (`verify_chain`, `/api/ledger`, `/api/ledger/verify`) and dev tamper/repair endpoints (`KAVACH_DEV=1`).
  - Evidence pack export (`POST /api/evidence/export`) building ZIP with manifest, risks, receipts, simulations, summary & limitations.
  - Standalone public verify page (`/verify/<pack_id>`) and interactive Evidence page (`templates/evidence.html`).
  - 152 tests passing (`tests/test_ledger.py` + full test suite).
