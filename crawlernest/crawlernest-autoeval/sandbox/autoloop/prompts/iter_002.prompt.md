You are a senior Python engineer improving CrawlerNest's extractor for AutoEval.

        Task:
        Modify ONLY this file:
        /Users/test/Desktop/crawlernest/crawlernest/crawlernest-extractors/extractor.py

        Goal:
        Improve extractor robustness without breaking current passing cases.

        Current baseline metrics:
        - score = 0.902777
        - required_fill_rate = 0.981481
        - exact_match_rate = 0.925926
        - optional_fill_rate = 1.000000
        - error_count = 4
        - error_rate = 0.074074
        - runtime_s = 0.001730
        - status = keep

        Dataset:
        /Users/test/Desktop/crawlernest/crawlernest/crawlernest-autoeval/datasets/extractor_goldens/samples.json

        Baseline report JSON:
        /Users/test/Desktop/crawlernest/crawlernest/crawlernest-autoeval/sandbox/autoloop/reports/baseline_iter0.json

        Hard rules:
        1. Only modify extractor.py
        2. Do not modify dataset, eval runner, eval_spec.md, or program.md
        3. Keep extract() deterministic
        4. Never crash; always return a dict
        5. Preserve or improve current passing behavior
        6. Prefer simple, readable logic over clever complexity

        What to optimize for:
        - stronger parsing robustness
        - whitespace / casing tolerance
        - separator tolerance (:, -, |)
        - mild noise tolerance
        - quota parsing stability

        Suggested strategy:
        - strengthen fallback parsing
        - normalize keys safely
        - add conservative regex fallback
        - keep code short and readable

        Evaluation spec:


# CrawlerNest AutoEval — Evaluation Specification (eval_spec.md)

This document defines the **evaluation metrics, scoring formula, and decision rules** used by the CrawlerNest AutoEval system.

It serves as the **single source of truth** for how extractor (and later normalization / ranking) performance is measured.

---

## 1. Scope

This specification currently applies to:

- Extractor evaluation (`run_extractor_eval.py`)

Future extensions:

- Normalization evaluation
- Ranking / recommendation evaluation

---

## 2. Dataset Definition

Each evaluation uses a fixed **golden dataset** located in:

```
datasets/extractor_goldens/samples.json
```

Each sample must follow:

```json
{
  "id": "sample-id",
  "input": "raw text or html",
  "expected": {
    "field_a": "...",
    "field_b": "..."
  },
  "required_fields": ["field_a", "field_b"]
}
```

### Notes

- `expected` = ground truth
- `required_fields` = fields that must be extracted
- Fields not listed in `required_fields` are treated as optional

---

## 3. Metric Definitions

### 3.1 Required Field Fill Rate

```
required_fill_rate = filled_required_fields / total_required_fields
```

- A field is considered **filled** if:
  - value is not None
  - value is not empty string

---

### 3.2 Exact Match Rate

```
exact_match_rate = exact_matches / total_expected_fields
```

Where:

- Exact match is defined as:
  - case-insensitive string match
  - normalized whitespace
  - numeric equality (e.g. "120" == 120)

---

### 3.3 Optional Field Fill Rate

```
optional_fill_rate = filled_optional_fields / total_optional_fields
```

If no optional fields exist:

```
optional_fill_rate = 1.0
```

---

### 3.4 Error Count

Error is counted when:

- required field is missing
- field value is incorrect (mismatch)
- extractor produces invalid or inconsistent output

```
error_count = total number of field-level errors
```

---

### 3.5 Error Rate

```
error_rate = error_count / total_expected_fields
```

---

### 3.6 Runtime

```
runtime_s = total execution time (seconds)
```

---

## 4. Scoring Formula

Final score is a weighted combination of metrics:

```
score =
  + 0.45 * exact_match_rate
  + 0.35 * required_fill_rate
  + 0.15 * optional_fill_rate
  - 0.10 * error_rate
  - runtime_penalty
```

Where:

```
runtime_penalty = min(avg_runtime / 10, 1.0) * 0.05
```

### Properties

- Score range: [0, 1]
- Higher score = better performance
- Strong bias toward correctness (exact match)

---

## 5. Decision Rules

### KEEP

- score improves vs baseline
- no significant increase in error_count
- behavior remains stable

---

### DISCARD

- score decreases
- error_count increases
- extraction becomes unstable

---

### CRASH

- extractor raises exception
- output is not valid dict

---

## 6. Logging Format (results.tsv)

Each evaluation appends one row:

```
commit\tscore\trequired_fill_rate\texact_match_rate\terror_count\truntime_s\tstatus\tdescription
```

Example:

```
a1b2c3\t0.950000\t1.000000\t1.000000\t0\t0.0021\tkeep\tbaseline extractor
```

---

## 7. Design Principles

### 7.1 Deterministic Evaluation

- Same input → same output
- No randomness allowed

---

### 7.2 Fixed Dataset

- Dataset must not change during comparison
- Ensures reproducibility

---

### 7.3 Isolation

- Evaluation must not modify production system

---

### 7.4 Simplicity First

- Metrics must be interpretable
- Avoid over-complex scoring

---

## 8. Future Extensions

Planned improvements:

- Field-level weighting (e.g. university > quota)
- Partial match scoring
- Fuzzy string matching
- Semantic comparison (LLM-assisted)
- Per-domain evaluation (by country / school)

---

## 9. Summary

This specification ensures that:

- All extractor changes are **measurable**
- Improvements are **comparable**
- System evolves in a **controlled, data-driven way**

AutoEval transforms extraction from:

> manual tuning → systematic optimization

        Program rules:
        # CrawlerNest AutoEval Program

This document defines how automated evaluation experiments are conducted within the CrawlerNest AutoEval module.

Unlike the original autoresearch setup (focused on LLM training), this system is adapted for:

- Data extraction (extractors)
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

---

## Allowed Modifications

Experiments must follow strict boundaries.

### You CAN modify:

Depending on experiment scope:

- Extractor rules
  - `crawlernest-extractors/`

- Normalization rules
  - `crawlernest-normalization/`
  - `crawlernest-normalization-py/`

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


        Output:
        Edit the file directly. Do not explain. Do not modify any other file.

        Iteration:
        2
