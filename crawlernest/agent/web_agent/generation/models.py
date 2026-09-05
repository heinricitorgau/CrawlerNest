from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class RetrievedContext:
    task_kind: str
    user_input: str
    original_input: str | None = None
    rewritten_query: str | None = None
    resolved_reference: dict[str, Any] | None = None
    focus_entity: str | None = None
    summary_facts: list[str] = field(default_factory=list)
    records: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    source_hints: list[str] = field(default_factory=list)
    long_term_memory: list[dict[str, Any]] = field(default_factory=list)
    strategy_hints: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PromptPayload:
    system_instruction: str
    user_message: str
    context_block: str
    response_constraints: list[str] = field(default_factory=list)
    # Ordered list of prior-turn message dicts {"role": ..., "content": ...}
    # injected between the system message and the current user message.
    conversation_turns: list[dict[str, str]] = field(default_factory=list)
    # What the corpus is, and the rules that hold whatever the conversation
    # does. These go into the *system* turn, and deliberately repeat what
    # context_block and response_constraints already say in the user turn.
    #
    # The duplication is the point. Everything above lands in the final user
    # message, and conversation_turns are inserted between the system message
    # and that one -- so the longer a session runs, the further the year lock
    # and the no-trend rule drift from the model's attention, and the more they
    # look like part of one turn's request rather than a standing constraint.
    # A rule stated in the system turn is not something a later turn can
    # plausibly be read as superseding.
    system_context: str = ""
    system_constraints: list[str] = field(default_factory=list)


@dataclass(slots=True)
class GenerationResult:
    reply_text: str
    paragraphs: list[str]
    source: str  # "llm" | "fallback"
    model_name: str | None = None
    warning: str | None = None
