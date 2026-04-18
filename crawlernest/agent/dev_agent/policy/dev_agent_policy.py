from __future__ import annotations


class DevAgentPolicy:
    allowed_task_kinds = {
        "dev_refinement",
        "data_query",
        "ranking_explain",
        "university_lookup",
    }
    allowed_tool_names = {
        "ranking_tools",
        "university_tools",
        "recommendation_tools",
        "dev_tools",
        "repo_indexer",
        "file_resolver",
        "patch_builder",
        "change_summary",
    }
    expose_traces = True
    response_style = "engineering_facing"
    autonomous_max_iterations = 5
    autonomous_success_threshold = 0.9
    self_improvement_sample_limit = 12
    self_improvement_strategy_confidence = 0.6
