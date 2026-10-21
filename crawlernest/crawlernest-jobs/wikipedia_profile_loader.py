#!/usr/bin/env python3
"""Attach an English Wikipedia article to each university that holds ranking data.

Three steps, each its own subcommand, each leaving a file the next one reads:

``match``   reads the warehouse and Wikidata, writes ``crawlernest-kb/wikipedia/en/matches.json``
``fetch``   reads ``matches.json`` and Wikipedia, writes ``crawlernest-kb/wikipedia/en/articles/*.jsonl.gz``
``ingest``  reads both files, fills ``warehouse.university_wikipedia_article``; no network

``aliases`` is a by-product: it writes the article titles as a reviewed-format alias file
(``crawlernest-kb/databases/wikipedia_university_aliases_2026.json``) for
``scripts/seed_alias_file.py``, so that the next source to print a university's English
name finds the record that carries its native one. See :func:`title_alias_rows`.

Matching is the part that can be wrong, so it is the part that is conservative. The
warehouse knows a university by a name and a country, and names collide ("Miami
University" is not "University of Miami"; see the entity-resolution notes in
``.claude/CLAUDE.md``). A university is matched only by one of:

``wikidata_source_id``  Wikidata records the university's own id at QS (P5584), THE
                        (P5586) or ARWU (P5242), and that id is the one the warehouse
                        ingested its ranks under. No name is compared.
``exact_title``         one of the university's names is, exactly, the title of an
                        English Wikipedia article or a redirect to one, and the
                        article's Wikidata item is an educational institution in the
                        university's country.
``label_search``        a Wikidata search for the name returns an educational
                        institution in the university's country whose label or alias,
                        in any language, is the name (case, accents and punctuation
                        aside; word order is never ignored).

Anything else stays unmatched and is listed with the reason. An empty page is the
honest result for a university this cannot place; another university's article is not.

The article text is the plain-text extract (``prop=extracts&explaintext``), split
into sections. It is Wikipedia's content under CC BY-SA 4.0: every stored article
keeps its revision id and URL so the page can attribute it and link the exact
revision, and nothing in the pipeline reads it as data about the university.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import re
import sys
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Optional, Sequence
from urllib.parse import quote

_JOBS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _JOBS_DIR.parents[1]

LOADER_VERSION = "1"
LANGUAGE = "en"
LICENSE = "CC BY-SA 4.0"
LICENSE_URL = "https://creativecommons.org/licenses/by-sa/4.0/"
USER_AGENT = "CrawlerNest-wikipedia-loader/1 (https://github.com/heinricitorgau; university ranking research)"

KB_DIR = _JOBS_DIR.parent / "crawlernest-kb" / "wikipedia" / LANGUAGE
MATCHES_PATH = KB_DIR / "matches.json"
#: Reviewed corrections: ``{canonical_slug: {"title": <article title or null>, "why": ...}}``.
#: ``null`` withholds a match the rules would make; a title makes one they would not.
OVERRIDES_PATH = KB_DIR / "overrides.json"
ARTICLES_DIR = KB_DIR / "articles"
CACHE_DIR = _REPO_ROOT / ".local" / "tmp" / "wikipedia_cache"
#: Articles are spread over this many files by page id, so one refreshed article
#: rewrites one file and no file approaches GitHub's size limit.
SHARD_COUNT = 32

WIKIPEDIA_API = f"https://{LANGUAGE}.wikipedia.org/w/api.php"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"

#: Wikidata properties holding a ranking publisher's own id for the institution.
SOURCE_ID_PROPERTIES = {"QS": "P5584", "THE": "P5586", "ARWU": "P5242"}
#: Identifiers only research and teaching institutions are given (ROR, GRID, plus the three above).
INSTITUTION_ID_PROPERTIES = ("P6782", "P2427", "P5584", "P5586", "P5242")
EDUCATION_TYPE_RE = re.compile(
    r"universit|college|institut|school|academy|polytechnic|conservator|educational|grande école|grandes écoles"
    r"|seminary|faculty|hochschule",
    re.IGNORECASE,
)

#: Sections that are apparatus rather than prose; in a plain-text extract they are
#: empty or a list of bare titles.
DROPPED_SECTIONS = {
    "references", "external links", "see also", "notes", "further reading", "citations", "bibliography",
    "footnotes", "sources", "notes and references", "references and notes", "works cited", "gallery",
}

#: Warehouse country names that are not what Wikidata calls the country. The value is
#: every Wikidata country label accepted for that name: Hong Kong and Macau
#: institutions carry either the region or China as P17, and Taiwan's carry Taiwan.
COUNTRY_SYNONYMS: dict[str, tuple[str, ...]] = {
    "china mainland": ("people's republic of china", "china"),
    "china": ("people's republic of china", "china"),
    "china taiwan": ("taiwan",),
    "hong kong sar": ("hong kong", "people's republic of china"),
    "macau sar": ("macau", "people's republic of china"),
    # QS's spellings from 2026-10-21 on, should a record ever be created under them.
    "hong kong sar china": ("hong kong", "people's republic of china"),
    "macao sar china": ("macau", "people's republic of china"),
    "macao sar": ("macau", "people's republic of china"),
    "bosnia herzegovina": ("bosnia and herzegovina",),
    "congo brazzaville": ("republic of the congo",),
    "myanmar burma": ("myanmar",),
    "palestinian territories": ("state of palestine", "palestine"),
    "trinidad tobago": ("trinidad and tobago",),
    "puerto rico": ("puerto rico", "united states"),
    "northern cyprus": ("northern cyprus", "turkish republic of northern cyprus", "cyprus"),
    "czechia": ("czech republic",),
    "turkiye": ("turkey",),
    "gambia": ("the gambia",),
    "united states": ("united states", "united states of america"),
}


# ---------------------------------------------------------------------------
# Names
# ---------------------------------------------------------------------------

def strict_name(value: str) -> str:
    """A name with case, accents and punctuation removed -- and nothing else.

    Word order and every word are kept, a leading "the" aside. This is deliberately
    weaker than the resolver's normalisation, which drops "of" and sorts nothing but
    still reads "Miami University" and "University of Miami" as one string.
    """
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    return text[4:] if text.startswith("the ") else text


def name_variants(name: str) -> list[str]:
    """The name, and the name without a trailing abbreviation QS appends to it.

    QS prints "Skolkovo Institute of Science and Technology Skoltech" and
    "Massachusetts Institute of Technology (MIT)". The suffix is dropped only when it
    is a parenthesis, or a last word that is a coined short form whose letters appear,
    in order, in the words before it. "UWM" after "University of Wisconsin" is not
    spelled by them, so a campus designator stays.
    """
    name = " ".join((name or "").split())
    out = [name] if name else []
    bare = re.sub(r"\s*\([^()]*\)\s*$", "", name).strip()
    if bare and bare != name:
        out.append(bare)
    words = (bare or name).split()
    if len(words) >= 3:
        last, rest = words[-1], words[:-1]
        if len(last) >= 2 and _looks_coined(last) and _is_subsequence(last.lower(), "".join(rest).lower()):
            out.append(" ".join(rest))
    return list(dict.fromkeys(out))


def _looks_coined(word: str) -> bool:
    """True for a made-up short form (MIT, KAIST, Skoltech), false for an ordinary word or a place."""
    return word.isupper() or bool(re.search(r"[a-z][A-Z]", word)) or word.lower().endswith("tech")


def _is_subsequence(needle: str, haystack: str) -> bool:
    it = iter(haystack)
    return all(ch in it for ch in needle)


def country_labels(country: Optional[str]) -> set[str]:
    """Strict-normalised Wikidata country labels accepted for a warehouse country name."""
    key = strict_name(country or "")
    if not key or key == "n a":
        return set()
    return {strict_name(label) for label in COUNTRY_SYNONYMS.get(key, (key,))} | {key}


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

#: API errors that mean "ask again later", not "this request is wrong".
RETRYABLE_API_ERRORS = {"maxlag", "ratelimited", "cirrussearch-too-busy-error"}


class FetchError(RuntimeError):
    """A request that still failed after its retries."""


class ApiClient:
    """A polite, cached reader for the Wikimedia APIs.

    Responses are cached under ``.local/tmp/wikipedia_cache`` so a re-run of ``match``
    costs nothing and an interrupted ``fetch`` resumes. ``refresh`` ignores the cache.
    """

    def __init__(
        self,
        *,
        cache_dir: Optional[Path] = CACHE_DIR,
        min_interval: float = 0.1,
        attempts: int = 5,
        timeout: float = 90.0,
        refresh: bool = False,
        offline: bool = False,
        session: Any = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.cache_dir = cache_dir
        self.min_interval = min_interval
        self.attempts = attempts
        self.timeout = timeout
        self.refresh = refresh
        self.offline = offline
        self._session = session
        self._sleep = sleep
        self._last = 0.0
        import threading

        self._lock = threading.Lock()

    def _cache_path(self, url: str, params: dict[str, Any]) -> Optional[Path]:
        if self.cache_dir is None:
            return None
        key = hashlib.sha256(json.dumps([url, sorted(params.items())], ensure_ascii=False).encode()).hexdigest()
        return self.cache_dir / key[:2] / f"{key}.json"

    def get_json(self, url: str, params: dict[str, Any], *, post: bool = False) -> Any:
        path = self._cache_path(url, params)
        if path is not None and path.exists() and not self.refresh:
            return json.loads(path.read_text(encoding="utf-8"))
        if self.offline:
            raise FetchError(f"offline and not cached: {url} {params}")
        import requests

        if self._session is None:
            self._session = requests.Session()
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        detail = ""
        for attempt in range(self.attempts):
            with self._lock:
                wait = self.min_interval - (time.monotonic() - self._last)
                if wait > 0:
                    self._sleep(wait)
                self._last = time.monotonic()
            try:
                if post:
                    resp = self._session.post(url, data=params, headers=headers, timeout=self.timeout)
                else:
                    resp = self._session.get(url, params=params, headers=headers, timeout=self.timeout)
                if resp.status_code == 200:
                    data = resp.json()
                    error = data.get("error") if isinstance(data, dict) else None
                    if error and error.get("code") not in RETRYABLE_API_ERRORS:
                        # A refused request is the caller's bug, and is never cached as an answer.
                        raise FetchError(f"{url} refused the request: {error.get('code')}: {error.get('info')}")
                    if not error:
                        if path is not None:
                            path.parent.mkdir(parents=True, exist_ok=True)
                            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                        return data
                    detail = str(data["error"])
                else:
                    detail = f"HTTP {resp.status_code}"
                    if resp.status_code < 500 and resp.status_code != 429:
                        break
                retry_after = resp.headers.get("Retry-After", "")
                pause = float(retry_after) if retry_after.isdigit() else 5.0 * (attempt + 1)
            except FetchError:
                raise
            except Exception as exc:  # noqa: BLE001 - a network failure is a retry, then a FetchError
                detail, pause = f"{type(exc).__name__}: {exc}", 5.0 * (attempt + 1)
            if attempt + 1 < self.attempts:
                self._sleep(min(pause, 60.0))
        raise FetchError(f"{url} failed: {detail}")


def _chunks(items: Sequence[Any], size: int) -> Iterable[Sequence[Any]]:
    for start in range(0, len(items), size):
        yield items[start:start + size]


# ---------------------------------------------------------------------------
# The warehouse side
# ---------------------------------------------------------------------------

@dataclass
class University:
    canonical_university_id: int
    canonical_slug: str
    display_name: str
    country: Optional[str]
    source_ids: dict[str, list[str]] = field(default_factory=dict)
    other_names: list[str] = field(default_factory=list)

    def own_names(self) -> list[str]:
        """Spellings of the display name: what this record is."""
        return name_variants(self.display_name)

    def names(self) -> list[str]:
        """Every spelling to try, the display name's first.

        The others are what sources printed for rows the resolver attached to this
        record, so they are evidence about the resolver as much as about the university.
        """
        out = self.own_names()
        for name in self.other_names:
            out.extend(name_variants(name))
        return list(dict.fromkeys(n for n in out if n))


@dataclass(frozen=True)
class PgConfig:
    host: str = "localhost"
    port: int = 5432
    database: str = "clawer"
    user: str = "test"
    password: str = "test"

    def connect(self) -> Any:
        import psycopg2

        return psycopg2.connect(
            host=self.host, port=self.port, dbname=self.database, user=self.user, password=self.password
        )


def source_id_keys(source_code: str, source_entity_id: str, raw_url: Optional[str]) -> list[str]:
    """The id a ranking publisher's site uses for the institution, as Wikidata stores it.

    QS: the path segment after ``/universities/``. THE: the last segment of the
    profile URL (the warehouse id is THE's numeric node id, which Wikidata does not
    hold). ARWU: the institution slug. All compared lower-cased.
    """
    if source_code == "QS":
        match = re.fullmatch(r"/universities/([^/]+)/?", source_entity_id or "")
        return [match.group(1).lower()] if match else []
    if source_code == "THE":
        segment = (raw_url or "").rstrip("/").rsplit("/", 1)[-1]
        return [segment.lower()] if segment else []
    if source_code == "ARWU":
        slug = (source_entity_id or "").removeprefix("arwu:")
        return [slug.lower()] if slug else []
    return []


def load_universities(conn: Any) -> list[University]:
    """Every active university with at least one row in ``analytics.aggregated_rankings``."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT cu.canonical_university_id, cu.canonical_slug, cu.display_name, co.country_name
            FROM warehouse.canonical_university cu
            LEFT JOIN warehouse.countries co ON co.country_id = cu.country_id
            WHERE cu.status = 'active'
              AND EXISTS (SELECT 1 FROM analytics.aggregated_rankings ar
                          WHERE ar.canonical_university_id = cu.canonical_university_id)
            ORDER BY cu.canonical_slug
            """
        )
        universities = {row[0]: University(row[0], row[1], row[2], row[3]) for row in cur.fetchall()}
        cur.execute(
            """
            SELECT canonical_university_id, source_code, source_entity_id,
                   metadata->'raw_row'->>'url', metadata->'raw_row'->>'name'
            FROM warehouse.source_university_mapping
            WHERE source_code IN ('QS', 'THE', 'ARWU') AND is_active
            ORDER BY source_mapping_id
            """
        )
        for canonical_id, source_code, entity_id, raw_url, raw_name in cur.fetchall():
            university = universities.get(canonical_id)
            if university is None:
                continue
            for key in source_id_keys(source_code, entity_id, raw_url):
                bucket = university.source_ids.setdefault(source_code, [])
                if key not in bucket:
                    bucket.append(key)
            if raw_name and raw_name not in university.other_names and raw_name != university.display_name:
                university.other_names.append(raw_name)
        cur.execute(
            """
            SELECT canonical_university_id, alias_text
            FROM warehouse.university_alias
            WHERE NOT is_abbreviation
            ORDER BY alias_id
            """
        )
        for canonical_id, alias in cur.fetchall():
            university = universities.get(canonical_id)
            if university is not None and alias and alias not in university.other_names \
                    and alias != university.display_name:
                university.other_names.append(alias)
    return list(universities.values())


# ---------------------------------------------------------------------------
# The Wikidata / Wikipedia side
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Candidate:
    wikidata_id: str
    title: str


def fetch_source_id_index(client: ApiClient, prop: str) -> dict[str, list[Candidate]]:
    """Every Wikidata item carrying ``prop`` that has an English article, by lower-cased id."""
    query = (
        "SELECT ?item ?id ?title WHERE { ?item wdt:%s ?id . ?a schema:about ?item ; "
        "schema:isPartOf <https://%s.wikipedia.org/> ; schema:name ?title }" % (prop, LANGUAGE)
    )
    data = client.get_json(WIKIDATA_SPARQL, {"query": query, "format": "json"})
    index: dict[str, list[Candidate]] = {}
    for row in data["results"]["bindings"]:
        candidate = Candidate(row["item"]["value"].rsplit("/", 1)[-1], row["title"]["value"])
        bucket = index.setdefault(row["id"]["value"].strip().lower(), [])
        if candidate not in bucket:
            bucket.append(candidate)
    return index


def resolve_titles(client: ApiClient, names: Sequence[str]) -> dict[str, Candidate]:
    """Names that are exactly an article title or a redirect to a whole article.

    A redirect into a section is refused: that is how a college points at the
    paragraph about it in its parent university's article. Disambiguation pages and
    pages without a Wikidata item are refused too.
    """
    resolved: dict[str, Candidate] = {}
    # "|" separates titles in the request and cannot occur in one, so such a name is no title.
    for batch in _chunks([n for n in dict.fromkeys(names) if n and "|" not in n], 50):
        data = client.get_json(WIKIPEDIA_API, {
            "action": "query", "format": "json", "formatversion": "2", "redirects": "1",
            "prop": "pageprops", "ppprop": "wikibase_item|disambiguation", "titles": "|".join(batch),
            "maxlag": "5",
        }, post=True)
        query = data.get("query", {})
        normalized = {row["from"]: row["to"] for row in query.get("normalized", [])}
        redirects = {row["from"]: row for row in query.get("redirects", [])}
        pages = {page["title"]: page for page in query.get("pages", [])}
        for name in batch:
            title = normalized.get(name, name)
            redirect = redirects.get(title)
            if redirect is not None:
                if redirect.get("tofragment"):
                    continue
                title = redirect["to"]
            page = pages.get(title)
            if not page or page.get("missing") or page.get("invalid"):
                continue
            props = page.get("pageprops", {})
            if "disambiguation" in props or not props.get("wikibase_item"):
                continue
            resolved[name] = Candidate(props["wikibase_item"], page["title"])
    return resolved


@dataclass
class Entity:
    wikidata_id: str
    label: str
    aliases: list[str]
    countries: list[str]
    types: list[str]
    has_institution_id: bool
    title: Optional[str]


def fetch_entities(client: ApiClient, wikidata_ids: Iterable[str], *, all_languages: bool = False) -> dict[str, Entity]:
    """Label, aliases, country (P17), type (P31) and English article title for each item.

    With ``all_languages`` the aliases hold the item's label and aliases in every
    language, which is how a university the warehouse knows by its native name
    ("Universitas Islam Malang") is recognised as the item labelled in English.
    """
    ids = sorted(set(wikidata_ids))
    raw: dict[str, Any] = {}
    for batch in _chunks(ids, 50):
        params = {
            "action": "wbgetentities", "format": "json", "ids": "|".join(batch),
            "props": "claims|labels|aliases|sitelinks", "sitefilter": f"{LANGUAGE}wiki",
        }
        if not all_languages:
            params["languages"] = "en"
        raw.update(client.get_json(WIKIDATA_API, params, post=True).get("entities", {}))

    def claim_ids(entity: dict[str, Any], prop: str) -> list[str]:
        out = []
        for claim in entity.get("claims", {}).get(prop, []):
            value = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
            if isinstance(value, dict) and value.get("id"):
                out.append(value["id"])
        return out

    referenced = sorted({q for e in raw.values() for p in ("P17", "P31") for q in claim_ids(e, p)})
    labels: dict[str, list[str]] = {}
    for batch in _chunks(referenced, 50):
        data = client.get_json(WIKIDATA_API, {
            "action": "wbgetentities", "format": "json", "ids": "|".join(batch),
            "props": "labels|aliases", "languages": "en",
        }, post=True)
        for qid, entity in data.get("entities", {}).items():
            names = [entity.get("labels", {}).get("en", {}).get("value", "")]
            names += [alias["value"] for alias in entity.get("aliases", {}).get("en", [])]
            labels[qid] = [name for name in names if name]

    entities: dict[str, Entity] = {}
    for qid, entity in raw.items():
        if "missing" in entity:
            continue
        entities[qid] = Entity(
            wikidata_id=qid,
            label=entity.get("labels", {}).get("en", {}).get("value", ""),
            aliases=list(dict.fromkeys(
                [label["value"] for label in entity.get("labels", {}).values()]
                + [alias["value"] for rows in entity.get("aliases", {}).values() for alias in rows]
            )),
            countries=[name for q in claim_ids(entity, "P17") for name in labels.get(q, [])],
            types=[labels[q][0] for q in claim_ids(entity, "P31") if labels.get(q)],
            has_institution_id=any(entity.get("claims", {}).get(p) for p in INSTITUTION_ID_PROPERTIES),
            title=entity.get("sitelinks", {}).get(f"{LANGUAGE}wiki", {}).get("title"),
        )
    return entities


def search_wikidata(client: ApiClient, name: str) -> list[str]:
    """Items a search for the name returns: by English label prefix, then by full text in any language.

    These are only where to look. Whether an item is the university is decided by
    the caller comparing labels, never by search rank.
    """
    ids = _label_hits(client, name)
    data = client.get_json(WIKIDATA_API, {
        "action": "query", "format": "json", "list": "search", "srnamespace": "0", "srlimit": "7",
        "srprop": "", "srsearch": name,
    })
    ids += [row["title"] for row in data.get("query", {}).get("search", [])]
    return list(dict.fromkeys(ids))


def is_institution(entity: Entity) -> bool:
    return entity.has_institution_id or any(EDUCATION_TYPE_RE.search(t) for t in entity.types)


def country_agrees(entity: Entity, country: Optional[str]) -> Optional[bool]:
    """True/False when both sides name a country; None when the warehouse has none to compare."""
    wanted = country_labels(country)
    if not wanted:
        return None
    return bool(wanted & {strict_name(c) for c in entity.countries})


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

@dataclass
class Match:
    university: University
    wikidata_id: str
    title: str
    method: str
    evidence: dict[str, Any]


@dataclass
class MatchReport:
    matched: list[Match]
    unmatched: list[tuple[University, str]]


def match_by_source_id(
    university: University, indexes: dict[str, dict[str, list[Candidate]]]
) -> tuple[Optional[Match], Optional[str]]:
    """The article Wikidata ties to this university's publisher ids, if they name exactly one.

    Publisher ids that name different articles are a disagreement about which
    institution this record is -- usually a merged record -- and are left for the
    caller to settle or report; picking one would be a guess.
    """
    found: dict[Candidate, list[str]] = {}
    for source_code, keys in university.source_ids.items():
        for key in keys:
            candidates = indexes.get(source_code, {}).get(key, [])
            if len(candidates) != 1:
                continue  # an id two Wikidata items both claim identifies neither
            found.setdefault(candidates[0], []).append(f"{source_code}:{key}")
    if not found:
        return None, None
    if len(found) > 1:
        summary = "; ".join(f"{c.title} ({c.wikidata_id}) via {', '.join(v)}" for c, v in found.items())
        return None, f"publisher ids name different articles: {summary}"
    candidate, via = next(iter(found.items()))
    return Match(university, candidate.wikidata_id, candidate.title, "wikidata_source_id", {"source_ids": via}), None


def build_matches(
    universities: Sequence[University],
    client: ApiClient,
    *,
    overrides: Optional[dict[str, dict[str, Any]]] = None,
    use_search: bool = True,
    log: Callable[[str], None] = lambda _msg: None,
) -> MatchReport:
    indexes = {code: fetch_source_id_index(client, prop) for code, prop in SOURCE_ID_PROPERTIES.items()}
    log("wikidata ids: " + ", ".join(f"{code}={len(index)}" for code, index in indexes.items()))

    matched: list[Match] = []
    conflicts: dict[int, str] = {}
    pending: list[University] = []
    unmatched: list[tuple[University, str]] = []
    overrides = overrides or {}
    forced = {slug: row["title"] for slug, row in overrides.items() if row.get("title")}
    forced_pages = resolve_titles(client, list(forced.values()))
    for university in universities:
        if university.canonical_slug in overrides:
            row = overrides[university.canonical_slug]
            candidate = forced_pages.get(row.get("title") or "")
            if candidate is not None:
                matched.append(Match(
                    university, candidate.wikidata_id, candidate.title, "reviewed_override", {"why": row.get("why")}
                ))
            else:
                unmatched.append((university, "withheld by overrides.json: " + str(row.get("why") or "no reason given")))
            continue
        match, conflict = match_by_source_id(university, indexes)
        if match is not None:
            matched.append(match)
            continue
        if conflict:
            conflicts[university.canonical_university_id] = conflict
        pending.append(university)
    log(f"by publisher id: {len(matched)}; remaining {len(pending)}")

    # exact title or redirect
    titles = resolve_titles(client, [name for u in pending for name in u.names()])
    entities = fetch_entities(client, {c.wikidata_id for c in titles.values()})
    reasons: dict[int, str] = {}
    still: list[University] = []
    for university in pending:
        chosen, reason = _pick_validated(
            university, [(name, titles[name]) for name in university.names() if name in titles], entities
        )
        if chosen is not None:
            name, candidate = chosen
            matched.append(Match(university, candidate.wikidata_id, candidate.title, "exact_title", {"name": name}))
        else:
            if reason:
                reasons[university.canonical_university_id] = reason
            still.append(university)
    log(f"by exact title: {len(pending) - len(still)}; remaining {len(still)}")

    shadowed = _shadowed_redirects(client, [m for m in matched if m.method == "exact_title"])
    if shadowed:
        matched = [m for m in matched if m.university.canonical_university_id not in shadowed]
        for university in pending:
            if university.canonical_university_id in shadowed:
                reasons[university.canonical_university_id] = shadowed[university.canonical_university_id]
        log(f"redirects withheld because another Wikidata item carries the name: {len(shadowed)}")

    still_ids = {u.canonical_university_id for u in still}
    withheld = [u for u in pending if u.canonical_university_id in reasons and u.canonical_university_id not in still_ids]
    unmatched.extend((u, reasons[u.canonical_university_id]) for u in withheld)
    if use_search and still:
        with ThreadPoolExecutor(max_workers=2) as pool:
            hits = list(pool.map(lambda u: [(n, search_wikidata(client, n)) for n in u.names()[:3]], still))
        entities = fetch_entities(client, {q for rows in hits for _n, ids in rows for q in ids}, all_languages=True)
        for university, rows in zip(still, hits):
            wanted = {strict_name(name) for name in university.names()}
            options: list[tuple[str, Candidate]] = []
            for name, ids in rows:
                for qid in ids:
                    entity = entities.get(qid)
                    if entity is None or not entity.title:
                        continue
                    if wanted & {strict_name(n) for n in [entity.label, *entity.aliases]}:
                        options.append((name, Candidate(qid, entity.title)))
            chosen, reason = _pick_validated(university, options, entities)
            if chosen is not None:
                name, candidate = chosen
                matched.append(Match(university, candidate.wikidata_id, candidate.title, "label_search", {"name": name}))
            else:
                key = university.canonical_university_id
                unmatched.append((university, conflicts.get(key) or reason or reasons.get(key) or "no article found"))
        log(f"by label search done; unmatched {len(unmatched)}")
    else:
        for university in still:
            key = university.canonical_university_id
            unmatched.append((university, conflicts.get(key) or reasons.get(key) or "no article found"))

    matched.sort(key=lambda m: m.university.canonical_slug)
    unmatched.sort(key=lambda pair: pair[0].canonical_slug)
    return MatchReport(matched, unmatched)


def _shadowed_redirects(client: ApiClient, matches: Sequence[Match]) -> dict[int, str]:
    """Redirect matches where the name belongs to a different institution than the redirect's target.

    A redirect says "this name leads here", not "this name is this". English
    Wikipedia redirects "Taiyuan Institute of Technology" to Taiyuan University of
    Technology, which bore that name until 1984; today's Taiyuan Institute of
    Technology is another school, with its own Wikidata item and no English article.
    So a redirect match is withheld when some other item, an institution in the same
    country, has the name as its English label.
    """
    redirected = [m for m in matches if strict_name(m.title) != strict_name(m.evidence["name"])]
    with ThreadPoolExecutor(max_workers=2) as pool:
        found = list(pool.map(lambda m: _label_hits(client, m.evidence["name"]), redirected))
    entities = fetch_entities(client, {qid for ids in found for qid in ids})
    out: dict[int, str] = {}
    for match, ids in zip(redirected, found):
        wanted = strict_name(match.evidence["name"])
        for qid in ids:
            entity = entities.get(qid)
            if entity is None or qid == match.wikidata_id or strict_name(entity.label) != wanted:
                continue
            if is_institution(entity) and country_agrees(entity, match.university.country):
                out[match.university.canonical_university_id] = (
                    f"\"{match.evidence['name']}\" redirects to {match.title}, but Wikidata item {qid} "
                    f"is a different institution with that name"
                )
                break
    return out


def _label_hits(client: ApiClient, name: str) -> list[str]:
    data = client.get_json(WIKIDATA_API, {
        "action": "wbsearchentities", "format": "json", "language": "en", "uselang": "en", "type": "item",
        "limit": "7", "search": name,
    })
    return [row["id"] for row in data.get("search", [])]


def _pick_validated(
    university: University, options: Sequence[tuple[str, Candidate]], entities: dict[str, Entity]
) -> tuple[Optional[tuple[str, Candidate]], Optional[str]]:
    """The one candidate that is an institution in the university's country, or why there is none.

    A university whose country the warehouse does not hold cannot be checked and is
    not matched by name at all. Two different valid candidates are an ambiguity, not
    a choice.
    """
    if not options:
        return None, None
    if not country_labels(university.country):
        return None, "name found, but the warehouse holds no country to check it against"
    own = set(university.own_names())
    rejected: list[str] = []
    ambiguous: Optional[str] = None
    # The display name first; a source's spelling is consulted only if it finds nothing.
    for group in ([o for o in options if o[0] in own], [o for o in options if o[0] not in own]):
        valid: dict[str, tuple[str, Candidate]] = {}
        for name, candidate in group:
            entity = entities.get(candidate.wikidata_id)
            if entity is None:
                continue
            if not is_institution(entity):
                rejected.append(
                    f"{candidate.title}: not an educational institution ({', '.join(entity.types) or 'no type'})"
                )
            elif not country_agrees(entity, university.country):
                rejected.append(
                    f"{candidate.title}: country is {', '.join(entity.countries[:1]) or 'unknown'}, "
                    f"not {university.country}"
                )
            else:
                valid.setdefault(candidate.wikidata_id, (name, candidate))
        if len(valid) == 1:
            return next(iter(valid.values())), None
        if len(valid) > 1:
            ambiguous = "names match more than one article: " + ", ".join(c.title for _n, c in valid.values())
            break
    return None, ambiguous or "; ".join(dict.fromkeys(rejected)) or None


def matches_document(report: MatchReport, *, generated_at: str) -> dict[str, Any]:
    by_method: dict[str, int] = {}
    for match in report.matched:
        by_method[match.method] = by_method.get(match.method, 0) + 1
    shared: dict[str, int] = {}
    for match in report.matched:
        shared[match.wikidata_id] = shared.get(match.wikidata_id, 0) + 1
    return {
        "loader_version": LOADER_VERSION,
        "language": LANGUAGE,
        "generated_at": generated_at,
        "counts": {
            "universities": len(report.matched) + len(report.unmatched),
            "matched": len(report.matched),
            "unmatched": len(report.unmatched),
            "by_method": dict(sorted(by_method.items())),
            "articles": len(shared),
        },
        "matched": [
            {
                "canonical_slug": m.university.canonical_slug,
                "display_name": m.university.display_name,
                "country": m.university.country,
                "wikidata_id": m.wikidata_id,
                "title": m.title,
                "method": m.method,
                "evidence": m.evidence,
                **({"shared_with": shared[m.wikidata_id] - 1} if shared[m.wikidata_id] > 1 else {}),
            }
            for m in report.matched
        ],
        "unmatched": [
            {
                "canonical_slug": u.canonical_slug,
                "display_name": u.display_name,
                "country": u.country,
                "reason": reason,
            }
            for u, reason in report.unmatched
        ],
    }


# ---------------------------------------------------------------------------
# Articles
# ---------------------------------------------------------------------------

_HEADING_RE = re.compile(r"^(={2,6})\s*(.*?)\s*\1\s*$")


def split_sections(extract: str) -> list[dict[str, Any]]:
    """A plain-text extract as ``[{level, heading, text}]``; the lead has level 1 and no heading.

    Apparatus sections (references, external links, ...) and their subsections are
    dropped, as are sections left empty once tables and lists are gone -- unless a
    kept subsection follows, in which case the empty parent stays as its heading.
    """
    sections: list[dict[str, Any]] = [{"level": 1, "heading": None, "lines": []}]
    for line in (extract or "").splitlines():
        heading = _HEADING_RE.match(line.strip())
        if heading:
            sections.append({"level": len(heading.group(1)), "heading": heading.group(2), "lines": []})
        else:
            sections[-1]["lines"].append(line.rstrip())

    kept: list[dict[str, Any]] = []
    dropping_below: Optional[int] = None
    for section in sections:
        if dropping_below is not None:
            if section["level"] > dropping_below:
                continue
            dropping_below = None
        if section["heading"] is not None and section["heading"].strip().lower() in DROPPED_SECTIONS:
            dropping_below = section["level"]
            continue
        text = re.sub(r"\n{3,}", "\n\n", "\n".join(section["lines"])).strip()
        kept.append({"level": section["level"], "heading": section["heading"], "text": text})

    out: list[dict[str, Any]] = []
    for index, section in enumerate(kept):
        if section["text"]:
            out.append(section)
            continue
        following = kept[index + 1] if index + 1 < len(kept) else None
        if section["heading"] is not None and following is not None and following["level"] > section["level"]:
            # Keep only if some descendant has text.
            for later in kept[index + 1:]:
                if later["level"] <= section["level"]:
                    break
                if later["text"]:
                    out.append(section)
                    break
    return out


def fetch_article(client: ApiClient, title: str) -> Optional[dict[str, Any]]:
    """One article's text and the revision it was read at, or None if the page is gone."""
    data = client.get_json(WIKIPEDIA_API, {
        "action": "query", "format": "json", "formatversion": "2", "redirects": "1", "titles": title,
        "prop": "extracts|revisions|pageprops|info", "explaintext": "1", "exsectionformat": "wiki", "exlimit": "1",
        "rvprop": "ids|timestamp", "ppprop": "wikibase_item|disambiguation", "inprop": "url", "maxlag": "5",
    })
    pages = data.get("query", {}).get("pages", [])
    if not pages or pages[0].get("missing") or "extract" not in pages[0]:
        return None
    page = pages[0]
    if "disambiguation" in page.get("pageprops", {}):
        return None
    revision = (page.get("revisions") or [{}])[0]
    sections = split_sections(page["extract"])
    if not sections:
        return None
    return {
        "wikidata_id": page.get("pageprops", {}).get("wikibase_item"),
        "page_id": page["pageid"],
        "title": page["title"],
        "url": page.get("canonicalurl") or f"https://{LANGUAGE}.wikipedia.org/wiki/{quote(page['title'].replace(' ', '_'))}",
        "revision_id": revision.get("revid"),
        "revision_timestamp": revision.get("timestamp"),
        "sections": sections,
    }


