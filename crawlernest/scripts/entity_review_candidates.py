#!/usr/bin/env python3
"""Build the entity review queue: record pairs and source mappings a person should look at.

Read-only. It never merges, splits or remaps anything; it writes a report under
``.local/reports/entity_review/`` that a person reads, and what they decide goes through the
tools that already apply decisions:

  * one university carried as two records -> a ``crawlernest-kb/entity_merges/duplicate_canonicals_<date>.json``
    entry, applied by ``merge_duplicate_canonicals.py`` (see docs/data/DUPLICATE_MERGE_2026-10-12.md);
  * a source entity attached to the wrong university -> a ``warehouse.mapping_review`` decision, the path
    ``split_false_entity_merges.py`` used (docs/data/ENTITY_SPLIT_2026-10-03.md);
  * a candidate that is fine as it is -> an entry in ``crawlernest-kb/entity_merges/review_dismissed.json``,
    so the next run does not list it again.

Two kinds of defect, five signals:

  duplicate (one university, two active records)
    shared_wikidata     both records are matched to one Wikidata item in wikipedia/en/matches.json
    same_name_key       same country, and the names agree once generic words ("university", "universidad",
                        "of", ...) are dropped, accents folded, a parenthesis removed and a few common words
                        translated ("autonoma" -> "autonomous"). Listed whatever the coverage says.
    name_key_subset     same country, one name's key is contained in the other's, AND the two records are
                        complementary (ranked in a shared year, never by one source in one table). Alone, a
                        subset is mostly noise ("North Dakota State" / "North Dakota").

  false merge (two universities on one record)
    same_edition_collision  one record holds two THE or ARWU entities of one edition
                            (split_false_entity_merges.collision_scan)
    unreviewed_fuzzy_mapping  an active fuzzy / fuzzy_review mapping no mapping_review has decided

The name key is a candidate generator for a person, not a matcher. It must never decide a merge or an
alias: it reads "Lagos" and "Los Lagos" alike, which is why the Wikipedia matching and the resolver do not
use it (CLAUDE.md, "never by a similar name"). Replayed against the 112 merges of 2026-10-12, an equal key
finds 43 and an equal key or a subset 56; the rest are translations no word list covers ("Hannover Medical
School" / "Medizinische Hochschule Hannover" is caught, "National Polytechnic Institute" / "IPN" is not).
That remainder is what a model annotator would be for.

Evidence against a pair is reported beside it, not used to hide it: a source ranking both records in one
table says they are two universities, and an ``institution_lineage`` row says they are a predecessor and a
successor. Such pairs are listed with priority ``low``.

A model may later be asked to annotate a candidate. That is the ``Annotator`` hook, and its output is
``model_note``: advisory text a person reads, never a decision, never written to the warehouse. The only
annotator today is ``none``, so nothing leaves this machine.

    ./.venv/bin/python crawlernest/scripts/entity_review_candidates.py build --pg-password test
"""
from __future__ import annotations

import argparse
import datetime as _dt
import itertools
import json
import re
import sys
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional, Protocol, Sequence

_HERE = Path(__file__).resolve()
_MODULE_ROOT = _HERE.parents[1]  # crawlernest/
_REPO_ROOT = _HERE.parents[2]

KB_DIR = _MODULE_ROOT / "crawlernest-kb"
MATCHES_PATH = KB_DIR / "wikipedia" / "en" / "matches.json"
DISMISSED_PATH = KB_DIR / "entity_merges" / "review_dismissed.json"
REPORT_DIR = _REPO_ROOT / ".local" / "reports" / "entity_review"

KIND_DUPLICATE = "duplicate"
KIND_MAPPING = "mapping"

SIG_SHARED_WIKIDATA = "shared_wikidata"
SIG_SAME_NAME_KEY = "same_name_key"
SIG_NAME_KEY_SUBSET = "name_key_subset"
SIG_COLLISION = "same_edition_collision"
SIG_UNREVIEWED_FUZZY = "unreviewed_fuzzy_mapping"

COVERAGE_BOTH = "source_ranks_both"
COVERAGE_COMPLEMENTARY = "complementary"
COVERAGE_NO_SHARED_YEAR = "no_shared_year"

FUZZY_METHODS = ("fuzzy", "fuzzy_review")

# ---------------------------------------------------------------------------------------------- name key

