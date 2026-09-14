# Model card — QS overall-score estimator

**Name** `linear_renorm` (`RenormalisedWeightedScore`)
**Version** trained from `last_crawl_snapshot.json`, QS World University Rankings 2026 (edition-verified, nid 4061771)
**Owner** CrawlerNest modelling layer, `crawlernest/crawlernest-ml/`
**Reproduce**
```bash
PYTHONPATH=crawlernest/crawlernest-ml ./.venv/bin/python -m ranking_ml.training.train_overall_score
```

## What it does

Estimates QS's `Overall Score` from the nine published component indicators, for
the 799 universities ranked 706–1504 where QS publishes the components but
withholds the total.

It is a weighted average. Missing indicators are handled by renormalising the
weights over those actually present, not by imputation.

## What it is *not*

It is not a predictor of anything QS has not already determined. The overall
score is a deterministic weighted sum of the indicators, and this model recovers
that sum. Calling its R² of 0.9996 "accuracy" would misrepresent an
identification result as a forecasting one.

It does not estimate future ranks, and it must not be used to. The model is
trained on a single edition.

## Data

| | |
|---|---|
| Source | QS World University Rankings 2026, crawl snapshot committed to the repo |
| Rows | 1,504 total — 705 labelled (ranks 1–705), 799 unlabelled (ranks 706–1504) |
| Features | 9 indicators, 0–100 scale |
| Target | `Overall Score`, 0–100 |
| Missing | 4 indicators, worst 5.78% (International Faculty Ratio) |
| Excluded | `rank` — QS derives it from the score, so it would leak the target |
| Not used | `International Student Diversity`, published from 2026; the nine indicators recover the score without it |

The snapshot committed before this one (700 labelled / 804 withheld) was the
QS **2027** table (nid 4153156), served from a cached ranking id and labelled
2026. Every number on this card was regenerated from the verified 2026 edition
and is not comparable to what the card said before.

## Results

Cross-validated on the 705 labelled rows, 5-fold, shuffled, seed 0:

| Model | RMSE | MAE | R² |
|---|---:|---:|---:|
| **linear_renorm** | **0.350 ± 0.091** | **0.074 ± 0.020** | **0.9996 ± 0.0002** |
| ridge | 0.480 ± 0.144 | 0.177 ± 0.025 | 0.9993 ± 0.0004 |
| linear_raw | 0.482 ± 0.141 | 0.167 ± 0.031 | 0.9993 ± 0.0004 |
| gradient_boosting | 2.167 ± 0.134 | 1.700 ± 0.118 | 0.9865 ± 0.0027 |
| random_forest | 3.487 ± 0.212 | 2.690 ± 0.141 | 0.9652 ± 0.0053 |
| *published-weight baseline* | *0.966* | *0.802* | *0.9974* |

The tree models do markedly worse. That is the expected result when the true
relationship is exactly linear: the extra capacity buys nothing and adds
variance.

### Weight recovery

Fitted coefficients, normalised to sum to 1, against QS's published weighting:

| Indicator | QS published | Recovered | Abs. error |
|---|---:|---:|---:|
| Academic Reputation | 0.30 | 0.3007 | 0.0007 |
| Citations per Faculty | 0.20 | 0.1984 | 0.0016 |
| Employer Reputation | 0.15 | 0.1507 | 0.0007 |
| Faculty Student Ratio | 0.10 | 0.0982 | 0.0018 |
| International Faculty Ratio | 0.05 | 0.0489 | 0.0011 |
| International Student Ratio | 0.05 | 0.0520 | 0.0020 |
| International Research Network | 0.05 | 0.0497 | 0.0003 |
| Employment Outcomes | 0.05 | 0.0502 | 0.0002 |
| Sustainability Score | 0.05 | 0.0512 | 0.0012 |

Mean absolute error 0.0011, worst case 0.0020. The published methodology is
recovered from the data alone. This is the result the module is built around,
because it is falsifiable: either the fit lands on the documented weights or it
does not.

Note that the ranking of the *correlations* does not match the ranking of the
weights — Citations per Faculty carries a 20% weight but correlates with the
target at only 0.494, below three indicators weighted at 5%. Reading feature
importance off correlations alone would have got this wrong.

### Behaviour outside the training distribution

Spearman between predicted score and QS's published rank on the 799 withheld
rows. Their scores are unknown, but their ordering is published, so this is a
real external check rather than a restatement of the training fit.

| Model | All 799 | Supported subset (440) |
|---|---:|---:|
| linear_renorm | +0.9614 | +0.9551 |
| published-weight baseline | +0.9614 | +0.9552 |
| linear_raw, median imputation | +0.9381 | — |

The third row is why this model exists. Changing only the missing-value strategy
moves Spearman from 0.9381 to 0.9614, and the published weights under the same
renormalisation land in the same place as the fitted ones — so the gap belongs
to imputation, not to the weights. Median imputation borrows values from a
training distribution whose medians run up to nearly six times higher than the
withheld tail's, biasing exactly the 96 withheld rows that carry a missing
indicator. Renormalisation removes that failure mode.

On this edition the supported subset agrees slightly *less* well than the full
withheld set. The flag still separates the served estimates — see the serving
check in the README, where supported rows agree at 0.9552 and unsupported ones at
0.8824 — but it is a coverage statement, not a guarantee of a better ordering.

## Support flag

Predictions carry a mechanical support flag: mean euclidean distance, in
standardised indicator space, to the 10 nearest training rows, thresholded at
the 95th percentile of the training set's own leave-one-out distances.

| Set | n | Supported | % |
|---|---:|---:|---:|
| Labelled (train) | 705 | 698 | 99.01 |
| Unlabelled (infer) | 799 | 440 | 55.07 |

**45% of the inference set falls outside the region the model was fitted on.**
The flag separates "the model has seen rows like this" from "it has not". It
does not estimate the error; a supported row can still be predicted badly.

## Known limitations

- **Single edition.** No time dimension, so nothing here forecasts.
- **Covariate shift.** Every indicator shifts by 0.55–1.78 pooled standard
  deviations between the labelled and unlabelled populations. Cross-validated
  error on the labelled rows is not an error estimate for the withheld ones.
- **Rounding.** Indicator values are scraped as published, to one decimal place.
  That quantisation is why the baseline's RMSE is 0.97 rather than 0.
- **Imputation still present in training.** The tree and ridge pipelines retain
  median imputation; only `linear_renorm` avoids it. They are kept for
  comparison, not for serving.
- **Region features unused by the recommended model.** `linear_renorm` reads the
  nine indicators only. Ridge, which does see the region block, does not beat
  it, so region appears to carry no signal beyond the indicators.

## Intended use

Populating `analytics.ml_predictions` with clearly-labelled estimates for
universities whose overall score QS withholds, with the support flag deciding
what is surfaced. Estimates never overwrite `composite_score` and never enter
`analytics.aggregated_rankings`. Any response carrying one must disclose in its
`caveats` array that the value is a model estimate, not a QS publication.
