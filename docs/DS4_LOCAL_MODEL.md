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
export WEB_AGENT_DS4_TIMEOUT="60"                          # seconds per request; default 60 for ds4
export WEB_AGENT_DS4_STREAM="1"                            # opt in to SSE streaming (see below)
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

## Pointing at a remote ds4-server

Most machines cannot run DeepSeek V4 Flash (it needs ~96–128 GB for the 2-bit
quant, more for q4). CrawlerNest itself is light, so the normal setup is to run
`ds4-server` on **one** capable host (a Mac Studio, a DGX box, a cloud GPU
instance) and point every CrawlerNest process at it over the network. Nothing in
the integration is tied to `localhost` — only the URL changes.

**On the ds4 host** — `ds4-server` binds `127.0.0.1` (localhost only) by default,
so it is not reachable from other machines until you bind a routable interface:

```bash
./ds4-server --ctx 100000 --host 0.0.0.0   # listen on all interfaces, port 8000
```

**On each CrawlerNest host** — point at the ds4 host's address:

```bash
export WEB_AGENT_DS4_BASE_URL="http://10.0.0.42:8000/v1"   # ds4 host IP or DNS name
export WEB_AGENT_DS4_MODEL="deepseek-v4-flash"
```

Confirm reachability before relying on it:

```bash
curl -s http://10.0.0.42:8000/v1/models        # should return the model list JSON
```

### Security

`ds4-server` has **no built-in authentication**. Binding `0.0.0.0` exposes the
model to everything that can route to the host, so only do it on a trusted,
firewalled network. Two safer options:

- **SSH tunnel** (recommended): leave the server on `127.0.0.1` on the ds4 host
  and forward a local port from the CrawlerNest host —
  `ssh -N -L 8000:localhost:8000 user@ds4-host` — then keep
  `WEB_AGENT_DS4_BASE_URL="http://localhost:8000/v1"`. Traffic is encrypted and
  the model is never exposed to the LAN.
- **Auth-terminating reverse proxy** (nginx/Caddy) in front of `ds4-server`;
  put its URL in `WEB_AGENT_DS4_BASE_URL` and the bearer token in
  `WEB_AGENT_DS4_API_KEY` (sent as `Authorization: Bearer …`).

Never send warehouse data to a ds4 host you do not control.

### Latency and timeouts

The client waits `WEB_AGENT_DS4_TIMEOUT` seconds per request (**default 60** for
ds4; other providers keep 20). Over a network, a cold prefill or a long
generation on a busy remote server can still exceed that; when it does, the
request **falls back to the deterministic reply** (`result.source == "fallback"`
with a timeout warning) rather than erroring — the same graceful degradation as
an unreachable server. Raise `WEB_AGENT_DS4_TIMEOUT` for slow hosts, keep `--ctx`
sane on the ds4 host, and prefer a low-latency link if you want the `llm` path to
win consistently.

### Streaming (SSE)

Set `WEB_AGENT_DS4_STREAM=1` to request `stream: true` and consume ds4's
`text/event-stream` response instead of waiting for one JSON body.

The practical win is timeout behaviour, not just responsiveness: the socket
timeout applies **per read**, so a slow model that keeps emitting chunks no
longer trips `WEB_AGENT_DS4_TIMEOUT` the way a single long request does. This is
the real fix for "the remote host is fast enough, but a long generation still
fell back".

Two deliberate behaviours:

- **A truncated stream falls back.** If the stream ends without `[DONE]` or a
  `finish_reason`, the partial text is discarded and the deterministic reply is
  used. Returning half an explanation could silently drop the caveats the
  honesty contract requires, so incomplete output is treated as failure.
- **A server that ignores `stream: true` still works.** If the response comes
  back as plain JSON, it is parsed normally.

`WebResponseGenerator.generate_response()` accepts an optional
`on_delta(text_chunk)` callback, invoked as each chunk arrives while streaming.
It is the attachment point for a future token-level UI; the return value is
always the complete text, so existing callers are unaffected.

### Observability

Every generation records its outcome in a process-wide counter, so you can watch
how often the model actually answered versus fell back:

```python
from crawlernest.agent.web_agent.generation.response_generator import generation_stats
print(generation_stats())
# {'llm': 42, 'fallback': 3, 'disabled': 0}
#   llm      = the model produced the reply
#   fallback = a provider was configured but the call failed (timeout / HTTP /
#              parse), deterministic reply used
#   disabled = no provider configured, deterministic reply used
```

Each outcome is also logged on the `crawlernest.agent.web_agent.generation.response_generator`
logger (`INFO` for `llm`, `WARNING` with the reason for `fallback`), so a spike in
fallbacks is visible in normal application logs.

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

| Task kind | Explainer | Reached via |
|-----------|-----------|-------------|
| `recommendation` | `RecommendationExplainer` | web-agent engine, `/explain` |
| `ranking_explain` | `RankingExplainer` | web-agent engine, `/explain` |
| `university_lookup` | `UniversityLookupExplainer` | web-agent engine, `/explain` |
| `data_query` | `DataQueryExplainer` | web-agent engine, `/explain` |
| `comparison` | `ComparisonExplainer` | `/explain` |
| `application_plan` | `ApplicationPlanExplainer` | `/explain` |

The first four are wired into the web-agent engine and share its single
generator, so the one provider configuration above drives every path.
`comparison` and `application_plan` are explanation-only surfaces reached
through the explain route:

- **`comparison`** explains how the universities placed side by side differ. It
  compares *only* on the supplied fields — never on teaching quality, campus
  life, or anything else it was not given — names the fields that are missing
  for some of the rows so absence is not read as similarity, and declines to
  declare a winner the data does not support. Takes `items` plus an optional
  `criterion` ("lowest IELTS").
