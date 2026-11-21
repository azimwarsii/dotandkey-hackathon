# Aspect tagger validation

An agent annotated the meaning and polarity of 150 real review sentences before generating predictions for them. The labels are model-reviewed and await independent human review. The release lexicon and tagger were frozen before scoring.

The sampling script considers unique sentences of 5–42 whitespace-delimited words from the Part 1 database. It draws up to six per broad topic with a fixed hash ordering, then fills the remaining places from the unselected pool. This makes rare topics easier to inspect. Precision estimates describe this challenge set. A product or source may appear more than once.

Annotations judge the stated experience with the reviewed product. A skin condition, another product, or a step in a routine alone does not express an opinion on the reviewed product. A relevant but non-directional statement is neutral. Conflicting directional experiences are mixed. The annotator saw only sentence text. The tagger may use review stars for neutral cue matches.

An exact match requires both the aspect and its polarity to be correct. A missed aspect contributes to gold support and does not enter the precision denominator. At least five predictions and exact precision ≥0.70 are required for use in claims. The metrics layer also requires 30 directional mentions per reported group before publishing a confidence-qualified claim. The stored raw counts remain inspectable.

| Aspect | Gold | Predicted | Correct aspect + polarity | Precision | Passes validation gate |
|---|---:|---:|---:|---:|---|
| white_cast | 6 | 6 | 3 | 50.0% | No |
| greasy_sticky | 28 | 19 | 17 | 89.5% | Yes |
| breakouts | 7 | 2 | 1 | 50.0% | No |
| irritation | 10 | 4 | 3 | 75.0% | No |
| fragrance | 10 | 8 | 8 | 100.0% | Yes |
| hydration | 23 | 10 | 9 | 90.0% | Yes |
| glow_results | 20 | 11 | 10 | 90.9% | Yes |
| texture | 16 | 13 | 9 | 69.2% | No |
| packaging | 6 | 2 | 2 | 100.0% | No |
| value_price | 8 | 7 | 6 | 85.7% | Yes |
| authenticity | 2 | 0 | 0 | — | No |
| spf_protection | 8 | 2 | 2 | 100.0% | No |
| longevity | 9 | 4 | 4 | 100.0% | No |
| under_makeup | 6 | 1 | 1 | 100.0% | No |
| absorption | 11 | 9 | 9 | 100.0% | Yes |
| cleansing | 7 | 0 | 0 | — | No |
| barrier_repair | 6 | 4 | 3 | 75.0% | No |
| pigmentation | 8 | 7 | 4 | 57.1% | No |

## Reproduce the evaluation

Run these commands from the repository root. The first verifies frozen labels, rules, and scores. The second prints the unlabeled sample drawn from the current database. New crawls can change that sample. Each frozen row includes a source URL, product reference, sentence, and normalized review-body hash for auditing.

```sh
.venv/bin/python -m pytest tests/test_aspects_metrics.py -q
.venv/bin/python -m validation.evaluate_aspects
.venv/bin/python -m validation.evaluate_aspects --sample data/market-intel.sqlite3
```

For an independent human pass, project only the row ID and sentence, assign aspects and polarities before opening the existing labels, then compare disagreements. Use a fresh holdout if rules are subsequently tuned.
