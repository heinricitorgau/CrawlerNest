"""CrawlerNest modelling layer.

Sits beside the deterministic pipeline, never inside it: nothing here writes to
``analytics.aggregated_rankings`` or changes a published rank. Model output is
an estimate and is stored and labelled as one.
"""
