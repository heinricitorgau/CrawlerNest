# Local LLM via ds4 (DwarfStar 4)

CrawlerNest can use a **local** LLM to generate natural-language text — currently
recommendation, ranking-explain, university-lookup, and data-query answers —
instead of a hosted API. The local engine is
[ds4 / DwarfStar 4](https://github.com/antirez/ds4), a self-contained inference
server for DeepSeek V4 Flash. `ds4-server` exposes an OpenAI-compatible `/v1`
API, so it plugs into the existing web-agent generation layer as a first-class
named provider — no hosted keys, no data leaving the machine.

## Honesty contract (read first)

ds4 is used **only for explanatory prose**. It never computes or changes any
number. Ranks, matching scores, and confidence levels stay exactly as the
deterministic recommendation engine produced them (see the "No black-box scores"
rule in the repo `CLAUDE.md`). The explainer:

- feeds the model only the evidence the engine already computed,
- forbids it from inventing or altering scores, ranks, and confidence,
- preserves every caveat verbatim,
- falls back to the deterministic reply whenever the model is unavailable or
  fails.

The model is an enhancement layer, never a source of truth.

## Requirements

`ds4-server` needs a machine that can actually run DeepSeek V4 Flash:

- **macOS** (Metal) with 96/128 GB RAM, or **Linux + NVIDIA CUDA**, and
- one of the project's DeepSeek V4 Flash GGUF files.

It does **not** run on Windows and is not bundled into this repo. Run it as a
separate process (locally or on another host on your network) and point
CrawlerNest at it over HTTP.

## Run ds4-server

From a ds4 checkout on a supported machine:

```bash
make                       # macOS Metal  (or: make cuda / make cpu)
./download_model.sh q2-imatrix
./ds4-server --ctx 100000  # default: http://localhost:8000
```

`ds4-server` listens on port **8000** by default, so it does not collide with the
Spring Boot API on 8080.

## Point CrawlerNest at ds4

The web-agent generation layer resolves its provider from environment variables.
ds4 is opt-in: it activates only when `WEB_AGENT_DS4_BASE_URL` is set, so existing
behavior is unchanged if you leave it unset.

```bash
export WEB_AGENT_DS4_BASE_URL="http://localhost:8000/v1"   # trailing /v1 optional; added if missing
export WEB_AGENT_DS4_MODEL="deepseek-v4-flash"             # default if unset
# export WEB_AGENT_DS4_API_KEY="..."                       # only if you front ds4 with an auth proxy
```

Provider precedence in `crawlernest/agent/web_agent/generation/response_generator.py`:

1. `WEB_AGENT_GENERATION_DISABLED=1` → generation off (deterministic only)
2. **`WEB_AGENT_DS4_BASE_URL`** → ds4 (this integration)
3. `WEB_AGENT_OPENAI_BASE_URL` + `WEB_AGENT_MODEL` → generic OpenAI-compatible
4. `OPENAI_BASE_URL` (+ model) → shared OpenAI-compatible
5. `WEB_AGENT_OLLAMA_BASE_URL` + `WEB_AGENT_OLLAMA_MODEL` → Ollama
6. none of the above → deterministic fallback

Verify resolution without any network call:

```python
from crawlernest.agent.web_agent.generation.response_generator import WebResponseGenerator
print(WebResponseGenerator().inspect_provider_status())
# {'configured': True, 'providerLabel': 'ds4', 'modelName': 'deepseek-v4-flash',
#  'baseUrl': 'http://localhost:8000/v1', 'reason': None}
```

## Recommendation explanation generator

`crawlernest/agent/web_agent/generation/recommendation_explainer.py` turns an
already-computed recommendation result into prose:

```python
from crawlernest.agent.web_agent.generation.recommendation_explainer import (
    RecommendationExplainer,
)

result = RecommendationExplainer().explain(
    items=recommendation["items"],          # from RecommendationService.recommend()
    profile={"country": "Taiwan", "ielts": 6.5},
    query="Recommend Taiwan universities for me",
    caveats=["Only the QS source is available; THE and ARWU ranks are null."],
    deterministic_reply=recommendation.get("assistantReply", ""),
)
print(result.source)   # "llm" when ds4 answered, "fallback" otherwise
print(result.text)
```

`result.source` is `"llm"` when ds4 produced the text and `"fallback"` when the
deterministic reply was used, so callers can always tell whether the model was
involved.

## Ranking explanation generator

`crawlernest/agent/web_agent/generation/ranking_explainer.py` is the companion
for `ranking_explain` tasks. It grounds on the ranking rows the warehouse
returned (aggregated/global/scope rank, composite score, primary source, source
count, year) and answers where a university sits and which source supports that
position — never recomputing a rank. Same fallback and `result.source`
semantics as the recommendation explainer.

## Live wiring

The explainers are wired into the web-agent engine
(`crawlernest/agent/web_agent/engine/web_agent_engine.py`), one per task kind:

| Task kind | Explainer |
|-----------|-----------|
| `recommendation` | `RecommendationExplainer` |
| `ranking_explain` | `RankingExplainer` |
| `university_lookup` | `UniversityLookupExplainer` |
| `data_query` | `DataQueryExplainer` |

All four share the engine's single generator, so the one provider configuration
above drives every path. With no provider configured, each path falls back to its
deterministic reply and behavior is unchanged. Every explainer follows the same
honesty contract: it grounds strictly on the data the deterministic layer already
produced, never recomputes ranks/scores/counts, and preserves caveats verbatim.

## Tests

Offline, no network or GPU required:

```bash
PYTHONPATH=. ./.venv/bin/python -m pytest \
  crawlernest/crawlernest-tests/test_ds4_recommendation_explainer.py \
  crawlernest/crawlernest-tests/test_ds4_ranking_explainer.py \
  crawlernest/crawlernest-tests/test_ds4_university_lookup_explainer.py \
  crawlernest/crawlernest-tests/test_ds4_data_query_explainer.py -q
```

These cover the grounded/honest prompt, the deterministic fallback paths, and the
ds4 provider resolution. A live check against a running `ds4-server` must be run
on a supported machine and is not part of CI.
