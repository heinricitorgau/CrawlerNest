from __future__ import annotations

from crawlernest.agent.shared.models.task_response import TaskResponse


class RecommendationFormatter:
    def format_recommendation(self, response: TaskResponse) -> dict:
        data = response.data
        raw_items = data.get("items", []) if isinstance(data.get("items"), list) else []
        items = [
            self._format_item(item)
            for item in raw_items
            if isinstance(item, dict)
        ]
        explanation = data.get("assistantReply") or data.get("summary") or response.message
        explanation_paragraphs = (
            data.get("assistantReplyParagraphs", [])
            if isinstance(data.get("assistantReplyParagraphs"), list)
            else []
        )
        return {
            "type": "recommendation",
            "title": "Recommended Universities",
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

    def _format_item(self, item: dict) -> dict:
        label = str(item.get("universityName") or item.get("label") or "Recommendation")
        category = str(item.get("category") or item.get("decision") or "recommendation")

        description_parts: list[str] = []
        if item.get("country"):
            description_parts.append(str(item["country"]))
        if item.get("aggregatedRank") is not None:
            description_parts.append(f"Rank {item['aggregatedRank']}")
        if item.get("matchingScore") is not None:
            description_parts.append(f"Match {item['matchingScore']}")
        if item.get("ieltsRequirement") is not None:
            description_parts.append(f"IELTS {item['ieltsRequirement']}")

        description = " · ".join(description_parts) if description_parts else None

        return {
            "label": label,
            "kind": category,
            "description": description,
            "data": item,
        }
