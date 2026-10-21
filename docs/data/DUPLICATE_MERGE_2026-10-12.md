# 2026-10-12: one university carried as two records

**What.** 112 canonical universities were a second record of a university the warehouse already held. The repair is
`crawlernest/scripts/merge_duplicate_canonicals.py`; its decisions are the committed file
`crawlernest/crawlernest-kb/entity_merges/duplicate_canonicals_2026-10-12.json` (one entry per merge, with the evidence),
tested by `crawlernest-tests/test_merge_duplicate_canonicals.py`.

**Status.** The 112 merges of `duplicate_canonicals_2026-10-12.json` are applied to `clawer`: each merged-away record
is `status = 'merged'` and each survivor `active` (checked 2026-10-21). The Albany/Buffalo repair at the end of this
document -- `restore_rejected_entities.py`, then the two merges of `duplicate_canonicals_2026-10-12b.json` -- is not
applied yet: both of its merged-away records are still `active`. The figures below were measured on a rehearsal copy
of the warehouse (`clawer_rehearsal`).

**How it was found.** Matching universities to Wikipedia articles (`crawlernest-jobs/wikipedia_profile_loader.py`) put
two records on one article 102 times. Looking at what each record held: in 94 of those pairs the two never appear in
the same table of the same source in the same year. The data is complementary, which is what one university split in
two looks like.

**Why it happened.** THE and ARWU print "Ankara University"; the record QS seeded is "Ankara Üniversitesi". The
resolver had no way to know the two names are one university, so the THE/ARWU backfill of 2026-09-20 opened a new
record: 243 that day, of which at least 96 were duplicates. Nothing flagged it, because a duplicate is not a collision.

**What it cost.** In the 2026 global table 54 universities were listed twice, each row with fewer sources than the
university has (21 pairs were 1 + 1 sources, 32 were 1 + 2). Source count is what confidence is derived from, so the
confidence level and the composite position of both rows were wrong. Another 41 pairs had their history split, which
is what rank deltas and trends read.

| Decisions | Count | Evidence |
|---|---|---|
| Both records matched to one Wikipedia article, no table ranks both | 93 | `wikidata:<id>` |
| Same, plus one QS 2025 row held twice with the same rank (a legacy row with no source mapping and its mapped copy) | 6 | `wikidata:<id>`, `overlap: identical_rank` |
| Empty record whose only entity a mapping review had already remapped to the survivor | 11 | `mapping_review:<id>` |
| Read by name | 2 | `reviewed_by_name` (UPEC, INSA Toulouse) |

**What a merge does.** The loser's ranking rows, source mappings and aliases move to the survivor; the loser's name
becomes an alias of the survivor; a mapping review that decided an entity onto the loser is re-pointed; the loser stays
as `status = 'merged'` with `metadata.merged_into`, as the two merges of 2026-09-14 did. Then the aggregated rankings
of every table a survivor is in are recomputed, and the survivors' rows of `ranking_decision_preview` rewritten.
Survivors keep their name and slug. `/universities/by-slug/<loser slug>` still answers, with no rankings.

**Rehearsal** (on `clawer_rehearsal`, restored from a dump of `clawer`; repeated after the scheduled refresh of 2026-10-12 03:45 with the same counts):
1,150 ranking rows and 146 mappings moved, 108 aliases added, 6 reviews re-pointed, 6 legacy duplicates dropped. Among
universities not named in a merge, no source rank and no composite score changed; only positions shifted, because the
tables are shorter. 2026 global: 2,241 rows -> 2,188; universities with all three sources 608 -> 640. A second run does
nothing. `split_false_entity_merges.py verify` still reports no problems.

**Aliases withheld.** Four loser names were not made aliases, because the resolver tries aliases before display names
and ignores the country on an exact match: "Northeastern University (Shenyang)" is indexed as "Northeastern University"
too. The others are "University of New England", "National Polytechnic Institute" and "University of Los Andes
(Colombia)". `entity_resolution/alias_safety.py` is the check; the decision file says why for each.

## Keeping it from happening again

No rule turns "Universidad de Sevilla" into "University of Seville", so the fix is knowledge, not a cleverer match:

- `wikipedia_profile_loader.py aliases` writes `crawlernest-kb/databases/wikipedia_university_aliases_2026.json`: the
  English Wikipedia title of each matched university, 698 rows, for `seed_alias_file.py`. A title is left out if it is
  disambiguated with a parenthesis, shared by two records, or reachable as another record's name. Replayed against the
  duplicates above, it resolves 79 of the 112 loser names to the survivor. Re-resolving all 3,176 source names the
  warehouse has placed moves none of them off its record, and 9 more land on theirs.
- The resolver read "Türkiye" and "Turkey", and "Czechia" and "Czech Republic", as different countries, which narrowed
  fuzzy candidates to the wrong half and flagged right matches as country mismatches. Fixed in `_country_variants`.
- A folded key ("universidad"/"università"/... -> "university") was measured and not built: it would have caught 15 of
  the 112 and joins the University of Lagos with Universidad de Los Lagos.
