

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