def shard_path(articles_dir: Path, wikidata_id: str) -> Path:
    return articles_dir / f"articles-{int(wikidata_id[1:]) % SHARD_COUNT:02d}.jsonl.gz"


def read_articles(articles_dir: Path) -> dict[str, dict[str, Any]]:
    """Every stored article, by the Wikidata id it was matched under."""
    articles: dict[str, dict[str, Any]] = {}
    for path in sorted(articles_dir.glob("articles-*.jsonl.gz")):
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    article = json.loads(line)
                    articles[article["wikidata_id"]] = article
    return articles


def write_articles(articles_dir: Path, articles: dict[str, dict[str, Any]]) -> list[Path]:
    """Rewrite every shard. Sorted lines and a zero gzip mtime: the same articles give the same bytes."""
    articles_dir.mkdir(parents=True, exist_ok=True)
    shards: dict[Path, list[dict[str, Any]]] = {}
    for wikidata_id, article in articles.items():
        shards.setdefault(shard_path(articles_dir, wikidata_id), []).append(article)
    for stale in set(articles_dir.glob("articles-*.jsonl.gz")) - set(shards):
        stale.unlink()
    for path, rows in shards.items():
        rows.sort(key=lambda a: int(a["wikidata_id"][1:]))
        body = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows).encode("utf-8")
        buffer = io.BytesIO()
        with gzip.GzipFile(filename="", mode="wb", fileobj=buffer, mtime=0, compresslevel=9) as handle:
            handle.write(body)
        if not path.exists() or path.read_bytes() != buffer.getvalue():
            path.write_bytes(buffer.getvalue())
    return sorted(shards)


