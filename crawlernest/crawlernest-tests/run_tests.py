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
        "test_extractor",
        "test_db_writer",
        # Aggregation: these existed but no runner loaded them, so a change to
        # the source weights or the composite maths went unchecked here.
        "test_ranking_aggregation",
        "test_multi_source_pipeline",
        "test_analytics_bridge_weights",
        # Needs PostgreSQL; skips itself unless CRAWLERNEST_RUN_PG_TESTS=1.
        "test_analytics_bridge_prune",
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
