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
