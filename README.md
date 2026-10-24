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

Evaluation on messy free-text and held-out data (`python -m app.eval --set heldout`) highlights known detector limitations:
- **Non-comma CSV delimiters**: Semicolon- or tab-delimited CSV files parse as single rows unless sniffed, causing column-offset detection errors.
- **Slash-separated phone numbers**: Numbers formatted with slashes (e.g., `(987) 654/3210`) are excluded by standard Indian mobile regex.
- **Emoji-prefixed names**: Names preceded by unicode avatars/emojis (e.g., `👤 Ramesh Kumar`) require emoji-stripping to match pure alphabetic name boundaries.
- **Split-cell contact numbers**: ISD code and local numbers separated across adjacent columns (`+91` | `98765-43210`) evaluate as isolated parts.
- **Compound medical negations**: Multi-term health negations ("no diabetes or hypertension") catch subsequent terms without deep grammatical parsing.
