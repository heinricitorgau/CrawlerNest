# CrawlerNest AutoEval Program

This document defines how automated evaluation experiments are conducted within the CrawlerNest AutoEval module.

Unlike the original autoresearch setup (focused on LLM training), this system is adapted for:

- Crawler-engine extraction and parsing refinement
- Data normalization (cleaning / standardization)
- Future ranking / recommendation systems

---

## Core Principle

AutoEval follows a controlled improvement loop:

> Modify → Evaluate → Compare → Keep or Discard

The goal is NOT to explore randomly, but to:

- Improve data quality
- Maintain system stability
- Track measurable progress

---

## Setup

Before running experiments:

1. **Select a target module**
   - extractor
   - normalization
   - (future) ranking / recommendation

2. **Load evaluation dataset**
   - Located in `datasets/`
   - Must include ground truth (expected output)

3. **Verify baseline exists**
   - Baseline results stored in `baselines/` or `results.tsv`

4. **Initialize results.tsv (if not exists)**

```
commit\tscore\trequired_fill_rate\texact_match_rate\terror_count\truntime_s\tstatus\tdescription
```

5. **Confirm evaluation runner works**

Example:

```
python runners/run_extractor_eval.py
```

In practice, this usually evaluates changes in ranking/admission extraction logic rather than changes to a single monolithic crawler.

---

## Allowed Modifications

Experiments must follow strict boundaries.

### You CAN modify:

Depending on experiment scope:

- Ranking crawler extraction rules
  - `crawlernest_ranking_crawler/` (repo root)

- Admission crawler extraction rules
  - `crawlernest-admission-crawler/`

- Shared extractor helpers
  - `crawlernest-extractors/`

- Normalization rules
  - `crawlernest-normalization/` (C engine, canonical source)
  - `crawlernest-normalization-py/` (Python bridge + fallback)

- Prompt / parsing logic (if applicable)

---

### You CANNOT modify:

- Database schema (`crawlernest-schema/`)
- Core system logic (`crawlernest-core/`)
- Evaluation metrics (`eval_spec.md`)
- Evaluation runners (`runners/`)

---

## Evaluation Metrics

Defined in `eval_spec.md`.

Typical metrics include:

- required_field_fill_rate
- exact_match_rate
- error_count
- runtime

A combined score is used for comparison.

Higher score = better performance.

---

## Experiment Loop

LOOP:

1. Identify current baseline
2. Apply ONE small change
3. Run evaluation

```
python runners/run_extractor_eval.py
```

4. Collect metrics
5. Append result to `results.tsv`

---

## Decision Rules

### KEEP

- Score improves
- No major increase in errors
- Complexity increase is acceptable

---

### DISCARD

- Score decreases
- Error count increases significantly
- Output becomes unstable

---

### CRASH

- Code fails to run
- Output invalid

Log crash and move on.

---

## Logging Format

Each experiment must be recorded:

```
commit\tscore\trequired_fill_rate\texact_match_rate\terror_count\truntime_s\tstatus\tdescription
```

Example:

```
a1b2c3d\t0.812\t0.90\t0.78\t4\t22.1\tkeep\tbaseline extractor
b2c3d4e\t0.836\t0.92\t0.81\t3\t23.4\tkeep\tadd fallback selector
c3d4e5f\t0.790\t0.88\t0.76\t6\t20.2\tdiscard\tregex-only parsing
```

---

## Experiment Constraints

### 1. Small Changes Only

Each experiment must modify ONLY one aspect.

Bad example:
- Change parser + normalization + schema together

Good example:
- Adjust one selector rule

---

### 2. Reproducibility

- Always use the same dataset
- Do not modify test data

---

### 3. Isolation

- Do NOT directly modify production pipeline
- Use sandbox or temporary rules if needed

---

### 4. Stability over novelty

A small stable improvement is better than a risky change.

---

## Failure Handling

If an experiment fails:

1. Check error
2. If trivial → fix and rerun
3. If fundamental → log as crash and skip

Do NOT spend excessive time debugging one experiment.

---

## Termination Condition

Unlike autoresearch, AutoEval is NOT infinite.

Stop when:

- No meaningful improvement after multiple iterations
- Diminishing returns observed
- Target metric reaches acceptable threshold

---

## Philosophy

AutoEval is not about randomness.

It is about:

- Structured experimentation
- Measurable improvement
- Continuous refinement

---

## Summary

AutoEval turns trial-and-error into a system:

> From intuition-driven tuning → to data-driven optimization

This enables CrawlerNest to evolve systematically, not manually.
