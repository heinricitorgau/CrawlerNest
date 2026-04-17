from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


# ---------------------------------------------------------------------------
# TaskRequest
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class TaskRequest:
    """
    Unified agent input contract.

    All callers — CLI, Web API, dev scripts — must pass this object.
    Never pass a raw string directly to AgentService; always construct
    a TaskRequest first.

    Fields
    ------
    prompt      : The task description in natural language.
    task_type   : "dev"  → developer task (fix extractor, validate code, etc.)
                  "web"  → end-user task  (recommend university, query data, etc.)
                  "auto" → agent infers the type from the prompt keywords.
    session_id  : Optional caller-provided session identifier.
                  Used for memory scoping when session management is added.
    metadata    : Free-form dict for callers to pass extra context.
                  Not used by the agent core; available for logging / tracing.
    """

    prompt: str
    task_type: Literal["dev", "web", "auto"] = "auto"
    session_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.prompt = self.prompt.strip()
        if not self.prompt:
            raise ValueError("TaskRequest.prompt cannot be empty.")


# ---------------------------------------------------------------------------
# TaskResponse
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class TaskResponse:
    """
    Unified agent output contract.

    AgentService always returns this object.
    Callers convert it into whatever external format they need
    (JSON for HTTP, printed lines for CLI, etc.).

    Fields
    ------
    task        : Echo of the original prompt.
    result      : The agent's final output text.
    score       : Evaluator score in [0.0, 1.0].
    passed      : True if score >= configured threshold.
    iterations  : Number of refinement loops executed.
    mode        : Resolved execution mode ("dev", "web", "tool", "generation").
    feedback    : List of evaluator notes / reasons.
    tool_outputs: Structured results from tool calls (recommender, db query, etc.).
    session_id  : Echoed back from the request.
    error       : Non-None when the agent caught an unrecoverable exception.
    """

    task: str
    result: str
    score: float
    passed: bool
    iterations: int
    mode: str
    feedback: list[str]
    tool_outputs: dict[str, Any] | None = None
    session_id: str | None = None
    error: str | None = None

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    @property
    def ok(self) -> bool:
        """True when the run completed without a hard error."""
        return self.error is None

    def to_dict(self) -> dict[str, Any]:
        """Shallow dict serialisation for logging and API responses."""
        return {
            "task": self.task,
            "result": self.result,
            "score": self.score,
            "passed": self.passed,
            "iterations": self.iterations,
            "mode": self.mode,
            "feedback": self.feedback,
            "tool_outputs": self.tool_outputs,
            "session_id": self.session_id,
            "error": self.error,
        }
