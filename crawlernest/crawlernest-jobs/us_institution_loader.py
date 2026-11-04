#!/usr/bin/env python3
"""Attach US federal institutional data (College Scorecard, IPEDS) to US universities.

Three steps, each its own subcommand, each leaving a file the next one reads:

``match``   reads the warehouse, the Wikipedia matches and Wikidata, writes
            ``crawlernest-kb/us_institutions/matches.json``: which IPEDS UNITID each university is
``fetch``   downloads the pinned federal files, writes ``manifest.json`` (what was read, its
            SHA-256) and ``records.json`` (the chosen fields for the matched UNITIDs only)
``ingest``  reads both files, fills ``warehouse.us_institution`` and
            ``warehouse.us_institution_metric``; no network

What this data is, and is not
-----------------------------
It is not a ranking source. Nothing here enters ``DATASET_SOURCES``, the composite score,
the coverage ratio or the confidence label, which count *ranking* sources. It is a set of
facts the U.S. Department of Education publishes about an institution, each with its own
reference period: an admission rate for one fall, earnings for a cohort that entered a
decade earlier. Every value is stored with that period, the source field it came from, and
its status, because "suppressed for privacy", "imputed by NCES" and "not in the file" are
three different things and none of them is zero.

Matching
--------
A university is tied to a UNITID only through identifiers, never through a name:

``wikidata_ipeds_id``   the university's Wikidata item (from the Wikipedia loader's
                        ``matches.json``) carries exactly one IPEDS ID (P1771).
``reviewed_override``   ``overrides.json`` names the UNITID, with the reason.

Refused, and listed with the reason: no Wikidata item; an item with no P1771 or several;
an item two active records share (one university carried as two records -- see
``.claude/CLAUDE.md``); a UNITID two records would share. University systems (CUNY) and
campuses Wikidata does not separate are left to ``overrides.json``.

Sources (both public domain, U.S. federal government works):
  College Scorecard, Most Recent Institution-Level file and its data dictionary, ed.gov
  IPEDS Complete Data Files (HD directory, EFFY 12-month enrollment, ADM admissions), NCES
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Optional, Sequence

_JOBS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _JOBS_DIR.parents[1]

LOADER_VERSION = "1"
USER_AGENT = "CrawlerNest-us-institution-loader/1 (https://github.com/heinricitorgau; university data research)"

KB_DIR = _JOBS_DIR.parent / "crawlernest-kb" / "us_institutions"
MATCHES_PATH = KB_DIR / "matches.json"
#: Reviewed corrections: ``{canonical_slug: {"unitid": "<UNITID>" or null, "why": "..."}}``.
#: ``null`` withholds a match the rules would make; a UNITID makes one they would not.
OVERRIDES_PATH = KB_DIR / "overrides.json"
MANIFEST_PATH = KB_DIR / "manifest.json"
RECORDS_PATH = KB_DIR / "records.json"
WIKIPEDIA_MATCHES_PATH = _JOBS_DIR.parent / "crawlernest-kb" / "wikipedia" / "en" / "matches.json"
CACHE_DIR = _REPO_ROOT / ".local" / "tmp" / "us_institution_cache"

#: Warehouse countries whose institutions IPEDS covers (Puerto Rico reports to IPEDS).
US_COUNTRIES = ("United States", "Puerto Rico")

WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
IPEDS_PROPERTY = "P1771"

SCORECARD = "COLLEGE_SCORECARD"
IPEDS = "IPEDS"

#: The files read. The Scorecard file name carries its publication date; when ed.gov
#: publishes a new one, change it here and re-run ``fetch``.
FILES: dict[str, dict[str, str]] = {
    "scorecard_institution": {
        "source": SCORECARD,
        "url": "https://ed-public-download.scorecard.network/downloads/Most-Recent-Cohorts-Institution_11022026.zip",
        "member": "Most-Recent-Cohorts-Institution.csv",
    },
    "scorecard_dictionary": {
        "source": SCORECARD,
        "url": "https://collegescorecard.ed.gov/files/CollegeScorecardDataDictionary.xlsx",
    },
    "ipeds_hd": {"source": IPEDS, "url": "https://nces.ed.gov/ipeds/datacenter/data/HD2024.zip", "member": "HD2024.csv"},
    "ipeds_hd_dictionary": {
        "source": IPEDS, "url": "https://nces.ed.gov/ipeds/datacenter/data/HD2024_Dict.zip", "member": "HD2024_dict.xlsx",
    },
    "ipeds_effy": {
        "source": IPEDS, "url": "https://nces.ed.gov/ipeds/datacenter/data/EFFY2024.zip", "member": "EFFY2024.csv",
    },
    "ipeds_effy_dictionary": {
        "source": IPEDS, "url": "https://nces.ed.gov/ipeds/datacenter/data/EFFY2024_Dict.zip",
        "member": "EFFY2024_dict.xlsx",
    },
    "ipeds_adm": {"source": IPEDS, "url": "https://nces.ed.gov/ipeds/datacenter/data/ADM2023.zip", "member": "adm2023.csv"},
    "ipeds_adm_dictionary": {
        "source": IPEDS, "url": "https://nces.ed.gov/ipeds/datacenter/data/ADM2023_Dict.zip", "member": "adm2023.xlsx",
    },
}

UNITS = ("ratio", "percent", "usd", "count", "score", "code", "text")
STATUSES = ("reported", "imputed", "privacy_suppressed", "not_available", "not_applicable")
MATCH_METHODS = ("wikidata_ipeds_id", "reviewed_override")


@dataclass(frozen=True)
class Metric:
    key: str
    source: str
    field: str
    unit: str
    #: For IPEDS: the file it is read from ("hd", "effy", "adm").
    table: str = ""


#: Scorecard fields. ``average_net_price`` is NPT4_PUB or NPT4_PRIV by the institution's
#: control, read in :func:`scorecard_metrics`; the others are one column each.
SCORECARD_METRICS: tuple[Metric, ...] = (
    Metric("control", SCORECARD, "CONTROL", "code"),
    Metric("admission_rate", SCORECARD, "ADM_RATE", "ratio"),
    Metric("sat_reading_25", SCORECARD, "SATVR25", "score"),
    Metric("sat_reading_75", SCORECARD, "SATVR75", "score"),
    Metric("sat_math_25", SCORECARD, "SATMT25", "score"),
    Metric("sat_math_75", SCORECARD, "SATMT75", "score"),
    Metric("act_composite_25", SCORECARD, "ACTCM25", "score"),
    Metric("act_composite_75", SCORECARD, "ACTCM75", "score"),
    Metric("undergraduate_enrollment", SCORECARD, "UGDS", "count"),
    Metric("cost_of_attendance", SCORECARD, "COSTT4_A", "usd"),
    Metric("tuition_in_state", SCORECARD, "TUITIONFEE_IN", "usd"),
    Metric("tuition_out_of_state", SCORECARD, "TUITIONFEE_OUT", "usd"),
    Metric("pell_share", SCORECARD, "PCTPELL", "ratio"),
    Metric("completion_rate_4yr", SCORECARD, "C150_4", "ratio"),
    Metric("retention_rate_4yr", SCORECARD, "RET_FT4", "ratio"),
    Metric("median_earnings_10yr", SCORECARD, "MD_EARN_WNE_P10", "usd"),
    Metric("median_debt_completers", SCORECARD, "GRAD_DEBT_MDN", "usd"),
)
NET_PRICE_FIELDS = {"1": "NPT4_PUB", "2": "NPT4_PRIV", "3": "NPT4_PRIV"}

IPEDS_METRICS: tuple[Metric, ...] = (
    Metric("system_name", IPEDS, "F1SYSNAM", "text", "hd"),
    Metric("carnegie_basic_2021", IPEDS, "C21BASIC", "code", "hd"),
    Metric("carnegie_research_2025", IPEDS, "CARNEGIERSCH", "code", "hd"),
    Metric("total_enrollment_12mo", IPEDS, "EFYTOTLT", "count", "effy"),
    Metric("graduate_enrollment_12mo", IPEDS, "EFYTOTLT", "count", "effy"),
    Metric("applicants_total", IPEDS, "APPLCN", "count", "adm"),
    Metric("admitted_total", IPEDS, "ADMSSN", "count", "adm"),
    Metric("enrolled_first_year_total", IPEDS, "ENRLT", "count", "adm"),
    Metric("test_score_policy", IPEDS, "ADMCON7", "code", "adm"),
    Metric("sat_submitters_percent", IPEDS, "SATPCT", "percent", "adm"),
    Metric("act_submitters_percent", IPEDS, "ACTPCT", "percent", "adm"),
)
#: EFFYLEV rows the two enrollment metrics read: 1 = all students, 4 = graduate.
EFFY_LEVELS = {"total_enrollment_12mo": "1", "graduate_enrollment_12mo": "4"}

#: IPEDS imputation flags (the ``X<field>`` columns), from the files' "Imputation values" sheet.
IPEDS_REPORTED_FLAGS = {"R"}
IPEDS_NOT_APPLICABLE_FLAGS = {"A"}
IPEDS_MISSING_FLAGS = {"B", "D", "H"}  # left blank, do not know, not usable


# ---------------------------------------------------------------------------
# Reading the federal files
# ---------------------------------------------------------------------------

_XLSX_NS = {
    "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}


def read_xlsx(data: bytes) -> dict[str, list[dict[str, str]]]:
    """Every sheet of a workbook as rows of ``{column letter: text}``. Standard library only."""
    book = zipfile.ZipFile(io.BytesIO(data))
    names = book.namelist()
    shared: list[str] = []
    if "xl/sharedStrings.xml" in names:
        for item in ET.fromstring(book.read("xl/sharedStrings.xml")).findall("m:si", _XLSX_NS):
            shared.append("".join(t.text or "" for t in item.iter(f"{{{_XLSX_NS['m']}}}t")))
    workbook = ET.fromstring(book.read("xl/workbook.xml"))
    rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))}
    out: dict[str, list[dict[str, str]]] = {}
    sheets = workbook.find("m:sheets", _XLSX_NS)
    for sheet in (list(sheets) if sheets is not None else []):
        target = (rels[sheet.get(f"{{{_XLSX_NS['r']}}}id")] or "").lstrip("/")
        target = target if target.startswith("xl/") else f"xl/{target}"
        rows: list[dict[str, str]] = []
        for row in ET.fromstring(book.read(target)).iter(f"{{{_XLSX_NS['m']}}}row"):
            cells: dict[str, str] = {}
            for cell in row.findall("m:c", _XLSX_NS):
                column = re.match(r"[A-Z]+", cell.get("r") or "").group(0)
                value = cell.find("m:v", _XLSX_NS)
                kind = cell.get("t")
                if kind == "s" and value is not None:
                    text = shared[int(value.text or 0)]
                elif kind == "inlineStr":
                    text = "".join(t.text or "" for t in cell.iter(f"{{{_XLSX_NS['m']}}}t"))
                else:
                    text = value.text if value is not None and value.text is not None else ""
                cells[column] = text
            rows.append(cells)
        out[sheet.get("name") or ""] = rows
    return out


def read_csv_rows(data: bytes) -> list[dict[str, str]]:
    """A federal CSV as dicts. Strips the BOM, and the padding IPEDS leaves on names and values."""
    text = data.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))
    header = [h.strip().upper() for h in next(reader)]
    return [{h: (v or "").strip() for h, v in zip(header, row)} for row in reader]


def zip_member(data: bytes, member: str) -> bytes:
    """One file from a zip, matched case-insensitively (NCES capitalises inconsistently)."""
    book = zipfile.ZipFile(io.BytesIO(data))
    for name in book.namelist():
        if name.lower() == member.lower():
            return book.read(name)
    raise KeyError(f"{member} not in archive (has: {book.namelist()})")


@dataclass
class ScorecardDictionary:
    #: field -> the cohort/measure text of the Most Recent file, verbatim
    periods: dict[str, str]
    #: field -> {code: label}
    labels: dict[str, dict[str, str]]
    #: the README's "Released ..." line
    release: str


def parse_scorecard_dictionary(sheets: Mapping[str, list[dict[str, str]]]) -> ScorecardDictionary:
    periods = {
        row["A"].strip().upper(): row["B"].strip()
        for row in sheets["Most_Recent_Inst_Cohort_Map"][1:]
        if row.get("A") and row.get("B")
    }
    labels: dict[str, dict[str, str]] = defaultdict(dict)
    current = ""
    for row in sheets["Institution_Data_Dictionary"][1:]:
        if row.get("F"):
            current = row["F"].strip().upper()
        if current and row.get("G", "").strip() and row.get("H", "").strip():
            labels[current][row["G"].strip()] = row["H"].strip()
    release = next((row["A"].strip() for row in sheets.get("README", []) if row.get("A", "").startswith("Released")), "")
    return ScorecardDictionary(periods, dict(labels), release)


@dataclass
class IpedsDictionary:
    #: "IPEDS Directory, 2024-25 (Release 1)": the file's own title, verbatim
    title: str
    #: field -> {code: label}
    labels: dict[str, dict[str, str]]
    #: imputation flag -> label
    flags: dict[str, str]


def parse_ipeds_dictionary(sheets: Mapping[str, list[dict[str, str]]]) -> IpedsDictionary:
    intro = next(rows for name, rows in sheets.items() if name.lower() == "introduction")
    heading = intro[0].get("A", "").strip()
    release = intro[1].get("A", "").strip() if len(intro) > 1 else ""
    title = re.sub(r"^File Documentation for the\s+", "", heading)
    if release.startswith("("):
        title = f"{title} {release}"
    frequencies = next(rows for name, rows in sheets.items() if name.lower() == "frequencies")
    labels: dict[str, dict[str, str]] = defaultdict(dict)
    for row in frequencies[1:]:
        var, code, label = row.get("B", "").strip().upper(), row.get("C", "").strip(), row.get("D", "").strip()
        if var and code:
            labels[var][code] = " ".join(label.split())
    flags: dict[str, str] = {}
    for name, rows in sheets.items():
        if name.lower().startswith("imputation"):
            for row in rows:
                code, label = row.get("A", "").strip(), row.get("B", "").strip()
                if len(code) == 1 and code.isalpha() and label:
                    flags[code] = label.rstrip(";").strip()
    return IpedsDictionary(title, dict(labels), flags)


# ---------------------------------------------------------------------------
# Values
# ---------------------------------------------------------------------------

def number_text(raw: str) -> Optional[str]:
    """A source number as exact decimal text ("0.0455", "85960"), or None when it is not one."""
    try:
        value = Decimal(raw)
    except (InvalidOperation, ValueError):
        return None
    if not value.is_finite():
        return None
    text = format(value.normalize(), "f")
    return text


def value_row(metric: Metric, *, status: str, period: str, release: str, field: Optional[str] = None,
              number: Optional[str] = None, text: Optional[str] = None, detail: Optional[str] = None) -> dict[str, Any]:
    if status not in STATUSES:
        raise ValueError(f"unknown status {status!r}")
    if (status in ("reported", "imputed")) != (number is not None or text is not None):
        raise ValueError(f"{metric.key}: status {status} with value {number!r}/{text!r}")
    return {
        "key": metric.key, "source": metric.source, "field": field or metric.field, "unit": metric.unit,
        "value_number": number, "value_text": text, "status": status, "status_detail": detail,
        "period": period, "release": release,
    }


def scorecard_value(metric: Metric, raw: str, *, field: str, dictionary: ScorecardDictionary,
                    release: str) -> dict[str, Any]:
    """One Scorecard value. ``PS`` is privacy-suppressed; ``NA`` and blank are not available."""
    period = dictionary.periods.get(field, "")
    if not period:
        raise ValueError(f"the data dictionary gives no period for {field}")
    common = dict(period=period, release=release, field=field)
    raw = (raw or "").strip()
    if raw == "PS":
        return value_row(metric, status="privacy_suppressed", detail="PS: privacy suppressed by the source", **common)
    if raw in ("", "NA", "NULL"):
        return value_row(metric, status="not_available", detail="NA in the source file", **common)
    if metric.unit == "code":
        label = dictionary.labels.get(field, {}).get(raw)
        return value_row(metric, status="reported", number=number_text(raw), text=label, **common)
    number = number_text(raw)
    if number is None:
        return value_row(metric, status="not_available", detail=f"not a number in the source file: {raw!r}", **common)
    return value_row(metric, status="reported", number=number, **common)


def scorecard_metrics(row: Mapping[str, str], dictionary: ScorecardDictionary, release: str) -> list[dict[str, Any]]:
    out = [scorecard_value(m, row.get(m.field, ""), field=m.field, dictionary=dictionary, release=release)
           for m in SCORECARD_METRICS]
    net_field = NET_PRICE_FIELDS.get((row.get("CONTROL") or "").strip())
    net = Metric("average_net_price", SCORECARD, net_field or "NPT4_PUB", "usd")
    if net_field:
        out.append(scorecard_value(net, row.get(net_field, ""), field=net_field, dictionary=dictionary, release=release))
    else:
        out.append(value_row(net, status="not_available", detail="control unknown, so no net-price field applies",
                             period=dictionary.periods.get("NPT4_PUB", ""), release=release))
    return out


def ipeds_value(metric: Metric, row: Optional[Mapping[str, str]], dictionary: IpedsDictionary, *,
                file_label: str) -> dict[str, Any]:
    """One IPEDS value, with its imputation flag read from the ``X<field>`` column."""
    common = dict(period=dictionary.title, release=file_label)
    if row is None:
        return value_row(metric, status="not_available", detail=f"the institution has no row in {file_label}", **common)
    raw = (row.get(metric.field) or "").strip()
    flag = (row.get(f"X{metric.field}") or "").strip().upper()
    flag_label = dictionary.flags.get(flag, flag)
    if metric.unit == "text":
        if raw in ("", "-1", "-2", "."):
            return value_row(metric, status="not_applicable" if raw == "-2" else "not_available",
                             detail=f"{raw or 'blank'} in the source file", **common)
        return value_row(metric, status="reported", text=raw, **common)
    if flag in IPEDS_NOT_APPLICABLE_FLAGS or raw == "-2":
        return value_row(metric, status="not_applicable", detail=flag_label or "-2: not applicable", **common)
    if flag in IPEDS_MISSING_FLAGS or raw in ("", ".", "-1", "-3"):
        return value_row(metric, status="not_available", detail=flag_label or f"{raw or 'blank'} in the source file",
                         **common)
    number = number_text(raw)
    if number is None:
        return value_row(metric, status="not_available", detail=f"not a number in the source file: {raw!r}", **common)
    label = dictionary.labels.get(metric.field, {}).get(raw) if metric.unit == "code" else None
    # A field without a flag column (codes, directory items) is as reported.
    status = "reported" if not flag or flag in IPEDS_REPORTED_FLAGS else "imputed"
    return value_row(metric, status=status, number=number, text=label,
                     detail=None if status == "reported" else f"{flag}: {flag_label}", **common)


def ipeds_metrics(unitid: str, tables: Mapping[str, Mapping[str, Any]],
                  dictionaries: Mapping[str, IpedsDictionary], labels: Mapping[str, str]) -> list[dict[str, Any]]:
    out = []
    for metric in IPEDS_METRICS:
        table = tables[metric.table]
        if metric.table == "effy":
            row = table.get((unitid, EFFY_LEVELS[metric.key]))
        else:
            row = table.get(unitid)
        if metric.key == "system_name" and row is not None and (row.get("F1SYSTYP") or "").strip() == "2":
            out.append(value_row(metric, status="not_applicable", detail="not part of a multi-campus organization",
                                 period=dictionaries[metric.table].title, release=labels[metric.table]))
            continue
        out.append(ipeds_value(metric, row, dictionaries[metric.table], file_label=labels[metric.table]))
    return out


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class University:
    canonical_slug: str
    display_name: str
    country: str


def load_universities(conn: Any) -> list[University]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT cu.canonical_slug, cu.display_name, co.country_name
            FROM warehouse.canonical_university cu
            JOIN warehouse.countries co ON co.country_id = cu.country_id
            WHERE cu.status = 'active' AND co.country_name = ANY(%s)
            ORDER BY cu.canonical_slug
            """,
            (list(US_COUNTRIES),),
        )
        return [University(*row) for row in cur.fetchall()]


