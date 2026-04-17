from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Exhaustive set of recognised source values. Anything outside this falls back
# to "web" so that unexpected or missing values never reach the routing logic.
_VALID_SOURCES: frozenset[str] = frozenset({"web", "cli", "api-dev", "system"})


@dataclass(slots=True)
class AgentTaskPayload:
    mode: str
    kind: str
    user_input: str
    context: dict[str, Any] = field(default_factory=dict)
    constraints: dict[str, Any] = field(default_factory=dict)
    source: str = "web"
    # Optional: clients that support multi-turn memory supply a session_id.
    # Missing or blank values are normalised to None (stateless request).
    session_id: str | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AgentTaskPayload":
        raw_source = str(payload.get("source", "web"))
        raw_session = payload.get("session_id")
        session_id = str(raw_session).strip() if raw_session and str(raw_session).strip() else None
        return cls(
            mode=str(payload.get("mode", "")),
            kind=str(payload.get("kind", "")),
            user_input=str(payload.get("user_input", "")),
            context=dict(payload.get("context", {}) or {}),
            constraints=dict(payload.get("constraints", {}) or {}),
            source=raw_source if raw_source in _VALID_SOURCES else "web",
            session_id=session_id,
        )

