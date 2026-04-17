from __future__ import annotations

import re
from typing import Any

from crawlernest.core.services.recommendation_service import RecommendationService


class RecommendationTools:
    def __init__(self, service: RecommendationService | None = None) -> None:
        self._service = service or RecommendationService()

    def recommend(self, context: dict[str, Any], user_input: str = "") -> dict[str, Any]:
        merged_context = self._merge_prompt_context(context, user_input)
        return self._service.recommend(merged_context)

    def _merge_prompt_context(self, context: dict[str, Any], user_input: str) -> dict[str, Any]:
        merged = dict(context)

        extracted = {
            "country": self._extract_country(user_input),
            "ielts": self._extract_float(user_input, [r"ielts\s*([0-9]+(?:\.[0-9])?)", r"雅思\s*([0-9]+(?:\.[0-9])?)"]),
            "toefl": self._extract_int(user_input, [r"toefl\s*([0-9]+)", r"托福\s*([0-9]+)"]),
            "targetRank": self._extract_int(
                user_input,
                [
                    r"target\s*rank\s*([0-9]+)",
                    r"rank\s*(?:under|<=?|below)\s*([0-9]+)",
                    r"top\s*([0-9]+)",
                    r"排名\s*(?:前|以內|内)\s*([0-9]+)",
                ],
            ),
            "limit": self._extract_int(
                user_input,
                [
                    r"(?:show|give|recommend)\s*(?:me\s*)?([0-9]+)",
                    r"([0-9]+)\s*(?:schools|universities|options|results)",
                    r"([0-9]+)\s*所",
                ],
            ),
            "riskProfile": self._extract_risk_profile(user_input),
            "preferredRankingSource": self._extract_ranking_source(user_input),
        }

        for key, value in extracted.items():
            if value not in (None, "", [], {}):
                merged[key] = value

        return merged

    def _extract_country(self, user_input: str) -> str | None:
        lowered = user_input.lower()
        country_aliases = {
            "united kingdom": "United Kingdom",
            "uk": "United Kingdom",
            "britain": "United Kingdom",
            "england": "United Kingdom",
            "united states": "United States",
            "us": "United States",
            "usa": "United States",
            "america": "United States",
            "canada": "Canada",
            "australia": "Australia",
            "singapore": "Singapore",
            "hong kong": "Hong Kong",
            "japan": "Japan",
            "germany": "Germany",
            "netherlands": "Netherlands",
            "china": "China",
            "台灣": "Taiwan",
            "台湾": "Taiwan",
            "英國": "United Kingdom",
            "英国": "United Kingdom",
            "美國": "United States",
            "美国": "United States",
            "加拿大": "Canada",
            "澳洲": "Australia",
            "澳大利亚": "Australia",
            "新加坡": "Singapore",
            "香港": "Hong Kong",
            "日本": "Japan",
            "德國": "Germany",
            "德国": "Germany",
            "荷蘭": "Netherlands",
            "荷兰": "Netherlands",
            "中國": "China",
            "中国": "China",
        }
        for alias, canonical in country_aliases.items():
            if alias in lowered or alias in user_input:
                return canonical
        return None

    def _extract_risk_profile(self, user_input: str) -> str | None:
        lowered = user_input.lower()
        mapping = {
            "conservative": ["conservative", "保守"],
            "balanced": ["balanced", "平衡", "均衡"],
            "aggressive": ["aggressive", "積極", "激進", "进取"],
        }
        for canonical, aliases in mapping.items():
            if any(alias in lowered or alias in user_input for alias in aliases):
                return canonical
        return None

    def _extract_ranking_source(self, user_input: str) -> str | None:
        lowered = user_input.lower()
        for source in ("QS", "THE", "ARWU"):
            if source.lower() in lowered:
                return source
        return None

    def _extract_float(self, user_input: str, patterns: list[str]) -> float | None:
        for pattern in patterns:
            match = re.search(pattern, user_input, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1))
                except (TypeError, ValueError):
                    return None
        return None

    def _extract_int(self, user_input: str, patterns: list[str]) -> int | None:
        for pattern in patterns:
            match = re.search(pattern, user_input, re.IGNORECASE)
            if match:
                try:
                    return int(match.group(1))
                except (TypeError, ValueError):
                    return None
        return None