#: Words that say "a university" in some language, and connectives. Dropped from the key.
GENERIC_WORDS = frozenset({
    "university", "universidad", "universidade", "universite", "universita", "universitat", "universiteit",
    "universitet", "universitas", "universitesi", "universiti", "uniwersytet", "univerzita", "univerzitet",
    "universitatea", "universitaet", "univ", "studi", "studies",
    "of", "de", "the", "la", "le", "del", "di", "des", "du", "da", "do", "degli", "dos", "das", "der",
    "and", "y", "e", "et", "und", "at", "in", "i", "a",
})

#: A few words that differ only by language. Mapped to the English form before comparing.
TRANSLATIONS = {
    "autonoma": "autonomous", "autonome": "autonomous", "federale": "federal",
    "tecnica": "technical", "technische": "technical", "tecnologica": "technological",
    "technologique": "technological", "nacional": "national", "nationale": "national", "nazionale": "national",
    "politecnico": "polytechnic", "politecnica": "polytechnic", "polytechnique": "polytechnic",
    "medizinische": "medical", "medica": "medical", "hochschule": "school", "escuela": "school", "ecole": "school",
    "catolica": "catholic", "catholique": "catholic", "cattolica": "catholic", "katholieke": "catholic",
    "libre": "free", "freie": "free", "libera": "free", "estadual": "state", "estatal": "state",
    "statale": "state", "pontificia": "pontifical", "instituto": "institute", "institut": "institute",
    "istituto": "institute", "sciences": "science", "ciencias": "science", "scienze": "science",
    "appliquees": "applied", "aplicadas": "applied", "angewandte": "applied", "tecnologia": "technology",
    "technologie": "technology", "agraria": "agriculture", "agricultural": "agriculture",
    "agronomica": "agriculture", "norte": "north", "nord": "north", "sul": "south", "sur": "south",
    "sud": "south",
}


def name_key(name: str) -> frozenset[str]:
    """The distinctive words of a university name, order-free. Empty when nothing distinctive is left."""
    text = re.sub(r"\([^)]*\)", " ", str(name or ""))
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower().replace("ı", "i")
    words = (TRANSLATIONS.get(w, w) for w in re.split(r"[^a-z0-9]+", text) if w and w not in GENERIC_WORDS)
    return frozenset(words)


def key_relation(a: frozenset[str], b: frozenset[str]) -> Optional[str]:
    """``same_name_key``, ``name_key_subset`` or None. A subset needs two words on the smaller side."""
    if not a or not b:
        return None
    if a == b:
        return SIG_SAME_NAME_KEY
    if (a < b or b < a) and min(len(a), len(b)) >= 2:
        return SIG_NAME_KEY_SUBSET
    return None


# ---------------------------------------------------------------------------------------------- records

#: One ranking table: (source, year, ranking_type, universe_type, universe_key).
Table = tuple[str, int, str, str, str]


@dataclass(frozen=True)
class Record:
    canonical_id: int
    slug: str
    name: str
    country: Optional[str]
    wikidata_id: Optional[str] = None
    tables: frozenset[Table] = frozenset()

    @property
    def years(self) -> frozenset[int]:
        return frozenset(t[1] for t in self.tables)

    @property
    def sources(self) -> frozenset[str]:
        return frozenset(t[0] for t in self.tables)

    def brief(self) -> dict[str, Any]:
        return {
            "canonical_id": self.canonical_id, "slug": self.slug, "name": self.name, "country": self.country,
            "wikidata_id": self.wikidata_id, "sources": sorted(self.sources),
            "years": [min(self.years), max(self.years)] if self.years else [],
        }


def coverage(a: Record, b: Record) -> tuple[str, list[str]]:
    """How the two records' ranks relate, and the tables a source ranks both in (at most five)."""
    both = sorted(a.tables & b.tables)
    if both:
        return COVERAGE_BOTH, [f"{s} {y} {rt}/{ut}:{uk}" for s, y, rt, ut, uk in both[:5]]
    if a.years & b.years:
        return COVERAGE_COMPLEMENTARY, []
    return COVERAGE_NO_SHARED_YEAR, []


