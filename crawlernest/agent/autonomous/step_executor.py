from __future__ import annotations


class StepExecutor:
    def __init__(
        self,
        *,
        dev_tools,
        file_resolver,
        patch_builder,
        patch_generator=None,
        patch_validator=None,
        patch_executor=None,
        root_dir: str | None = None,
    ) -> None:
        self._dev_tools = dev_tools
        self._file_resolver = file_resolver
        self._patch_builder = patch_builder
        self._patch_generator = patch_generator
        self._patch_validator = patch_validator
        self._patch_executor = patch_executor
        self._root_dir = root_dir

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
            patch_candidate = (
                self._patch_generator.generate(
                    task=goal,
                    resolution_result=resolution,
                    repo_index=repo_index,
                )
                if self._patch_generator is not None
                else None
            )
            file_patch = (
                patch_candidate.get("semantic_patch")
                if isinstance(patch_candidate, dict) and isinstance(patch_candidate.get("semantic_patch"), dict)
                else self._patch_builder.build(
                    task=goal,
                    resolution_result=resolution,
                    repo_index=repo_index,
                )
            )
            return {
                "resolution": resolution,
                "filePatch": file_patch,
                "patchCandidate": patch_candidate,
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
            patch_candidate = state.get("patchCandidate")
            patch_validation = (
                self._patch_validator.validate(
                    patch_candidate=patch_candidate,
                    repo_index=repo_index,
                    root_dir=self._root_dir or "",
                )
                if self._patch_validator is not None and isinstance(patch_candidate, dict)
                else None
            )
            patch_execution = (
                self._patch_executor.execute_in_sandbox(
                    patch_candidate=patch_candidate,
                    patch_validation=patch_validation,
                    resolution_result=resolution,
                )
                if self._patch_executor is not None
                and isinstance(patch_candidate, dict)
                and isinstance(patch_validation, dict)
                else None
            )
            return {
                "resolution": resolution,
                "validation": validation,
                "patchValidation": patch_validation,
                "patchExecution": patch_execution,
                "strategyHints": step_strategy_hints,
            }

        return {"note": "No executor branch for this step."}
