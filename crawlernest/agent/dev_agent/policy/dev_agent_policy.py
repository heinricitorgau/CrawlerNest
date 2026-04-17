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
    }
    expose_traces = True
    response_style = "engineering_facing"
