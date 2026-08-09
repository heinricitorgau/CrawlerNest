# MATLAB port of the QS indicator EDA

A MATLAB reimplementation of [`ranking_ml/eda/run_eda.py`](../ranking_ml/eda/run_eda.py),
reading the same committed snapshot and producing the same three figures and
four numeric tables. Tested on MATLAB **R2026a**; no toolboxes beyond
Statistics and Machine Learning (`pca`, `corr`) are used.

It exists as a *port*, not a rewrite: the point is that two independent
implementations agree on the numbers the Phase 2 modelling decisions rest on. A
parity check runs at the end of every run and prints the largest deviation from
the Python output.

## Running it

From the MATLAB prompt:

```matlab
cd crawlernest/crawlernest-ml/matlab
results = run_qs_eda();
```

Headless, from a Windows shell:

```bash
"C:/Program Files/MATLAB/R2026a/bin/matlab.exe" -batch "cd('//wsl.localhost/ubuntu-24.04/home/torgau/dev/University-Data-Infrastructure-Web-Platform/crawlernest/crawlernest-ml/matlab'); run_qs_eda();"
```

Options:

| Call | Effect |
|---|---|
| `run_qs_eda(Snapshot="...json")` | analyse a different crawl snapshot |
| `run_qs_eda(OutDir="...")` | write somewhere other than `artifacts/eda_matlab/` |
| `run_qs_eda(SaveFigures=false)` | on-screen only, writes nothing |

No database, no network, no pipeline run: the input is
`crawlernest/crawlernest-kb/databases/last_crawl_snapshot.json`, which is
committed. Output lands in `../artifacts/eda_matlab/`, deliberately separate
from the Python-committed `../artifacts/eda/` so neither run clobbers the other.

## Output

![QS indicator correlation, labelled rows only](../artifacts/eda_matlab/correlation_heatmap.png)

Pearson correlation on the 600 labelled rows, target included as the last row
and column. The ordering broadly tracks QS's published weighting, with one
exception worth reading off the bottom row: **Citations per Faculty carries a
20% weight but correlates with Overall Score at only 0.48**, below three
indicators weighted at 5%. Correlation is not importance — Phase 2 confirms the
20% is really there by recovering it from a linear fit.

![Target distribution, ranks 1-600](../artifacts/eda_matlab/target_distribution.png)

The regression target, published only for ranks 1-600 (n=600, mean 41.8, std
18.8). The right skew is the shape of the ranking table itself: scores above 60
are rare because few universities are near the top. The 903 rows QS withholds a
score for are not in this histogram at all — that gap is what the PCA figure is
about.

## Files

```
load_qs_snapshot.m   snapshot JSON -> 1503x9 indicator matrix, y, rank, names
qs_to_float.m        QS cell -> double; "n/a" and off-scale values -> NaN
qs_to_rank.m         published rank -> double; "901-950" -> midpoint
run_qs_eda.m         the analysis, the figures, and the parity check
```

`rank` is loaded but kept out of the feature matrix. QS derives the rank *from*
the overall score, so using it as a feature would leak the target — the same
rule the Python side enforces in `features/schema.py`.

## Parity with the Python run

Every run prints this table. Deviations are at the level of the rounding in the
hard-coded reference values, not at the level of the computation:

```
--- parity with ranking_ml.eda.run_eda ---
            table                    max_abs_deviation_from_python
    "correlation with target"                  4.4310e-07
    "covariate shift (Cohen's d)"              4.8632e-05
    "PCA explained variance %"                 3.9696e-05
    "target mean / std"                        3.3333e-07
```

Anything above `1e-3` raises a warning. Treat it as a real signal — it means one
of the two ports has drifted, and the figures should not be used until that is
explained.

Three places where MATLAB and scikit-learn defaults differ, all handled
explicitly in `run_qs_eda.m`:

- **Standardisation.** `StandardScaler` uses the population standard deviation
  (ddof=0). MATLAB's `std(X)` uses the sample one. The PCA input uses
  `std(X, 1, 1)`; the plain default shifts PC1 by ~0.03% of variance.
- **Cohen's *d*.** The pooled standard deviation uses ddof=1, matching the
  Python side. MATLAB's `var` default already does this.
- **Component signs.** PCA component signs are arbitrary and MATLAB and sklearn
  do not agree on them. Both components are flipped to a positive loading sum,
  so reruns and the Python figure orient the same way.

## Deliberate visual differences

The numbers are identical; two colour choices are not, because MATLAB ships
neither colormap:

- matplotlib `RdBu_r` → a hand-built blue-white-red diverging map.
- matplotlib `viridis` → `parula`.

## What this does *not* cover

Only the Phase 1 EDA. The Phase 2 weight recovery, the support flag, and the
Phase 3 cross-source disagreement classifier remain Python-only — see the
[ML README](../README.md) and the model cards.
