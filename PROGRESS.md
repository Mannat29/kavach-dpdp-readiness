# Progress

## Done
- Task 5a: Breach Blast-Radius Simulator backend & tests (`app/breach.py`, `app/rules/breach_scenarios.yaml`, `tests/test_breach.py`).
  - Scenarios: owner_phone_stolen (299 recs, 15 people: 10 confirmed, 5 possible, range 10-15, high);
    billing_laptop_ransomware (35 recs, 20 people: 20 confirmed, range 20-20, critical);
    public_form_link_leaked (20 recs, 20 people: 20 confirmed, range 20-20, medium);
    staff_laptop_lost (10 recs, 10 people: 10 confirmed, range 10-10, high).
  - Explainable severity scoring, DPDP statutory clocks (72h deadline), PII-free draft generation, recipients, and HTML export.
  - 138 tests passing (`python -m pytest -q`).

## Next: Task 5b (Breach simulator UI).
