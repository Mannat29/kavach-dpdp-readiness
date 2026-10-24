# Kavach

DPDP readiness tool for small businesses.

## Quick start

```bash
pip install -r requirements.txt
python scripts/seed.py        # generate synthetic demo data
python -m app.eval             # run PII detection evaluation
python -m app.eval --set hard  # run evaluation on messy/hard dataset
python -m app.entity_eval      # run entity resolution evaluation
python -m pytest -q            # run tests
python -m flask --app app run --debug  # start dev server
```

## Known limitations

Evaluation on messy free-text and non-standard formatted data (`python -m app.eval --set hard`) highlights known detector limitations:
- **Aadhaar formatted with dots**: Numbers formatted like `1234.5678.9012` fail standard space/hyphen patterns (Recall 0.35).
- **Non-standard phone formatting**: Numbers containing dots or brackets (e.g., `9876.543.210`, `(987) 654-3210`) are missed by standard 10-digit mobile regex (Recall 0.58).
- **Names in unstructured text / remarks**: Names inside free-text chat ("hi this is ramesh...") or unlabelled/remarks columns require NLP / NER beyond column-header heuristics (Recall 0.78).
- **Health terms in free-text**: Clinical keywords matching in general conversational sentences may generate false positives (Precision 0.67).
