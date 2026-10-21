# `qs_university_aliases_2026.json`

Reviewed QS names for a canonical university the resolver would otherwise not reach. Seeded into
`warehouse.university_alias` with `crawlernest/scripts/seed_alias_file.py`; `test_alias_files.py` holds it to the
same rules as the THE and ARWU files (one-to-one, a reason on every `curated` row, ids that still exist).

QS's own names normally resolve by exact display name, because QS seeded most records. A row belongs here only when
QS renames the page of a ranked entry and the new name matches nothing:

| Alias | Canonical | Why |
| --- | --- | --- |
| Northumbria University QAHE- London campus | 534 Northumbria University at Newcastle | QS moved rank 550 to the London campus page in the crawl of 2026-10-21 |

Seed with `seed_alias_file.py`, which keeps the file and the table in step. Until 2026-10-21 `run_pipeline
seed-university-alias` also rewrote the canonical's `display_name_normalized` in title case, which
`ranking_decision_preview` joins on; it now leaves an existing canonical untouched (`test_alias_seed.py`).
