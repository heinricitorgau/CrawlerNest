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
is committed — so everything here runs with no database and no network. It is a
byte copy of `crawlernest-kb/qs_universes/2026/global/global/raw_snapshot.json`,
the QS World University Rankings **2026** table (nid 4061771), whose
`run_status.json` records the edition as verified against the 2026 edition page.

The file it replaced was the **2027** table (nid 4153156) — resolved from a
cached ranking id and saved under the 2026 name, so Peking sat at 13 and
Tsinghua at 14 where the 2026 edition has Peking at 14 and Tsinghua at =17. Every number below was
regenerated from the verified edition on 2026-09-14.

| | |
|---|---|
| Universities | 1,504 (QS 2026) |
| Indicators | 9, all present on every record |
| Countries | 107, grouped into 12 regions |
| Feature matrix | `(1504, 9)` indicators, `(1504, 21)` with region one-hot |

The records also carry `rank_display` (the published label, `=17`, `1401+`) and
an `International Student Diversity` metric new in the 2026 table. Neither is
read: `rank` is the table position, and the feature set is the fixed nine.

The target is QS's `Overall Score`, and its availability is the reason this is a
supervised problem at all:

```
rank    1– 705  →  Overall Score published   →  705 labelled rows  (training set)
rank  706–1504  →  Overall Score = "n/a"     →  799 unlabelled rows (inference set)
```

QS publishes the nine component indicators for all 1,504 universities but the
total only for the top 705.

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
| International Faculty Ratio | 87 | 5.78 |
| International Student Ratio | 37 | 2.46 |
| Sustainability Score | 24 | 1.60 |
| International Research Network | 2 | 0.13 |
| the other five | 0 | 0.00 |

Median imputation is the current strategy. It is a decision, not a default —
`missingness_report()` exists so it stays visible.

### 2. The indicators line up with QS's published weighting

Correlation with `Overall Score` on the 705 labelled rows:

| Indicator | Pearson r | QS published weight |
|---|---:|---:|
| Academic Reputation | 0.905 | 30% |
| Employer Reputation | 0.786 | 15% |
| Sustainability Score | 0.670 | 5% |
| Employment Outcomes | 0.648 | 5% |
| International Research Network | 0.518 | 5% |
| Citations per Faculty | 0.494 | 20% |
| International Student Ratio | 0.405 | 5% |
| International Faculty Ratio | 0.382 | 5% |
| Faculty Student Ratio | 0.312 | 10% |

The ordering broadly tracks the published weights, with one worth noting:
**Citations per Faculty carries a 20% weight but correlates at only 0.494**,
below three indicators weighted at 5%. Whether a fitted model recovers the
published 20% is a concrete, checkable question for Phase 2 rather than a
hand-wave about feature importance.

![Indicator correlation heatmap](artifacts/eda/correlation_heatmap.png)

### 3. Training set and inference set are not the same population

