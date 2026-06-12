# Agent Demo Prompts

This prompt library keeps `/agent` demos consistent. The expected answers should
remain readonly, advisory-only, caveat-aware, and honest about source limits.

## Core Demo Prompts

| Prompt | Expected answer themes | Key caveats | What judges should learn |
| --- | --- | --- | --- |
| Why does source disagreement matter? | Explain that QS, THE, and ARWU use different methodologies, so disagreement shows where a ranking is less stable or needs more context. Point to `/analytics` and source disagreement views. | Current source coverage may be incomplete; disagreement is evidence, not a final truth label. | CrawlerNest treats rankings as explainable evidence rather than a single opaque score. |
| What does stale data mean? | Define stale as data older than expected freshness thresholds. Explain that stale data can still be inspectable but should not be presented as current. | Current snapshots may show stale aggregation and missing THE/ARWU. | The system separates operational freshness from product presentation. |
| How should I interpret recommendation confidence? | Explain that confidence reflects available evidence, ranking signals, and fit constraints. It should guide review, not make an admission decision. | Recommendation confidence does not replace official admissions criteria or fresh source validation. | Recommendations are explainable and bounded, not magical decisions. |
| Why is explainability important? | Explain that users and judges can inspect why a result appears, what sources contributed, and where caveats exist. | Explainability depends on the available evidence and current source coverage. | CrawlerNest prioritizes transparent university intelligence over hidden ranking output. |
| What are the limitations of CrawlerNest? | Mention localhost/demo assumptions, stale data risk, source gaps, subject ranking incompleteness, and advisory agent responses. | Do not imply production-grade global freshness or complete source coverage. | The demo is operationally honest and release-aware. |
| Why is THE unavailable? | Explain that THE is currently unavailable in the operational state and should be treated as a source gap, not silently substituted. Suggest checking freshness and source health reports. | The agent cannot fetch THE, repair selectors, or rerun ingestion. | CrawlerNest exposes source availability honestly instead of hiding missing inputs. |
| How should I use analytics caveats? | Explain that caveats identify stale data, missing sources, disagreement, and confidence limits before interpreting charts or recommendations. | Caveats are context, not automatic blockers or automatic fixes. | Analytics are demo-ready when paired with visible operational caveats. |

## Presenter Notes

- Prefer mock or Ollama for competition demos unless OpenAI is already verified.
- If a provider fails, show the safe fallback wording and continue with mock.
- Do not ask the agent to modify code, rerun pipelines, or repair data during a
  demo; use it to explain what a maintainer should inspect.