@dataclass
class Candidate:
    kind: str
    signals: list[str]
    subject: dict[str, Any]
    evidence: list[str] = field(default_factory=list)
    against: list[str] = field(default_factory=list)
    priority: str = "medium"
    model_note: Optional[str] = None

    @property
    def key(self) -> tuple:
        if self.kind == KIND_DUPLICATE:
            return (KIND_DUPLICATE, frozenset(r["slug"] for r in self.subject["records"]))
        return (KIND_MAPPING, self.subject["source_code"], str(self.subject["source_entity_id"]))

    def to_json(self) -> dict[str, Any]:
        return {"kind": self.kind, "priority": self.priority, "signals": self.signals, "subject": self.subject,
                "evidence": self.evidence, "against": self.against, "model_note": self.model_note}


_PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def duplicate_candidates(records: Sequence[Record],
                         lineage: Iterable[tuple[int, int, str]] = ()) -> list[Candidate]:
    """Pairs of active records that may be one university. ``lineage`` is (predecessor, successor, type)."""
    related = {frozenset((p, s)): t for p, s, t in lineage}
    found: dict[frozenset[int], Candidate] = {}

    def add(a: Record, b: Record, signal: str, evidence: str) -> None:
        pair = frozenset((a.canonical_id, b.canonical_id))
        if pair not in found:
            first, second = sorted((a, b), key=lambda r: r.canonical_id)
            found[pair] = Candidate(KIND_DUPLICATE, [], {"records": [first.brief(), second.brief()]})
        cand = found[pair]
        if signal not in cand.signals:
            cand.signals.append(signal)
            cand.evidence.append(evidence)

    by_wikidata: dict[str, list[Record]] = defaultdict(list)
    for r in records:
        if r.wikidata_id:
            by_wikidata[r.wikidata_id].append(r)
    for qid, group in by_wikidata.items():
        for a, b in itertools.combinations(group, 2):
            add(a, b, SIG_SHARED_WIKIDATA, f"both matched to Wikidata {qid} (wikipedia/en/matches.json)")

    by_country: dict[Optional[str], list[tuple[Record, frozenset[str]]]] = defaultdict(list)
    for r in records:
        by_country[r.country].append((r, name_key(r.name)))
    for country, group in by_country.items():
        if country is None:
            continue
        for (a, ka), (b, kb) in itertools.combinations(group, 2):
            rel = key_relation(ka, kb)
            if rel is None:
                continue
            if rel == SIG_NAME_KEY_SUBSET and coverage(a, b)[0] != COVERAGE_COMPLEMENTARY:
                continue
            add(a, b, rel, f"same country ({country}); name keys {sorted(ka)} / {sorted(kb)}")

    by_id = {r.canonical_id: r for r in records}
    out: list[Candidate] = []
    for pair, cand in found.items():
        a, b = (by_id[cid] for cid in sorted(pair))
        cov, tables = coverage(a, b)
        if cov == COVERAGE_BOTH:
            cand.against.append(f"a source ranks both in one table ({'; '.join(tables)}): it lists them as two")
        elif cov == COVERAGE_COMPLEMENTARY:
            cand.evidence.append("complementary: ranked in a shared year, never by one source in one table")
        else:
            cand.evidence.append("never ranked in the same year")
        if pair in related:
            cand.against.append(f"institution_lineage records a {related[pair]} between them")
        strong = SIG_SHARED_WIKIDATA in cand.signals or SIG_SAME_NAME_KEY in cand.signals
        cand.priority = "low" if cand.against else ("high" if strong else "medium")
        out.append(cand)
    return out


@dataclass(frozen=True)
class FuzzyMapping:
    source_code: str
    source_entity_id: str
    source_name: str
    canonical_slug: str
    canonical_name: str
    match_method: str
    confidence: float
    suspicious_merge: bool = False
    country_mismatch: bool = False


def fuzzy_candidates(rows: Iterable[FuzzyMapping]) -> list[Candidate]:
    """Active fuzzy mappings nobody has reviewed. Flagged ones (by the resolver) come first."""
    out = []
    for m in rows:
        flags = [f for f, on in (("suspicious_merge", m.suspicious_merge), ("country_mismatch", m.country_mismatch))
                 if on]
        cand = Candidate(
            KIND_MAPPING, [SIG_UNREVIEWED_FUZZY],
            {"source_code": m.source_code, "source_entity_id": m.source_entity_id, "source_name": m.source_name,
             "canonical_slug": m.canonical_slug, "canonical_name": m.canonical_name},
            evidence=[f"{m.match_method} at confidence {m.confidence:.4f}; no mapping_review decision"],
        )
        if flags:
            cand.evidence.append("the resolver flagged it: " + ", ".join(flags))
        cand.priority = "high" if flags else ("medium" if m.confidence < 0.88 else "low")
        out.append(cand)
    return out


