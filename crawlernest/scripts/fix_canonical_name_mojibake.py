#!/usr/bin/env python3
from __future__ import annotations

"""
Correct the canonical names QS served damaged, and keep its spelling resolving.

Two canonical universities carry a name that is not a name. QS's payload holds
"Juà¡rez" and "Tucumà¡n" -- the letter á arriving as the two characters
à and ¡ -- and the fetch layer copied it faithfully, which is the right
behaviour for a crawler and the wrong thing to show a reader. Unlike the control
characters text_hygiene recovers, no decode rule gets á back out of this: the
lead byte is gone, so the repair is a statement about these two institutions
rather than a transformation, and that is why it lives in a reviewable list here
instead of in the ingest.

Both halves matter and the second is easy to forget:

  1. the canonical row gets the correct display name, its normalized form and the
     slug the pipeline's own builder makes of it;
  2. the spelling QS sends is recorded in warehouse.university_alias, so QS's
     next payload still resolves to this university.

Without (2) the fix breaks what it was meant to help. exact_display matching
compares the source's name against the canonical display name, and the
normalised forms of the two spellings differ -- "universidad nacional de
tucuman" against "universidad nacional de tucuma n" -- so correcting the name
alone would drop the university into the unresolved log at the next crawl.

    # show what would change; writes nothing
    ./.venv/bin/python crawlernest/scripts/fix_canonical_name_mojibake.py

    # write it
    ./.venv/bin/python crawlernest/scripts/fix_canonical_name_mojibake.py --commit

Each correction is applied only if the stored name is still exactly the damaged
one recorded below. A row somebody has since edited is reported and skipped
rather than overwritten.
"""

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_ROOT = REPO_ROOT / "crawlernest"
for _path in (MODULE_ROOT / "crawlernest-core", REPO_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from crawlernest_ranking_crawler.alias_seed import _build_canonical_slug  # noqa: E402
from entity_resolution.normalizer import normalize_university_name  # noqa: E402

try:
    import psycopg2
except ImportError:  # pragma: no cover - the script cannot run without it
    psycopg2 = None  # type: ignore[assignment]

#: Why this alias exists, written into university_alias.source_name so the next
#: reader of that row does not have to rediscover it.
ALIAS_SOURCE_NAME = "QS payload spelling, mojibake corrected 2026-09-22"


@dataclass(frozen=True)
class NameCorrection:
    canonical_university_id: int
    damaged: str
    correct: str
    #: What establishes the correct spelling. Deliberately per row: the evidence
    #: is not the same strength for both.
    evidence: str


CORRECTIONS: tuple[NameCorrection, ...] = (
    NameCorrection(
        canonical_university_id=364917,
        damaged="Universidad Autónoma de Ciudad Juà¡rez (UACJ)",
        correct="Universidad Autónoma de Ciudad Juárez (UACJ)",
        evidence=(
            "THE's 2025 table prints 'Universidad Autónoma de Ciudad Juárez' "
            "correctly, and that row is in this warehouse -- so the correct spelling "
            "is corroborated by a second source we hold rather than asserted."
        ),
    ),
    NameCorrection(
        canonical_university_id=1457,
        damaged="Universidad Nacional de Tucumà¡n",
        correct="Universidad Nacional de Tucumán",
        evidence=(
            "No other source in this warehouse prints this university, so there is "
            "no second copy to compare against. The reading rests on the byte: "
            "¡ is 0xA1, the continuation byte of á in UTF-8 (C3 A1), and the "
            "letters around it spell 'Tucum_n' in an Argentine university's name. "
            "á is the only reading that is both a letter and that name."
        ),
    ),
)


@dataclass(frozen=True)
class Planned:
    correction: NameCorrection
    stored_name: Optional[str]
    stored_slug: Optional[str]
    new_normalized: str
    new_slug: str
    alias_exists: bool

    @property
    def applicable(self) -> bool:
        return self.stored_name == self.correction.damaged


def plan(conn) -> list[Planned]:
    out: list[Planned] = []
    with conn.cursor() as cur:
        for correction in CORRECTIONS:
            cur.execute(
                """
                SELECT display_name, canonical_slug
                  FROM warehouse.canonical_university
                 WHERE canonical_university_id = %s
                """,
                (correction.canonical_university_id,),
            )
            row = cur.fetchone()
            stored_name, stored_slug = (row if row else (None, None))

            cur.execute(
                """
                SELECT 1 FROM warehouse.university_alias
                 WHERE canonical_university_id = %s AND alias_text = %s
                """,
                (correction.canonical_university_id, correction.damaged),
            )
            alias_exists = cur.fetchone() is not None

            normalized = normalize_university_name(correction.correct)
            out.append(
                Planned(
                    correction=correction,
                    stored_name=stored_name,
                    stored_slug=stored_slug,
                    new_normalized=normalized,
                    new_slug=_build_canonical_slug(correction.correct, normalized),
                    alias_exists=alias_exists,
                )
            )
    return out


def apply(conn, planned: list[Planned]) -> int:
    applied = 0
    with conn.cursor() as cur:
        for item in planned:
            if not item.applicable:
                continue
            correction = item.correction
            # The damaged spelling becomes an alias first: for the moment between
            # the two statements the source's name must still reach this row.
            if not item.alias_exists:
                cur.execute(
                    """
                    INSERT INTO warehouse.university_alias (
                        canonical_university_id, alias_text, alias_normalized,
                        source_name, is_primary, is_abbreviation
                    )
                    VALUES (%s, %s, %s, %s, FALSE, FALSE)
                    """,
                    (
                        correction.canonical_university_id,
                        correction.damaged,
                        normalize_university_name(correction.damaged),
                        ALIAS_SOURCE_NAME,
                    ),
                )
            cur.execute(
                """
                UPDATE warehouse.canonical_university
                   SET display_name = %s,
                       display_name_normalized = %s,
                       canonical_slug = %s,
                       updated_at = CURRENT_TIMESTAMP
                 WHERE canonical_university_id = %s
                   AND display_name = %s
                """,
                (
                    correction.correct,
                    item.new_normalized,
                    item.new_slug,
                    correction.canonical_university_id,
                    correction.damaged,
                ),
            )
            applied += cur.rowcount
    return applied


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", action="store_true", help="actually write; without it this only reports")
    parser.add_argument("--pg-host", default=os.environ.get("CRAWLERNEST_PG_HOST", "localhost"))
    parser.add_argument("--pg-port", type=int, default=int(os.environ.get("CRAWLERNEST_PG_PORT", "5432")))
    parser.add_argument("--pg-database", default=os.environ.get("CRAWLERNEST_PG_DATABASE", "clawer"))
    parser.add_argument("--pg-user", default=os.environ.get("CRAWLERNEST_PG_USER", "test"))
    parser.add_argument("--pg-password", default=os.environ.get("CRAWLERNEST_PG_PASSWORD", "test"))
    args = parser.parse_args()

    if psycopg2 is None:
        raise SystemExit("psycopg2 is required")

    conn = psycopg2.connect(
        host=args.pg_host,
        port=args.pg_port,
        dbname=args.pg_database,
        user=args.pg_user,
        password=args.pg_password,
    )
    conn.set_client_encoding("UTF8")
    try:
        planned = plan(conn)
        for item in planned:
            correction = item.correction
            print(f"canonical {correction.canonical_university_id}")
            print(f"  stored     : {item.stored_name!r}")
            if not item.applicable:
                print("  SKIPPED    : the stored name is not the damaged one recorded here")
                print(f"  expected   : {correction.damaged!r}")
                continue
            print(f"  display    : {correction.correct!r}")
            print(f"  normalized : {item.new_normalized!r}")
            print(f"  slug       : {item.stored_slug!r} -> {item.new_slug!r}")
            print(f"  alias      : {'already present' if item.alias_exists else 'adding ' + repr(correction.damaged)}")
            print(f"  evidence   : {correction.evidence}")

        if not args.commit:
            print("\nReport only. Nothing was written. Re-run with --commit to apply.")
            return 0

        applied = apply(conn, planned)
        conn.commit()
        print(f"\nCorrected {applied} canonical name(s); the damaged spellings are aliases now.")
        print("Re-ingest the affected source to confirm it still resolves:")
        print("  the QS universe for the edition that holds them.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
