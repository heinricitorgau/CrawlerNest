# Model card — cross-source disagreement classifier

**Name** `disagreement` (gradient boosting over QS indicators)
**Version** trained from the QS and THE 2026 crawl snapshots
**Owner** CrawlerNest modelling layer, `crawlernest/crawlernest-ml/`
**Reproduce**
```bash
PYTHONPATH=crawlernest/crawlernest-ml ./.venv/bin/python -m ranking_ml.training.train_disagreement
```

## What it does

Given only what QS published about a university, predicts whether THE will place
it substantially differently.

The use is operational: flag contested institutions at QS ingest time, before
THE data arrives for that university — or at all, given THE is currently in a
degraded state in this deployment.

## The question it deliberately does not ask

The label is derived from both sources' ranks, and each source's rank is close to
a deterministic function of its own published component scores. Phase 2
established that QS's overall score is a weighted sum of its nine indicators to
within 0.0008. A classifier handed *both* sources' scores is therefore not
predicting; it is recomputing a quantity it was given the inputs to, and its
score would be meaningless.

So the modelled task is one-sided: **QS features only**. The two-sided model is
still fitted and reported as a ceiling, so the distance between them is visible.

## Data

| | |
|---|---|
| QS population | 1,503 |
| THE population | 2,191 |
| Matched | **1,082** |
| Match rule | the warehouse's reviewed pairing, falling back to exact normalised name |
| Features | 9 QS indicators |
| Missing | International Faculty Ratio 41, International Student Ratio 21, Sustainability 1 |

Matching is still never fuzzy. A wrong pairing corrupts the label, and on this
data a similarity score pairs Tokyo Institute of Technology with MIT and
University of British Columbia with University of Northern British Columbia.

What changed is where the pairing comes from. It used to be derived here, by
exact match on a normalised name, which recovered 820. It is now read from
`crawlernest-kb/databases/qs_the_pairing_2026.json`, exported from the warehouse
after its entity resolver was seeded with 112 reviewed aliases and its ambiguous
cases were resolved by hand — 1,080 pairs, plus 2 the name rule still catches
that the warehouse dropped.

The two methods were compared before switching: on the 818 universities both
place, they choose the same THE entity every time. This adds rows rather than
correcting them, and removes the situation where two independent joins answered
"which institution is this" and nothing checked that they agreed.

Percentiles are computed within each source's **full** population, so a
university's standing means "top x% of what QS ranked", not "top x% of the
overlap".

## Label

`disagreement = |QS percentile − THE percentile| > threshold`, where the
threshold is the 80th percentile of the observed gap — 0.2349, giving 217
positives (20.1%). Stating the positive rate as the design choice, rather than
picking a round cutoff and discovering the rate afterwards, is what makes the
sensitivity analysis below meaningful.

Gap distribution over the 1,082: median 0.108, 75th percentile 0.215, max 0.738.

## Results

Out-of-fold, 5-fold stratified, seed 0:

| Feature set | Model | ROC-AUC | PR-AUC | Brier |
|---|---|---:|---:|---:|
| **QS only** | **gradient boosting** | **0.8262** | **0.5196** | **0.1265** |
| QS only | logistic regression | 0.7307 | 0.3198 | 0.1455 |
| both sources *(ceiling)* | gradient boosting | 0.9048 | 0.7693 | 0.0870 |
| both sources *(ceiling)* | logistic regression | 0.8281 | 0.5702 | 0.1180 |
| chance | — | 0.5000 | 0.2000 | — |

![Diagnostics](../artifacts/eda/disagreement_diagnostics.png)

Reading these:

- **PR-AUC 0.520 against a 0.201 base rate** is the honest headline. ROC-AUC
  flatters imbalanced problems; the 2.6× lift in average precision is the part
  that means something operationally.
- **QS alone reaches 0.826 against a two-sided ceiling of 0.905.** Most of what
  is predictable about cross-source disagreement is already visible in QS's own
  numbers. That the ceiling is 0.905 rather than ~0.99 is itself informative:
  THE's published ranks are heavily tied at the tail, which caps how
  deterministic the label can be.
- **Gradient boosting beats logistic regression by a wide margin** (0.826 vs
  0.731). Worth contrasting with the overall-score model, where trees lost badly
  to a linear fit. There the relationship was exactly linear; here it is not.
- **Calibration is good in the low and middle range and still over-confident at
  the top**, though less so than before: the highest-probability bin predicts
  0.71 where the observed frequency is 0.63, against 0.72 vs 0.52 on the
  820-row join. Any threshold placed in that region should account for it.

### Threshold sensitivity

| Gap threshold | Positive rate | ROC-AUC | PR-AUC |
|---:|---:|---:|---:|
| 0.1854 (q=0.70) | 30.0% | 0.8379 | 0.6588 |
| 0.2349 (q=0.80) | 20.1% | 0.8262 | 0.5196 |
| 0.3217 (q=0.90) | 10.1% | 0.7900 | 0.2584 |

The result survives the choice of cutoff and degrades in the expected direction:
rarer, more extreme disagreements are harder to anticipate.

**These numbers are not comparable to the 820-row version and the improvement is
not uniform.** The label is the 80th percentile of the gap *within the joined
set*, so enlarging the join moved the threshold and relabelled rows: it is a
different task, not the same task done better. Compared at matched positive
rates, the larger set is better at 20% (0.8133 → 0.8262) and 10% (0.7485 →
0.7900) and **worse at 30% (0.8534 → 0.8379)**. The metrics gate refused the
comparison outright on the invariant change, which is what it is for.

### Asymmetry

Among the 217 disagreeing pairs, **THE ranks the university higher in 171 cases
and QS in 46** — roughly 4 to 1. The two sources do not merely differ; they
differ in a consistent direction, which is a finding about the sources rather
than about the model.

## Known limitations

- **Single year.** Nothing here is temporal.
- **Still an incomplete overlap.** 1,082 of a possible 1,503. The 421 absent
  universities are the ones whose names diverge most between sources, or that
  THE does not rank at all, and the first group is plausibly also more likely to
  be treated differently by the two sources — so the sample may still be biased
  toward easier cases, less so than at 820.
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
