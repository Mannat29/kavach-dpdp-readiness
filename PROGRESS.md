# Progress

## Done
- Task 7: Hardening, input safety, offline vendoring, and documentation.
  - Dependencies verified; salt moved to env `KAVACH_SALT` with fallback to `data/.salt` (git-ignored).
  - Upload safety guards (10 MB size, 50k rows, .xlsx/.csv/.txt only, path traversal & malformed error handling).
  - Offline Cytoscape vendored to `static/vendor/cytoscape.min.js`; zero remote calls / LLM runtime dependencies.
  - `scripts/demo_reset.py` for one-command reset; comprehensive `README.md` and `docs/DEMO.md` script.
  - 166 tests passing (`python -m pytest -q`).
