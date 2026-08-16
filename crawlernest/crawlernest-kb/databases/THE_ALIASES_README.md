# `the_university_aliases_2026.json`

112 reviewed name variants that let the entity resolver match a canonical
university to its THE entity. Seeded into `warehouse.university_alias`, which the
resolver reads into every `CanonicalProfile` and matches against.

## Why this file exists

The alias table was empty, so resolution was effectively exact-display-name only
and 530 of 1,499 universities carried no THE rank. Most of them were in THE all
along, under a translated or repunctuated version of the same name:

| Canonical (QS) | THE |
| --- | --- |
| Universidade de São Paulo | University of São Paulo |
| Osaka University | The University of Osaka |
| Humboldt-Universität zu Berlin | Humboldt University of Berlin |
| Universiti Malaya (UM) | University of Malaya |
| Yonsei University | Yonsei University (Seoul campus) |

Seeding these took two-source coverage from 969 to 1,080.

## How the pairs were chosen

Not by similarity scoring. A fuzzy matcher on this data pairs Tokyo Institute of
Technology with MIT, University of British Columbia with University of Northern
British Columbia, and University of East London with University of West London —
the names are close and the institutions are not.

Every pair here satisfies all of:

1. **Same country**, after normalising the spellings the two sources use for one
   country ("Russia" / "Russian Federation", "China" / "China (mainland)").
2. **Identical content words**, once accents are folded, punctuation dropped, a
   trailing parenthetical removed, and the *language* of the word "university"
   collapsed — `Universidad`, `Universität`, `Universiteit` all become
   `university`. No content word is ever removed. Treating "science" or
   "national" as noise is exactly what made Tokyo Tech look like MIT.
3. **One-to-one in both directions**: the THE entity matches no other canonical
   university, and the canonical university matches no other THE entity. Word
   order cannot separate "University of Washington" from "Washington University",
   so this is the check that does.

All 112 passed the one-to-one test with zero collisions.

## What is still missing

419 universities have no THE rank. Some are genuinely outside THE's table;
others are name variants no rule here can reach — renames (Tokyo Institute of
Technology is now Institute of Science Tokyo), abbreviation-only forms, and
campus qualifiers that cannot be told from a different institution's name
("Purdue University" vs "Purdue University West Lafayette" is safe;
"Nagoya University" vs "Nagoya City University" is not). Those need a human, one
at a time, which is why they are not here.

A missing THE rank is disclosed as our matching gap rather than as THE declining
to rank the university — see `AnalyticsService.appendSourceCoverageCaveats`.
