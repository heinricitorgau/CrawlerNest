# Agent Provider Matrix

This matrix compares provider choices for `/agent` competition and demo use.

| Provider | Setup difficulty | Demo suitability | Internet dependency | Reliability | Cost | Recommendation |
| --- | --- | --- | --- | --- | --- | --- |
| mock | Very low | High for scripted demos and fallback | None | Very high | None | Use as the safest default and fallback. |
| ollama | Medium | High when local model is preloaded | None after local setup | Medium to high, depending on machine | None after setup | Best competition default when hardware is ready. |
| openai | Low to medium | High quality when network/key are stable | Required | Medium, depends on network and quota | Usage-based | Use only when key, network, and model are verified before demo. |

## Competition Default

Competition default should be:

1. `mock` for maximum repeatability and no external dependency.
2. `ollama` when the local model is already pulled, tested, and responsive.

OpenAI is useful for richer answers, but it should not be the sole demo path
because it depends on internet access, account state, quota, and server-side key
configuration.

## Provider Recommendations

- Use mock for smoke checks, build validation, screenshots, and fallback.
- Use Ollama for local competition rooms where internet reliability is unknown.
- Use OpenAI only when the presenter has verified the key, model name, timeout
  behavior, and fallback flow on the same machine.
- Never put provider keys in frontend env variables.
