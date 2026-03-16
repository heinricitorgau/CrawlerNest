#!/usr/bin/env python3
import unittest
import sys
import os
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
    # Discover tests in the current directory (which is crawlernest-tests/)
    suite = loader.discover(start_dir=os.path.dirname(__file__), pattern='test_*.py')
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
