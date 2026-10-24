# Progress

## Done
- Task 4b: Rights Desk UI (`templates/rights_desk.html`, `static/js/rights_desk.js`, `static/css/rights_desk.css`).
  - Intake panel: WhatsApp paste textarea, load demo text, detect requests, empty state demo trigger.
  - Request cards: intent & status badges, confidence, masked excerpt, live countdown, data locations table, ignored messages accordion.
  - Erase workflow stepper: 1 Verify identity -> 2 Review plan (overrides, verify chips) -> 3 Approve & run (counts dialog) -> 4 Result (residuals, receipt, zip).
  - Non-erase cards: suggested next step + close handler; timezone-aware UTC datetime cleanups in rights/ledger; Rights Desk in ENABLED_PAGES.
  - 122 tests passing (`python -m pytest -q`).

## Next: Breach simulator.
