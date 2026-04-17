from __future__ import annotations

from crawlernest.agent.shared.models.task_response import TaskResponse
from crawlernest.agent.web_agent.formatter.error_formatter import ErrorFormatter
from crawlernest.agent.web_agent.formatter.query_formatter import QueryFormatter
from crawlernest.agent.web_agent.formatter.recommendation_formatter import (
    RecommendationFormatter,
)


class WebResponseFormatter:
    def __init__(self) -> None:
        self._query_formatter = QueryFormatter()
        self._recommendation_formatter = RecommendationFormatter()
        self._error_formatter = ErrorFormatter()

    def format_recommendation(self, response: TaskResponse) -> dict:
        return self._recommendation_formatter.format_recommendation(response)

    def format_query(self, response: TaskResponse) -> dict:
        return self._query_formatter.format_query(response)

    def format_error(self, response: TaskResponse) -> dict:
        return self._error_formatter.format_error(response)

    def format_generic(self, response: TaskResponse) -> dict:
        return {
            "type": "generic",
            "title": response.message,
            "explanation": response.message,
            "items": [],
            "meta": {},
        }