This is the finding that constrains Phase 2. Standardised difference in means
(Cohen's *d*) between the 705 labelled and 799 unlabelled rows:

| Indicator | Labelled mean | Unlabelled mean | Cohen's *d* |
|---|---:|---:|---:|
| Sustainability Score | 66.10 | 38.03 | 1.78 |
| Academic Reputation | 42.10 | 11.33 | 1.61 |
| Citations per Faculty | 49.64 | 13.57 | 1.53 |
| Employer Reputation | 43.01 | 12.70 | 1.48 |
| International Research Network | 71.28 | 37.54 | 1.44 |
| Employment Outcomes | 44.92 | 16.71 | 1.10 |
| International Faculty Ratio | 52.73 | 19.98 | 1.08 |
| International Student Ratio | 47.71 | 20.00 | 0.94 |
| Faculty Student Ratio | 42.02 | 26.90 | 0.55 |

Every indicator shifts by more than 0.5 pooled standard deviations and seven of
nine by more than 1.0. Predicting the 799 from the 705 is **extrapolation, not
interpolation**.

![PCA scatter](artifacts/eda/pca_scatter.png)

PC1 alone explains 49.9% of the variance and orders the labelled rows almost
monotonically by rank. The unlabelled rows pile up at the low end of PC1, in a
region where the training data is sparse — though the two populations do overlap
just above the publication cut-off, so predictions just past it rest on real
support and predictions deep in the tail do not.

**Consequences for Phase 2**, all of them arising from this figure:

1. A cross-validated RMSE on the 705 labelled rows measures how well the model
   recovers QS's scoring function. It does **not** estimate the error on the 799.
   Reporting it as though it did would be the exact kind of flattering,
   unfalsifiable number this repo's honesty contract exists to prevent.
2. Every prediction needs a **support flag** — a distance from the training
   distribution — and only predictions inside the supported region should be
   surfaced. This maps onto the existing mechanically-derived confidence rule
   rather than inventing a new one.
3. Spearman ρ between predicted score and QS's published rank on the 799 is not
   an optional extra. It is the only external validation available in the
   shifted region, because the ordering is known even though the scores are not.

![Target distribution](artifacts/eda/target_distribution.png)

## Phase 2 results

Full detail in the [model card](model_cards/overall_score.md). Three things came
out of it.

### The published weighting is recovered from the data

A linear fit on the raw indicators reproduces QS's documented weighting to a
mean absolute error of **0.0011** (worst case 0.0020): Academic Reputation
0.3007 against a published 0.30, Citations per Faculty 0.1984 against 0.20, and
so on for all nine.

This reframes what the model is. The overall score is a deterministic weighted
sum, so this is system identification, not forecasting — and an R² of 0.9996
should be read as "the formula was recovered", never as predictive accuracy.
Tree models do *worse* here (random forest RMSE 3.49 against 0.35), which is the
expected result when the true relationship is exactly linear.

It also shows why correlation is not importance: Citations per Faculty carries a
20% weight but correlates with the target at only 0.494, below three indicators
weighted at 5%.

### Imputation, not model choice, decided performance under shift

Median imputation scores Spearman 0.9381 against the published ranks of the 799.
Changing only how missing indicators are handled:

| Missing-value strategy | Spearman on the 799 |
|---|---:|
| median imputation (fitted weights) | 0.9381 |
| renormalise over available weights (fitted) | **0.9614** |
| renormalise over available weights (QS published) | 0.9614 |

Fitted and published weights land in the same place once missing values are
renormalised, so none of that gap is about the model. Median imputation borrows
values from a training distribution whose medians run up to nearly six times
higher than the withheld tail, biasing exactly the 96 withheld rows that carry a
missing indicator. The recommended model, `linear_renorm`, renormalises instead
— and then wins on both cross-validation (RMSE 0.350 against 0.482) and
extrapolation.

The general lesson is worth stating plainly: under covariate shift the default
preprocessing step did more damage than any modelling decision, and it was the
out-of-distribution check that first surfaced it.

### Almost half of the inference set is unsupported

| Set | n | Supported | % |
|---|---:|---:|---:|
| Labelled (train) | 705 | 698 | 99.01 |
| Unlabelled (infer) | 799 | 440 | 55.07 |

Support is the mean distance to the 10 nearest training rows in standardised
indicator space, thresholded at the 95th percentile of the training set's own
leave-one-out distances — mechanical and inspectable, like the rest of the
confidence handling in this repo. **45% of the rows we would predict sit outside
the region the model was fitted on**, and the flag is what decides whether an
estimate is publishable. That share is larger on the 2026 edition than on the
2027 table this snapshot replaced (37%), with near-identical labelled and
withheld counts — so the support rate is a property of the edition, and has to
be re-read whenever the snapshot changes.

## Phase 3 results — cross-source disagreement

Full detail in the [model card](model_cards/disagreement.md). QS and THE both
rank 1,109 of the same universities, and they frequently disagree about them.
The pairing comes from the warehouse — entity resolution seeded with reviewed
aliases, ambiguous cases settled by hand — rather than being re-derived here
from a name key, which reaches 842. On the 830 both methods place, they pick the
same THE entity every time.

The trap here was the same shape as Phase 2's, one level up. Each source's rank
is close to a deterministic function of its own component scores, so a
classifier handed *both* sources' scores would be recomputing the label rather
than predicting it, and would score well while meaning nothing. The task
modelled is therefore one-sided: **given only QS's view of a university, will
THE disagree?** That is a real prediction, and it has a use — flagging contested
institutions at QS ingest time, before THE data arrives.

| Feature set | Model | ROC-AUC | PR-AUC |
|---|---|---:|---:|
| **QS only** | **gradient boosting** | **0.8384** | **0.5201** |
| QS only | logistic regression | 0.7460 | 0.3547 |
| both sources *(ceiling)* | gradient boosting | 0.9258 | 0.7620 |
| chance | — | 0.5000 | 0.2002 |

![Disagreement diagnostics](artifacts/eda/disagreement_diagnostics.png)

PR-AUC 0.520 against a 0.200 base rate is the honest headline — a 2.6× lift,
where ROC-AUC would flatter an imbalanced problem. QS alone reaches 0.838 of a
two-sided ceiling of 0.926, so most of what is predictable is already in QS's own
numbers. Gradient boosting beats the linear model here by a wide margin, the
opposite of the overall-score result, because this relationship genuinely is not
linear. Calibration holds in the low and middle range and goes over-confident in
the top bin (0.72 predicted against 0.59 observed).

These are lower than the numbers committed before (ROC-AUC 0.8662, PR-AUC
0.5922), which were trained on the 2027 table mislabelled as 2026. Same code,
different edition; the metrics gate refused the comparison on its `matched` and
`positives` invariants.

Among disagreeing pairs, **THE ranks the university higher 178 times to QS's
44** — the sources do not merely differ, they differ in a consistent direction.

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

The job fits the estimator on the 705 labelled universities, predicts the 799
withheld ones, resolves each to a `canonical_university_id`, and writes one
`analytics.ml_model_runs` row plus its predictions in a single transaction.
Against the live warehouse on 2026-09-14, 787 of 799 resolve. The 12 that do not
— Pratt Institute, University of Tunis, Universidad Diego Portales and nine more
— have no canonical university whose normalised name matches, and are reported
and skipped rather than guessed at.

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

It trains on the 1,109 universities QS and THE both rank, then scores **all 1,504
QS universities** — including the 395 outside that overlap. That is where the
probability is useful: a contested institution can be flagged at QS ingest time
rather than after a second source arrives.

Worth checking, since the training set is an overlap rather than a slice: **97.1%
of the 1,504 fall inside the training support**, against 55.1% for the
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

QS's lowest published overall score in 2026 is 25.1, and every estimated
university ranks below 705, so on QS's own ordering no estimate should exceed
25.1. Six of the 787 served do (0.76%), the worst by 2.88. They are left
unclipped: clipping would pile
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

**38 feature-layer tests** run first: matrix shape, the 705/799 publication
split, region coverage for all 107 countries, value parsing, the renormalising
baseline, and that `rank` never appears among the features. They are fast and
have no model in them, so a broken feature layer fails as itself rather than
surfacing later as an unexplained metric movement.

**The MATLAB parity check** then compares the committed `artifacts/eda_matlab/`
tables against a fresh Python run, at a tolerance of 1e-9. Two implementations
that disagree are not a redundancy — they are a bug in one of them, and nobody
knows which. Measured agreement on the QS 2026 snapshot, after re-running every
port on R2026a:

| Table | Column | Max absolute difference |
|---|---|---:|
| correlation_with_target | `pearson_r` | 7.8e-16 |
| covariate_shift | `labelled_mean` | 5.0e-14 |
| covariate_shift | `unlabelled_mean` | 4.6e-14 |
| covariate_shift | `standardised_gap` | 4.2e-15 |
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

**Since the repository became public**, that last gap is closed. MathWorks' free
GitHub-hosted MATLAB covers public repositories, so a third job,
`matlab-reexecution`, installs MATLAB with the Statistics and Machine Learning
Toolbox — `run_qs_eda.m` calls `pca` and `corr` — runs the sources into a scratch
directory, and checks the result twice:

- `--matlab-dir` points at the fresh output, so the Python comparison above is
  now against sources that just executed rather than against committed CSVs.
- `--committed-dir` compares fresh against committed, asserting directly that the
  sources still produce what is in the repository. That is the statement the
  git-ordering guard could only approximate.

The ordering guard stays anyway: it runs in the fast job on every push and needs
no MATLAB.

Before this the sources were verified by hand on R2026a — re-running
`run_qs_eda.m` reproduced all three CSVs byte for byte, with only the PNGs
differing in encoding.

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

**The row check is about shape, and every way a model goes quietly wrong
produces rows of the right shape.** `check_serving_quality.py` scores them
instead, against the published data each target can be checked against.
Neither model has its label at serving time — that is what they are for — but
each has something the label orders:

| Target | Ground truth available at serving time | Currently |
|---|---|---:|
| `qs_overall_score` | QS withholds the score for ranks 706–1504 and publishes the rank | Spearman **−0.9627** |
| `qs_the_disagreement` | both sources' ranks are in the warehouse for the universities both rank | ROC-AUC **0.8906** |

The score check also compares against `metrics_json.rank_agreement_spearman`,
recorded by the training run, so it regresses against a number rather than
admiring one: served −0.9627 on 774 rows against a recorded 0.9614.
(Measured on the live warehouse on 2026-09-14, after the serving jobs were re-run
from the verified 2026 snapshot.)

Support is reported split rather than pooled, which turns the flag into a
claim that can fail. Supported predictions agree with published ranks at
0.9552 and unsupported ones at 0.8824 — the flag is measuring something. Were
the two equal, or the unsupported ones better, that would say it is not.

Verified by breaking it, on a copy of the warehouse: shuffling the scores
between universities drops agreement to 0.00, inverting them fails on the
sign, setting every support flag true fails on the fraction, and randomising
the probabilities lands the AUC at 0.51. **All four pass `verify_predictions`
unchanged** — right shape, right scale, right disclosure columns, wrong
numbers.

It found one the first time it ran: the live database was serving
disagreement probabilities from the pre-retrain model, because the model was
rebuilt on the 1,082-row join and the serving jobs were never re-run against
it. Visible as 0.8591 where a fresh run gives 0.8907, and invisible to every
other check in the chain.

Rehearsing this job locally found a bug the live database had been hiding. Four
rows of the snapshot at the time were named `N/A` (one is, in 2026); against a
warehouse seeded one row per name they
all resolved onto a single invented university and the insert aborted on a
duplicate key, writing nothing. Two fixes: the seeder skips missing-data markers
instead of creating an entity for them, and both serving jobs collapse to one row
per canonical university before inserting. The second matters beyond this bug —
real entity resolution merges variant spellings, so snapshot rows and canonical
universities are not one-to-one, and `ml_predictions` is unique on canonical id.

**The metrics gate** then retrains both models and compares against the
committed `artifacts/metrics/*.json`. A model has no compiler and no failing test
to say it broke; without a gate, a change that quietly costs three points of AUC
looks exactly like a change that costs nothing. This repo already had that
failure mode once — a Java test that stayed red for two months because no
workflow ran it.

Two kinds of guard, because they fail differently:

| Kind | Checked how | Examples |
|---|---|---|
| **Invariant** | exactly, and first | `rows_labelled` = 705, `matched` = 1,109, `positives` = 222 |
| **Metric** | against a direction and tolerance | `linear_renorm` RMSE (±0.05), weight-recovery error (±0.0005), disagreement ROC-AUC (±0.02) |

Invariants come first because they describe the *data*: if the training set
stops being 705 rows, no metric comparison below it means anything. Replacing the
mislabelled 2027 snapshot with the verified 2026 one tripped exactly these
(`rows_labelled` 700 → 705, `matched` 1,104 → 1,109), and the metrics files were
recommitted from the new edition rather than compared against the old one.

Training is seeded and reproducible — a rerun on the same snapshot reproduces
every guarded number exactly, so the tolerances exist for library drift rather
than for run-to-run noise. Metric movement within tolerance is reported but does
not fail; it is the cue to retrain and recommit the metrics files.

The gate was verified by feeding it a deliberately degraded report: a 0.063 drop
in ROC-AUC and a changed row count both fail it with exit 1. A gate that cannot
fail is not a gate.

## Next

1. **Nineteen hand-written cases is a thin basis for a claim about a whole class
   of failure.** The provenance checker was built against six of them and catches
   all six, so the union reaching 1.000 says the dataset has been exhausted, not
   that the class has. It is not evidence of generalisation to provenance
   failures nobody has written down. Six phrase patterns are also six phrasings:
   the structured half of each check is general, the textual half is not, and a
   model wording the same lie differently would get past it.

2. **The ordering check is only as closed as the vocabulary.** It rests on QS
   publishing nine indicators and no more. Adding THE or ARWU, whose indicator
   sets differ, means extending `_DIMENSIONS` — the drift test catches a renamed
   QS indicator but cannot know about a source that is not implemented yet.

These are honest limits rather than a backlog. The judge is wired in as a second
signal; its two failure modes announce themselves on stdout — silence after five
consecutive no-opinion replies, objections after ten in a row, each reported once
per episode with recovery logged so the warning can be closed. The counters
behind `GET /api/v1/agent/stats` are process-local, which is the whole picture
for a single-worker deployment and a fraction of it for anything larger.
