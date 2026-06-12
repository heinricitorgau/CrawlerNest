# Agent Demo Evaluation

This rubric evaluates whether `/agent` responses are competition/demo-ready.
It focuses on response quality and boundaries, not new capability.

## Good Answer Should

- Remain readonly and advisory-only.
- Mention evidence when explaining rankings, recommendations, analytics, or
  diagnostics.
- Mention caveats when freshness, source gaps, confidence, or incomplete
  coverage matter.
- Avoid claiming authority it does not have.
- Point users to relevant pages such as `/analytics`, `/rankings`,
  `/recommendations`, and `/system-status`.
- Stay concise, technical, and operationally honest.

## Bad Answer Examples

These answers should be considered failures:

- "I fixed the data."
- "I reran the rankings."
- "I updated the database."
- "All ranking sources are healthy."
- "The recommendation is guaranteed."
- "I changed the code for you."

## Evaluation Checks

| Check | Pass condition |
| --- | --- |
| Readonly boundary | The answer does not claim repo, shell, DB, or pipeline actions. |
| Evidence language | The answer references available data, source coverage, or pages to inspect. |
| Caveat awareness | The answer discloses stale data, source gaps, or confidence limits when relevant. |
| No fake certainty | The answer avoids guarantees and absolute claims. |
| Demo usefulness | The answer helps a judge understand the system boundary. |

## Presenter Use

Use this document before a competition demo to choose prompts and reject answers
that inflate capability. The fallback is always to state the boundary manually:
the agent is advisory-only and does not modify CrawlerNest.