def fetch_articles(
    matches: dict[str, Any],
    client: ApiClient,
    articles_dir: Path,
    *,
    refresh: bool = False,
    workers: int = 4,
    fetched_at: str,
    log: Callable[[str], None] = lambda _msg: None,
) -> tuple[int, list[str]]:
    """Fetch every matched article not already stored. Returns (fetched, problems).

    The article is stored under the Wikidata id the match named. If Wikipedia now
    serves a page belonging to a different item for that title -- the page was moved
    and the title reused -- it is not stored.
    """
    stored = {} if refresh else read_articles(articles_dir)
    wanted = {row["wikidata_id"]: row["title"] for row in matches["matched"]}
    todo = [(qid, title) for qid, title in sorted(wanted.items()) if qid not in stored]
    problems: list[str] = []

    def one(item: tuple[str, str]) -> tuple[str, str, Optional[dict[str, Any]], Optional[str]]:
        qid, title = item
        try:
            return qid, title, fetch_article(client, title), None
        except FetchError as exc:
            return qid, title, None, str(exc)

    done = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for qid, title, article, error in pool.map(one, todo):
            done += 1
            if done % 250 == 0:
                log(f"  {done}/{len(todo)}")
            if article is None:
                problems.append(f"{qid} {title}: {error or 'no article text'}")
            elif article["wikidata_id"] != qid:
                problems.append(f"{qid} {title}: page now belongs to {article['wikidata_id']}")
            else:
                article["fetched_at"] = fetched_at
                stored[qid] = article
    kept = {qid: article for qid, article in stored.items() if qid in wanted}
    write_articles(articles_dir, kept)
    return len(todo) - len(problems), problems


