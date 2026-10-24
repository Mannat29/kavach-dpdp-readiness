# Kavach: DPDP readiness for small businesses (hackathon, 48h, solo)
Users: owners of small businesses (clinic, shop, coaching centre) whose personal data lives in WhatsApp exports, Excel/CSV, Google Forms exports, billing exports and phones. India's DPDP Act 2023 + DPDP Rules 2025 (core duties apply ~May 2027). READINESS tool, not legal advice; all legal output is a DRAFT needing human review.

Stack: Python/Flask + SQLite (app/), HTML/CSS/vanilla JS (templates/, static/), Cytoscape.js via CDN for graphs. No build step. No LLM needed for core features; optional llm.py wrapper with rule-based fallback.
Windows dev machine, no make. Use the python commands above. Always open files with encoding='utf-8' (utf-8-sig when writing CSV that Excel will open).

Commands:
- seed: `python scripts/seed.py`
- eval: `python -m app.eval`
- test: `python -m pytest -q`
- run: `python -m flask --app app run --debug`

Product modules (UI nav labels): Scanner, Data Map, Rights Desk, Breach Simulator, Risk Analysis, Reports, Evidence.
Code modules: ingest, detect, inventory (entity resolution), rules (YAML; each rule has id, citation, trigger, remediation, severity, "verify": true), rights (informal request catcher incl. Hinglish/Kannada-in-Latin keywords + erasure engine with residual re-scan), breach (blast-radius simulator + two-stage clocks + drafts), ledger (hash-chained audit + public /verify), reports.

Principles: DB stores masked samples + salted hashes of identifiers, never raw values; uploads are kept in a local git-ignored workspace so cleaned copies can be produced; originals are never modified, erasure writes cleaned copies. Product name in UI, page titles and README is "Kavach".

Build order (future tasks, not now): 1 synthetic data + detection + eval, 2 inventory + rules + dashboard, 3 request catcher + erasure, 4 breach simulator, 5 ledger + reports, 6 hardening + README.

# Agent rules
- Read PROJECT.md and PROGRESS.md first in every session; do not re-read the whole repo.
- Do only what the task says. No refactors, no extra features, no extra docs.
- Terse tool/test output. If a test fails twice, stop and report.
- No browser/screenshot checks unless the task says so.
- End every task by updating PROGRESS.md (done/next/known issues, max 15 lines).
