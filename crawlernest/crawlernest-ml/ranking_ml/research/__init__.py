"""Research loop for the overall-score model, after Microsoft RD-Agent's R&D loop.

RD-Agent splits research into a fixed cycle -- propose a hypothesis, turn it into
an experiment, run it, judge the result against the best one so far, record both
in a trace -- and grows each new hypothesis from the current best node. This
package is that cycle over the QS overall-score model, with two deliberate
departures:

* **No generated code.** RD-Agent's coder writes the experiment. Here a
  hypothesis can only name components from :mod:`ranking_ml.research.space`, and
  anything outside it is rejected before it runs. A proposer -- the built-in
  one-change-at-a-time search, or an LLM behind :class:`CallableProposer` -- picks
  among known estimators; it never writes one.
* **A holdout the loop never sees.** The withheld rows are split by rank into a
  *search* half, which every decision is made on, and a *holdout* half, scored
  once for the final best experiment. Choosing the best of N trials on the same
  rows makes the winning margin optimistic, and the report says how many trials
  that was.

Nothing here writes to the warehouse or to ``artifacts/metrics/``; the trace goes
to ``.local/reports/research/``.
"""
