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
        data = response.data if isinstance(response.data, dict) else {}
        if {"type", "title", "explanation"}.issubset(data.keys()):
            return {
                "type": data.get("type", "generic"),
                "title": data.get("title", response.message),
                "explanation": data.get("explanation", response.message),
                "explanationParagraphs": (
                    data.get("explanationParagraphs", [])
                    if isinstance(data.get("explanationParagraphs"), list)
                    else []
                ),
                "items": data.get("items", []) if isinstance(data.get("items"), list) else [],
                "meta": data.get("meta", {}) if isinstance(data.get("meta"), dict) else {},
            }
        return {
            "type": "generic",
            "title": response.message,
            "explanation": response.message,
            "items": [],
            "meta": {},
        }
