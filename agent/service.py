from __future__ import annotations

from agent.contracts import TaskRequest, TaskResponse
from agent.memory import Memory
from agent.runner import run_task

# ---------------------------------------------------------------------------
# Task-type inference
# ---------------------------------------------------------------------------

_DEV_KEYWORDS = frozenset(
    ("fix", "build", "implement", "extractor", "parser", "validate", "patch", "refactor")
)
_WEB_KEYWORDS = frozenset(
    ("recommend", "query", "explain", "search", "rank", "university", "compare")
)


def _infer_mode(prompt: str, task_type: str) -> str:
    """Resolve the effective execution mode from task_type and prompt keywords."""
    if task_type in ("dev", "web"):
        return task_type

    lowered = prompt.lower()
    if any(kw in lowered for kw in _DEV_KEYWORDS):
        return "dev"
    if any(kw in lowered for kw in _WEB_KEYWORDS):
        return "web"
    return "auto"


# ---------------------------------------------------------------------------
# AgentService
# ---------------------------------------------------------------------------

class AgentService:
    """
    The single public entry point for all agent interactions.

    Design rules
    ------------
    - CLI and Web API both call AgentService.run(TaskRequest).
    - Neither caller knows about Agent, AgentEngine, runner, or tools directly.
    - Memory is scoped per AgentService instance → one instance = one session.

    Usage
    -----
    Dev agent (CLI)::

        service = AgentService(mode="dev")
        response = service.run(TaskRequest(prompt="fix extractor", task_type="dev"))

    Web agent (FastAPI)::

        service = AgentService(mode="web")
        response = service.run(TaskRequest(prompt="recommend UK universities"))

    Both callers use the same class and the same underlying agent core.
    """

    def __init__(
        self,
        threshold: float = 0.75,
        mode: str = "auto",
        session_id: str | None = None,
    ) -> None:
        self.threshold = threshold
        self.default_mode = mode
        self.session_id = session_id
        self.memory = Memory()
        self.memory.add("system", f"AgentService session started. mode={mode}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, request: TaskRequest) -> TaskResponse:
        """
        Execute a task and return a TaskResponse.

        Never raises — errors are captured in TaskResponse.error.
        """
        effective_mode = _infer_mode(request.prompt, request.task_type)

        try:
            raw = run_task(
                task_input=request.prompt,
                memory=self.memory,
                threshold=self.threshold,
            )
            return TaskResponse(
                task=raw.task,
                result=raw.output,
                score=raw.score,
                passed=raw.passed,
                iterations=raw.iterations,
                mode=effective_mode,
                feedback=list(raw.feedback),
                session_id=request.session_id or self.session_id,
            )

        except Exception as exc:  # noqa: BLE001
            return TaskResponse(
                task=request.prompt,
                result="",
                score=0.0,
                passed=False,
                iterations=0,
                mode="error",
                feedback=[],
                error=str(exc),
                session_id=request.session_id or self.session_id,
            )

    def reset_memory(self) -> None:
        """Clear session memory and re-initialise."""
        self.memory = Memory()
        self.memory.add("system", f"AgentService session reset. mode={self.default_mode}")


# ---------------------------------------------------------------------------
# Factory helpers — preferred construction shortcuts
# ---------------------------------------------------------------------------

def create_dev_service(threshold: float = 0.85) -> AgentService:
    """
    Build an AgentService tuned for development tasks.
    Higher threshold → more refinement iterations before passing.
    """
    return AgentService(threshold=threshold, mode="dev")


def create_web_service(
    threshold: float = 0.75,
    session_id: str | None = None,
) -> AgentService:
    """
    Build an AgentService tuned for end-user web tasks.
    """
    return AgentService(threshold=threshold, mode="web", session_id=session_id)
