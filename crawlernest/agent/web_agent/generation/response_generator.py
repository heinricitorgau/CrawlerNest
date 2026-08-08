from __future__ import annotations

import json
import logging
import os
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib import error, request

from crawlernest.agent.web_agent.generation.models import GenerationResult, PromptPayload

logger = logging.getLogger(__name__)

# Default per-request HTTP timeout (seconds). ds4 gets a longer default because
# a remote, large local model can spend real time on prefill before the first
# byte; other OpenAI-compatible providers keep the historical 20s.
_DEFAULT_TIMEOUT = 20.0
_DS4_DEFAULT_TIMEOUT = 60.0

# Process-wide generation outcome counters, for observability: watch the
# llm-vs-fallback rate when a ds4 host is (or isn't) reachable.
_stats_lock = threading.Lock()
_generation_stats: dict[str, int] = {"llm": 0, "fallback": 0, "disabled": 0}


def generation_stats() -> dict[str, int]:
    """Snapshot of generation outcomes since process start.

    - ``llm``: the model produced the reply.
    - ``fallback``: a provider was configured and tried, but the call failed
      (network / HTTP / parse / timeout) and the deterministic reply was used.
    - ``disabled``: no provider configured, deterministic reply used.
    """
    with _stats_lock:
        return dict(_generation_stats)


def reset_generation_stats() -> None:
    """Zero the outcome counters (mainly for tests)."""
    with _stats_lock:
        for key in _generation_stats:
            _generation_stats[key] = 0


def _record(outcome: str) -> None:
    with _stats_lock:
        _generation_stats[outcome] = _generation_stats.get(outcome, 0) + 1


def _ensure_v1_base(base_url: str) -> str:
    """Normalize an OpenAI-compatible base URL to end in ``/v1``."""
    normalized = base_url.rstrip("/")
    return normalized if normalized.endswith("/v1") else f"{normalized}/v1"


def _resolve_timeout(env_name: str, default: float) -> float:
    """Positive float from ``env_name``, else ``default``."""
    raw = os.getenv(env_name, "").strip()
    if raw:
        try:
            value = float(raw)
            if value > 0:
                return value
        except ValueError:
            pass
    return default


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


@dataclass(slots=True)
class ProviderConfig:
    base_url: str
    api_key: str
    model_name: str
    provider_label: str
    timeout: float = _DEFAULT_TIMEOUT
    stream: bool = False


