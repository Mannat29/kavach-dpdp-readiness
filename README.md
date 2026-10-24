# Kavach

DPDP readiness tool for small businesses.

## Quick start

```bash
pip install -r requirements.txt
python scripts/seed.py        # generate synthetic demo data
python -m app.eval             # run PII detection evaluation
python -m pytest -q            # run tests
python -m flask --app app run --debug  # start dev server
```
