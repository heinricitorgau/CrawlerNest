#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Smoke test the Spring Boot /recommendations endpoint")
    parser.add_argument("--base-url", default="http://localhost:8080")
    parser.add_argument("--country", default="United Kingdom")
    parser.add_argument("--ielts", type=float, default=6.5)
    parser.add_argument("--target-rank", type=int, default=100)
    parser.add_argument("--preferred-ranking-source", default="QS")
    parser.add_argument("--limit", type=int, default=3)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    params = {
        "country": args.country,
        "ielts": args.ielts,
        "targetRank": args.target_rank,
        "preferredRankingSource": args.preferred_ranking_source,
        "limit": args.limit,
    }
    url = args.base_url.rstrip("/") + "/recommendations?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=15) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    if not isinstance(payload, list) or not payload:
        raise SystemExit("[fail] endpoint returned no recommendation rows")

    required_fields = {
        "canonicalUniversityId",
        "universityName",
        "country",
        "aggregatedRank",
        "ieltsMin",
        "matchingScore",
        "explanation",
    }
    first = payload[0]
    missing = sorted([field for field in required_fields if field not in first])
    if missing:
        raise SystemExit(f"[fail] missing fields in response: {missing}")

    print(f"[ok] recommendation rows: {len(payload)}")
    print(f"[ok] first result: {first['universityName']} (score={first['matchingScore']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