def collision_candidates(lines: Iterable[str]) -> list[Candidate]:
    """Wrap collision_scan's findings. Each line names the source, edition, record and entities."""
    out = []
    for line in lines:
        m = re.match(r"(\w+) (\d{4}): c(\d+)", line)
        source, year, cid = (m.group(1), m.group(2), m.group(3)) if m else ("?", "?", "?")
        out.append(Candidate(KIND_MAPPING, [SIG_COLLISION],
                             {"source_code": source, "source_entity_id": f"collision:{year}:c{cid}",
                              "detail": line},
                             evidence=[line], priority="high"))
    return out


# ---------------------------------------------------------------------------------------------- dismissals

def load_dismissed(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    entries = json.loads(path.read_text(encoding="utf-8")).get("dismissed", [])
    for e in entries:
        if not str(e.get("why", "")).strip():
            raise ValueError(f"a dismissal needs its reason: {e}")
        if e.get("kind") == KIND_DUPLICATE and len(set(e.get("slugs", []))) != 2:
            raise ValueError(f"a duplicate dismissal names exactly two slugs: {e}")
        if e.get("kind") == KIND_MAPPING and not (e.get("source_code") and e.get("source_entity_id")):
            raise ValueError(f"a mapping dismissal names source_code and source_entity_id: {e}")
        if e.get("kind") not in (KIND_DUPLICATE, KIND_MAPPING):
            raise ValueError(f"unknown dismissal kind: {e}")
    return entries


def dismissal_key(entry: dict[str, Any]) -> tuple:
    if entry["kind"] == KIND_DUPLICATE:
        return (KIND_DUPLICATE, frozenset(entry["slugs"]))
    return (KIND_MAPPING, entry["source_code"], str(entry["source_entity_id"]))


def split_dismissed(cands: Sequence[Candidate], dismissed: Sequence[dict[str, Any]]
                    ) -> tuple[list[Candidate], list[dict[str, Any]], list[dict[str, Any]]]:
    """(queue, dismissed candidates with their reason, dismissals that no longer match anything)."""
    by_key = {dismissal_key(e): e for e in dismissed}
    queue, hidden, used = [], [], set()
    for c in cands:
        entry = by_key.get(c.key)
        if entry is None:
            queue.append(c)
        else:
            used.add(c.key)
            hidden.append({"candidate": c.to_json(), "dismissed_because": entry["why"],
                           "dismissed_on": entry.get("decided_on")})
    stale = [e for e in dismissed if dismissal_key(e) not in used]
    queue.sort(key=lambda c: (_PRIORITY_ORDER[c.priority], c.kind, json.dumps(c.subject, sort_keys=True)))
    return queue, hidden, stale


# ---------------------------------------------------------------------------------------------- annotation

class Annotator(Protocol):
    """Writes advisory text for a person. Its output never becomes a decision."""
    name: str

    def annotate(self, candidate: Candidate) -> Optional[str]: ...


class NoAnnotator:
    name = "none"

    def annotate(self, candidate: Candidate) -> Optional[str]:
        return None


ANNOTATORS: dict[str, type] = {"none": NoAnnotator}


# ---------------------------------------------------------------------------------------------- warehouse

def fetch_records(conn: Any, matches_path: Path = MATCHES_PATH) -> list[Record]:
    wikidata: dict[str, str] = {}
    if matches_path.exists():
        for row in json.loads(matches_path.read_text(encoding="utf-8")).get("matched", []):
            if row.get("wikidata_id"):
                wikidata[row["canonical_slug"]] = row["wikidata_id"]
    with conn.cursor() as cur:
        cur.execute("SELECT rr.canonical_university_id, rs.source_code, rr.ranking_year, rr.ranking_type, "
                    "rr.universe_type, rr.universe_key FROM warehouse.ranking_record rr "
                    "JOIN warehouse.ranking_source rs USING (ranking_source_id)")
        tables: dict[int, set[Table]] = defaultdict(set)
        for cid, src, year, rtype, utype, ukey in cur.fetchall():
            tables[cid].add((src, int(year), rtype, utype, ukey))
        cur.execute("SELECT cu.canonical_university_id, cu.canonical_slug, cu.display_name, c.country_name "
                    "FROM warehouse.canonical_university cu LEFT JOIN warehouse.countries c USING (country_id) "
                    "WHERE cu.status = 'active'")
        return [Record(cid, slug, name, country, wikidata.get(slug), frozenset(tables.get(cid, ())))
                for cid, slug, name, country in cur.fetchall()]


def fetch_lineage(conn: Any) -> list[tuple[int, int, str]]:
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass('warehouse.institution_lineage') IS NOT NULL")
        if not cur.fetchone()[0]:
            return []
        cur.execute("SELECT predecessor_canonical_id, successor_canonical_id, kind "
                    "FROM warehouse.institution_lineage")
        return [(int(p), int(s), str(t)) for p, s, t in cur.fetchall()]


def fetch_fuzzy(conn: Any) -> list[FuzzyMapping]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT m.source_code, m.source_entity_id, "
            "COALESCE(m.metadata->'raw_row'->>'name', m.metadata->>'normalized_name', m.source_entity_id), "
            "cu.canonical_slug, cu.display_name, m.match_method, m.confidence_score, "
            "COALESCE((m.metadata->>'suspicious_merge')::boolean, false), "
            "COALESCE((m.metadata->>'country_mismatch')::boolean, false) "
            "FROM warehouse.source_university_mapping m "
            "JOIN warehouse.canonical_university cu USING (canonical_university_id) "
            "WHERE m.is_active AND m.match_method = ANY(%s) AND NOT EXISTS ("
            "  SELECT 1 FROM warehouse.mapping_review r "
            "  WHERE r.source_code = m.source_code AND r.source_entity_id = m.source_entity_id)",
            (list(FUZZY_METHODS),))
        return [FuzzyMapping(s, str(e), str(n), slug, name, meth, float(conf), bool(sus), bool(cm))
                for s, e, n, slug, name, meth, conf, sus, cm in cur.fetchall()]


