from __future__ import annotations

import json
import os
from dataclasses import dataclass
from urllib import error, request

from crawlernest.agent.web_agent.generation.models import GenerationResult, PromptPayload


def _ensure_v1_base(base_url: str) -> str:
    """Normalize an OpenAI-compatible base URL to end in ``/v1``."""
    normalized = base_url.rstrip("/")
    return normalized if normalized.endswith("/v1") else f"{normalized}/v1"


@dataclass(slots=True)
class ProviderConfig:
    base_url: str
    api_key: str
    model_name: str
    provider_label: str


class WebResponseGenerator:
    def inspect_provider_status(self) -> dict[str, object]:
        provider = self._resolve_provider()
        if provider is None:
            return {
                "configured": False,
                "providerLabel": None,
                "modelName": None,
                "baseUrl": None,
                "reason": "No web generation provider configured.",
            }

        return {
            "configured": True,
            "providerLabel": provider.provider_label,
            "modelName": provider.model_name,
            "baseUrl": provider.base_url,
            "reason": None,
        }

    def generate_response(
        self,
        *,
        prompt: PromptPayload,
        fallback_text: str,
    ) -> GenerationResult:
        provider = self._resolve_provider()

        if provider is None:
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
            )
            paragraphs = [part.strip() for part in reply.split("\n\n") if part.strip()]
            return GenerationResult(
                reply_text=reply,
                paragraphs=paragraphs or [reply],
                source="llm",
                model_name=provider.model_name,
            )
        except Exception as exc:
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
        # "deepseek-v4-flash".
        ds4_base = os.getenv("WEB_AGENT_DS4_BASE_URL", "").strip()
        if ds4_base:
            return ProviderConfig(
                base_url=_ensure_v1_base(ds4_base),
                api_key=os.getenv("WEB_AGENT_DS4_API_KEY", "").strip(),
                model_name=os.getenv("WEB_AGENT_DS4_MODEL", "").strip() or "deepseek-v4-flash",
                provider_label="ds4",
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

        body = {
            "model": model_name,
            "temperature": 0.4,
            "messages": messages,
        }
        headers: dict[str, str] = {
            "Content-Type": "application/json",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        req = request.Request(
            endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=20) as response:
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
