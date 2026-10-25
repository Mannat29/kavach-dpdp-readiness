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

