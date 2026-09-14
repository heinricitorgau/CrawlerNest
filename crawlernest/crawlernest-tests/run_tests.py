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

    # The repo root, so `crawlernest.agent.*` / `crawlernest.core.*` import.
    # Running this file as a script puts crawlernest-tests on sys.path, not the
    # root, so without this any test touching the agent layer fails to load --
    # which is why none of them could be registered below until now.
    REPO_ROOT = ROOT.parent
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
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
        # Plans the rewrite of human decisions onto ARWU's year-free ids. A bad
        # plan orphans decisions nobody can regenerate, so it runs in CI.
        "test_rekey_arwu_source_ids",
        # No web prompt carries an instruction the agent wrote for itself, and
        # answering a request writes no strategy or experience store.
        "test_web_prompt_is_static",
        # Every serving read of a multi-edition relation names one explicit
        # edition, so a shadow ingest cannot leak or duplicate rows.
        "test_year_isolation_audit",
        # Needs PostgreSQL; skips itself unless CRAWLERNEST_RUN_PG_TESTS=1.
        "test_institution_lineage_pg",
        # Golden constraints for WebPromptBuilder; sat unregistered.
        "test_prompt_builder_instruction",
        # Needs PostgreSQL; skips itself unless CRAWLERNEST_RUN_PG_TESTS=1. The
        # rule that links ranking_record rows to the mapping that produced them.
        "test_mapping_provenance",
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
        # The ranking_type/universe_type/universe_key scope that keeps a
        # university's ranking summary from mixing in the region/regional/
        # subject/special universes the QS crawler now also writes.
        "test_ranking_scope",
        # Both sat unregistered for months. test_qs_universe_invariants was
        # failing that whole time -- region/europe/standardized_rows.json is an
        # empty artifact from a Cloudflare-blocked run -- and nobody saw it.
        "test_qs_universe_invariants",
        "test_qs_resolution_strategy",
        # A crawl labels rows with a ranking_year only after proving it read that
        # edition. Without it the 2027 QS table was ingested as 2026.
        "test_ranking_edition",
        # The external scheduler's one-shot command, and the guardrail that the
        # API and web app cannot start the pipeline.
        "test_scheduled_refresh",
        "test_no_pipeline_triggers_from_api",
        # Needs PostgreSQL; skips itself unless CRAWLERNEST_RUN_PG_TESTS=1.
        "test_legacy_source",
        "test_arwu_crawler",
        "test_analytics_bridge_weights",
        # Structural half runs anywhere; warehouse half is PostgreSQL-gated.
        "test_alias_files",
        # Need PostgreSQL; skip themselves unless CRAWLERNEST_RUN_PG_TESTS=1.
        "test_analytics_bridge_prune",
        "test_ingest_idempotency",
        "test_merged_canonical_pg",
        "test_pairing_matches_warehouse",
        # The 2026 single-year dataset declaration: that the explainers put it
        # in front of the model, and that the query defaults still agree with
        # the year the warehouse holds. Registered here as well as in
        # agent-tests.yml (which covers the rest of the generation layer under
        # pytest) because a wrong default year is a warehouse-shaped bug, and
        # this is the runner the warehouse tests live in.
        "test_dataset_context",
        # The ML read path's disclosure guard: estimates cannot leave
        # ml_tools without isEstimated and the caveat, which is what keeps
        # faith-105 catchable. Offline -- MlService is stubbed.
        "test_ml_tools",
        # The caveat strings agree across Python, Java, TypeScript and the
        # explainability doc. Two of them had already drifted.
        "test_caveat_contract",
        # A request naming a year the warehouse does not hold gets told so.
        # Registered here as well as in agent-tests.yml because "which years
        # exist" is a warehouse fact, and this is the runner those live in.
        "test_unsupported_year_warning",
        # The two opt-in constraints the chat route's data pass runs on: no
        # engine-side prose, and no silent handoff to the dev agent.
        "test_two_pass_constraints",
        # Cross-year rank movement, settled before a second year is ingested:
        # withheld for today's single-year dataset, intervals for banded ranks,
        # and no delta across a change of source identity.
        "test_rank_delta",
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
