# Progress

## Done
- Exact commands: `python scripts/seed.py`, `python -m app.eval`, `python -m pytest -q`, `python -m flask --app app run --debug`. Makefile removed.
- Task 1: Synthetic data, ingest, detectors, eval, tests completed.
- Eval table (`python -m app.eval`):
| Category | TP | FP | FN | Prec | Recall | F1 |
| aadhaar/phone/email/pan/gstin | 156 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| overall (11 categories) | 585 | 0 | 0 | 1.00 | 1.00 | 1.00 |

## Next
- Task 2: inventory + rules + dashboard.

## Known issues
- None.