- **`application_plan`** narrates an already-grouped reach/target/safety plan.
  It never regroups a school, never restates a risk label, and **never predicts
  an admission outcome** — reach/target/safety describe the shape of a
  portfolio, not a probability. An empty group is stated plainly rather than
  glossed over. Takes `plan` instead of `items`. With no provider configured, each path falls back to its
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
  crawlernest/crawlernest-tests/test_ds4_data_query_explainer.py \
  crawlernest/crawlernest-tests/test_ds4_live_path_mock_server.py \
  crawlernest/crawlernest-tests/test_faithfulness.py -q
```

These cover the grounded/honest prompt, the deterministic fallback paths, and the
ds4 provider resolution. `test_ds4_live_path_mock_server.py` additionally spins up
a mock OpenAI-compatible server and drives the **real HTTP round-trip** — request
encoding, the `/v1/chat/completions` call, response parsing, and the
`source="llm"` vs `"fallback"` mapping — so everything except the model itself is
verified without a GPU. A check against a real `ds4-server` (i.e. model output
quality) must still be run on a supported machine and is not part of CI.

## In the product UI

The `/recommendations` page shows an explanation of the results it just
rendered. Two rules shape how it is wired:

**The model is not in the data path.** The Spring Boot read API is untouched.
Ranks, scores, and confidence reach the page exactly as before; the explanation
is fetched separately as a progressive enhancement. If the agent or ds4 is down,
the page is byte-for-byte what it is today — a read-only analytics endpoint never
waits on an optional GPU service.

**The agent explains what is on screen, never its own query.** The page POSTs the
rows it is displaying to `/api/agent/explain`, which proxies to the agent's
`POST /api/v1/agent/explain`. That route is deliberately *not* a task kind: it
never reaches the planner, the tools, or the warehouse. Had it re-run a
recommendation, the agent could have computed a different list and described
universities the user cannot see.

```
/recommendations ──rows──▶ /api/agent/explain ──▶ agent :8090 /api/v1/agent/explain
                                                        │ (explainer only, no DB)
                                                        ▼
                                                   ds4 /v1/chat/completions
```

The panel renders **only when `source == "llm"`**. When the deterministic reply
was used, nothing is shown rather than presenting rule-based text as a model
explanation, and the panel always carries the line *"Ranks, scores, and
confidence come from the ranking data — the model only describes them."*

Request body (`items` capped at 20, `caveats` at 10):

```jsonc
{
  "taskKind": "recommendation",   // see the task-kind table below
  "items": [ /* the rows on screen */ ],
  "caveats": ["Only the QS source is available; ..."],
  "profile": { "country": "Taiwan" },   // detail preview for university_lookup
  "plan": { /* grouped plan */ },        // application_plan only, instead of items
  "criterion": "lowest IELTS",           // comparison only
  "query": "Recommend Taiwan universities for me"
}
```

The recommendations page uses two of these surfaces today: the result sections
get a `recommendation` explanation, and the side-by-side table gets a
`comparison` one, rendered separately from the deterministic explanation already
shown there.

## Faithfulness eval

The honesty contract above is a promise; this is the check that it held. After an
explanation is generated, the evidence it was supposed to stay inside is known
exactly, so faithfulness is verified **mechanically** — no LLM judge, no scoring
model — by `crawlernest/agent/web_agent/generation/faithfulness.py`:

| Violation | Meaning |
|-----------|---------|
| `unsupported_number` | a number in the prose that is not in the evidence (list positions and counts are allowed — "the top 2" describes the given rows) |
| `missing_caveat` | a supplied caveat that was not reproduced (whitespace-insensitive) |
| `unsupported_university` | a university-shaped name that never appeared in the evidence |

Run it over the golden dataset (needs no model):

```bash
PYTHONPATH=. ./.venv/bin/python \
  crawlernest/crawlernest-autoeval/runners/run_faithfulness_eval.py
```

The dataset (`crawlernest/crawlernest-autoeval/datasets/faithfulness/golden.json`)
pairs faithful explanations with known-bad ones — a fabricated rank, a dropped
caveat, an invented institution, a score silently rescaled from `0.82` to `82%` —
so the run also guards the checker itself against regressions. Add `--json` for a
machine-readable summary.

To check what a **real model** produces, point at a running ds4 and use live mode:

```bash
WEB_AGENT_DS4_BASE_URL=http://localhost:8000/v1 PYTHONPATH=. ./.venv/bin/python \
  crawlernest/crawlernest-autoeval/runners/run_faithfulness_eval.py --live
```

Live mode regenerates each entry's explanation through the configured provider
and reports violations in the actual output; any violation is a failure.

Two limits worth stating plainly. Number matching is textual, so a legitimate
reformat (`0.82` → `82%`) is reported — deliberately, since rescaling a score is
the kind of silent transformation the contract forbids. University detection is a
name-shape heuristic: it catches confidently fabricated institutions, not every
possible invented entity.

### Continuous integration

[![Agent Tests](https://github.com/heinricitorgau/University-Data-Infrastructure-Web-Platform/actions/workflows/agent-tests.yml/badge.svg)](https://github.com/heinricitorgau/University-Data-Infrastructure-Web-Platform/actions/workflows/agent-tests.yml)

The [`Agent Tests`](../.github/workflows/agent-tests.yml) workflow runs the test
files above **and** the fixture-mode faithfulness eval on every push and pull
request to `main` (Ubuntu, Python 3.12, `pip install -r requirements.txt`). The
badge above reflects the latest run. Model-output-quality checks against a real
`ds4-server` — including `--live` faithfulness — remain out of CI, since they
need a GPU/large-memory host.
