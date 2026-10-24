# Progress

## Done
- Task 3a: Detector fixes (phone, aadhaar, health_term, free-text names) & honest held-out evaluation.
- All 48 tests passing (`python -m pytest -q`).

### Evaluation Summary Tables

| Dataset | TP | FP | FN | Precision | Recall | F1 |
|---------|---:|---:|---:|----------:|-------:|---:|
| **Demo** (`--set demo`) | 585 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| **Hard** (`--set hard`) | 202 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| **Heldout** (`--set heldout`) | 157 | 16 | 28 | 0.91 | 0.85 | 0.88 |

### Entity Resolution (Pairwise)

| Dataset | Records | Pairs | TP | FP | FN | Precision | Recall | F1 |
|---------|--------:|------:|---:|---:|---:|----------:|-------:|---:|
| **Demo** | 289 | 41,616 | 3478 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| **Hard** | 58 | 1,653 | 158 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |

## Next
- Task 3: Request catcher + erasure engine (UI & workflows).

## Known issues
- Non-comma CSV delimiters, slash-phones, emoji-prefixed names, and multi-word medical negations documented in README.md.
