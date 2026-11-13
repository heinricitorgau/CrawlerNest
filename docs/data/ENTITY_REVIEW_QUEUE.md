# The entity review queue

`crawlernest/scripts/entity_review_candidates.py build` lists what a person should look at for the two entity
defects this warehouse has had: one university carried as two records (docs/data/DUPLICATE_MERGE_2026-10-12.md)
and two universities on one record (docs/data/ENTITY_SPLIT_2026-10-03.md). It reads the warehouse in a read-only
session, writes `.local/reports/entity_review/candidates_<date>.{json,md}`, and changes nothing.

```bash
./.venv/bin/python crawlernest/scripts/entity_review_candidates.py build --pg-password test
```

Run it after any backfill, after `wikipedia_profile_loader.py match` (the shared-Wikidata signal reads its
`matches.json`).

## What it lists

| Signal | Kind | Listed when |
|---|---|---|
| `shared_wikidata` | duplicate | two active records are matched to one Wikidata item |
| `same_name_key` | duplicate | same country, and the names agree once generic words, accents and a parenthesis are dropped |
| `name_key_subset` | duplicate | same country, one key inside the other, **and** the records are complementary |
| `same_edition_collision` | false merge | one record holds two THE or ARWU entities of one edition |
| `unreviewed_fuzzy_mapping` | false merge | an active fuzzy mapping with no `mapping_review` decision |

Evidence against a pair (a source ranks both in one table; an `institution_lineage` row) is printed beside it
and makes it `low`. It does not hide it.

The name key is a way to find pairs for a person, not a matcher, and must not be used to decide a merge or an
alias. Replayed on the 112 merges of 2026-10-12 it finds 43 with an equal key and 56 with an equal key or a
subset; the other 56 are translations ("National Polytechnic Institute" / "Instituto Politécnico Nacional (IPN)").

**First run, 2026-11-13** (3,942 active records): 11 duplicate candidates (2 high, 5 medium, 4 low) and 40
mapping candidates (1 high, 17 medium, 22 low; no collisions), with the two documented non-duplicates
dismissed. The two high duplicates:

- *G d'Annunzio University of Chieti-Pescara*, an empty record beside the ranked *Universita' degli Studi "G.
  d'Annunzio" Chieti Pescara*. Its sibling *University of Chieti-Pescara* was merged on 2026-10-12.
- *Ecole Normale Super Cachan* and *École normale supérieure Paris-Saclay*, the pair DUPLICATE_MERGE left for
  later because the 2026-10-03 split's `verify` pins what sits on the Paris-Saclay record.

## How a candidate is decided

- **Same university**: add a merge to a new `crawlernest-kb/entity_merges/duplicate_canonicals_<date>.json`,
  rehearse on a copy, apply with `merge_duplicate_canonicals.py`.
- **Wrong university on a mapping**: a `remapped` decision in `warehouse.mapping_review`, as the 2026-10-03 split
  did; the next ingest applies it.
- **Fine as it is**: an entry in `crawlernest-kb/entity_merges/review_dismissed.json`, with the reason. The report
  lists dismissals that no longer match anything, so the file does not silently rot.

## The model hook

`--annotator` selects what writes `model_note`, advisory text beside a candidate. The only annotator is `none`.
A model annotator (Kimi K3 through its API, or the `kimi-k3-in-c` engine on a machine with the 1.7 TB it needs)
would be for the translations the key misses. Its note is read by a person; it never becomes a merge, a
mapping decision or an alias, and nothing from it is written to the warehouse. Adding one sends candidate
names, countries and rank summaries to wherever the model runs, which is why `test_entity_review_candidates`
fails until the test is changed with it.
