"""What the warehouse actually contains, stated once so nothing has to guess.

Two facts about this release are load-bearing and were, until now, re-asserted
independently by every caller that needed them: the warehouse holds ranking data
for exactly one year, and which sources are actually in it.

The second fact changed and nothing noticed. QS was the only ingested source for
most of this project's life, and a good deal of prose still says so -- the repo
``CLAUDE.md`` among it. As of the 2026-09-04 ingest the warehouse also carries
1,637 THE and 838 ARWU ranks for 2026. Coverage is partial and QS remains far the
largest, but "QS only" is no longer a true thing to tell a user or a model, which
is why :data:`DATASET_SOURCES` is read from here rather than written out wherever
it is needed.

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

#: Ranking sources actually ingested, largest coverage first. This tuple is what
#: is loaded, not what is anticipated: a source belongs here once the warehouse
#: holds ranks from it, and coverage being partial is not a reason to omit it --
#: claiming a source is absent while the API serves its figures is the worse
#: error of the two.
DATASET_SOURCES = ("QS", "THE", "ARWU")
