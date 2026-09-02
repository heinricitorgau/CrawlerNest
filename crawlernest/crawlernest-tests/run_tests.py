#!/usr/bin/env python3
import unittest
import sys
import os
import importlib.util
from pathlib import Path

def run_all_tests():
    # Identify project root
    ROOT = Path(__file__).resolve().parent.parent
    
    # List of modules to add to sys.path
    MODULES = [
        "crawlernest-core",
        "crawlernest-extractors",
        "crawlernest-jobs",
        "crawlernest-db-writer",
        "crawlernest-cli",
        "crawlernest-analytics",
    ]

    # Add all modules to sys.path
    for mod in MODULES:
        mod_path = ROOT / mod
        if mod_path.is_dir() and str(mod_path) not in sys.path:
            sys.path.insert(0, str(mod_path))
            
    # Add the current directory (tests) to path too
    sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
    
    loader = unittest.TestLoader()

    test_modules = [
        "test_fetcher",
        # Backend selection and the header policy that goes with it. Sending the
        # hand-built browser header set through an impersonated stack re-triggers
        # the Cloudflare challenge the stack exists to avoid.
        "test_transport",
        # The QS block probe's verdict. Its first version judged each variant by
        # its final step alone, which turned "cleared Cloudflare then hit a dead
        # ranking id" into "blocked by Cloudflare" -- and recommended the wrong
        # remedy off the live evidence.
        "test_probe_qs_block",
        "test_extractor",
        "test_db_writer",
        # Aggregation: these existed but no runner loaded them, so a change to
        # the source weights or the composite maths went unchecked here.
        "test_ranking_aggregation",
        "test_multi_source_pipeline",
        # Entity resolution: also unregistered until now, so the normalizer and
        # the resolver's blocking/threshold logic were unguarded in CI.
        "test_entity_resolution",
        "test_mapping_reviews",
        # Mirrors a backfill in crawlernest-schema/admission_postgresql.sql;
        # unregistered, a drift between the two would go unnoticed.
        "test_admission_source_identity",
        # Admission rows resolving through the shared EntityResolver, and the
        # review rule still overriding it across the two row types.
        "test_admission_entity_resolution",
        # The crawler-to-staging bridge, including that a snapshot run stays
        # offline rather than falling back to live university sites.
        "test_admission_crawl_bridge",
        # The shared crawler-core primitives: per-host rate limiting, the
        # non-retriable-exception rule that stops a 403 being re-sent, and the
        # host scheduler the admissions crawl now runs on.
        "test_crawler_core",
        # Both sat unregistered for months. test_qs_universe_invariants was
        # failing that whole time -- region/europe/standardized_rows.json is an
        # empty artifact from a Cloudflare-blocked run -- and nobody saw it.
        "test_qs_universe_invariants",
        "test_qs_resolution_strategy",
        # Needs PostgreSQL; skips itself unless CRAWLERNEST_RUN_PG_TESTS=1.
        "test_legacy_source",
        "test_arwu_crawler",
        "test_analytics_bridge_weights",
        # Structural half runs anywhere; warehouse half is PostgreSQL-gated.
        "test_alias_files",
        # Need PostgreSQL; skip themselves unless CRAWLERNEST_RUN_PG_TESTS=1.
        "test_analytics_bridge_prune",
        "test_ingest_idempotency",
        "test_pairing_matches_warehouse",
    ]

    # pytest-based modules are optional for the unified unittest runner.
    if importlib.util.find_spec("pytest") is not None:
        test_modules.extend(["test_ranking_api", "test_regions"])
    else:
        print("[WARN] pytest not installed: skipping test_ranking_api and test_regions")

    suite = unittest.TestSuite()
    for mod in test_modules:
        suite.addTests(loader.loadTestsFromName(mod))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
