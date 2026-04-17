from __future__ import annotations

from typing import Any

from crawlernest.agent.shared.models.task_response import TaskResponse


class QueryFormatter:
    def format_query(self, response: TaskResponse) -> dict:
        data = response.data
        top_universities = (
            data.get("topUniversities", [])
            if isinstance(data.get("topUniversities"), list)
            else []
        )
        explanation = (
            data.get("assistantReply")
            or data.get("summary")
            or response.message
        )
        explanation_paragraphs = (
            data.get("assistantReplyParagraphs", [])
            if isinstance(data.get("assistantReplyParagraphs"), list)
            else []
        )

        items: list[dict[str, Any]] = []
        if top_universities:
            items = [
                {"label": str(name), "kind": "university"}
                for name in top_universities
            ]
        elif isinstance(data.get("items"), list):
            items = [
                {
                    "label": str(item.get("universityName", "Unknown"))
                    if isinstance(item, dict)
                    else str(item),
                    "kind": "university",
                    "data": item,
                }
                for item in data["items"][:5]
            ]

        if data.get("universityDisplayName") or data.get("university_display_name"):
            display_name = data.get("universityDisplayName") or data.get(
                "university_display_name"
            )
            aliases = data.get("aliases", []) if isinstance(data.get("aliases"), list) else []
            items = [
                {
                    "label": str(display_name),
                    "kind": "university_detail",
                    "description": (
                        f"Aliases: {', '.join(str(alias) for alias in aliases[:5])}"
                        if aliases
                        else None
                    ),
                }
            ]

        return {
            "type": "query",
            "title": response.message,
            "explanation": explanation,
            "explanationParagraphs": explanation_paragraphs,
            "items": items,
            "meta": {
                **(data.get("metadata", {}) if isinstance(data.get("metadata"), dict) else {}),
                **(
                    {"generationSource": data.get("generationSource")}
                    if data.get("generationSource")
                    else {}
                ),
                **(
                    {"modelName": data.get("modelName")}
                    if data.get("modelName")
                    else {}
                ),
            },
        }
