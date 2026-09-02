#!/usr/bin/env python3
"""Resolve every QS universe's ranking id from its own ranking page, and check it.

Why this is a tool and not a one-off
------------------------------------
QS node ids change every edition. They were previously pinned in
qs_universe_registry.py and defaulted to a hardcoded "3990755" when a spec left
them unset, which gave eleven of thirteen universes the same id -- the World 2025
ranking. That id still answers 200, so asia, europe, africa and the rest would
have ingested world rows under their own labels with no error anywhere. Resolving
ids from each universe's own page is what makes that self-correcting, and this
script is how you check the result without running the whole pipeline.

What it does per universe
-------------------------
1. Builds the config through the real crawler classes (not a hand-rolled request).
2. Runs the fetcher's own ``_ensure_ranking_id()`` -- the live page-resolution path.
3. Fetches page 0 of the ranking endpoint and shows the top rows, so the data can
   be eyeballed against the universe it claims to be. A resolved id that returns
   MIT/Imperial/Oxford for "QS Asia" is the exact failure this exists to catch.
4. Flags any id claimed by more than one universe.

Subject universes pin their ids and have no ranking page, so step 2 is skipped for
them and only the verification runs.

Politeness
----------
QS publishes ``crawl-delay: 10``, honoured globally across universes. A full run
is roughly 25 requests and takes about four minutes.

Usage
-----
    python3 scripts/resolve_qs_ranking_ids.py --dry-run
    python3 scripts/resolve_qs_ranking_ids.py
    python3 scripts/resolve_qs_ranking_ids.py --only region:africa,special:mba
    python3 scripts/resolve_qs_ranking_ids.py --write     # persist to the cache
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from crawlernest.pipeline.bootstrap import bootstrap_module_paths  # noqa: E402

bootstrap_module_paths(REPO_ROOT / "crawlernest")

from fetcher import UniversityFetcher, _qs_ranking_fetch_urls  # noqa: E402
from qs_universe_crawlers import (  # noqa: E402
    QSGlobalCrawler,
    QSRegionCrawler,
    QSSpecialCrawler,
    QSSubjectCrawler,
)
from qs_universe_registry import iter_all_qs_universes  # noqa: E402

DEFAULT_CACHE = REPO_ROOT / "crawlernest" / "crawlernest-kb" / "qs_universe_resolution_cache.json"

_CRAWLERS = {
    "global": QSGlobalCrawler,
    "region": QSRegionCrawler,
    "regional": QSRegionCrawler,
    "subject": QSSubjectCrawler,
    "special": QSSpecialCrawler,
}


@dataclass
class Outcome:
    universe: str
    label: str
    pinned: Optional[str]
    resolved: str = ""
    source: str = ""
    failure: str = ""
    block_reason: str = ""
    total_record: Optional[int] = None
    sample: List[str] = field(default_factory=list)
    page_url: str = ""
    resolved_page_url: str = ""
    scope: str = ""

    @property
    def is_world_slice(self) -> bool:
        return self.scope == "world_slice"

    @property
    def via_fallback(self) -> bool:
        """Was the id read off a *different* page than the one configured?

        _ranking_page_fallbacks walks to sibling and parent slugs when the
        configured page yields nothing, which keeps the crawler alive across site
        restructures -- but it also means a 404 page can end in a confident id
        belonging to a neighbouring ranking. That is how region:latin-america
        reported success while its own page was gone: the fallback landed on the
        Caribbean ranking and returned 28 Caribbean rows as "Latin America".
        """
        return bool(
            self.page_url
            and self.resolved_page_url
            and self.resolved_page_url.rstrip("/") != self.page_url.rstrip("/")
        )

    @property
    def ok(self) -> bool:
        return bool(self.resolved) and self.total_record is not None and not self.via_fallback


class Pacer:
    def __init__(self, delay: float) -> None:
        self.delay = max(0.0, delay)
        self._last = 0.0
        self.count = 0

    def wait(self) -> None:
        if self.delay <= 0:
            return
        remaining = self.delay - (time.monotonic() - self._last)
        if remaining > 0 and self._last > 0.0:
            time.sleep(remaining)
        self._last = time.monotonic()


def resolve_one(spec: Any, *, year: int, pacer: Pacer, cache_path: Path) -> Outcome:
    key = f"{spec.universe_type}:{spec.universe_key}"
    out = Outcome(universe=key, label=spec.label, pinned=spec.ranking_id,
                  page_url=spec.ranking_page_url or "",
                  scope=getattr(spec, "ranking_scope", ""))

    crawler = _CRAWLERS[spec.universe_type](
        spec=spec, limit=10, ranking_year=year, use_async=False,
        workers=1, request_delay=0.0, local_parse_workers=1,
    )
    config = crawler.build_config()
    config.items_per_page = 5
    # Resolution writes a cache entry on success; point it somewhere disposable
    # unless the caller explicitly asked to persist.
    config.resolution_cache_path = str(cache_path)
    # Force page resolution rather than trusting whatever is already cached --
    # verifying a cached id against itself proves nothing.
    fetcher = UniversityFetcher(config)

    if spec.ranking_page_url:
        pacer.wait()
        pacer.count += 1
        try:
            out.resolved = fetcher._ensure_ranking_id(force_refresh=True)
            out.source = str(getattr(config, "_ranking_id_source", "") or "")
            out.resolved_page_url = str(getattr(config, "_resolved_ranking_page_url", "") or "")
        except Exception as exc:
            out.failure = f"{type(exc).__name__}: {exc}"
            out.block_reason = str(getattr(config, "_last_block_reason", "") or "")
            fetcher.close()
            return out
    else:
        out.resolved = str(spec.ranking_id or "")
        out.source = "pinned (no ranking page)"
        config.ranking_id = out.resolved

    if not out.resolved or out.resolved == "0":
        out.failure = "no usable ranking id"
        fetcher.close()
        return out

    url = _qs_ranking_fetch_urls(config, out.resolved)[0]
    pacer.wait()
    pacer.count += 1
    try:
        resp = fetcher._session_get_transient_retry(
            url, params=config.get_api_params(),
            headers=config.get_headers("api"), purpose="verify",
        )
        ct = str(resp.headers.get("content-type", ""))
        if "json" not in ct.lower():
            out.failure = f"HTTP {resp.status_code}, content-type={ct!r} (not JSON)"
        else:
            data = resp.json()
            out.total_record = data.get("total_record")
            for node in (data.get("score_nodes") or [])[:4]:
                out.sample.append(
                    f"#{node.get('rank')} {str(node.get('title'))[:38]} ({node.get('country')})"
                )
    except Exception as exc:
        out.failure = f"{type(exc).__name__}: {exc}"
    finally:
        fetcher.close()
    return out


def find_collisions(outcomes: List[Outcome]) -> Dict[str, List[str]]:
    """Ranking ids claimed by more than one universe that should not share one.

    World slices are excluded: every region cut out of the world ranking uses the
    world ranking's id by design, so listing them here would report the intended
    arrangement as a fault and bury any real collision among them.
    """
    by_id: Dict[str, List[str]] = {}
    for o in outcomes:
        if o.resolved and not o.is_world_slice:
            by_id.setdefault(o.resolved, []).append(o.universe)
    return {rid: names for rid, names in by_id.items() if len(names) > 1}


def report(outcomes: List[Outcome], pacer: Pacer) -> int:
    print()
    print("=" * 96)
    print(f"{'universe':<28} {'pinned':>9} {'resolved':>10} {'records':>8}  source / failure")
    print("-" * 96)
    for o in outcomes:
        detail = o.failure or o.source
        if o.block_reason:
            detail = f"{detail} [{o.block_reason}]"
        if o.via_fallback:
            detail = f"WRONG PAGE -- id came from {o.resolved_page_url}"
        print(
            f"{o.universe:<28} {str(o.pinned or '-'):>9} {str(o.resolved or '-'):>10} "
            f"{str(o.total_record if o.total_record is not None else '-'):>8}  {detail}"
        )
    print()
    print("Top rows, to check each id returns its own universe")
    print("-" * 96)
    for o in outcomes:
        if not o.sample:
            continue
        note = ""
        if o.is_world_slice:
            # The crawl narrows these with a region parameter; this verification
            # deliberately does not, so what follows is the head of the *world*
            # ranking. For a world slice the thing worth checking here is that
            # the id is the current world edition, not that the rows are regional.
            note = "  [world ranking head -- region filter is applied during the crawl, not here]"
        print(f"  {o.universe} ({o.label}):{note}")
        for row in o.sample:
            print(f"      {row}")

    collisions = find_collisions(outcomes)
    print()
    if collisions:
        print("COLLISIONS -- one ranking id cannot belong to two universes:")
        for rid, names in collisions.items():
            print(f"  {rid}: {', '.join(names)}")
    else:
        print("No ranking id is claimed by more than one universe.")

    fell_back = [o for o in outcomes if o.via_fallback]
    if fell_back:
        print()
        print("RESOLVED FROM A DIFFERENT PAGE -- the configured URL did not yield an id,")
        print("so these ids belong to whatever ranking the fallback landed on:")
        for o in fell_back:
            print(f"  {o.universe}: configured {o.page_url}")
            print(f"      resolved from {o.resolved_page_url} -> id {o.resolved} "
                  f"({o.total_record} records)")

    failed = [o for o in outcomes if not o.ok]
    if failed:
        print()
        print(f"{len(failed)} universe(s) did not resolve and verify:")
        for o in failed:
            reason = o.failure or ("resolved from the wrong page" if o.via_fallback else "unknown")
            print(f"  {o.universe}: {reason}")

    print()
    print(f"({pacer.count} requests at {pacer.delay:.1f}s crawl-delay)")
    return 0 if (not collisions and not failed) else 1


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--delay", type=float, default=10.0, help="QS robots.txt says 10")
    parser.add_argument("--only", default="", help="comma list of type:key, e.g. region:africa,special:mba")
    parser.add_argument("--write", action="store_true", help="persist resolved ids to the resolution cache")
    parser.add_argument("--cache-path", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None, help="write the full result as JSON")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    specs = list(iter_all_qs_universes())
    if args.only:
        wanted = {s.strip() for s in args.only.split(",") if s.strip()}
        specs = [s for s in specs if f"{s.universe_type}:{s.universe_key}" in wanted]
        if not specs:
            parser.error(f"no universe matched {args.only!r}")

    if args.write:
        cache_path = args.cache_path or DEFAULT_CACHE
    else:
        # Resolution writes a cache entry as a side effect; keep it out of the
        # repo unless persisting was asked for.
        cache_path = args.cache_path or Path("/tmp/qs_resolve_scratch_cache.json")

    if args.dry_run:
        print(f"\nDRY RUN -- would resolve {len(specs)} universe(s) at {args.delay}s delay")
        print(f"  cache target: {cache_path} ({'PERSISTED' if args.write else 'scratch'})")
        for s in specs:
            page = s.ranking_page_url or "(pinned id, no page)"
            print(f"    {s.universe_type}:{s.universe_key:<20} {page}")
        return 0

    pacer = Pacer(args.delay)
    outcomes: List[Outcome] = []
    for spec in specs:
        key = f"{spec.universe_type}:{spec.universe_key}"
        print(f"[resolve] {key}", flush=True)
        outcomes.append(resolve_one(spec, year=args.year, pacer=pacer, cache_path=cache_path))

    code = report(outcomes, pacer)

    if args.out:
        payload = {
            "resolved_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "ranking_year": args.year,
            "universes": [vars(o) for o in outcomes],
            "collisions": find_collisions(outcomes),
        }
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[resolve] JSON written to {args.out}")

    if args.write:
        print(f"[resolve] resolution cache updated at {cache_path}")
    return code


if __name__ == "__main__":
    sys.exit(main())
