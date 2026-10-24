# Progress

## Done
- Task 1: Synthetic data, detection, eval, tests.
- Task 2: Inventory, entity resolution, 12 rules, JSON routes, seed_hard.
- Eval demo (`python -m app.eval`): 585 TP, 0 FP, 0 FN, Prec 1.00, Recall 1.00, F1 1.00.
- Eval hard (`python -m app.eval --set hard`): 158 TP, 4 FP, 44 FN, Prec 0.98, Recall 0.78, F1 0.87.
  Aadhaar recall 0.35, phone recall 0.58, name recall 0.78.
- Entity resolution (`python -m app.entity_eval`):
  289 records across 12 shared people, 41,616 pairs: TP 3478, FP 0, FN 0, Prec 1.00, Recall 1.00, F1 1.00.
- Rules & Questionnaire: 12 DPDP rules (YAML), 6 questionnaire keys, explainable readiness score.
- Tests: 43 passing tests (`python -m pytest -q`).

## Next
- Task 3: Request catcher + erasure engine (UI & workflows).

## Known issues
- Detectors underperform on non-standard punctuation and free-text chat (documented in README.md).
