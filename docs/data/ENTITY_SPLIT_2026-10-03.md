# 2026-10-03: seven source entities taken off another university's canonical

**What.** Seven source entities were attached to a canonical university that is a different institution.
Two universities on one canonical keep one rank per edition and silently drop the other, so the damage was
missing rows and rows credited to the wrong university, not only a wrong label. The repair is
`crawlernest/scripts/split_false_entity_merges.py` (decision table, phases, and the reasons are in its
docstring), tested by `crawlernest-tests/test_split_false_entity_merges.py`.

| Entity | Was on | Now on | Evidence |
|---|---|---|---|
| THE 131462, QS `/universities/miami-university` | c1262 "Miami University" | c694537 **Miami University** (Ohio, new) | QS and THE list it separately from the University of Miami |
| (c1262 itself) | "Miami University" | renamed **University of Miami**, slug `university-of-miami` | THE 636, ARWU `university-of-miami`, QS `university-miami` are the Florida university |
| THE 624081 Kazan National Research Technical University | c1247 (Technological University) | c694538 (new) | THE lists both; fuzzy match 0.88 |
| THE 639095 UNIRIO | c560898 (UFRJ) | c1484 (existing: Universidade Federal do Estado do Rio de Janeiro) | different university |
| THE 131404 ENS Paris-Saclay | c561011 (ENS Paris) | c694539 (new) | THE lists both (523 and 131404) |
| THE 715159 National Taichung University of Science and Technology | c389 (Taiwan Tech) | c694540 (new) | different university |
| THE 623826 Jiangxi University of Finance and Economics | c363854 (Guangxi) | c694541 (new) | different province; collided with nothing |

THE 624069 (Irkutsk National Research Technical University) got a `rejected` review: once a canonical named
"Kazan National Research Technical University" existed, the replay fuzzy-matched Irkutsk to it (0.83). Found by
rehearsing on a copy, not by guessing.

**Why it happened.** Name normalisation treats "Miami University" and "University of Miami" as one string
(`exact`), which is how the University of Miami reached a canonical that was seeded from QS's Miami University
(the legacy bridge, `warehouse.universities` 1262, is Ohio's). The other five were fuzzy matches (0.85-0.90) made
when THE 2015-2024 was ingested on 2026-10-02. The other 30 fuzzy mappings made that day (QS and THE) were read
one by one and look right, except THE "Islamic Azad University Karaj" -> "Islamic Azad University." (c364060),
which is **unchanged and unverified**.

**What changed in the database** (rehearsed on a restored copy first; the real run matched it exactly):
the rename; five canonicals; the legacy bridge row of 1262 moved to the Ohio canonical; seven `remapped` and one
`rejected` rows in `warehouse.mapping_review` (decided_by names Claude Code at the user's direction); THE 2016-2026
replayed from the committed files; QS 2026 `world` and `region:north-america` replayed from their snapshots;
Ohio's QS rows for 2025 global and 2026 special/sustainability moved by id; four rows of the derived
`ranking_decision_preview` rewritten. No row count went down anywhere; rows that had been displaced came back
(THE +1 to +2 per affected edition, QS 2026 +1 global and +1 North America, the new canonicals' own rows).
Backup: `backups/entity_split_before_20261003T035124Z.dump`, restore with
`pg_restore -h localhost -U test -d clawer --clean --if-exists <that file>`.

**Why not the obvious shortcuts.**
- `decision-ranking-preview` was not run. It inserts with `ON CONFLICT DO NOTHING`, so it would have left the stale
  `miami university` rows (a blend of both universities) and added about fifteen thousand rows for editions the
  preview table never held.
- QS 2025 `world` was not replayed. Its prune would delete 13 legacy rows carrying a `relabelled_on` note that are in
  no snapshot.

**Slugs.** `/universities/by-slug/miami-university` is now the Ohio university; the University of Miami is
`university-of-miami`. Anything that stored the old slug for what was mostly the Florida university now points at Ohio.

**Not repaired.**
- The 2025 QS snapshot has no row for the University of Miami, so it has no QS 2025 rank. 2026 `special:sustainability`
  has no verified snapshot, so a Florida row there, if QS ranked one, cannot be restored.
- ~~`analytics.ml_predictions` held 15 rows for c1262 computed while it was a blend.~~ **Regenerated 2026-10-04** (01:06 +08)
  (`ml_run_id` 1043 and 1044; both targets re-run, older runs are kept as history). The old latest rows were wrong in a
  specific way: the overall-score estimate (11.9403) and the disagreement probability (0.7970) stored under the
  University of Miami (c1262) belonged to the QS row of Miami University (Ohio), not to Florida. Now the estimate sits
  on the Ohio canonical (c694537, 11.9403, unchanged), and c1262 carries its own disagreement probability (0.0090;
  Ohio's is 0.4164). The disagreement run now has 1,483 rows, up from 1,482, and records the retrained model
  (1,112 training rows, ROC-AUC 0.8437) instead of the 2026-09-14 one (1,109 rows, 0.8384): the other 1,470 rows moved
  by 0.023 on average because the model was retrained after the 2026-09-21 refresh, not because of the split. Backup
  taken first (`backups/ml_predictions_regen_pre_clawer_20261003T170618Z.dump`, a UTC stamp; gitignored).
- Nothing in the QS archive load is withheld for the entity split any more. QS's two Miami ids were reloaded into all
  seven archive editions on 2026-10-03 (`b89a6d5`), and so was Perugia (receipts under
  `crawlernest-kb/qs_archive/receipts/`). Perugia was not a missing review: a review for the new spelling was refused
  too, because `find_reappeared_reviews` flagged review 134 (the old spelling) as "reappeared" whenever a batch held
  the other spelling -- the two spellings slug to the same name -- without asking whether the new id had a review of its
  own. It now skips a batch row whose own id has a decision that applied and assigns the same canonical; a rejection,
  a different canonical, no decision, or a decision that did not itself apply is still refused (13 tests, each
  condition checked by removing it). Review 134 is untouched; the new spelling has its own, `confirmed` to c844.
  Two withholds remain, for other reasons: 2020 `/universities/university-paris` (matched a different institution)
  and 2023 `/universities/california-state-university-long-beach-college-business-administration`.
- Anything outside THE, ARWU and QS 2025/2026: the scan reads those files.

**Checking again.** `split_false_entity_merges.py verify --pg-password test` is read-only. It re-runs the collision scan
(a canonical with two actively mapped universities in one THE or ARWU edition), confirms the seven remaps, and fails if
anything other than those entities sits on a canonical this script created. Run it after any backfill that adds editions.
