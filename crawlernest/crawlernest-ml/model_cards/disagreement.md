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
| Matched | **820** |
| Match rule | exact on normalised name (lowercase, letters only) |
| Features | 9 QS indicators |
| Missing | International Faculty Ratio 32, International Student Ratio 15, Sustainability 1 |

Matching is exact rather than fuzzy. It under-matches, so 820 is a lower bound
on the true overlap — but a wrong pairing would corrupt the label, and fuzzy
matching would need its own evaluation before it could be trusted here.

Percentiles are computed within each source's **full** population, so a
university's standing means "top x% of what QS ranked", not "top x% of the
overlap".

## Label

`disagreement = |QS percentile − THE percentile| > threshold`, where the
threshold is the 80th percentile of the observed gap — 0.2327, giving 164
positives (20.0%). Stating the positive rate as the design choice, rather than
picking a round cutoff and discovering the rate afterwards, is what makes the
sensitivity analysis below meaningful.

Gap distribution over the 820: median 0.105, 75th percentile 0.213, max 0.654.

## Results

Out-of-fold, 5-fold stratified, seed 0:

| Feature set | Model | ROC-AUC | PR-AUC | Brier |
|---|---|---:|---:|---:|
| **QS only** | **gradient boosting** | **0.8133** | **0.4696** | **0.1355** |
| QS only | logistic regression | 0.7307 | 0.3198 | 0.1455 |
| both sources *(ceiling)* | gradient boosting | 0.8902 | 0.7048 | 0.0979 |
| both sources *(ceiling)* | logistic regression | 0.8282 | 0.6131 | 0.1137 |
| chance | — | 0.5000 | 0.2000 | — |

![Diagnostics](../artifacts/eda/disagreement_diagnostics.png)

Reading these:

- **PR-AUC 0.470 against a 0.200 base rate** is the honest headline. ROC-AUC
  flatters imbalanced problems; the 2.3× lift in average precision is the part
  that means something operationally.
- **QS alone reaches 0.813 against a two-sided ceiling of 0.890.** Most of what
  is predictable about cross-source disagreement is already visible in QS's own
  numbers. That the ceiling is 0.890 rather than ~0.99 is itself informative:
  THE's published ranks are heavily tied at the tail, which caps how
  deterministic the label can be.
- **Gradient boosting beats logistic regression by a wide margin** (0.813 vs
  0.731). Worth contrasting with the overall-score model, where trees lost badly
  to a linear fit. There the relationship was exactly linear; here it is not.
- **Calibration is good in the low and middle range and over-confident at the
  top.** The highest-probability bin predicts 0.72 where the observed frequency
  is 0.52. Any threshold placed in that region should account for it.

### Threshold sensitivity

| Gap threshold | Positive rate | ROC-AUC | PR-AUC |
|---:|---:|---:|---:|
| 0.1869 (q=0.70) | 30.0% | 0.8534 | 0.6756 |
| 0.2327 (q=0.80) | 20.0% | 0.8133 | 0.4696 |
| 0.3076 (q=0.90) | 10.0% | 0.7485 | 0.2124 |

The result survives the choice of cutoff and degrades in the expected direction:
rarer, more extreme disagreements are harder to anticipate.

### Asymmetry

Among the 164 disagreeing pairs, **THE ranks the university higher in 133 cases
and QS in 31** — roughly 4 to 1. The two sources do not merely differ; they
differ in a consistent direction, which is a finding about the sources rather
than about the model.

## Known limitations

- **Single year.** Nothing here is temporal.
- **Exact name matching only.** 820 of a possible larger overlap. Institutions
  with divergent naming between sources are absent, and they are plausibly the
  ones most likely to be mismatched in other ways too — so the sample may be
  biased toward easier cases.
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
