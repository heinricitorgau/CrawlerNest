# Model card — cross-source disagreement classifier

**Name** `disagreement` (gradient boosting over QS indicators)
**Version** trained from the QS 2026 (edition-verified, nid 4061771) and THE 2026 crawl snapshots
**Owner** CrawlerNest modelling layer, `crawlernest/crawlernest-ml/`
**Reproduce**
```bash
PYTHONPATH=crawlernest/crawlernest-ml ./.venv/bin/python -m ranking_ml.training.train_disagreement
```

## What it does

Given only what QS published about a university, predicts whether THE will place
it substantially differently.

The use is operational: flag contested institutions at QS ingest time, before
THE data arrives for that university — or at all, since THE covers only part of
what QS ranks.

## The question it deliberately does not ask

The label is derived from both sources' ranks, and each source's rank is close to
a deterministic function of its own published component scores. Phase 2
established that QS's overall score is a weighted sum of its nine indicators to
within 0.0020. A classifier handed *both* sources' scores is therefore not
predicting; it is recomputing a quantity it was given the inputs to, and its
score would be meaningless.

So the modelled task is one-sided: **QS features only**. The two-sided model is
still fitted and reported as a ceiling, so the distance between them is visible.

## Data

| | |
|---|---|
| QS population | 1,504 |
| THE population | 2,191 |
| Matched | **1,109** |
| Match rule | the warehouse's reviewed pairing, falling back to exact normalised name |
| Features | 9 QS indicators |
| Missing | International Faculty Ratio 44, International Student Ratio 19, Sustainability 2 |

Matching is still never fuzzy. A wrong pairing corrupts the label, and on this
data a similarity score pairs Tokyo Institute of Technology with MIT and
University of British Columbia with University of Northern British Columbia.

The pairing is read from `crawlernest-kb/databases/qs_the_pairing_2026.json`,
exported from the warehouse after its entity resolver was seeded with reviewed
aliases and its ambiguous cases were resolved by hand. On the 2026 edition it
places all 1,109 matched universities; exact match on a normalised name alone
would reach 842. `test_pairing_matches_warehouse` confirms the file agrees with
the warehouse's THE 2026 records, and `export_qs_the_pairing.py` reports no
difference.

The two methods were compared on this edition too: on the 830 universities both
place, they choose the same THE entity every time. The pairing adds rows rather
than correcting them, and removes the situation where two independent joins
answered "which institution is this" and nothing checked that they agreed.

Percentiles are computed within each source's **full** population, so a
university's standing means "top x% of what QS ranked", not "top x% of the
overlap".

## Label

`disagreement = |QS percentile − THE percentile| > threshold`, where the
threshold is the 80th percentile of the observed gap — 0.2568, giving 222
positives (20.0%). Stating the positive rate as the design choice, rather than
picking a round cutoff and discovering the rate afterwards, is what makes the
sensitivity analysis below meaningful.

Gap distribution over the 1,109: median 0.112, 75th percentile 0.223, max 0.738.

## Results

Out-of-fold, 5-fold stratified, seed 0:

| Feature set | Model | ROC-AUC | PR-AUC | Brier |
|---|---|---:|---:|---:|
| **QS only** | **gradient boosting** | **0.8384** | **0.5201** | **0.1256** |
| QS only | logistic regression | 0.7460 | 0.3547 | 0.1424 |
| both sources *(ceiling)* | gradient boosting | 0.9258 | 0.7620 | 0.0869 |
| both sources *(ceiling)* | logistic regression | 0.8150 | 0.5845 | 0.1195 |
| chance | — | 0.5000 | 0.2002 | — |

![Diagnostics](../artifacts/eda/disagreement_diagnostics.png)

Reading these:

- **PR-AUC 0.520 against a 0.200 base rate** is the honest headline. ROC-AUC
  flatters imbalanced problems; the 2.6× lift in average precision is the part
  that means something operationally.
- **QS alone reaches 0.838 against a two-sided ceiling of 0.926.** Most of what
  is predictable about cross-source disagreement is already visible in QS's own
  numbers. That the ceiling is 0.926 rather than ~0.99 is itself informative:
  THE's published ranks are heavily tied at the tail, which caps how
  deterministic the label can be.
- **Gradient boosting beats logistic regression by a wide margin** (0.838 vs
  0.746). Worth contrasting with the overall-score model, where trees lost badly
  to a linear fit. There the relationship was exactly linear; here it is not.
- **Calibration is good in the low and middle range and over-confident at the
  top**: the highest-probability bin predicts 0.72 where the observed frequency
  is 0.59. Any threshold placed in that region should account for it.

### Threshold sensitivity

| Gap threshold | Positive rate | ROC-AUC | PR-AUC |
|---:|---:|---:|---:|
| 0.1928 (q=0.70) | 30.0% | 0.8363 | 0.6482 |
| 0.2568 (q=0.80) | 20.0% | 0.8384 | 0.5201 |
| 0.3321 (q=0.90) | 10.0% | 0.8409 | 0.3608 |

The result survives the choice of cutoff. ROC-AUC is flat across the three
(0.836–0.841); PR-AUC falls with the base rate, as it must, while its lift over
chance grows from 2.2× to 3.6×. On the 2026 edition rarer, more extreme
disagreements are not harder to rank — an earlier snapshot suggested they were,
and that finding did not survive the change of edition.

### Against the previous committed numbers

The metrics file committed before this one (ROC-AUC 0.8662, PR-AUC 0.5922 on
1,104 matched) was trained on the QS **2027** table, which had been saved as the
2026 snapshot. The metrics gate refused the comparison on the invariant change
(`matched` 1,104 → 1,109, `positives` 221 → 222), which is what it is for. The
lower numbers above describe a different edition, not a regression in the code:
the model, features and pairing rule are unchanged.

### Asymmetry

Among the 222 disagreeing pairs, **THE ranks the university higher in 178 cases
and QS in 44** — roughly 4 to 1. The two sources do not merely differ; they
differ in a consistent direction, which is a finding about the sources rather
than about the model.

## Known limitations

- **Single edition.** Nothing here is temporal.
- **Still an incomplete overlap.** 1,109 of a possible 1,504. The 395 absent
  universities are the ones THE does not rank, or whose pairing has not been
  reviewed, and the second group is plausibly also more likely to be treated
  differently by the two sources — so the sample may be biased toward easier
  cases.
- **Label is a discretised continuum.** Disagreement is a matter of degree;
  thresholding it loses information. The sensitivity table is the mitigation,
  not a fix.
- **THE rank ties.** THE caps its tail at rank 1501 with many ties, which makes
  percentiles in that region coarse.
- **Over-confidence at the top of the probability range**, as above.
- **Not causal.** The model says which QS profiles tend to accompany
  disagreement, not why the sources disagree.

## Intended use

Flagging candidates for review in the cross-source disagreement analytics the
platform already surfaces. Output is a probability, not a verdict, and any
surfaced use must carry a `caveats` entry saying so. It must not be used to
adjust, reweight, or override either source's published rank.