def fetch_collisions(conn: Any) -> list[str]:
    scripts = str(_HERE.parent)
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    from split_false_entity_merges import collision_scan  # noqa: E402  (that script owns the scan)
    return collision_scan(conn)


# ---------------------------------------------------------------------------------------------- report

def build_report(records: Sequence[Record], lineage: Sequence[tuple[int, int, str]],
                 fuzzy: Sequence[FuzzyMapping], collisions: Sequence[str], dismissed: Sequence[dict[str, Any]],
                 annotator: Annotator, *, matches_generated_at: Optional[str], today: str) -> dict[str, Any]:
    cands = duplicate_candidates(records, lineage) + collision_candidates(collisions) + fuzzy_candidates(fuzzy)
    queue, hidden, stale = split_dismissed(cands, dismissed)
    for c in queue:
        c.model_note = annotator.annotate(c)
    counts: dict[str, int] = defaultdict(int)
    for c in queue:
        counts[f"{c.kind}:{c.priority}"] += 1
    return {
        "generated_on": today,
        "annotator": annotator.name,
        "inputs": {"active_records": len(records), "wikipedia_matches_generated_at": matches_generated_at,
                   "lineage_rows": len(lineage), "unreviewed_fuzzy_mappings": len(fuzzy),
                   "dismissals": len(dismissed)},
        "counts": dict(sorted(counts.items())),
        "queue": [c.to_json() for c in queue],
        "dismissed": hidden,
        "stale_dismissals": stale,
        "how_to_decide": {
            KIND_DUPLICATE: "same university: add a merge to crawlernest-kb/entity_merges/duplicate_canonicals_<date>.json "
                            "and apply it with merge_duplicate_canonicals.py (rehearse on a copy first). "
                            "Two universities: dismiss it in review_dismissed.json with the reason.",
            KIND_MAPPING: "wrong university: record a 'remapped' decision in warehouse.mapping_review, as "
                          "split_false_entity_merges.py did. Right university: a 'confirmed' decision, or dismiss it.",
        },
    }


def _record_line(r: dict[str, Any]) -> str:
    years = f"{r['years'][0]}-{r['years'][1]}" if r["years"] else "no ranks"
    qid = f", {r['wikidata_id']}" if r.get("wikidata_id") else ""
    return (f"`{r['slug']}` {r['name']} ({r['country']}{qid}) -- "
            f"{'/'.join(r['sources']) or 'no source'}, {years}")


