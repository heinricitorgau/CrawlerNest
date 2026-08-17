# `arwu_university_aliases_2026.json`

70 reviewed name variants that let the entity resolver match a canonical
university to its ARWU entity. Seeded into `warehouse.university_alias` by

```bash
python3 crawlernest/scripts/seed_alias_file.py \
  --alias-file crawlernest/crawlernest-kb/databases/arwu_university_aliases_2026.json \
  --pg-password test
```

which is idempotent — re-running inserts nothing — and takes `--dry-run`.

## Two kinds of row, and the file says which

Every entry carries a `method`:

| `method` | rows | what it rests on |
| --- | ---: | --- |
| `rule` | 48 | a stated normalisation, applied by `build_arwu_aliases` and checked one-to-one |
| `curated` | 22 | a fact about the institution that no rule here knows |

The distinction is the point of the field. A `rule` row can be re-derived by
anyone who runs the generator against the same two datasets. A `curated` row
cannot: it is an assertion that two names denote one institution, and it is only
as good as whoever made it. Those rows carry a `reason` stating the fact being
asserted — that Albert Ludwig is Freiburg's founding patron, that Unicamp is the
state university of Campinas and PUC-Campinas is a different school. A reviewer
who does not want to inherit those judgements can filter the file on `method`
and drop exactly 22 rows.

## The rules

The three conditions are the ones the THE aliases used, unchanged, because they
are the ones that have not produced a wrong match:

1. **Same country**, after normalising the spellings the two sources use.
2. **Identical content words**, after folding accents, dropping a trailing
   parenthetical, and collapsing the *language* of a word rather than the word
   itself. No content word is ever removed.
3. **One-to-one in both directions.**

Three normalisations were added for ARWU, all of them translations rather than
tolerances:

- `technical` / `technology` / `technische` fold together, which pairs
  *Technische Universität Dresden* with *Dresden University of Technology*.
- The Italian legal formula *degli studi* ("of the studies of") is dropped as a
  phrase, pairing *Università degli Studi di Pavia* with *University of Pavia*.
- Roman numerals fold to arabic, so Toulouse III meets Toulouse 3. Bare `I` is
  deliberately excluded: in Italian it is the plural article far more often than
  it is a university's number.

And one removal, which is the only rule here that can do real damage: a trailing
campus qualifier — after a comma, ` at ` or ` in ` — may be dropped from either
side. *Purdue University, West Lafayette* meets *Purdue University* this way. It
carries three guards:

- what remains must still be an institution name **with a distinctive word in
  it**. Without this, *University at Albany* strips to the bare word "University",
  a key that matches every institution in the country. Two of those collided and
  were rejected as ambiguous, which was the right answer reached by luck; a lone
  one would have matched something arbitrary.
- **`system` anywhere on either side disqualifies the pair.** A system is not a
  campus. The guard is read from the raw name, not the normalised words, because
  the normaliser strips parentheticals and *University of Minnesota (System)*
  carries the entire distinction inside its parenthetical.
- the one-to-one test runs over the stripped variants, so the several
  *University of California, X* entities collide with each other and are all
  rejected rather than racing for a bare *University of California*.

## What is deliberately not here

ARWU ranks *University of Minnesota, Twin Cities*; the canonical row is
*University of Minnesota (System)*. The rule rejects the pair and it has not
been added by hand. Overriding a rule by hand, in the same file the rule wrote,
is not a habit worth starting — and the omission being visible here is worth
more than the one row.

The weakest row in the file is Tokyo: ARWU's *Institute of Science Tokyo* is
mapped to the canonical *Tokyo Institute of Technology*. That is a succession,
not a rename — Tokyo Tech merged with Tokyo Medical and Dental University in
2024 — and it is the one pair whose identity is genuinely arguable. It is
included because the alternative reports Tokyo Tech as unranked by ARWU, which
is the more misleading of the two available errors. Its `reason` says so.

## What is still missing

291 of the 1,000 ARWU entities are unmatched. Re-running the generator against
the seeded database now proposes nothing, so this is what the rules can reach.
They fall into four groups:

- **167 have no close name in their country.** ARWU ranks many regional and
  specialist institutions that QS does not, so most of these have nothing to
  match against and never will.
- **8 have no canonical university in that country at all, or share a name with
  one somewhere else** — *Northeastern University (Shenyang)* against the
  Boston one, for instance, which is exactly what condition 1 is for.
- **116 are same-country near misses that rules must not touch.** This is the
  dangerous group, and it is why nothing here is similarity-scored. Among the
  closest name pairs in the data are *Sichuan Agricultural University* /
  *Sichuan University*, *North Dakota State University* / *North Carolina State
  University*, and *University of California, San Francisco* / *University of
  San Francisco* — three different institutions in each case. A matcher tuned
  loosely enough to catch the real variants catches these too.
- **A handful are genuinely one institution under two names** and need a person
  to say so, one at a time, the way the 22 curated rows were.

A missing ARWU rank is disclosed as our matching gap rather than as ARWU
declining to rank the university — see `AnalyticsService.appendSourceCoverageCaveats`.
