# Model card — QS overall-score estimator

**Name** `linear_renorm` (`RenormalisedWeightedScore`)
**Version** trained from `last_crawl_snapshot.json`, QS 2026
**Owner** CrawlerNest modelling layer, `crawlernest/crawlernest-ml/`
**Reproduce**
```bash
PYTHONPATH=crawlernest/crawlernest-ml ./.venv/bin/python -m ranking_ml.training.train_overall_score
```

## What it does

Estimates QS's `Overall Score` from the nine published component indicators, for
the 903 universities ranked 601–1503 where QS publishes the components but
withholds the total.

It is a weighted average. Missing indicators are handled by renormalising the
weights over those actually present, not by imputation.

## What it is *not*

It is not a predictor of anything QS has not already determined. The overall
score is a deterministic weighted sum of the indicators, and this model recovers
that sum. Calling its R² of 0.9999 "accuracy" would misrepresent an
identification result as a forecasting one.

It does not estimate future ranks, and it must not be used to. The data covers a
single year.

## Data

| | |
|---|---|
| Source | QS World University Rankings 2026, crawl snapshot committed to the repo |
| Rows | 1,503 total — 600 labelled (ranks 1–600), 903 unlabelled (ranks 601–1503) |
| Features | 9 indicators, 0–100 scale |
| Target | `Overall Score`, 0–100 |
| Missing | 4 indicators, worst 6.65% (International Faculty Ratio) |
| Excluded | `rank` — QS derives it from the score, so it would leak the target |

## Results

Cross-validated on the 600 labelled rows, 5-fold, shuffled, seed 0:

| Model | RMSE | MAE | R² |
|---|---:|---:|---:|
| **linear_renorm** | **0.175 ± 0.123** | **0.047 ± 0.022** | **0.9999 ± 0.0001** |
| linear_raw | 0.278 ± 0.157 | 0.091 ± 0.020 | 0.9997 ± 0.0002 |
| ridge | 0.286 ± 0.152 | 0.103 ± 0.020 | 0.9997 ± 0.0002 |
| gradient_boosting | 2.394 ± 0.219 | 1.830 ± 0.169 | 0.9835 ± 0.0022 |
| random_forest | 3.843 ± 0.549 | 2.880 ± 0.263 | 0.9572 ± 0.0099 |
| *published-weight baseline* | *0.783* | *0.679* | *0.9983* |

The tree models do markedly worse. That is the expected result when the true
relationship is exactly linear: the extra capacity buys nothing and adds
variance.

### Weight recovery

Fitted coefficients, normalised to sum to 1, against QS's published weighting:

| Indicator | QS published | Recovered | Abs. error |
|---|---:|---:|---:|
| Academic Reputation | 0.30 | 0.2996 | 0.0004 |
| Citations per Faculty | 0.20 | 0.1992 | 0.0008 |
| Employer Reputation | 0.15 | 0.1504 | 0.0004 |
| Faculty Student Ratio | 0.10 | 0.0993 | 0.0007 |
| International Faculty Ratio | 0.05 | 0.0493 | 0.0007 |
| International Student Ratio | 0.05 | 0.0508 | 0.0008 |
| International Research Network | 0.05 | 0.0499 | 0.0001 |
| Employment Outcomes | 0.05 | 0.0506 | 0.0006 |
| Sustainability Score | 0.05 | 0.0508 | 0.0008 |

Mean absolute error 0.0006, worst case 0.0008. The published methodology is
recovered from the data alone. This is the result the module is built around,
because it is falsifiable: either the fit lands on the documented weights or it
does not.

Note that the ranking of the *correlations* does not match the ranking of the
weights — Citations per Faculty carries a 20% weight but correlates with the
target at only 0.476, below three indicators weighted at 5%. Reading feature
importance off correlations alone would have got this wrong.

### Behaviour outside the training distribution

Spearman between predicted score and QS's published rank on the 903 withheld
rows. Their scores are unknown, but their ordering is published, so this is a
real external check rather than a restatement of the training fit.

| Model | All 903 | Supported subset (657) |
|---|---:|---:|
| linear_renorm | +0.9754 | +0.9736 |
| published-weight baseline | +0.9754 | +0.9735 |
| linear_raw, median imputation | +0.9551 | — |

The third row is why this model exists. Holding the weights fixed and changing
only the missing-value strategy moves Spearman from 0.9551 to 0.9755 — the
fitted and published weights differ by at most 0.0008, so the gap is entirely
attributable to imputation. Median imputation borrows values from a training
distribution whose medians run three to five times higher than the withheld
tail, biasing exactly the 114 rows that need the help. Renormalisation removes
that failure mode.

## Support flag

Predictions carry a mechanical support flag: mean euclidean distance, in
standardised indicator space, to the 10 nearest training rows, thresholded at
the 95th percentile of the training set's own leave-one-out distances.

| Set | n | Supported | % |
|---|---:|---:|---:|
| Labelled (train) | 600 | 590 | 98.33 |
| Unlabelled (infer) | 903 | 657 | 72.76 |

**27% of the inference set falls outside the region the model was fitted on.**
The flag separates "the model has seen rows like this" from "it has not". It
does not estimate the error; a supported row can still be predicted badly.

## Known limitations

- **Single year.** No time dimension, so nothing here forecasts.
- **Covariate shift.** Every indicator shifts by 0.67–1.91 pooled standard
  deviations between the labelled and unlabelled populations. Cross-validated
  error on the labelled rows is not an error estimate for the withheld ones.
- **Rounding.** Indicator values are scraped as published, rounded to whole
  numbers. That quantisation is why the baseline's RMSE is 0.78 rather than 0.
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