def render_markdown(report: dict[str, Any]) -> str:
    lines = [f"# Entity review queue, {report['generated_on']}", "",
             "Read-only output of `crawlernest/scripts/entity_review_candidates.py`. Nothing here is a decision.", ""]
    inp = report["inputs"]
    lines += [f"- active records: {inp['active_records']}; unreviewed fuzzy mappings: {inp['unreviewed_fuzzy_mappings']}",
              f"- wikipedia/en/matches.json generated at {inp['wikipedia_matches_generated_at']} "
              "(re-run `wikipedia_profile_loader.py match` after a backfill)",
              f"- annotator: {report['annotator']}", ""]
    lines += ["| queue | count |", "|---|---:|"] + [f"| {k} | {v} |" for k, v in report["counts"].items()] + [""]
    for i, c in enumerate(report["queue"], 1):
        if c["kind"] == KIND_DUPLICATE:
            head = " / ".join(r["name"] for r in c["subject"]["records"])
        else:
            s = c["subject"]
            head = s.get("detail") or f"{s['source_code']} {s['source_entity_id']} \"{s['source_name']}\" -> {s['canonical_name']}"
        lines += [f"## {i}. [{c['priority']}] {c['kind']}: {head}", ""]
        if c["kind"] == KIND_DUPLICATE:
            lines += [f"- {_record_line(r)}" for r in c["subject"]["records"]]
        lines += [f"- signals: {', '.join(c['signals'])}"] + [f"- for: {e}" for e in c["evidence"]]
        lines += [f"- against: {a}" for a in c["against"]]
        if c["model_note"]:
            lines.append(f"- model note (advisory): {c['model_note']}")
        lines.append("")
    if report["dismissed"]:
        lines += ["## Dismissed (not in the queue)", ""]
        for d in report["dismissed"]:
            subj = d["candidate"]["subject"]
            what = " / ".join(r["name"] for r in subj["records"]) if "records" in subj else subj.get("source_name", "")
            lines.append(f"- {what}: {d['dismissed_because']}")
        lines.append("")
    if report["stale_dismissals"]:
        lines += ["## Dismissals that matched nothing this run", ""]
        lines += [f"- {json.dumps(e, ensure_ascii=False)}" for e in report["stale_dismissals"]] + [""]
    lines += ["## How to decide", ""] + [f"- **{k}**: {v}" for k, v in report["how_to_decide"].items()]
    return "\n".join(lines) + "\n"


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("phase", choices=["build"])
    parser.add_argument("--annotator", choices=sorted(ANNOTATORS), default="none")
    parser.add_argument("--dismissed", type=Path, default=DISMISSED_PATH)
    parser.add_argument("--matches", type=Path, default=MATCHES_PATH)
    parser.add_argument("--out-dir", type=Path, default=REPORT_DIR)
    parser.add_argument("--pg-host", default="localhost")
    parser.add_argument("--pg-port", type=int, default=5432)
    parser.add_argument("--pg-database", default="clawer")
    parser.add_argument("--pg-user", default="test")
    parser.add_argument("--pg-password", default="test")
    args = parser.parse_args(argv)

    import psycopg2

    dismissed = load_dismissed(args.dismissed)
    matches_at = (json.loads(args.matches.read_text(encoding="utf-8")).get("generated_at")
                  if args.matches.exists() else None)
    conn = psycopg2.connect(host=args.pg_host, port=args.pg_port, dbname=args.pg_database, user=args.pg_user,
                            password=args.pg_password)
    try:
        conn.set_session(readonly=True)
        report = build_report(fetch_records(conn, args.matches), fetch_lineage(conn), fetch_fuzzy(conn),
                              fetch_collisions(conn), dismissed, ANNOTATORS[args.annotator](),
                              matches_generated_at=matches_at, today=_dt.date.today().isoformat())
    finally:
        conn.close()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    stem = args.out_dir / f"candidates_{report['generated_on']}"
    stem.with_suffix(".json").write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    stem.with_suffix(".md").write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({"counts": report["counts"], "dismissed": len(report["dismissed"]),
                      "stale_dismissals": len(report["stale_dismissals"]),
                      "report": str(stem.with_suffix(".md"))}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