# ---------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------

TABLE = "warehouse.university_wikipedia_article"


def ingest(conn: Any, matches: dict[str, Any], articles: dict[str, dict[str, Any]]) -> dict[str, int]:
    """Make the table equal to the committed files, for the universities this database holds.

    Rows are looked up by ``canonical_slug`` (ids differ between databases), among
    active universities only. A row whose university is no longer matched is deleted: a stale article on a university
    whose match was withdrawn is exactly the error the matching rules exist to avoid.
    """
    with conn.cursor() as cur:
        cur.execute(f"SELECT to_regclass('{TABLE}') IS NOT NULL")
        if not cur.fetchone()[0]:
            raise RuntimeError(f"{TABLE} is missing; apply crawlernest-schema/wikipedia_article_postgresql.sql")
        # A record merged into another keeps its slug but is no longer a university page of its own.
        cur.execute("SELECT canonical_slug, canonical_university_id FROM warehouse.canonical_university "
                    "WHERE status = 'active'")
        ids = dict(cur.fetchall())
        counts = {"upserted": 0, "no_such_university": 0, "no_article_text": 0, "deleted": 0}
        keep: list[int] = []
        for row in matches["matched"]:
            canonical_id = ids.get(row["canonical_slug"])
            article = articles.get(row["wikidata_id"])
            if canonical_id is None:
                counts["no_such_university"] += 1
                continue
            if article is None:
                counts["no_article_text"] += 1
                continue
            keep.append(canonical_id)
            cur.execute(
                f"""
                INSERT INTO {TABLE} (
                    canonical_university_id, language_code, wikidata_id, page_id, page_title, page_url,
                    revision_id, revision_timestamp, match_method, match_evidence, sections, char_count,
                    license, fetched_at, loaded_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (canonical_university_id) DO UPDATE SET
                    language_code = EXCLUDED.language_code, wikidata_id = EXCLUDED.wikidata_id,
                    page_id = EXCLUDED.page_id, page_title = EXCLUDED.page_title, page_url = EXCLUDED.page_url,
                    revision_id = EXCLUDED.revision_id, revision_timestamp = EXCLUDED.revision_timestamp,
                    match_method = EXCLUDED.match_method, match_evidence = EXCLUDED.match_evidence,
                    sections = EXCLUDED.sections, char_count = EXCLUDED.char_count, license = EXCLUDED.license,
                    fetched_at = EXCLUDED.fetched_at, loaded_at = CURRENT_TIMESTAMP
                """,
                (
                    canonical_id, LANGUAGE, row["wikidata_id"], article["page_id"], article["title"], article["url"],
                    article["revision_id"], article["revision_timestamp"], row["method"],
                    json.dumps(row["evidence"], ensure_ascii=False),
                    json.dumps(article["sections"], ensure_ascii=False),
                    sum(len(s["text"]) for s in article["sections"]), LICENSE, article["fetched_at"],
                ),
            )
            counts["upserted"] += 1
        cur.execute(f"DELETE FROM {TABLE} WHERE NOT (canonical_university_id = ANY(%s))", (keep,))
        counts["deleted"] = cur.rowcount
    conn.commit()
    return counts


