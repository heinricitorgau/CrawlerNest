"""What the warehouse actually contains, stated once so nothing has to guess.

Two facts about this release are load-bearing and were, until now, re-asserted
independently by every caller that needed them: the warehouse holds ranking data
for exactly one year, and QS is the only source ingested (see the repo
``CLAUDE.md`` -- THE and ARWU exist in the schemas as null-valued keys).

Stating them here rather than in each service fixes the default-year drift. Each
caller that needed a year picked its own: a literal ``2026`` in ``RankingQuery``,
another in ``ranking_tools``, and ``datetime.now().year`` in
``recommendation_service`` -- which silently starts querying a year the warehouse
has no rows for the moment the wall clock rolls over, returning an empty result
that looks like a data problem rather than a code one. A constant cannot do that.

These are warehouse facts, so they live in ``core`` and the agent layer reads
them from here -- ``agent`` imports ``core`` and never the reverse. How the facts
are described *to a model* is a generation concern and lives in
``agent/web_agent/generation/dataset_context.py``, which re-exports both names
alongside the prose it builds from them.

Changing :data:`DATASET_YEAR` is therefore a data-migration step, not an edit: it
re-points every query default and rewrites what the model is told the corpus
contains.
"""

from __future__ import annotations

#: The single ranking year present in the warehouse. Every query default and
#: every generated explanation is pinned to it.
DATASET_YEAR = 2026

#: Ranking sources actually ingested. THE and ARWU appear throughout the
#: schemas as planned sources carrying null data and are deliberately absent
#: here -- this tuple is what is loaded, not what is anticipated.
DATASET_SOURCES = ("QS",)
