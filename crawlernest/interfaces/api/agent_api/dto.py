from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Exhaustive set of recognised source values. Anything outside this falls back
# to "web" so that unexpected or missing values never reach the routing logic.
_VALID_SOURCES: frozenset[str] = frozenset({"web", "cli", "api-dev", "system"})


# Explanation requests are bounded so a client cannot push an unbounded prompt
# into the model through the public route.
_MAX_EXPLAIN_ITEMS = 20
_MAX_EXPLAIN_CAVEATS = 10

_EXPLAIN_TASK_KINDS: frozenset[str] = frozenset(
    {"recommendation", "ranking_explain", "university_lookup", "data_query"}
)


@dataclass(slots=True)
class AgentExplainPayload:
    """Request to explain results the caller already has.

    This is deliberately *not* a task: nothing here queries the warehouse or
    recomputes a recommendation. The caller sends the rows it is already
    displaying and gets prose about exactly those rows, so the explanation can
    never describe a different result set than the user is looking at.
    """

    task_kind: str
    items: list[dict[str, Any]] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)
    profile: dict[str, Any] = field(default_factory=dict)
    query: str = ""
    deterministic_reply: str = ""

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AgentExplainPayload":
        raw_kind = str(payload.get("taskKind") or payload.get("task_kind") or "recommendation")
        task_kind = raw_kind if raw_kind in _EXPLAIN_TASK_KINDS else "recommendation"

        raw_items = payload.get("items")
        items = (
            [i for i in raw_items if isinstance(i, dict)][:_MAX_EXPLAIN_ITEMS]
            if isinstance(raw_items, list)
            else []
        )

        raw_caveats = payload.get("caveats")
        caveats = (
            [str(c) for c in raw_caveats if str(c).strip()][:_MAX_EXPLAIN_CAVEATS]
            if isinstance(raw_caveats, list)
            else []
        )

        raw_profile = payload.get("profile")
        raw_reply = payload.get("deterministicReply") or payload.get("deterministic_reply") or ""

        return cls(
            task_kind=task_kind,
            items=items,
            caveats=caveats,
            profile=dict(raw_profile) if isinstance(raw_profile, dict) else {},
            query=str(payload.get("query", "") or ""),
            deterministic_reply=str(raw_reply),
        )


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

