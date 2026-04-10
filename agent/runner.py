from __future__ import annotations

from agent.engine import AgentEngine, AgentRunResult
from agent.evaluator import Evaluator
from agent.memory import Memory
from agent.refiner import Refiner
from agent.tasks import AgentTask, create_task
from agent.tools import get_default_tools


def build_engine(logger=None, threshold: float = 0.75) -> AgentEngine:
    return AgentEngine(
        evaluator=Evaluator(),
        refiner=Refiner(),
        tools=get_default_tools(),
        threshold=threshold,
        max_iterations=2,
        logger=logger,
    )


def run_task(
    task_input: str | AgentTask,
    memory: Memory | None = None,
    logger=None,
    threshold: float = 0.75,
) -> AgentRunResult:
    engine = build_engine(logger=logger, threshold=threshold)
    resolved_task = task_input if isinstance(task_input, AgentTask) else create_task(task_input)
    active_memory = memory or Memory()
    return engine.run(resolved_task, active_memory)

