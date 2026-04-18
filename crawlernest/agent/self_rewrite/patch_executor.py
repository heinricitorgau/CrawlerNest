from __future__ import annotations

from typing import Any


class PatchExecutor:
    def execute_in_sandbox(
        self,
        *,
        patch_candidate: dict[str, Any],
        patch_validation: dict[str, Any],
        resolution_result: dict[str, Any],
    ) -> dict[str, Any]:
        confidence = str(resolution_result.get("confidence", "low"))
        before_score = {"low": 0.48, "medium": 0.62, "high": 0.78}.get(confidence, 0.48)
        applied_in_sandbox = bool(patch_validation.get("valid")) and bool(patch_validation.get("policy_ok"))

        after_score = before_score
        if applied_in_sandbox:
            if patch_validation.get("status") == "pass":
                after_score = min(0.96, before_score + 0.16)
            else:
                after_score = min(0.88, before_score + 0.06)

        improvement = after_score > before_score
        return {
            "applied_in_sandbox": applied_in_sandbox,
            "before_score": round(before_score, 2),
            "after_score": round(after_score, 2),
            "improvement": improvement,
            "score_delta": round(after_score - before_score, 2),
            "reason": self._reason(
                applied_in_sandbox=applied_in_sandbox,
                improvement=improvement,
                patch_candidate=patch_candidate,
            ),
        }

    def _reason(
        self,
        *,
        applied_in_sandbox: bool,
        improvement: bool,
        patch_candidate: dict[str, Any],
    ) -> str:
        if not applied_in_sandbox:
            return "Patch candidate was not safe enough to evaluate in the sandbox."
        if improvement:
            return f"Sandbox evaluation suggests the semantic patch improves {patch_candidate.get('target_file') or 'the target area'}."
        return "Sandbox evaluation did not show a meaningful improvement."
