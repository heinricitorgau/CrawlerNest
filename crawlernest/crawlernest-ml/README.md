# CrawlerNest ML

Modelling layer over the QS indicator data. It sits **beside** the deterministic
pipeline, never inside it: nothing here writes to `analytics.aggregated_rankings`
or changes a published rank, and every model output is stored and labelled as an
estimate. This is the same honesty contract the rest of the repo runs on — see
the "No black-box scores" rule in the root [`CLAUDE.md`](../../CLAUDE.md).

Status: feature layer, EDA, two evaluated models, and a serving path that writes
estimates into `analytics.ml_predictions` for the API to read. Full records in
[`model_cards/overall_score.md`](model_cards/overall_score.md) and
[`model_cards/disagreement.md`](model_cards/disagreement.md).

## The data

Built from `crawlernest/crawlernest-kb/databases/last_crawl_snapshot.json`, which
is committed — so everything here runs with no database and no network.

| | |
|---|---|
| Universities | 1,503 (QS 2026) |
| Indicators | 9, all present on every record |
| Countries | 107, grouped into 12 regions |
| Feature matrix | `(1503, 9)` indicators, `(1503, 21)` with region one-hot |

The target is QS's `Overall Score`, and its availability is the reason this is a
supervised problem at all:

```
rank    1– 600  →  Overall Score published   →  600 labelled rows  (training set)
rank  601–1503  →  Overall Score = "n/a"     →  903 unlabelled rows (inference set)
```

QS publishes the nine component indicators for all 1,503 universities but the
total only for the top 600.

`rank` is never a feature — QS derives the rank *from* the overall score, so
using it would leak the target. It is carried alongside the matrix for
evaluation only.

## Running it

```bash
./.venv/bin/pip install -r requirements-ml.txt
PYTHONPATH=crawlernest/crawlernest-ml ./.venv/bin/python -m ranking_ml.features.build_features
PYTHONPATH=crawlernest/crawlernest-ml ./.venv/bin/python -m ranking_ml.eda.run_eda
PYTHONPATH=crawlernest/crawlernest-ml ./.venv/bin/python -m ranking_ml.training.train_overall_score
PYTHONPATH=crawlernest/crawlernest-ml ./.venv/bin/python -m ranking_ml.training.train_disagreement
```

## Phase 1 findings

### 1. Missingness is small but real

Every indicator is *present* on every record, but some carry `"n/a"`:

| Indicator | Missing | % |
|---|---:|---:|
| International Faculty Ratio | 100 | 6.65 |
| International Student Ratio | 58 | 3.86 |
| Sustainability Score | 19 | 1.26 |
| International Research Network | 1 | 0.07 |
| the other five | 0 | 0.00 |

Median imputation is the current strategy. It is a decision, not a default —
`missingness_report()` exists so it stays visible.

### 2. The indicators line up with QS's published weighting

Correlation with `Overall Score` on the 600 labelled rows:

| Indicator | Pearson r | QS published weight |
|---|---:|---:|
| Academic Reputation | 0.901 | 30% |
| Employer Reputation | 0.777 | 15% |
| Employment Outcomes | 0.630 | 5% |
| Sustainability Score | 0.576 | 5% |
| International Research Network | 0.478 | 5% |
| Citations per Faculty | 0.476 | 20% |
| International Student Ratio | 0.405 | 5% |
| International Faculty Ratio | 0.351 | 5% |
| Faculty Student Ratio | 0.333 | 10% |

The ordering broadly tracks the published weights, with one worth noting:
**Citations per Faculty carries a 20% weight but correlates at only 0.476**,
below three indicators weighted at 5%. Whether a fitted model recovers the
published 20% is a concrete, checkable question for Phase 2 rather than a
hand-wave about feature importance.

![Indicator correlation heatmap](artifacts/eda/correlation_heatmap.png)

### 3. Training set and inference set are not the same population

