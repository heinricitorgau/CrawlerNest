from __future__ import annotations

from crawlernest.agent.shared.models.task_request import TaskRequest


class SharedPlanner:
    def build_plan(self, request: TaskRequest) -> list[dict[str, str]]:
        if request.kind == "university_lookup":
            return [
                {"step": "resolve_identity", "owner": "university_tools"},
                {"step": "load_detail_preview", "owner": "university_tools"},
            ]
        if request.kind == "data_query":
            return [{"step": "load_rankings", "owner": "ranking_tools"}]
        if request.kind == "ranking_explain":
            return [
                {"step": "load_rankings", "owner": "ranking_tools"},
                {"step": "summarize_ranking_context", "owner": "ranking_tools"},
            ]
        if request.kind == "recommendation":
            return [
                {"step": "validate_profile", "owner": "recommendation_tools"},
                {"step": "run_recommendation", "owner": "recommendation_tools"},
            ]
        if request.kind == "dev_refinement":
            return [
                {"step": "collect_dev_context", "owner": "dev_tools"},
                {"step": "suggest_refinement_loop", "owner": "dev_tools"},
            ]
        return [{"step": "unknown", "owner": "agent_engine"}]