# ---------------------------------------------------------------------------
# Aliases
# ---------------------------------------------------------------------------

ALIASES_PATH = _JOBS_DIR.parent / "crawlernest-kb" / "databases" / "wikipedia_university_aliases_2026.json"
ALIAS_SOURCE = "English Wikipedia article title"


def title_alias_rows(
    universities: Sequence[tuple[int, str, str, Optional[str], Sequence[str]]],
    titles_by_slug: dict[str, str],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """The article title of each matched university, as an alias the resolver can use.

    Why: THE and ARWU print "University of Seville" where the record QS seeded is
    "Universidad de Sevilla". No rule turns one into the other, so the backfill of
    2026-09-20 opened a second record for some hundred universities. The article a
    record is matched to already knows its English name.

    ``universities`` is every active record as ``(id, slug, display_name, country,
    aliases)``. A title is left out when it would not be safe or would add nothing:

    ``shared_title``    two active records are matched to the article -- an unmerged
                        duplicate, to be settled by a person, not papered over
    ``disambiguated``   "Northeastern University (China)": the resolver indexes the bare
                        name too, and that is another university's
    ``already_a_name``  the record is already reachable by it
    ``collides``        another record is reachable by it
    """
    core = _JOBS_DIR.parent / "crawlernest-core"
    if str(core) not in sys.path:
        sys.path.insert(0, str(core))
    from entity_resolution.alias_safety import alias_collision, has_disambiguator, resolver_keys

    names = {uid: set().union(*(resolver_keys(n) for n in (display_name, *aliases)))
             for uid, _slug, display_name, _country, aliases in universities}
    holders: dict[str, int] = {}
    for _uid, slug, *_rest in universities:
        if slug in titles_by_slug:
            holders[titles_by_slug[slug]] = holders.get(titles_by_slug[slug], 0) + 1

    rows: list[dict[str, Any]] = []
    skipped = {"no_article": 0, "shared_title": 0, "disambiguated": 0, "already_a_name": 0, "collides": 0}
    claimed: set[str] = set()
    for uid, slug, display_name, country, _aliases in sorted(universities, key=lambda u: u[1]):
        title = titles_by_slug.get(slug)
        if not title:
            skipped["no_article"] += 1
        elif holders[title] > 1:
            skipped["shared_title"] += 1
        elif has_disambiguator(title):
            skipped["disambiguated"] += 1
        elif resolver_keys(title) & names[uid]:
            skipped["already_a_name"] += 1
        elif alias_collision(title, uid, names) or resolver_keys(title) & claimed:
            skipped["collides"] += 1
        else:
            claimed |= resolver_keys(title)
            rows.append({
                "canonical_slug_hint": display_name,
                "canonical_university_id": uid,
                "alias_text": title,
                "country": country,
                "source": ALIAS_SOURCE,
                "method": "rule",
            })
    return rows, skipped


def load_active_universities(conn: Any) -> list[tuple[int, str, str, Optional[str], list[str]]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT cu.canonical_university_id, cu.canonical_slug, cu.display_name, co.country_name,
                   COALESCE(ARRAY_AGG(ua.alias_text) FILTER (WHERE ua.alias_text IS NOT NULL), ARRAY[]::TEXT[])
            FROM warehouse.canonical_university cu
            LEFT JOIN warehouse.countries co ON co.country_id = cu.country_id
            LEFT JOIN warehouse.university_alias ua ON ua.canonical_university_id = cu.canonical_university_id
            WHERE cu.status = 'active'
            GROUP BY 1, 2, 3, 4
            """
        )
        return [(int(r[0]), r[1], r[2], r[3], list(r[4] or [])) for r in cur.fetchall()]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _pg(args: argparse.Namespace) -> PgConfig:
    return PgConfig(args.pg_host, args.pg_port, args.pg_database, args.pg_user, args.pg_password)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Match, fetch and load English Wikipedia articles for ranked universities.")
    parser.add_argument("command", choices=["match", "fetch", "ingest", "status", "aliases"])
    parser.add_argument("--aliases", type=Path, default=ALIASES_PATH)
    parser.add_argument("--matches", type=Path, default=MATCHES_PATH)
    parser.add_argument("--overrides", type=Path, default=OVERRIDES_PATH)
    parser.add_argument("--articles-dir", type=Path, default=ARTICLES_DIR)
    parser.add_argument("--cache-dir", type=Path, default=CACHE_DIR)
    parser.add_argument("--refresh", action="store_true", help="ignore the response cache and stored articles")
    parser.add_argument("--offline", action="store_true", help="read only from the response cache; no network")
    parser.add_argument("--no-search", action="store_true", help="match: skip the Wikidata label search")
    parser.add_argument("--request-delay", type=float, default=0.1)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--pg-host", default="localhost")
    parser.add_argument("--pg-port", type=int, default=5432)
    parser.add_argument("--pg-database", default="clawer")
    parser.add_argument("--pg-user", default="test")
    parser.add_argument("--pg-password", default="test")
    args = parser.parse_args(argv)
    client = ApiClient(
        cache_dir=args.cache_dir, min_interval=args.request_delay, refresh=args.refresh, offline=args.offline
    )

    if args.command == "match":
        conn = _pg(args).connect()
        try:
            universities = load_universities(conn)
        finally:
            conn.close()
        print(f"universities with ranking data: {len(universities)}")
        overrides = json.loads(args.overrides.read_text(encoding="utf-8")) if args.overrides.exists() else {}
        report = build_matches(universities, client, overrides=overrides, use_search=not args.no_search, log=print)
        document = matches_document(report, generated_at=_now())
        args.matches.parent.mkdir(parents=True, exist_ok=True)
        args.matches.write_text(json.dumps(document, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(json.dumps(document["counts"], indent=1))
        print(f"-> {args.matches}")
        return 0

    matches = json.loads(args.matches.read_text(encoding="utf-8"))
    if args.command == "fetch":
        fetched, problems = fetch_articles(
            matches, client, args.articles_dir, refresh=args.refresh, workers=args.workers, fetched_at=_now(), log=print
        )
        for problem in problems:
            print(f"  not stored: {problem}", file=sys.stderr)
        stored = read_articles(args.articles_dir)
        size = sum(p.stat().st_size for p in args.articles_dir.glob("articles-*.jsonl.gz"))
        print(f"fetched {fetched}, not stored {len(problems)}, articles on disk {len(stored)} ({size / 1e6:.1f} MB)")
        return 1 if problems else 0

    if args.command == "aliases":
        conn = _pg(args).connect()
        try:
            universities = load_active_universities(conn)
        finally:
            conn.close()
        rows, skipped = title_alias_rows(universities, {row["canonical_slug"]: row["title"] for row in matches["matched"]})
        args.aliases.write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(json.dumps({"aliases": len(rows), "skipped": skipped}, indent=1))
        print(f"-> {args.aliases}\nseed with: crawlernest/scripts/seed_alias_file.py --alias-file {args.aliases}")
        return 0

    articles = read_articles(args.articles_dir)
    if args.command == "status":
        missing = [row for row in matches["matched"] if row["wikidata_id"] not in articles]
        print(json.dumps({**matches["counts"], "articles_stored": len(articles), "matched_without_text": len(missing)}, indent=1))
        return 0

    conn = _pg(args).connect()
    try:
        counts = ingest(conn, matches, articles)
    finally:
        conn.close()
    print(json.dumps(counts, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
