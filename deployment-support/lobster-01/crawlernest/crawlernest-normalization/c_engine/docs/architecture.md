# Clawer C Data Normalization Engine – Architecture

## Overview

The Clawer C Data Normalization Engine is a modular C-based data processing pipeline designed to normalize university ranking datasets. The system ingests raw CSV data, cleans and standardizes fields, and exports normalized output for further analysis.

Pipeline:

Raw CSV → CSV Reader → Normalization Modules → CSV Writer → Normalized CSV


## Input Dataset Format

The system expects a CSV file with the following column order:

QS Rank,University,Country,GMAT,GRE,GPA,IELTS,TOEFL,Duolingo,Overall Score,URL

Only a subset of columns is currently used:

| Column | Used For |
|------|------|
| QS Rank | rank parsing |
| University | name normalization |
| Country | country normalization |
| Overall Score | score parsing |

All other columns are ignored but preserved in the dataset structure for possible future extensions.


## Core Modules

### CSV Reader

File: `src/csv_reader.c`

Responsibilities:

- Load CSV file
- Split rows into fields
- Map CSV columns into internal data structures
- Skip header row

Important constants:

MAX_FIELDS = 11


### Record Structure

File: `include/record.h`

Represents a single university record.

Stores both:

- Raw values
- Normalized values

Fields include:

- raw_name
- raw_country
- raw_rank
- raw_score
- normalized_name
- normalized_country
- rank_min
- rank_max
- score


### Normalization Pipeline

File: `src/normalizer.c`

This module orchestrates all normalization steps.

Steps:

1. Name normalization
2. Country normalization
3. Rank parsing
4. Score parsing


### Name Normalizer

File: `src/name_normalizer.c`

Responsibilities:

- Remove punctuation
- Convert to lowercase
- Collapse whitespace


### Country Normalizer

File: `src/country_normalizer.c`

Standardizes country names.

Examples:

U.S.A. → United States
ROC → Taiwan


### Rank Parser

File: `src/rank_parser.c`

Parses ranking strings.

Supported formats:

53
101-150
Top 100

Outputs:

rank_min
rank_max


### Score Parser

File: `src/score_parser.c`

Extracts numeric scores from strings.

Examples:

98.4
Score: 91.25

Invalid scores are stored as -1.


### CSV Writer

File: `src/csv_writer.c`

Exports normalized records to a CSV file.

Output schema:

University,Country,Rank Min,Rank Max,Overall Score

If score is invalid (<0), an empty value is written.


## CLI Application

File: `src/main.c`

Provides a simple interactive menu.

Menu:

1. Load CSV data
2. Show raw records
3. Run normalization pipeline
4. Show normalized records
5. Export normalized CSV


## Testing

File: `src/tests/test_normalizer.c`

Unit tests cover:

- name normalization
- country normalization
- rank parsing
- score parsing
- full normalization pipeline

Tests can be executed using:

make test


## Build System

The project uses a Makefile-based build system.

Main commands:

make
make run
make test
make clean


## Directory Structure

```
clawer_c_data_normalization_engine
│
├── src
│   ├── main.c
│   ├── csv_reader.c
│   ├── csv_writer.c
│   ├── normalizer.c
│   ├── name_normalizer.c
│   ├── country_normalizer.c
│   ├── rank_parser.c
│   ├── score_parser.c
│   └── utils.c
│
├── include
│   ├── record.h
│   ├── csv_reader.h
│   ├── csv_writer.h
│   └── normalizer.h
│
├── src/tests
│   └── test_normalizer.c
│
├── docs
│   └── architecture.md
│
└── data
    └── samples
```


## Future Improvements

Potential next steps:

- Header validation for CSV input
- Robust CSV parsing (quoted fields)
- Streaming parser for large datasets
- Benchmarking tools
- CI integration for automated testing