class WebResponseGenerator:
    def inspect_provider_status(self) -> dict[str, object]:
        provider = self._resolve_provider()
        if provider is None:
            return {
                "configured": False,
                "providerLabel": None,
                "modelName": None,
                "baseUrl": None,
                "timeout": None,
                "stream": None,
                "reason": "No web generation provider configured.",
            }

        return {
            "configured": True,
            "providerLabel": provider.provider_label,
            "modelName": provider.model_name,
            "baseUrl": provider.base_url,
            "timeout": provider.timeout,
            "stream": provider.stream,
            "reason": None,
        }

    def generate_response(
        self,
        *,
        prompt: PromptPayload,
        fallback_text: str,
        on_delta: Callable[[str], None] | None = None,
    ) -> GenerationResult:
        """Generate a reply, falling back to *fallback_text* on any failure.

        ``on_delta`` is called with each text chunk as it arrives, but only when
        the provider is in streaming mode; it is a hook for a future token-level
        UI. The return value is always the complete text either way, so callers
        that ignore it are unaffected.
        """
        provider = self._resolve_provider()

        if provider is None:
            _record("disabled")
            logger.debug("web-agent generation: no provider configured; deterministic reply used")
            return self._fallback(
                fallback_text,
                warning="No web generation provider configured; deterministic fallback used.",
            )

        try:
            reply = self._call_openai_compatible(
                base_url=provider.base_url,
                api_key=provider.api_key,
                model_name=provider.model_name,
                prompt=prompt,
                timeout=provider.timeout,
                stream=provider.stream,
                on_delta=on_delta,
            )
            paragraphs = [part.strip() for part in reply.split("\n\n") if part.strip()]
            _record("llm")
            logger.info(
                "web-agent generation: source=llm provider=%s model=%s",
                provider.provider_label,
                provider.model_name,
            )
            return GenerationResult(
                reply_text=reply,
                paragraphs=paragraphs or [reply],
                source="llm",
                model_name=provider.model_name,
            )
        except Exception as exc:
            _record("fallback")
            logger.warning(
                "web-agent generation: source=fallback provider=%s model=%s reason=%s",
                provider.provider_label,
                provider.model_name,
                exc,
            )
            return self._fallback(
                fallback_text,
                warning=(
                    f"Generation failed via {provider.provider_label}; "
                    f"deterministic fallback used. Reason: {exc}"
                ),
            )

    def _fallback(self, fallback_text: str, *, warning: str | None = None) -> GenerationResult:
        text = fallback_text.strip() or "I could not generate a richer reply, so I fell back to the current deterministic answer."
        paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()] or [text]
        return GenerationResult(
            reply_text=text,
            paragraphs=paragraphs,
            source="fallback",
            warning=warning,
        )

    def _resolve_provider(self) -> ProviderConfig | None:
        if os.getenv("WEB_AGENT_GENERATION_DISABLED", "").strip() in {"1", "true", "TRUE"}:
            return None

        # DwarfStar 4 (ds4) local inference engine. ds4-server exposes an
        # OpenAI-compatible /v1 API, so it plugs in as a first-class named
        # provider. Opt-in: only active when WEB_AGENT_DS4_BASE_URL is set, so
        # default behavior is unchanged. Recommended value:
        # http://localhost:8000/v1 (ds4-server default port), model
        # "deepseek-v4-flash". WEB_AGENT_DS4_TIMEOUT (seconds) overrides the
        # longer default request timeout for slow/remote generation, and
        # WEB_AGENT_DS4_STREAM=1 switches to SSE streaming (see _read_sse_stream).
        ds4_base = os.getenv("WEB_AGENT_DS4_BASE_URL", "").strip()
        if ds4_base:
            return ProviderConfig(
                base_url=_ensure_v1_base(ds4_base),
                api_key=os.getenv("WEB_AGENT_DS4_API_KEY", "").strip(),
                model_name=os.getenv("WEB_AGENT_DS4_MODEL", "").strip() or "deepseek-v4-flash",
                provider_label="ds4",
                timeout=_resolve_timeout("WEB_AGENT_DS4_TIMEOUT", _DS4_DEFAULT_TIMEOUT),
                stream=_env_flag("WEB_AGENT_DS4_STREAM"),
            )

        web_base = os.getenv("WEB_AGENT_OPENAI_BASE_URL", "").strip()
        web_key = os.getenv("WEB_AGENT_OPENAI_API_KEY", "").strip()
        web_model = os.getenv("WEB_AGENT_MODEL", "").strip()
        if web_base and web_model:
            return ProviderConfig(
                base_url=web_base,
                api_key=web_key,
                model_name=web_model,
                provider_label="web-openai-compatible",
            )

        shared_base = os.getenv("OPENAI_BASE_URL", "").strip()
        shared_key = os.getenv("OPENAI_API_KEY", "").strip()
        shared_model = os.getenv("WEB_AGENT_MODEL", "").strip() or os.getenv(
            "OPENAI_MODEL", ""
        ).strip()
        if shared_base and shared_model:
            return ProviderConfig(
                base_url=shared_base,
                api_key=shared_key,
                model_name=shared_model,
                provider_label="shared-openai-compatible",
            )

        ollama_base = os.getenv("WEB_AGENT_OLLAMA_BASE_URL", "").strip()
        ollama_model = os.getenv("WEB_AGENT_OLLAMA_MODEL", "").strip()
        if ollama_base and ollama_model:
            return ProviderConfig(
                base_url=_ensure_v1_base(ollama_base),
                api_key="",
                model_name=ollama_model,
                provider_label="ollama",
            )

        return None

    def _call_openai_compatible(
        self,
        *,
        base_url: str,
        api_key: str,
        model_name: str,
        prompt: PromptPayload,
        timeout: float = _DEFAULT_TIMEOUT,
        stream: bool = False,
        on_delta: Callable[[str], None] | None = None,
    ) -> str:
        endpoint = base_url.rstrip("/")
        if not endpoint.endswith("/chat/completions"):
            endpoint = f"{endpoint}/chat/completions"

        messages: list[dict[str, str]] = [
            {"role": "system", "content": prompt.system_instruction},
        ]
        # Inject prior conversation turns (alternating user/assistant) between
        # the system instruction and the current user message.
        if prompt.conversation_turns:
            messages.extend(prompt.conversation_turns)
        messages.append({"role": "user", "content": self._compose_user_content(prompt)})

        body: dict[str, Any] = {
            "model": model_name,
            "temperature": 0.4,
            "messages": messages,
        }
        headers: dict[str, str] = {
            "Content-Type": "application/json",
        }
        if stream:
            body["stream"] = True
            headers["Accept"] = "text/event-stream"
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        req = request.Request(
            endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=timeout) as response:
                if stream:
                    # A server that ignores stream:true and answers with plain
                    # JSON is handled by falling through to the non-stream parse.
                    content_type = (response.headers.get("Content-Type") or "").lower()
                    if "text/event-stream" in content_type:
                        return self._read_sse_stream(response, on_delta=on_delta)
                payload = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc

        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RuntimeError("No choices returned from generation provider.")

        message = choices[0].get("message", {})
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()

        if isinstance(content, list):
            text_parts: list[str] = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_value = block.get("text")
                    if isinstance(text_value, str) and text_value.strip():
                        text_parts.append(text_value.strip())
            if text_parts:
                return "\n\n".join(text_parts)

        raise RuntimeError("Generation provider returned no text content.")

    def _read_sse_stream(
        self,
        response: Any,
        *,
        on_delta: Callable[[str], None] | None = None,
    ) -> str:
        """Accumulate an OpenAI-style ``text/event-stream`` into the full reply.

        Streaming is what makes long generation survivable: the socket timeout
        applies per read, so a slow model that keeps emitting chunks no longer
        trips the single-shot request timeout.

        A stream that ends without its terminator is treated as a failure rather
        than returned as partial text. Truncated prose can silently drop the
        caveats the honesty contract requires, so the caller degrades to the
        deterministic reply instead.
        """
        parts: list[str] = []
        finished = False

        for raw_line in response:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line or line.startswith(":"):
                continue  # keep-alive / comment
            if not line.startswith("data:"):
                continue
            data = line[len("data:") :].strip()
            if data == "[DONE]":
                finished = True
                break
            try:
                chunk = json.loads(data)
            except ValueError:
                continue  # tolerate a malformed frame rather than losing the stream

            choices = chunk.get("choices")
            if not isinstance(choices, list) or not choices:
                continue
            choice = choices[0]
            delta = choice.get("delta")
            piece = delta.get("content") if isinstance(delta, dict) else None
            if isinstance(piece, str) and piece:
                parts.append(piece)
                if on_delta is not None:
                    on_delta(piece)
            if choice.get("finish_reason"):
                finished = True

        if not finished:
            raise RuntimeError("Generation stream ended before completion.")

        text = "".join(parts).strip()
        if not text:
            raise RuntimeError("Generation stream produced no text content.")
        return text

    def _compose_user_content(self, prompt: PromptPayload) -> str:
        parts = [
            "User question:",
            prompt.user_message,
            "",
            "Retrieved context:",
            prompt.context_block or "(no retrieved context)",
        ]
        if prompt.response_constraints:
            parts.extend(
                [
                    "",
                    "Response constraints:",
                    *[f"- {constraint}" for constraint in prompt.response_constraints],
                ]
            )
        return "\n".join(parts)
