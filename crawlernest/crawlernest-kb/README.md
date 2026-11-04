# crawlernest-kb

Knowledge Base build scripts and database snapshots.

## Folders
- `databases/`: Contains JSON checkpoints and archived migration artifacts; PostgreSQL is the runtime source of truth.
- `wikipedia/en/`: The English Wikipedia article matched to each university that holds ranking data, shown as the
  introduction on the university page. Written by `crawlernest-jobs/wikipedia_profile_loader.py`; the warehouse table
  `warehouse.university_wikipedia_article` is a copy of these files.
  - `matches.json`: which article each university got and by which rule, and every unmatched university with the reason.
  - `articles/articles-NN.jsonl.gz`: the article text as sections, one article per line, each with its revision id and URL.
    Text is Wikipedia's, CC BY-SA 4.0.
  - `overrides.json` (optional): reviewed corrections, `{canonical_slug: {"title": "<article>" | null, "why": "..."}}`.
- `us_institutions/`: US federal institutional data (College Scorecard, IPEDS) for each US and Puerto Rico university
  matched to an IPEDS UNITID. Written by `crawlernest-jobs/us_institution_loader.py`; `warehouse.us_institution` and
  `warehouse.us_institution_metric` are a copy of these files. Not a ranking source. Public domain (U.S. federal works).
  - `matches.json`: the UNITID each university got (through its Wikidata item's IPEDS ID, P1771) and every unmatched
    university with the reason.
  - `manifest.json`: the federal files read, with their URL, size and SHA-256.
  - `records.json`: the chosen fields for the matched UNITIDs, one value per line, each with its source field and
    status; `fields` gives each field's reference period and release, verbatim from the source's documentation.
  - `overrides.json`: reviewed corrections, `{canonical_slug: {"unitid": "<UNITID>" | null, "why": "..."}}`.
- `entity_merges/`: Reviewed decisions that two canonical universities are one, applied by
  `crawlernest/scripts/merge_duplicate_canonicals.py`. Each entry names the record merged away, the survivor and the evidence.
