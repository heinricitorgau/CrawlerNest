from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class RoutingSignals:
    is_dev_intent: bool
    has_code_keywords: bool
    explicit_dev_kind: bool


@dataclass(slots=True)
class RoutingDecision:
    route: str
    reason: str
    signals: RoutingSignals


@dataclass(slots=True)
class DevHandoff:
    original_user_input: str
    interpreted_task: str
    context: dict[str, object] = field(default_factory=dict)