This is the finding that constrains Phase 2. Standardised difference in means
(Cohen's *d*) between the 600 labelled and 903 unlabelled rows:

| Indicator | Labelled mean | Unlabelled mean | Cohen's *d* |
|---|---:|---:|---:|
| Sustainability Score | 49.98 | 6.88 | 1.91 |
| Academic Reputation | 37.72 | 8.70 | 1.68 |
| Citations per Faculty | 44.56 | 9.51 | 1.60 |
| International Research Network | 72.57 | 35.22 | 1.58 |
| Employer Reputation | 37.00 | 8.35 | 1.49 |
| International Faculty Ratio | 50.46 | 15.61 | 1.21 |
| Employment Outcomes | 40.02 | 13.06 | 1.13 |
| International Student Ratio | 41.86 | 13.74 | 1.03 |
| Faculty Student Ratio | 38.71 | 21.10 | 0.67 |

Every indicator shifts by more than 0.6 pooled standard deviations and most by
more than 1.0. Predicting the 903 from the 600 is **extrapolation, not
interpolation**.

![PCA scatter](artifacts/eda/pca_scatter.png)

PC1 alone explains 50.7% of the variance and orders the labelled rows almost
monotonically by rank. The unlabelled rows pile up at the low end of PC1, in a
region where the training data is sparse — though the two populations do overlap
around ranks 500–600, so predictions just past the cutoff rest on real support
and predictions deep in the tail do not.

**Consequences for Phase 2**, all of them arising from this figure:

1. A cross-validated RMSE on the 600 labelled rows measures how well the model
   recovers QS's scoring function. It does **not** estimate the error on the 903.
   Reporting it as though it did would be the exact kind of flattering,
   unfalsifiable number this repo's honesty contract exists to prevent.
2. Every prediction needs a **support flag** — a distance from the training
   distribution — and only predictions inside the supported region should be
   surfaced. This maps onto the existing mechanically-derived confidence rule
   rather than inventing a new one.
3. Spearman ρ between predicted score and QS's published rank on the 903 is not
   an optional extra. It is the only external validation available in the
   shifted region, because the ordering is known even though the scores are not.

![Target distribution](artifacts/eda/target_distribution.png)

## Phase 2 results

Full detail in the [model card](model_cards/overall_score.md). Three things came
out of it.

### The published weighting is recovered from the data

A linear fit on the raw indicators reproduces QS's documented weighting to a
mean absolute error of **0.0006** (worst case 0.0008): Academic Reputation
0.2996 against a published 0.30, Citations per Faculty 0.1992 against 0.20, and
so on for all nine.

This reframes what the model is. The overall score is a deterministic weighted
sum, so this is system identification, not forecasting — and an R² of 0.9999
should be read as "the formula was recovered", never as predictive accuracy.
Tree models do *worse* here (random forest RMSE 3.84 against 0.18), which is the
expected result when the true relationship is exactly linear.

It also shows why correlation is not importance: Citations per Faculty carries a
20% weight but correlates with the target at only 0.476, below three indicators
weighted at 5%.

### Imputation, not model choice, decided performance under shift

The first run used median imputation and scored Spearman 0.9551 against the
published ranks of the 903. Holding the weights fixed and only changing how
missing indicators are handled:

| Missing-value strategy | Spearman on the 903 |
|---|---:|
| median imputation | 0.9551 |
| renormalise over available weights | **0.9755** |

The fitted and published weights differ by at most 0.0008, so none of that gap
is about the model. Median imputation borrows values from a training
distribution whose medians run three to five times higher than the withheld
tail, biasing exactly the 114 rows that carry a missing indicator. The
recommended model, `linear_renorm`, renormalises instead — and then wins on both
cross-validation (RMSE 0.175 against 0.278) and extrapolation.

The general lesson is worth stating plainly: under covariate shift the default
preprocessing step did more damage than any modelling decision, and only the
out-of-distribution check surfaced it. Cross-validation alone would have shipped
the worse pipeline.

### A quarter of the inference set is unsupported

| Set | n | Supported | % |
|---|---:|---:|---:|
| Labelled (train) | 600 | 590 | 98.33 |
| Unlabelled (infer) | 903 | 657 | 72.76 |

Support is the mean distance to the 10 nearest training rows in standardised
indicator space, thresholded at the 95th percentile of the training set's own
leave-one-out distances — mechanical and inspectable, like the rest of the
confidence handling in this repo. **27% of the rows we would predict sit outside
the region the model was fitted on**, and the flag is what decides whether an
estimate is publishable.

## Phase 3 results — cross-source disagreement

Full detail in the [model card](model_cards/disagreement.md). QS and THE both
rank 820 of the same universities (exact name match), and they frequently
disagree about them.

The trap here was the same shape as Phase 2's, one level up. Each source's rank
is close to a deterministic function of its own component scores, so a
classifier handed *both* sources' scores would be recomputing the label rather
than predicting it, and would score well while meaning nothing. The task
modelled is therefore one-sided: **given only QS's view of a university, will
THE disagree?** That is a real prediction, and it has a use — flagging contested
institutions at QS ingest time, before THE data arrives.

| Feature set | Model | ROC-AUC | PR-AUC |
|---|---|---:|---:|
| **QS only** | **gradient boosting** | **0.8133** | **0.4696** |
| QS only | logistic regression | 0.7307 | 0.3198 |
| both sources *(ceiling)* | gradient boosting | 0.8902 | 0.7048 |
| chance | — | 0.5000 | 0.2000 |

![Disagreement diagnostics](artifacts/eda/disagreement_diagnostics.png)

PR-AUC 0.470 against a 0.200 base rate is the honest headline — a 2.3× lift,
where ROC-AUC would flatter an imbalanced problem. QS alone reaches 0.813 of a
two-sided ceiling of 0.890, so most of what is predictable is already in QS's own
numbers. Gradient boosting beats the linear model here by a wide margin, the
opposite of the overall-score result, because this relationship genuinely is not
linear. Calibration holds in the low and middle range and goes over-confident in
the top bin (0.72 predicted against 0.52 observed).

Among disagreeing pairs, **THE ranks the university higher 133 times to QS's
31** — the sources do not merely differ, they differ in a consistent direction.

## Phase 3 results — LLM evaluation

The faithfulness checker was already mechanical and already ran in CI, but it
reported only pass/fail over 6 golden cases, of which just 2 were faithful. A
pass count cannot distinguish a checker that catches everything from one that
also fires on clean text, and with 2 clean cases the false-positive rate had no
denominator worth reading.

Two changes:

- **The golden set is now 34 cases, 17 of them faithful.** The new entries cover
  fabricated scores, years and counts, dropped, paraphrased and softened
  caveats, invented institutions in both name forms, three-way combinations, and
  edge cases that *should* pass — whitespace-normalised caveats, rank bands
  quoted as published, trailing-zero variants, ordinals written as words, and
  institutions named from nested profile evidence.
- **The runner scores the checker as a detector**, reporting per-kind precision,
  recall and F1 plus the false-positive rate on clean text.

| Violation kind | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| unsupported_number | 9 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| missing_caveat | 7 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| unsupported_university | 4 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| micro-average | 20 | 0 | 0 | 1.000 | 1.000 | 1.000 |

False positives on clean text: **0 over 17 faithful cases**.

The checker turned out to be more robust than its own docstring implied — it
handles whitespace variation and numeric formatting correctly. Two cases are
tagged `known_limitation` because the flagged behaviour is deliberate rather than
a bug: a score rescaled from 0.82 to 82%, and a rank difference computed rather
than quoted. Both are unverifiable transformations, so flagging them is the
intended contract, and the dataset now records that decision instead of leaving
it in a comment.

### The judge was rejected, then the dataset was fixed and the answer changed

The rejection below was correct for the dataset it was made on, and the dataset
was the problem. Every case had been written from the rule checker's own
taxonomy, so the judge was being examined on the ground where rules are
strongest. Eleven cases were then added the other way round: unfaithfulness
first, then verified that no rule reaches it — a caveat reproduced verbatim and
undercut by the next sentence, a causal claim the evidence does not contain, a
model estimate attributed to the ranking source, a subject rank presented as a
global one.

Those cases carry a `ground_truth` field separate from `expect`. `expect` says
what the checker should report; `ground_truth` says whether the explanation is
actually faithful. For the original cases they agree. For these they do not, and
that gap is the only thing that can measure what a judge adds.

The set has since grown to **55 cases, 19 of them beyond the rules**, covering
provenance and scope as well as overreach: missing data reported as absence of
the thing, a comparison stated in the wrong direction, a limitation of our
coverage blamed on the university, a published rank band reported as a precise
position, a figure attributed to the wrong source, a coverage ratio of 0.33
described as a broad base.

Measured against ground truth:

| | Recall | Precision | Accuracy | Missed | False alarms |
|---|---:|---:|---:|---:|---:|
| Rules only | 0.472 | **1.000** | 0.655 | 19 | 0 |
| Judge only | 0.667 | 0.960 | 0.764 | 12 | 1 |
| **Either flags it** | **0.833** | 0.968 | **0.873** | **6** | 1 |

The judge catches **13 of the 19 failures the rules cannot express**, and misses
six the rules catch perfectly. They fail in different directions, which is what
makes the union worth having.

Cohen's κ is **0.247** — and that is the point rather than a warning. On the
original 34-case set it was 0.588 and the judge mostly restated what the rules
found. Every case added since has pushed it down, because each one is somewhere
the two must disagree. κ measures agreement, and agreement is not what a second
signal is for.

### What the judge misses has a shape

The six beyond-rules cases it does not catch — `faith-105`, `108`, `113`, `115`,
`116`, `118` — are not a random sample. Every one is a claim about **provenance,
absence, or completeness** rather than about the assertions in the sentence: an
estimate credited to the ranking source, a superlative on a dimension the
evidence does not rank, missing data reported as the source declining to rank,
our coverage gap blamed on the university, an ingestion point described as
current, one page of results called the complete set.

The judge reads what the text says and asks whether the evidence supports it. It
does not reliably ask *where the evidence came from, how old it is, or what is
absent from it* — which is precisely the class this repository's honesty contract
is built around. That is a concrete specification for a third signal, and it
comes from which cases were missed rather than from a guess about model
weaknesses.

So the recommendation reverses: **adopt the judge as a second signal, never as a
replacement.** The rules keep perfect precision and must stay authoritative for
the violations they define; the judge covers a class they provably cannot reach.

### The third signal: provenance, absence, completeness

That specification was then built, as structured checks rather than a second
prompt — `provenance.py`. Each one compares a field the pipeline already writes
against a phrase pattern: `isEstimated` against a figure credited to a ranking
body, a null in `sourceRanks` against a claim that the source declines to rank,
a coverage caveat against language blaming the university, an ingestion
timestamp against an assertion of currency, a ranking claim against the
dimensions the evidence actually carries, and any claim about what lies outside
the supplied rows. A mechanical signal fits what these failures are — each is a
mismatch with a known field, not a judgement call — and it keeps the precision
that lets a signal act rather than merely warn.

| | Recall | False alarms |
|---|---:|---:|
| Rules only | 0.472 | 0 |
| Provenance only | 0.167 | 0 |
| Rules + provenance | 0.639 | 0 |
| Rules + judge | 0.833 | 1 |
| **All three** | **1.000** | 1 |

**Read that 1.000 as saturation of the measuring instrument, not as a claim
about unfaithfulness in general.** Nineteen of these cases were written to
characterise gaps in the first two signals, and the sixth check was then built
against six of them. A dataset cannot both define a target and independently
confirm it was hit. What the number does support is narrower and still worth
having: no failure mode identified so far escapes all three signals, and the two
mechanical ones reached 0.639 without a single false alarm.

### The ordering check, and a reversed judgement

The sixth check nearly did not exist. A superlative on a dimension the evidence
does not rank looked undecidable — it needs to know which dimensions *are*
ranked, and a pattern catching "the better choice for international students"
also catches ordinary comparative prose.

That was wrong, and the reason is in `schema.py`: **the dimension vocabulary is
closed.** QS publishes nine indicators and no more, so "for international
students" resolves to a named column, and whether that column is in the evidence
is a fact about the item keys. Add `internationalStudentRatio` to the rows and
the check goes quiet. An ordering claim over a criterion outside that vocabulary
is left alone — guessing there is where false positives would come from.

`provenance.py` restates the vocabulary instead of importing it, because
`crawlernest-ml` is not on the agent's import path. `test_provenance` loads
`schema.py` by file path and asserts the two agree in both directions, so a
renamed indicator fails a test rather than silently leaving a dimension
unwatched. That guard was checked by breaking it: dropping an indicator and
inventing one each turn it red.

Each check is tested against its own negative: the same sentence with the
structured field flipped, asserting the check goes quiet. Five of the six are
gated that way. The exception — completeness — has no gate by design, because
the evidence is always a page of results, so a claim about what lies outside it
is never supportable whatever the fields say.

The negatives matter more than the positives here, and the golden set cannot
supply them: it holds exactly **one** faithful comparative case, so it could not
tell a working ordering check from one that fires on every comparison. Those
negatives are written in the test file instead — a bare rank comparison, a
superlative with no criterion, "ranked in the top 100", a dimension named
without being ranked on, a scoped claim ("all 3 universities on this page"), and
an unrecognised criterion. One of them found a real defect: a 60-character
lookback reached across a sentence boundary and read "NTU is the best on rank. A
separate note: policies for international students vary…" as an ordering claim.
The window is now clipped at the nearest clause break.

Because both mechanical signals now discard the model's text, `/api/v1/agent/stats`
counts them apart — `rules_flag_rate` and `provenance_flag_rate` alongside
`mechanical_rejection_rate`. A signal that never fires is worth noticing, and a
combined number would hide it.

That is now wired in, and it turned out the checker itself never had been: it was
scored in CI every run and never consulted at generation time, so a violation was
measured rather than stopped. `generation/verification.py` sits between the model
and the caller and weights the two signals by their measured precision — a rules
violation (precision 1.000) discards the model's text for the deterministic
reply; a judge-only concern (precision 0.952) keeps the text and attaches a
warning, because discarding a good answer on a signal wrong one time in twenty is
the worse trade. The judge is absent unless `WEB_AGENT_JUDGE_BASE_URL` is set, and
an unreachable one returns *no opinion* rather than approval.

Two limits still stand. It remains one 7B model, and `--model` makes a larger one
a measurement rather than an argument. And eleven hand-written cases is a small
basis for a claim about a whole class of failure.

### The original measurement, on the rules' home ground

An LLM judge is the obvious next move: it is the only thing that can catch
unfaithfulness the rules cannot express. So it was measured before being
adopted, on the same 34 golden cases, against `qwen2.5:7b-instruct` at
temperature 0.

| | Accuracy vs golden labels |
|---|---:|
| Mechanical checker | **1.0000** |
| LLM judge | 0.7941 |

Cohen's κ between the two raters: **0.588**. Every judge reply parsed.

The κ alone would read as moderate agreement and might be talked into an
adoption. The direction of the disagreements is what settles it. Seven cases
differ, and the judge is wrong in all seven:

- **Six missed violations.** It passed an invented institution ("does not invent
  any figures or institutions" — the explanation named Pacific Rim University),
  a dropped caveat, a partially dropped caveat, a paraphrased caveat, a
  fabricated row count, and computed arithmetic.
- **One false alarm** on clean text, `faith-015`, where the institution was
  named in nested profile evidence rather than in the item list.

**Caught only by the judge: none.** It contributed no detection the rules missed,
missed six the rules caught, and invented one objection. On this dataset it is
strictly worse and adds a model dependency, latency and cost for it.

On that dataset the conclusion was to reject the judge, and it was the right
conclusion: it contributed nothing the rules missed, in exchange for a model
dependency, latency and cost.

The reasoning that turned out to matter was the caveat attached to it — that the
golden set was built from the rule checker's own taxonomy, so it tested the judge
where rules are strongest, and a judge's real value would lie on unfaithfulness
nobody has written a rule for. Extending the dataset was listed as the next step
for exactly that reason. Doing it reversed the answer.

```bash
python crawlernest/crawlernest-autoeval/runners/run_judge_calibration.py \
    --base-url http://localhost:11434/v1 --model qwen2.5:7b-instruct \
    --out crawlernest/crawlernest-autoeval/reports/judge_calibration_qwen2.5-7b.json
```

Full per-case output is committed at that path.

## Layout

```
ranking_ml/
  features/
    schema.py               feature contract, QS published weights, validation
    regions.py              107 countries → 12 regions, documented judgement calls
    build_features.py       snapshot → FeatureMatrix (X, y, rank, names)
  eda/
    run_eda.py              the analysis and figures above
    cross_source.py         QS ∩ THE join, percentiles, disagreement label
  models/
    overall_score.py        candidate estimators, incl. RenormalisedWeightedScore
    support.py              distance-to-training-data flag
  evaluation/
    metrics.py              RMSE / MAE / R², and rank agreement
    baselines.py            QS's published weighting, and weight-recovery tables
  training/
    train_overall_score.py  the overall-score run
    train_disagreement.py   the cross-source disagreement run
  serving/
    predict.py              batch scoring into analytics.ml_predictions
model_cards/
  overall_score.md          full record for the score estimator
  disagreement.md           full record for the disagreement classifier
artifacts/
  eda/                      committed figures
  metrics/                  committed metrics.json, what CI compares against
  models/                   trained binaries (gitignored, rebuildable)
```

## Serving

Estimates reach the API through their own tables, never through
`analytics.aggregated_rankings`:

```bash
PYTHONPATH=crawlernest/crawlernest-ml ./.venv/bin/python -m ranking_ml.serving.predict \
    --pg-user test --pg-password test --pg-database clawer
# add --dry-run to compute everything and write nothing
```

The job fits the estimator on the 600 labelled universities, predicts the 903
withheld ones, resolves each to a `canonical_university_id`, and writes one
`analytics.ml_model_runs` row plus its predictions in a single transaction. On
the current snapshot 902 of 903 resolve; the one that does not is a snapshot row
literally named "N/A", which is skipped rather than guessed at.

The schema enforces two things rather than trusting callers to:
`ml_predictions.is_estimated` is `CHECK`-constrained true, so no writer can turn
the disclosure off, and every row carries its support distance, so no consumer
can surface an estimate without the means to say how far outside the training
data it sits.

The disagreement classifier has its own job, and the asymmetry between them is
the point:

```bash
PYTHONPATH=crawlernest/crawlernest-ml ./.venv/bin/python \
    -m ranking_ml.serving.predict_disagreement \
    --pg-user test --pg-password test --pg-database clawer
```

It trains on the 820 universities QS and THE both rank, then scores **all 1,503
QS universities** — including the 683 THE has never covered. That is where the
probability is useful: a contested institution can be flagged at QS ingest time
rather than after a second source arrives, which in this deployment it never has.

Worth checking, since the training set is an overlap rather than a slice: **96.8%
of the 1,503 fall inside the training support**, against 72.8% for the
overall-score model. The overlap spans the QS distribution instead of clustering
at one end of it the way a published-score cutoff does.

`GET /api/v1/analytics/estimated-scores` and
`GET /api/v1/analytics/disagreement-risk` read them. Every non-empty response
carries `AnalyticsService.ESTIMATED_SCORE_CAVEAT`, and each item carries
`is_estimated` and `is_supported`. Unsupported rows are returned by default —
`?supported_only=true` filters them — because dropping them silently would hide
the part of the output least worth trusting.

They are two endpoints rather than one with a parameter because one returns a
0–100 score and the other a 0–1 probability. A shared response shape would mean a
shared field name for two different quantities; instead the fields are
`estimated_overall_score` and `disagreement_probability`, and neither appears in
the other's response.

The risk endpoint also carries a caveat the score endpoint does not: **a
probability is not a finding.** A high value means universities with similar QS
profiles are often placed differently by THE — not that this university has been
shown to be misranked.

### A bug the second model exposed

`v_ml_predictions_latest` holds the latest run per target, so adding the
classifier put two quantities in one view. The existing query had no target
filter: it would have returned 0–100 scores and 0–1 probabilities in one list
sorted by value, burying every probability beneath every score and reporting a
total that counted both. Both reads now filter on target, and the integration
test seeds **both** fixtures so each endpoint has something to leak. Removing
either filter turns that test red — checked, not assumed.

### A boundary check worth knowing about

QS's lowest published overall score is 20.8, and every estimated university ranks
below 600, so on QS's own ordering no estimate should exceed 20.8. Two of 902
do (0.22%), the worst by 0.585. They are left unclipped: clipping would pile
rows up at the boundary and hide the error rather than remove it, and the size of
the overshoot is a useful read on the estimates' precision near the cut-off.

## CI

`.github/workflows/ml-tests.yml` runs on every push and pull request, with no
database and no network — everything trains from the committed snapshot.

```bash
# what CI does, locally
PYTHONPATH=crawlernest/crawlernest-ml ./.venv/bin/python -m pytest crawlernest/crawlernest-ml/tests -q
mkdir -p /tmp/metrics-baseline && cp artifacts/metrics/*.json /tmp/metrics-baseline/
PYTHONPATH=crawlernest/crawlernest-ml ./.venv/bin/python -m ranking_ml.training.train_overall_score
PYTHONPATH=crawlernest/crawlernest-ml ./.venv/bin/python -m ranking_ml.training.train_disagreement
PYTHONPATH=crawlernest/crawlernest-ml ./.venv/bin/python -m ranking_ml.evaluation.check_metrics \
    --baseline-dir /tmp/metrics-baseline
```

**38 feature-layer tests** run first: matrix shape, the 600/903 publication
split, region coverage for all 107 countries, value parsing, the renormalising
baseline, and that `rank` never appears among the features. They are fast and
have no model in them, so a broken feature layer fails as itself rather than
surfacing later as an unexplained metric movement.

**The MATLAB parity check** then compares the committed `artifacts/eda_matlab/`
tables against a fresh Python run, at a tolerance of 1e-9. Two implementations
that disagree are not a redundancy — they are a bug in one of them, and nobody
knows which. Measured agreement:

| Table | Column | Max absolute difference |
|---|---|---:|
| correlation_with_target | `pearson_r` | 7.2e-16 |
| covariate_shift | `labelled_mean` | 7.1e-14 |
| covariate_shift | `unlabelled_mean` | 1.8e-14 |
| covariate_shift | `standardised_gap` | 4.9e-15 |
| missingness | `missing`, `missing_pct` | 0 |

Machine precision, which is what the same formulas over the same inputs should
give. The check needs no MATLAB on the runner, because the MATLAB side is
committed output.

That bounds what it proves — stale CSVs still match — so it also asks git about
ordering: it fails if a `.m` was committed after the artifacts, or is modified in
the working tree while they are not. That does not re-execute the sources, but it
catches the sequence that makes an artifact stale. Verified in both directions:
clean tree passes, and editing `run_qs_eda.m` without regenerating fails with the
instruction to re-run it.

Re-executing the sources in CI needs MATLAB on the runner, and MathWorks' free
GitHub-hosted MATLAB covers public repositories only; this one is private. The
sources were instead verified by hand on R2026a: re-running `run_qs_eda.m`
reproduces all three CSVs byte for byte, with only the PNGs differing in encoding.
[`matlab/README.md`](matlab/README.md) records the workflow step to add if that
ever becomes possible.

**A second job, `ml-serving`,** runs the write path against a throwaway
PostgreSQL: create the schema, seed canonical universities from the committed
snapshot, run both serving jobs, then check the rows. The metrics gate stops at
the model, so before this the write path had no coverage at all.

The row check is the part that earns its keep. Exiting 0 only means a job did not
crash; `verify_predictions.py` asserts both targets are present, that each value
sits on the scale its target implies — a 0–1 probability and a 0–100 score share
a column, so a job writing to the wrong target shows up as a value in the wrong
range — that the disclosure columns are intact, and that no estimate has reached
`analytics.aggregated_rankings`. Both jobs are then run a second time and checked
again, because the API reads "latest per target" and a re-run that left both
visible would surface two models at once.

Rehearsing this job locally found a bug the live database had been hiding. Four
snapshot rows are named `N/A`; against a warehouse seeded one row per name they
all resolved onto a single invented university and the insert aborted on a
duplicate key, writing nothing. Two fixes: the seeder skips missing-data markers
instead of creating an entity for them, and both serving jobs collapse to one row
per canonical university before inserting. The second matters beyond this bug —
real entity resolution merges variant spellings, which is why the warehouse holds
1,499 canonical universities for 1,503 snapshot rows, and `ml_predictions` is
unique on canonical id.

**The metrics gate** then retrains both models and compares against the
committed `artifacts/metrics/*.json`. A model has no compiler and no failing test
to say it broke; without a gate, a change that quietly costs three points of AUC
looks exactly like a change that costs nothing. This repo already had that
failure mode once — a Java test that stayed red for two months because no
workflow ran it.

Two kinds of guard, because they fail differently:

| Kind | Checked how | Examples |
|---|---|---|
| **Invariant** | exactly, and first | `rows_labelled` = 600, `matched` = 820, `positives` = 164 |
| **Metric** | against a direction and tolerance | `linear_renorm` RMSE (±0.05), weight-recovery error (±0.0005), disagreement ROC-AUC (±0.02) |

Invariants come first because they describe the *data*: if the training set
stops being 600 rows, no metric comparison below it means anything.

Training is seeded and reproducible — a rerun on the same snapshot reproduces
every guarded number exactly, so the tolerances exist for library drift rather
than for run-to-run noise. Metric movement within tolerance is reported but does
not fail; it is the cue to retrain and recommit the metrics files.

The gate was verified by feeding it a deliberately degraded report: a 0.063 drop
in ROC-AUC and a changed row count both fail it with exit 1. A gate that cannot
fail is not a gate.

## Next

1. Re-executing the MATLAB sources in CI, which needs either a public repository
   or an `MLM_LICENSE_TOKEN`. The ordering guard covers the failure that actually
   happens — a `.m` edited without regenerating its artifacts — so what remains
   is the narrower case of the sources changing meaning while still producing
   output that matches. Until then, re-run `run_qs_eda.m` by hand after editing
   it.

2. **Nineteen hand-written cases is a thin basis for a claim about a whole class
   of failure.** The provenance checker was built against six of them and catches
   all six, so the union reaching 1.000 says the dataset has been exhausted, not
   that the class has. It is not evidence of generalisation to provenance
   failures nobody has written down. Six phrase patterns are also six phrasings:
   the structured half of each check is general, the textual half is not, and a
   model wording the same lie differently would get past it.

3. **The ordering check is only as closed as the vocabulary.** It rests on QS
   publishing nine indicators and no more. Adding THE or ARWU, whose indicator
   sets differ, means extending `_DIMENSIONS` — the drift test catches a renamed
   QS indicator but cannot know about a source that is not implemented yet.

These are honest limits rather than a backlog. The judge is wired in as a second
signal; its two failure modes announce themselves on stdout — silence after five
consecutive no-opinion replies, objections after ten in a row, each reported once
per episode with recovery logged so the warning can be closed. The counters
behind `GET /api/v1/agent/stats` are process-local, which is the whole picture
for a single-worker deployment and a fraction of it for anything larger.