- **After any backfill**, re-run `wikipedia_profile_loader.py match` and read the entries of `matches.json` that carry
  `shared_with`: two active records on one article is this defect.

## Not merged, and why

- **China University of Mining and Technology / (Beijing)**: two universities; QS ranks both in one table. Their
  shared Wikipedia article is withheld from the Beijing record in `wikipedia/en/overrides.json`.
- **University at Buffalo** (c464 and c560963): c560963 also holds QS 2026 rank 941 of
  `/universities/university-albany-state-university-new-york`, a `fuzzy_review` match to the wrong university. Albany
  has to come off first (see below).
- **ENS Paris-Saclay** (c694539) and "Ecole Normale Super Cachan" (c561063, ARWU): the same school, but c694539 was
  created by the 2026-10-03 split, whose `verify` pins what sits on it.
- **Lappeenranta University of Technology** (c561069): empty, but named in `warehouse.institution_lineage`.

## Found on the way: ranks that are missing, and one on the wrong university

Seven source entities were matched by `fuzzy_review` to a different university with a similar
name, and the match was then rejected in `warehouse.mapping_review` (reviews 15, 18, 20, 34, 40 by the
deterministic-collision rule; 230 and 232 by a person: "Henan is not Hunan"). A rejection withdraws the wrong credit
and stops there, so the entity resolves to nothing and every rank its source published for it is absent: 38 ARWU rows
and 1 THE row. The record each belongs on exists, created empty on 2026-09-20.

| Source entity | Rejected match | Belongs on (empty today) | Editions absent |
|---|---|---|---|
| ARWU `federal-university-of-sao-paulo` | c1138 UFSCar | c695 Universidade Federal de São Paulo (c560899 is an empty duplicate of it) | 2017-2026 |
| ARWU `henan-normal-university` | c363969 Hunan Normal | c560908 | 2021, 2023-2026 |
| ARWU `jiangsu-university-of-science-and-technology` | c562 Nanjing UST | c560912 | 2023-2026 |
| THE 685267 (the same university) | c562 Nanjing UST | c560912 | 2026 |
| ARWU `nanjing-university-of-chinese-medicine` | c1208 Beijing UCM | c560923 | 2020-2026 |
| ARWU `wuhan-university-of-science-and-technology` | c848 Wuhan UT | c561004 | 2021, 2023-2026 |
| ARWU `xian-university-of-technology` | c365635 Xi'an UST | c561005 | 2020-2026 |

One entity does hold a rank on the wrong university. QS renamed the University at Albany's page to
`/universities/university-albany-state-university-new-york` in the crawl of 2026-10-08; the new id was matched by
`fuzzy_review` (0.856) to c560963, "University at Buffalo, the State University of New York". Albany's QS 2026 world
rank (941) is therefore shown on a Buffalo record, and c882 "University at Albany SUNY" has no QS 2026 world rank.

**The repair** is `crawlernest/scripts/restore_rejected_entities.py`, the procedure of `ENTITY_SPLIT_2026-10-03.md`:
`prepare` turns each rejection into a `remapped` review naming the right record (the two a person wrote keep their
note and gain one), records a review for Albany and moves its one QS row; `replay` replays ARWU 2017-2026 and THE 2026
from the committed files; `verify` is read-only. Then `entity_merges/duplicate_canonicals_2026-10-12b.json` merges the
two records this frees: the Buffalo record into c464, and the empty c560899 into c695.

Rehearsed on a copy taken after the scheduled refresh of 2026-10-12 03:45: all 39 ranks restored and Albany's moved,
no existing rank or mapping target changed, the collision scan clean, and among universities not involved no source
rank or composite score changed. 2026 global ends at 2,226 rows, 654 of them with all three sources (608 before any
of this work).

**What the aliases did in the same replay.** With the Wikipedia-title aliases seeded, the replay also resolved 73
ranks that had been unresolved (69 of them THE 2026): THE's "Free University of Berlin" now finds "Freie Universitaet
Berlin". 63 of the new mappings are exact or normalised alias matches. Nine are fuzzy, and one of those was wrong:
THE 639047 "Ceará State University" matched "Universidade do Estado do Pará" at 0.8227 through the alias "Pará State
University". It is rejected (`apply_mapping_reviews.py`, then a second replay withdraws it), which is the hazard this
file's sibling warns of: a new name attracts fuzzy matches, so rehearse. The other eight (PUC-Rio, Guerrero,
Lobachevsky, San Martín, Nueva Granada, Politehnica Bucharest, Picardie, Rouen) were read and are right; seven of them
are `fuzzy_review` and wait in the review queue for a person to confirm.

Twelve more empty records from 2026-09-20 were not traced (c560922, c561009, c561019, c561035, c561044, c561047,
c561048, c561052, c561072, c561105, c561110, c561112).

## Still stale after the merge

- `analytics.ml_predictions` and the models behind it were computed against the old QS<->THE pairing. The merge adds
  pairs (a QS rank and a THE rank that sat on two records are now on one), so the estimates should be regenerated.
- Historical aggregation runs keep their rows for the merged records; only the latest run per table is read.
