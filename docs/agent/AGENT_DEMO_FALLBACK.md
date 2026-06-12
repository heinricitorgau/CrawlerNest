# Agent Demo Fallback

The `/agent` demo should continue even when a model provider is unavailable.
Fallback behavior must stay honest, readonly, and presentation-safe.

## Fallback Scenarios

| Scenario | What user sees | What presenter should say | Fallback path |
| --- | --- | --- | --- |
| Ollama unavailable | Safe provider-unavailable response; no raw stack trace. | "The local model service is not reachable. The agent did not modify anything." | Switch `AGENT_MODEL_PROVIDER=mock` and continue. |
| OpenAI unavailable | Safe provider-unavailable response; no raw provider detail. | "The hosted model path depends on network/account readiness, so demo fallback is mock or Ollama." | Use mock, or use Ollama if local model is ready. |
| Timeout | Safe unavailable/timeout wording. | "The request timed out safely. No tools, DB writes, or pipeline runs happened." | Retry once, then switch to mock. |
| API key missing | Safe OpenAI key missing message in status/warnings, without exposing a key. | "The OpenAI provider is intentionally server-side and currently not configured." | Set server env if appropriate, or use mock. |
| Provider misconfigured | Safe invalid provider message. | "Provider configuration is invalid; the agent protects the page by returning a bounded error." | Set `AGENT_MODEL_PROVIDER=mock`, `ollama`, or `openai`. |

Keyword for validation: provider misconfigured.

## Presenter Script

If the model path fails, say:

"The agent is advisory-only. Provider fallback is working as designed: it does
not run tools, write the database, rerun pipelines, or hide the failure. I will
continue with the mock provider so the demo remains repeatable."

## Recovery Commands

Mock fallback:

```bash
AGENT_MODEL_PROVIDER=mock npm run dev
```

Ollama fallback:

```bash
export AGENT_MODEL_PROVIDER=ollama
export OLLAMA_BASE_URL=http://localhost:11434
export AGENT_MODEL_NAME=qwen2.5-coder:7b
npm run dev
```

## Boundary Reminder

Fallback is not remediation. It does not fetch sources, repair data, update
rankings, or change recommendations. It only preserves a safe advisory demo.
