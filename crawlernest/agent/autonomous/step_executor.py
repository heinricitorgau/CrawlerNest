from __future__ import annotations


class StepExecutor:
    def __init__(self, *, dev_tools, file_resolver, patch_builder) -> None:
        self._dev_tools = dev_tools
        self._file_resolver = file_resolver
        self._patch_builder = patch_builder

    def execute(
        self,
        *,
        step: dict[str, object],
        goal: str,
        context: dict,
        repo_index: dict,
        state: dict,
        validation_builder,
    ) -> dict[str, object]:
        step_name = str(step.get("step", "unknown"))
        step_strategy_hints = [
            str(item).strip()
            for item in step.get("strategy_hints", [])
            if isinstance(item, str) and str(item).strip()
        ]

        if step_name == "strategy_review":
            return {
                "strategyHints": step_strategy_hints,
                "note": "Reused prior successful strategy hints to guide the next refinement steps.",
            }

        if step_name == "analyze":
            resolution = self._file_resolver.resolve(
                user_input=goal,
                context=context,
                repo_index=repo_index,
            )
            return {
                "resolution": resolution,
                "strategyHints": step_strategy_hints,
            }

        if step_name in {"identify_weaknesses", "propose_fix", "propose_improvement", "refine"}:
            refinement = self._dev_tools.suggest_refinement_loop(goal, context)
            hints = list(refinement.get("loop", []))
            if step_name == "refine":
                hints = hints + ["tighten_scope", "improve_validation_confidence"]
            if step_strategy_hints:
                hints = step_strategy_hints + hints
            return {
                "task": refinement.get("task", goal),
                "hints": hints,
                "context": refinement.get("context", {}),
                "strategyHints": step_strategy_hints,
            }

        if step_name == "apply_refinement":
            resolution = state.get("resolution") or self._file_resolver.resolve(
                user_input=goal,
                context=context,
                repo_index=repo_index,
            )
            file_patch = self._patch_builder.build(
                task=goal,
                resolution_result=resolution,
                repo_index=repo_index,
            )
            return {
                "resolution": resolution,
                "filePatch": file_patch,
                "strategyHints": step_strategy_hints,
            }

        if step_name == "validate":
            resolution = state.get("resolution") or self._file_resolver.resolve(
                user_input=goal,
                context=context,
                repo_index=repo_index,
            )
            validation = validation_builder(
                resolution_result=resolution,
                repo_index=repo_index,
            )
            return {
                "resolution": resolution,
                "validation": validation,
                "strategyHints": step_strategy_hints,
            }

        return {"note": "No executor branch for this step."}