def build_matches(
    universities: Sequence[University],
    wikidata_ids: Mapping[str, str],
    ipeds_ids: Mapping[str, Sequence[str]],
    overrides: Mapping[str, Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Tie each university to one UNITID, or say why not.

    ``wikidata_ids``: canonical_slug -> QID, from the Wikipedia matches.
    ``ipeds_ids``: QID -> the P1771 values Wikidata holds.
    """
    by_qid: dict[str, list[str]] = defaultdict(list)
    for u in universities:
        if u.canonical_slug in wikidata_ids:
            by_qid[wikidata_ids[u.canonical_slug]].append(u.canonical_slug)

    candidates: dict[str, dict[str, Any]] = {}
    unmatched: list[dict[str, Any]] = []
    for u in universities:
        base = {"canonical_slug": u.canonical_slug, "display_name": u.display_name, "country": u.country}
        override = overrides.get(u.canonical_slug)
        if override is not None:
            unitid = override.get("unitid")
            if unitid is None:
                unmatched.append({**base, "reason": f"withheld by overrides.json: {override.get('why', '')}".strip()})
            else:
                candidates[u.canonical_slug] = {**base, "wikidata_id": wikidata_ids.get(u.canonical_slug),
                                                "unitid": str(unitid), "method": "reviewed_override",
                                                "evidence": {"why": override.get("why", "")}}
            continue
        qid = wikidata_ids.get(u.canonical_slug)
        if not qid:
            unmatched.append({**base, "reason": "no Wikidata item (not matched in wikipedia/en/matches.json)"})
            continue
        sharing = [slug for slug in by_qid[qid] if slug != u.canonical_slug]
        if sharing:
            unmatched.append({**base, "wikidata_id": qid, "reason":
                              f"Wikidata item {qid} is also matched to {', '.join(sharing)}: one university carried "
                              "as two records? Settle which record it is before attaching federal data."})
            continue
        values = sorted(set(ipeds_ids.get(qid, ())))
        if not values:
            unmatched.append({**base, "wikidata_id": qid, "reason": f"Wikidata item {qid} has no IPEDS ID ({IPEDS_PROPERTY})"})
            continue
        if len(values) > 1:
            unmatched.append({**base, "wikidata_id": qid,
                              "reason": f"Wikidata item {qid} has several IPEDS IDs: {', '.join(values)}"})
            continue
        candidates[u.canonical_slug] = {**base, "wikidata_id": qid, "unitid": values[0], "method": "wikidata_ipeds_id",
                                        "evidence": {"property": IPEDS_PROPERTY}}

    claims = Counter(row["unitid"] for row in candidates.values())
    matched = []
    for slug, row in sorted(candidates.items()):
        if claims[row["unitid"]] > 1:
            others = [s for s, r in candidates.items() if r["unitid"] == row["unitid"] and s != slug]
            unmatched.append({k: v for k, v in row.items() if k not in ("method", "evidence")}
                             | {"reason": f"UNITID {row['unitid']} would also go to {', '.join(sorted(others))}"})
        else:
            matched.append(row)
    unmatched.sort(key=lambda r: r["canonical_slug"])
    return {"matched": matched, "unmatched": unmatched}


def matches_document(report: Mapping[str, list[dict[str, Any]]], *, generated_at: str) -> dict[str, Any]:
    return {
        "loader_version": LOADER_VERSION,
        "generated_at": generated_at,
        "countries": list(US_COUNTRIES),
        "counts": {
            "universities": len(report["matched"]) + len(report["unmatched"]),
            "matched": len(report["matched"]),
            "unmatched": len(report["unmatched"]),
            "by_method": dict(Counter(row["method"] for row in report["matched"])),
        },
        "matched": list(report["matched"]),
        "unmatched": list(report["unmatched"]),
    }


def wikidata_ipeds_ids(qids: Iterable[str], http: "Http") -> dict[str, list[str]]:
    """QID -> its P1771 values, by SPARQL in batches."""
    qids = sorted(set(qids))
    out: dict[str, list[str]] = defaultdict(list)
    for start in range(0, len(qids), 200):
        batch = " ".join(f"wd:{q}" for q in qids[start:start + 200])
        query = f"SELECT ?item ?ipeds WHERE {{ VALUES ?item {{ {batch} }} ?item wdt:{IPEDS_PROPERTY} ?ipeds }}"
        data = json.loads(http.post(WIKIDATA_SPARQL, {"query": query, "format": "json"},
                                    accept="application/sparql-results+json"))
        for binding in data["results"]["bindings"]:
            qid = binding["item"]["value"].rsplit("/", 1)[1]
            out[qid].append(binding["ipeds"]["value"].strip())
    return dict(out)


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------

def build_records(
    matches: Mapping[str, Any],
    scorecard_rows: Sequence[Mapping[str, str]],
    scorecard_dictionary: ScorecardDictionary,
    scorecard_release: str,
    ipeds_tables: Mapping[str, Sequence[Mapping[str, str]]],
    ipeds_dictionaries: Mapping[str, IpedsDictionary],
    ipeds_labels: Mapping[str, str],
) -> tuple[dict[str, Any], list[str]]:
    """The chosen fields for the matched UNITIDs, and the UNITIDs neither source holds."""
    wanted = {row["unitid"] for row in matches["matched"]}
    scorecard = {row["UNITID"]: row for row in scorecard_rows if row.get("UNITID") in wanted}
    hd = {row["UNITID"]: row for row in ipeds_tables["hd"] if row.get("UNITID") in wanted}
    effy = {(row["UNITID"], row.get("EFFYLEV", "")): row for row in ipeds_tables["effy"] if row.get("UNITID") in wanted}
    adm = {row["UNITID"]: row for row in ipeds_tables["adm"] if row.get("UNITID") in wanted}
    institutions: dict[str, Any] = {}
    missing: list[str] = []
    for unitid in sorted(wanted, key=int):
        sc, directory = scorecard.get(unitid), hd.get(unitid)
        if sc is None and directory is None:
            missing.append(unitid)
            continue
        name = (directory or {}).get("INSTNM") or (sc or {}).get("INSTNM", "")
        metrics: list[dict[str, Any]] = []
        if sc is not None:
            metrics.extend(scorecard_metrics(sc, scorecard_dictionary, scorecard_release))
        metrics.extend(ipeds_metrics(unitid, {"hd": hd, "effy": effy, "adm": adm}, ipeds_dictionaries, ipeds_labels))
        institutions[unitid] = {
            "unitid": unitid,
            "name": name,
            "opeid": (sc or {}).get("OPEID") or (directory or {}).get("OPEID") or None,
            "city": (directory or {}).get("CITY") or (sc or {}).get("CITY") or None,
            "state": (directory or {}).get("STABBR") or (sc or {}).get("STABBR") or None,
            "website": (sc or {}).get("INSTURL") or (directory or {}).get("WEBADDR") or None,
            "in_scorecard": sc is not None,
            "in_ipeds_directory": directory is not None,
            "metrics": metrics,
        }
    return institutions, missing


def field_id(source: str, field: str) -> str:
    return f"{source}:{field}"


def records_document(institutions: Mapping[str, Any], manifest: Mapping[str, Any]) -> dict[str, Any]:
    """The values, with each field's period and release stated once rather than per institution.

    A field's period is the source's statement about the whole file ("Fall 2024, reported in
    IPEDS DCY2024-25"), so it is the same for every institution that has the field.
    """
    fields: dict[str, dict[str, str]] = {}
    compact: dict[str, Any] = {}
    for unitid, record in institutions.items():
        rows = []
        for m in record["metrics"]:
            fid = field_id(m["source"], m["field"])
            known = fields.setdefault(fid, {"period": m["period"], "release": m["release"]})
            if known != {"period": m["period"], "release": m["release"]}:
                raise ValueError(f"{fid} has two periods: {known} and {m['period']!r}")
            rows.append({k: v for k, v in m.items() if k not in ("period", "release")})
        compact[unitid] = {**record, "metrics": rows}
    return {
        "loader_version": LOADER_VERSION,
        "manifest_sha256": hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest(),
        "fields": dict(sorted(fields.items())),
        "institutions": compact,
    }


def expand_metrics(records: Mapping[str, Any], unitid: str) -> list[dict[str, Any]]:
    """An institution's values with their period and release put back."""
    fields = records["fields"]
    return [{**m, **fields[field_id(m["source"], m["field"])]} for m in records["institutions"][unitid]["metrics"]]


def write_records(path: Path, document: Mapping[str, Any]) -> None:
    """One value per line, so a refreshed file diffs value by value."""
    lines = ["{",
             f' "loader_version": {json.dumps(document["loader_version"])},',
             f' "manifest_sha256": {json.dumps(document["manifest_sha256"])},',
             ' "fields": ' + json.dumps(document["fields"], ensure_ascii=False, indent=1).replace("\n", "\n ") + ",",
             ' "institutions": {']
    items = list(document["institutions"].items())
    for i, (unitid, record) in enumerate(items):
        head = {k: v for k, v in record.items() if k != "metrics"}
        lines.append(f"  {json.dumps(unitid)}: {{")
        for k, v in head.items():
            lines.append(f"   {json.dumps(k)}: {json.dumps(v, ensure_ascii=False)},")
        lines.append('   "metrics": [')
        metrics = record["metrics"]
        for j, m in enumerate(metrics):
            lines.append("    " + json.dumps(m, ensure_ascii=False) + ("," if j < len(metrics) - 1 else ""))
        lines.append("   ]")
        lines.append("  }" + ("," if i < len(items) - 1 else ""))
    lines.append(" }")
    lines.append("}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------

class Http:
    """GET and POST with a descriptive User-Agent, a pause between requests, and an on-disk cache."""

    def __init__(self, cache_dir: Path, *, refresh: bool = False, min_interval: float = 1.0) -> None:
        self.cache_dir = cache_dir
        self.refresh = refresh
        self.min_interval = min_interval
        self._last = 0.0

    def _wait(self) -> None:
        delay = self._last + self.min_interval - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        self._last = time.monotonic()

    def get(self, url: str) -> bytes:
        path = self.cache_dir / hashlib.sha256(url.encode()).hexdigest()
        if path.exists() and not self.refresh:
            return path.read_bytes()
        self._wait()
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=300) as response:
            data = response.read()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return data

    def post(self, url: str, form: Mapping[str, str], *, accept: str) -> bytes:
        self._wait()
        request = urllib.request.Request(url, data=urllib.parse.urlencode(form).encode(),
                                         headers={"User-Agent": USER_AGENT, "Accept": accept})
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.read()


def fetch_files(http: Http, retrieved_at: str) -> tuple[dict[str, bytes], dict[str, Any]]:
    """Download every file in :data:`FILES`; the manifest records what was read."""
    payloads: dict[str, bytes] = {}
    entries: dict[str, Any] = {}
    for key, spec in FILES.items():
        data = http.get(spec["url"])
        payloads[key] = zip_member(data, spec["member"]) if "member" in spec else data
        entries[key] = {
            "source": spec["source"], "url": spec["url"], "member": spec.get("member"),
            "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
        }
    return payloads, {"loader_version": LOADER_VERSION, "retrieved_at": retrieved_at, "files": entries}


def parse_payloads(payloads: Mapping[str, bytes]) -> dict[str, Any]:
    scorecard_dictionary = parse_scorecard_dictionary(read_xlsx(payloads["scorecard_dictionary"]))
    ipeds_dictionaries = {
        table: parse_ipeds_dictionary(read_xlsx(payloads[f"ipeds_{table}_dictionary"])) for table in ("hd", "effy", "adm")
    }
    file_name = {"hd": "HD2024", "effy": "EFFY2024", "adm": "ADM2023"}
    return {
        "scorecard_rows": read_csv_rows(payloads["scorecard_institution"]),
        "scorecard_dictionary": scorecard_dictionary,
        "scorecard_release": f"College Scorecard Most Recent Institution-Level Data "
                             f"({FILES['scorecard_institution']['url'].rsplit('/', 1)[-1]}); data dictionary "
                             f"{scorecard_dictionary.release[0].lower() + scorecard_dictionary.release[1:]}",
        "ipeds_tables": {table: read_csv_rows(payloads[f"ipeds_{table}"]) for table in ("hd", "effy", "adm")},
        "ipeds_dictionaries": ipeds_dictionaries,
        "ipeds_labels": {table: f"IPEDS {file_name[table]}: {ipeds_dictionaries[table].title}" for table in file_name},
    }


# ---------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------

INSTITUTION_TABLE = "warehouse.us_institution"
METRIC_TABLE = "warehouse.us_institution_metric"


def ingest(conn: Any, matches: Mapping[str, Any], records: Mapping[str, Any]) -> dict[str, int]:
    """Make both tables equal to the committed files, for the universities this database holds.

    Rows are looked up by ``canonical_slug`` among active universities. A university whose
    match was withdrawn loses its rows: federal data on the wrong record is the error the
    matching rules exist to avoid.
    """
    institutions = records["institutions"]
    with conn.cursor() as cur:
        cur.execute(f"SELECT to_regclass('{INSTITUTION_TABLE}') IS NOT NULL AND to_regclass('{METRIC_TABLE}') IS NOT NULL")
        if not cur.fetchone()[0]:
            raise RuntimeError(f"{INSTITUTION_TABLE} is missing; apply crawlernest-schema/us_institution_postgresql.sql")
        cur.execute("SELECT canonical_slug, canonical_university_id FROM warehouse.canonical_university "
                    "WHERE status = 'active'")
        ids = dict(cur.fetchall())
        counts = {"loaded": 0, "metrics": 0, "no_such_university": 0, "not_in_source_files": 0, "deleted": 0}
        keep: list[int] = []
        for row in matches["matched"]:
            canonical_id = ids.get(row["canonical_slug"])
            record = institutions.get(row["unitid"])
            if canonical_id is None:
                counts["no_such_university"] += 1
                continue
            if record is None:
                counts["not_in_source_files"] += 1
                continue
            keep.append(canonical_id)
            cur.execute(
                f"""
                INSERT INTO {INSTITUTION_TABLE} (
                    canonical_university_id, unitid, opeid, institution_name, city, state_code, website,
                    wikidata_id, match_method, match_evidence, in_scorecard, in_ipeds_directory, loaded_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (canonical_university_id) DO UPDATE SET
                    unitid = EXCLUDED.unitid, opeid = EXCLUDED.opeid, institution_name = EXCLUDED.institution_name,
                    city = EXCLUDED.city, state_code = EXCLUDED.state_code, website = EXCLUDED.website,
                    wikidata_id = EXCLUDED.wikidata_id, match_method = EXCLUDED.match_method,
                    match_evidence = EXCLUDED.match_evidence, in_scorecard = EXCLUDED.in_scorecard,
                    in_ipeds_directory = EXCLUDED.in_ipeds_directory, loaded_at = CURRENT_TIMESTAMP
                """,
                (canonical_id, int(row["unitid"]), record["opeid"], record["name"], record["city"], record["state"],
                 record["website"], row.get("wikidata_id"), row["method"], json.dumps(row["evidence"]),
                 record["in_scorecard"], record["in_ipeds_directory"]),
            )
            cur.execute(f"DELETE FROM {METRIC_TABLE} WHERE canonical_university_id = %s", (canonical_id,))
            for m in expand_metrics(records, row["unitid"]):
                cur.execute(
                    f"""
                    INSERT INTO {METRIC_TABLE} (
                        canonical_university_id, source, metric_key, source_field, unit, value_number, value_text,
                        status, status_detail, reference_period, release
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (canonical_id, m["source"], m["key"], m["field"], m["unit"], m["value_number"], m["value_text"],
                     m["status"], m["status_detail"], m["period"], m["release"]),
                )
                counts["metrics"] += 1
            counts["loaded"] += 1
        # The metric rows cascade.
        cur.execute(f"DELETE FROM {INSTITUTION_TABLE} WHERE NOT (canonical_university_id = ANY(%s))", (keep,))
        counts["deleted"] = cur.rowcount
    conn.commit()
    return counts


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PgConfig:
    host: str = "localhost"
    port: int = 5432
    database: str = "clawer"
    user: str = "test"
    password: str = "test"

    def connect(self) -> Any:
        import psycopg2

        return psycopg2.connect(host=self.host, port=self.port, dbname=self.database, user=self.user,
                                password=self.password)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_json(path: Path, document: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main(argv: Optional[Sequence[str]] = None, *, log: Callable[[str], None] = print) -> int:
    parser = argparse.ArgumentParser(description="Match, fetch and load US federal institutional data.")
    parser.add_argument("command", choices=["match", "fetch", "ingest", "status"])
    parser.add_argument("--matches", type=Path, default=MATCHES_PATH)
    parser.add_argument("--overrides", type=Path, default=OVERRIDES_PATH)
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--records", type=Path, default=RECORDS_PATH)
    parser.add_argument("--wikipedia-matches", type=Path, default=WIKIPEDIA_MATCHES_PATH)
    parser.add_argument("--cache-dir", type=Path, default=CACHE_DIR)
    parser.add_argument("--refresh", action="store_true", help="ignore the download cache")
    parser.add_argument("--pg-host", default="localhost")
    parser.add_argument("--pg-port", type=int, default=5432)
    parser.add_argument("--pg-database", default="clawer")
    parser.add_argument("--pg-user", default="test")
    parser.add_argument("--pg-password", default="test")
    args = parser.parse_args(argv)
    pg = PgConfig(args.pg_host, args.pg_port, args.pg_database, args.pg_user, args.pg_password)
    http = Http(args.cache_dir, refresh=args.refresh)

    if args.command == "match":
        conn = pg.connect()
        try:
            universities = load_universities(conn)
        finally:
            conn.close()
        wikipedia = json.loads(args.wikipedia_matches.read_text(encoding="utf-8"))
        wikidata_ids = {row["canonical_slug"]: row["wikidata_id"] for row in wikipedia["matched"] if row.get("wikidata_id")}
        overrides = json.loads(args.overrides.read_text(encoding="utf-8")) if args.overrides.exists() else {}
        qids = {wikidata_ids[u.canonical_slug] for u in universities if u.canonical_slug in wikidata_ids}
        log(f"US universities: {len(universities)}; with a Wikidata item: {len(qids)}")
        report = build_matches(universities, wikidata_ids, wikidata_ipeds_ids(qids, http), overrides)
        document = matches_document(report, generated_at=_now())
        _write_json(args.matches, document)
        log(json.dumps(document["counts"], indent=1))
        log(f"-> {args.matches}")
        return 0

    matches = json.loads(args.matches.read_text(encoding="utf-8"))
    if args.command == "fetch":
        payloads, manifest = fetch_files(http, _now())
        parsed = parse_payloads(payloads)
        institutions, missing = build_records(matches, **parsed)
        _write_json(args.manifest, manifest)
        write_records(args.records, records_document(institutions, manifest))
        for unitid in missing:
            log(f"  UNITID {unitid} is in neither the Scorecard file nor the IPEDS directory")
        log(f"records: {len(institutions)}, not in the source files: {len(missing)} -> {args.records}")
        return 0

    records = json.loads(args.records.read_text(encoding="utf-8"))
    if args.command == "status":
        statuses = Counter(m["status"] for r in records["institutions"].values() for m in r["metrics"])
        log(json.dumps({**matches["counts"], "records": len(records["institutions"]), "values": dict(statuses)}, indent=1))
        return 0

    conn = pg.connect()
    try:
        counts = ingest(conn, matches, records)
    finally:
        conn.close()
    log(json.dumps(counts, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
