from __future__ import annotations


class AutonomousEvaluator:
    def evaluate(
        self,
        *,
        step_name: str,
        step_result: dict,
        state: dict,
    ) -> dict[str, object]:
        score = 0.35
        status = "unclear"
        reason = "Step produced partial evidence."

        if step_name == "analyze":
            resolution = step_result.get("resolution", {})
            confidence = str(resolution.get("confidence", "low"))
            score = {"low": 0.35, "medium": 0.58, "high": 0.72}.get(confidence, 0.35)
            status = "good" if score >= 0.58 else "unclear"
            reason = "Repo target resolution confidence drives the analysis score."

        elif step_name in {"identify_weaknesses", "propose_fix", "propose_improvement"}:
            hints = step_result.get("hints", [])
            score = 0.55 + min(0.25, 0.08 * len(hints))
            status = "good" if score >= 0.65 else "unclear"
            reason = "More concrete implementation hints increase proposal quality."

        elif step_name == "apply_refinement":
            file_patch = step_result.get("filePatch", {})
            change_count = len(file_patch.get("changes", [])) if isinstance(file_patch, dict) else 0
            score = 0.45 + min(0.35, 0.1 * change_count)
            status = "good" if change_count > 0 else "bad"
            reason = "Semantic patch coverage determines refinement usefulness."

        elif step_name == "validate":
            validation = step_result.get("validation", {})
            patch_execution = step_result.get("patchExecution", {})
            validation_status = validation.get("status")
            if isinstance(patch_execution, dict) and patch_execution.get("applied_in_sandbox"):
                after_score = float(patch_execution.get("after_score", 0.0))
                score = max(0.3, min(1.0, after_score))
                status = "good"
                if patch_execution.get("improvement"):
                    reason = "Sandbox patch evaluation shows an improvement."
                else:
                    reason = "Sandbox patch evaluation ran, but improvement stayed limited."
            elif validation_status == "pass":
                score = 0.95
                status = "good"
                reason = "Validation checks passed."
            elif validation_status == "review":
                score = 0.62
                status = "unclear"
                reason = "Validation surfaced follow-up review items."
            else:
                score = 0.25
                status = "bad"
                reason = "Validation failed to support the proposed refinement."

        elif step_name == "refine":
            prior_score = float(state.get("best_score", 0.0))
            hints = step_result.get("hints", [])
            score = min(0.98, prior_score + 0.08 + min(0.12, 0.04 * len(hints)))
            status = "good" if score > prior_score else "unclear"
            reason = "Refinement score reflects whether the revised plan gained specificity."

        return {
            "score": round(max(0.0, min(1.0, score)), 2),
            "status": status,
            "reason": reason,
        }
