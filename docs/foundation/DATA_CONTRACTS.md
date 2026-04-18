# CrawlerNest Data Contracts

## Purpose

This document defines the minimum stable contracts that must exist before
product recommendation and agent-driven automation become first-class.

The primary goal is to keep data layers explicit:

- raw records
- normalized records
- canonical records
- warehouse records

## Contract 1: Main Data Flow

Every production-facing data feature must map onto this chain:

1. `crawl`
2. `extract`
3. `normalize`
4. `canonicalize`
5. `write`
6. `query`

If a feature bypasses this chain, it must be clearly labeled as preview or experimental.

## Contract 2: Admission MVP Fields

The minimum admission extraction contract is:

- `university_name`
- `program_name` or `faculty_name` when available
- `degree_level`
- `ielts_requirement`
- `toefl_requirement`
- `gpa_requirement`
- `deadline`
- `source_url`
- `extracted_at`

### Required Raw Preservation

For each controlled crawl, the system must preserve:

- raw HTML
- raw extracted text
- extracted JSON

This is required for:

- debugging
- regression evaluation
- extractor verification

## Contract 3: Ranking MVP Fields

The minimum ranking contract is:

- `source`
- `ranking_year`
- `scope`
- `institution_name`
- `rank`
- `country`
- `region` when derivable
- `source_url`
- `canonical_university_id` after resolution

## Contract 4: Canonical Resolution

Canonical resolution must explicitly distinguish:

- raw source identity
- normalized identity
- canonical identity

Canonical alignment must support:

- admission to ranking linking
- alias normalization
- country normalization
- repeated-source consolidation

Examples that must resolve cleanly:

- `MIT` -> `Massachusetts Institute of Technology`
- `UK` -> `United Kingdom`
- multiple pages from the same university -> one `canonical_university_id`

## Contract 5: Warehouse Semantics

Formal warehouse data must be queryable independently of preview/demo paths.

Warehouse-backed APIs must expose:

- stable pagination
- stable metadata
- explicit filter semantics
- clear distinction between total matches and current page rows

Formal product routes must not silently depend on:

- preview tables
- demo seed records
- temporary staging paths

## Contract 6: Recommendation Inputs

Admission-aware recommendation may only be considered valid when these inputs are explicit:

- `country`
- `target_rank`
- `ielts` and/or `toefl`
- `risk_profile`

Recommendation factors must remain explainable:

- ranking position
- admission fit
- completeness
- source coverage

Output must explain:

- why selected
- why risky
- what information is missing

## Contract 7: Preview vs Formal

Every route, table, and service must clearly be one of:

- `preview`
- `formal`
- `experimental`

Preview and experimental paths are allowed for development, but:

- they must not back formal product claims
- they must not silently replace warehouse truth

## Contract 8: Evaluation Readiness

Before any agent-generated patch can be considered beyond suggestion level,
the underlying target path must have:

- rerunnable evaluation
- baseline vs candidate comparison
- regression visibility

Without this, data-affecting automation is considered unsafe.

## Release Gate Checklist

A data path is ready for downstream product use only if:

- crawl output is rerunnable
- extraction is human-checkable
- normalization rules are explicit
- canonical mapping is non-trivially complete
- warehouse write is stable
- API semantics are fixed

If any one of these fails, downstream recommendation and autonomous agent change
must remain gated.

