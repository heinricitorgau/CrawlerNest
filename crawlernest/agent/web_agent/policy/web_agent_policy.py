from __future__ import annotations


class WebAgentPolicy:
    allowed_task_kinds = {
        "data_query",
        "recommendation",
        "ranking_explain",
        "university_lookup",
    }
    allowed_tool_names = {
        "ranking_tools",
        "recommendation_tools",
        "university_tools",
    }
    expose_traces = False
    response_style = "user_facing"
    allow_generation = True
    generation_mode = "auto"
    max_context_items = 8
    max_context_chars = 6000
