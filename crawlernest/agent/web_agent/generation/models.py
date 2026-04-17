from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class RetrievedContext:
    task_kind: str
    user_input: str
    focus_entity: str | None = None
    summary_facts: list[str] = field(default_factory=list)
    records: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    source_hints: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PromptPayload:
    system_instruction: str
    user_message: str
    context_block: str
    response_constraints: list[str] = field(default_factory=list)
    # Ordered list of prior-turn message dicts {"role": ..., "content": ...}
    # injected between the system message and the current user message.
    conversation_turns: list[dict[str, str]] = field(default_factory=list)


@dataclass(slots=True)
class GenerationResult:
    reply_text: str
    paragraphs: list[str]
    source: str  # "llm" | "fallback"
    model_name: str | None = None
    warning: str | None = None
