from __future__ import annotations


DEV_TASK_MARKERS = ("fix", "build", "implement", "extractor", "parser")


def plan(task: str) -> list[dict[str, str]]:
    normalized_task = " ".join((task or "").strip().split())
    lowered = normalized_task.lower()

    if any(marker in lowered for marker in DEV_TASK_MARKERS):
        return [
            {
                "step": "analyze",
                "goal": f"Inspect the current task scope and behavior for: {normalized_task or 'the task'}",
            },
            {
                "step": "improve",
                "goal": "Identify concrete weaknesses and prepare a stronger implementation path.",
            },
            {
                "step": "refine",
                "goal": "Apply a more robust and structured refinement to the current output.",
            },
            {
                "step": "validate",
                "goal": "Verify that the refined result is clearer, safer, and more complete.",
            },
        ]

    return [
        {
            "step": "analyze",
            "goal": f"Understand the requested outcome for: {normalized_task or 'the task'}",
        },
        {
            "step": "refine",
            "goal": "Produce a concise and readable response aligned with the task.",
        },
    ]
