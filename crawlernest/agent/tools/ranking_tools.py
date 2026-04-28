from __future__ import annotations

import re
from typing import Any

from crawlernest.core.services.ranking_service import RankingQuery, RankingService
from crawlernest.core.services.university_service import UniversityService


class RankingTools:
    def __init__(
        self,
        service: RankingService | None = None,
        university_service: UniversityService | None = None,
    ) -> None:
        self._service = service or RankingService()
        self._university_service = university_service or UniversityService()

    def _detect_language(self, user_input: str) -> str:
        return "zh" if re.search(r"[\u4e00-\u9fff]", user_input) else "en"

    def _is_admission_question(self, user_input: str) -> bool:
        lowered = user_input.lower()
        keywords = [
            "錄取門檻",
            "申請門檻",
            "入學門檻",
            "門檻",
            "ielts",
            "toefl",
            "托福",
            "雅思",
            "admission requirement",
            "requirement",
            "admission",
        ]
        return any(keyword in lowered or keyword in user_input for keyword in keywords)

    def _is_location_question(self, user_input: str) -> bool:
        lowered = user_input.lower()
        keywords = [
            "在哪",
            "哪裡",
            "哪里",
            "哪個國家",
            "哪个国家",
            "國家",
            "location",
            "where is",
            "where's",
            "located",
            "位於",
            "位在",
        ]
        return any(keyword in lowered or keyword in user_input for keyword in keywords)

    def _clean_entity_candidate(self, value: str) -> str:
        candidate = value.strip(" 。？！!?.，,")
        candidate = re.sub(
            r"(?:在英國的哪裡|在哪個國家|在哪裡|在哪里|在哪|位於哪裡|位於哪個國家|的錄取門檻|的申請門檻|的入學門檻|的門檻|的排名)$",
            "",
            candidate,
            flags=re.IGNORECASE,
        )
        candidate = re.sub(r"\s+", " ", candidate).strip()
        return candidate

    def _extract_focus_entity(self, user_input: str) -> str:
        text = user_input.strip()
        if not text:
            return ""

        quoted_match = re.search(r'"([^"]+)"|\'([^\']+)\'', text)
        if quoted_match:
            return next(group for group in quoted_match.groups() if group).strip()

        zh_patterns = [
            r"(.+?)的(?:錄取門檻|申請門檻|入學門檻|門檻|排名)",
            r"(.+?)在哪個國家",
            r"(.+?)在哪裡",
            r"(.+?)在哪里",
            r"(.+?)在哪",
            r"(.+?)位於哪裡",
            r"(.+?)位於哪個國家",
            r"查一下(.+)",
            r"說明一下(.+)",
            r"介紹一下(.+)",
        ]
        for pattern in zh_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                candidate = self._clean_entity_candidate(match.group(1))
                if candidate:
                    return candidate

        patterns = [
            r"explain why\s+(.+?)\s+ranks",
            r"why\s+(.+?)\s+ranks",
            r"where is\s+(.+)",
            r"where's\s+(.+)",
            r"which country is\s+(.+?)(?:\s+in)?$",
            r"show\s+(.+?)\s+(?:university preview|preview|detail)",
            r"lookup\s+(.+)",
            r"find\s+(.+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                candidate = self._clean_entity_candidate(match.group(1))
                if candidate:
                    return candidate

        fallback_match = re.match(
            r"([A-Za-z0-9 .,&'()\\-]+?)(?:在英國的哪裡|在哪個國家|在哪裡|在哪里|在哪|位於哪裡|位於哪個國家)\??$",
            text,
            re.IGNORECASE,
        )
        if fallback_match:
            candidate = self._clean_entity_candidate(fallback_match.group(1))
            if candidate:
                return candidate

        return ""

    def _build_assistant_reply(
        self,
        *,
        user_input: str,
        focus_entity: str,
        items: list[dict[str, Any]],
        metadata: dict[str, Any],
    ) -> tuple[str, list[str]]:
        language = self._detect_language(user_input)
        admission_question = self._is_admission_question(user_input)
        top_names = [str(item["universityName"]) for item in items[:5] if item.get("universityName")]
        first = top_names[0] if top_names else ""
        total_count = metadata.get("totalCount")
        page = metadata.get("page")
        page_size = metadata.get("pageSize")

        if admission_question and focus_entity:
            try:
                detail = self._university_service.get_detail_preview(
                    university_name=focus_entity
                )
            except Exception:
                detail = {}

            admission_summary = detail.get("admissionSummary") or detail.get(
                "admission_summary"
            ) or {}
            ielts = admission_summary.get("bestIeltsRequirement")
            toefl = admission_summary.get("bestToeflRequirement")
            matched_name = detail.get("universityDisplayName") or detail.get(
                "university_display_name"
            ) or focus_entity

            if language == "zh":
                if ielts is not None or toefl is not None:
                    parts = []
                    if ielts is not None:
                        parts.append(f"IELTS 大約是 {ielts}")
                    if toefl is not None:
                        parts.append(f"TOEFL 大約是 {toefl}")
                    paragraphs = [
                        f"如果你是在問 {matched_name} 的錄取門檻，我目前能從 admission preview 看到的語言要求大致是 { '，'.join(parts) }。",
                        "這代表目前資料線裡已經有一部分 admission requirement，但它還不是完整招生政策，所以比較適合當快速參考，而不是最終申請標準。",
                    ]
                    return "\n\n".join(paragraphs), paragraphs

                paragraphs = [
                    f"如果你是在問 {matched_name} 的錄取門檻，這條 ranking explain 主要查到的是排名資料，不是完整招生標準。",
                ]
                if first:
                    paragraphs.append(
                        f"我目前看到 {matched_name} 確實出現在排名結果裡，但 admission preview 還沒有足夠的門檻資訊可直接回答你的問題。"
                    )
                else:
                    paragraphs.append(
                        "目前 admission preview 也沒有足夠的門檻資訊可以直接回答這個問題。"
                    )
                return "\n\n".join(paragraphs), paragraphs

            if ielts is not None or toefl is not None:
                parts = []
                if ielts is not None:
                    parts.append(f"IELTS is about {ielts}")
                if toefl is not None:
                    parts.append(f"TOEFL is about {toefl}")
                paragraphs = [
                    f"If you're asking about the admission threshold for {matched_name}, the admission preview I can see right now suggests {' and '.join(parts)}.",
                    "That is useful as a quick reference, but it is still preview-layer data rather than a complete admissions policy.",
                ]
                return "\n\n".join(paragraphs), paragraphs

            paragraphs = [
                f"If you're asking about the admission threshold for {matched_name}, this ranking tool mainly gives me ranking data, not full admissions criteria.",
                "I do not currently have enough admission preview detail to answer that threshold confidently.",
            ]
            return "\n\n".join(paragraphs), paragraphs

        if language == "zh":
            if focus_entity and first and focus_entity.lower() in first.lower():
                paragraphs = [
                    f"就目前這頁的資料來看，{first} 是和「{focus_entity}」最直接對應的結果，而且它排在這一頁最前面。",
                ]
            elif focus_entity and top_names:
                paragraphs = [
                    f"我剛剛用「{focus_entity}」去查目前的排名資料，這一頁最接近的結果是 { '、'.join(top_names) }。",
                ]
            elif top_names:
                paragraphs = [
                    f"我先看了目前這一頁的排名資料，最值得注意的幾所學校是 { '、'.join(top_names) }。",
                ]
            else:
                paragraphs = ["我查了目前的排名資料，但這一頁沒有回到任何學校。"]

            if isinstance(total_count, int) and total_count > 0:
                if isinstance(page, int) and isinstance(page_size, int) and total_count > page_size:
                    paragraphs.append(
                        f"這個查詢目前總共有 {total_count:,} 筆結果，你現在看到的是第 {page} 頁。"
                    )
                else:
                    paragraphs.append(
                        f"這個查詢目前共有 {total_count:,} 筆結果。"
                    )

            return "\n\n".join(paragraphs), paragraphs

        if focus_entity and first and focus_entity.lower() in first.lower():
            paragraphs = [
                f"From the data I just loaded, {first} is the clearest match for {focus_entity} and it appears at the top of the current results."
            ]
        elif focus_entity and top_names:
            paragraphs = [
                f"I looked up ranking data related to {focus_entity}, and the closest matches on this page are {', '.join(top_names)}."
            ]
        elif top_names:
            paragraphs = [
                f"I checked the current ranking slice, and the schools that stand out most here are {', '.join(top_names)}."
            ]
        else:
            paragraphs = [
                "I checked the ranking query, but this page did not return any universities."
            ]

        if isinstance(total_count, int) and total_count > 0:
            if isinstance(page, int) and isinstance(page_size, int) and total_count > page_size:
                paragraphs.append(
                    f"There are {total_count:,} matching rows in total, and you are currently looking at page {page}."
                )
            else:
                paragraphs.append(
                    f"This query currently comes back with {total_count:,} matching rows."
                )

        return "\n\n".join(paragraphs), paragraphs

    def _build_detail_driven_reply(
        self,
        *,
        user_input: str,
        focus_entity: str,
        fallback_country: str,
    ) -> tuple[str, list[str]]:
        language = self._detect_language(user_input)

        try:
            detail = self._university_service.get_detail_preview(
                university_name=focus_entity
            )
        except Exception:
            detail = {}

        display_name = (
            detail.get("universityDisplayName")
            or detail.get("university_display_name")
            or focus_entity
        )
        identity_summary = detail.get("identitySummary") or detail.get(
            "identity_summary"
        ) or {}
        admission_summary = detail.get("admissionSummary") or detail.get(
            "admission_summary"
        ) or {}
        aliases = detail.get("aliases") or []

        city_name = identity_summary.get("cityName") or identity_summary.get("city_name")
        countries = admission_summary.get("countries") or []
        country_name = countries[0] if countries else fallback_country
        website_url = identity_summary.get("websiteUrl") or identity_summary.get(
            "website_url"
        )

        if self._is_location_question(user_input):
            if language == "zh":
                pieces = []
                if city_name:
                    pieces.append(str(city_name))
                if country_name:
                    pieces.append(str(country_name))
                if pieces:
                    location_text = "、".join(pieces)
                    paragraphs = [
                        f"{display_name} 目前看起來位在 {location_text}。",
                    ]
                else:
                    paragraphs = [
                        f"我目前能確認你是在問 {display_name} 的地點，不過這份 preview 還沒有很完整的位置資訊。",
                    ]

                if aliases:
                    alias_text = "、".join(str(alias) for alias in aliases[:3])
                    paragraphs.append(f"它也常用 {alias_text} 這些名稱出現。")
                if website_url:
                    paragraphs.append(f"如果你要，我下一步也可以直接幫你整理它的官網資訊：{website_url}")
                else:
                    paragraphs.append("如果你要，我也可以接著幫你查它的排名、申請門檻，或直接比較它和其他英國學校。")
                return "\n\n".join(paragraphs), paragraphs

            paragraphs = []
            if city_name or country_name:
                location_bits = [str(bit) for bit in [city_name, country_name] if bit]
                paragraphs.append(
                    f"{display_name} appears to be located in {' / '.join(location_bits)}."
                )
            else:
                paragraphs.append(
                    f"I can see that you are asking about the location of {display_name}, but this preview does not yet have strong location detail."
                )
            if website_url:
                paragraphs.append(f"If you want, I can also help you look at its official site next: {website_url}")
            else:
                paragraphs.append(
                    "If you want, I can next look at its rankings, admission requirements, or compare it with other UK universities."
                )
            return "\n\n".join(paragraphs), paragraphs

        return "", []

    def _extract_country(self, user_input: str) -> str | None:
        """Extract a canonical country name from *user_input*.

        Uses the same alias map as RecommendationTools so country filtering
        is consistent across both ranking and recommendation queries.
        """
        lowered = user_input.lower()
        country_aliases = {
            "taiwanese universities": "Taiwan",
            "taiwan universities": "Taiwan",
            "universities in taiwan": "Taiwan",
            "taiwan schools": "Taiwan",
            "national taiwan": "Taiwan",
            "taiwan rankings": "Taiwan",
            "taiwan": "Taiwan",
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
            "國立台灣": "Taiwan",
            "國立臺灣": "Taiwan",
            "臺灣": "Taiwan",
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

    def _build_query_context(
        self,
        user_input: str,
        context: dict[str, Any],
        *,
        prefer_prompt_entity: bool,
    ) -> dict[str, Any]:
        next_context = dict(context)
        entity = self._extract_focus_entity(user_input)

        # Extract country from the prompt; when found, apply hard_filter so
        # ranking queries are scoped to that country and never fall back to
        # global results.
        country = self._extract_country(user_input)
        if country:
            next_context["country"] = country
            next_context["country_policy"] = "hard_filter"
            next_context["countryPolicy"] = "hard_filter"
            next_context["country_preference_mode"] = "hard_filter"

        if prefer_prompt_entity and entity:
            next_context["search"] = entity
        elif entity and not str(next_context.get("search", "")).strip():
            next_context["search"] = entity

        return next_context

    def list_rankings(self, context: dict[str, Any], user_input: str = "") -> dict[str, Any]:
        resolved_context = self._build_query_context(
            user_input,
            context,
            prefer_prompt_entity=False,
        )
        query = RankingQuery(
            year=int(resolved_context.get("year", 2026)),
            scope=str(resolved_context.get("scope", "global")),
            page=int(resolved_context.get("page", 1)),
            page_size=int(resolved_context.get("page_size", 20)),
            search=str(resolved_context.get("search", "")),
            country=resolved_context.get("country") or "",
            region=str(resolved_context.get("region", "")),
        )
        return self._service.list_rankings(query)

    def explain_rankings(self, context: dict[str, Any], user_input: str = "") -> dict[str, Any]:
        resolved_context = self._build_query_context(
            user_input,
            context,
            prefer_prompt_entity=True,
        )
        rankings = self.list_rankings(resolved_context, user_input=user_input)
        items = rankings.get("items", [])
        top_names = [item["universityName"] for item in items[:5]]
        focus_entity = str(resolved_context.get("search", "")).strip()
        fallback_country = ""
        if items and isinstance(items[0], dict):
            fallback_country = str(items[0].get("country", "")).strip()
        if focus_entity:
            summary = (
                f"I loaded {len(items)} ranking rows related to {focus_entity} for the current page."
            )
        else:
            summary = f"I loaded {len(items)} rankings rows for the current page."
        assistant_reply = ""
        assistant_reply_paragraphs: list[str] = []
        if focus_entity and self._is_location_question(user_input):
            assistant_reply, assistant_reply_paragraphs = self._build_detail_driven_reply(
                user_input=user_input,
                focus_entity=focus_entity,
                fallback_country=fallback_country,
            )

        if not assistant_reply_paragraphs:
            assistant_reply, assistant_reply_paragraphs = self._build_assistant_reply(
                user_input=user_input,
                focus_entity=focus_entity,
                items=items,
                metadata=rankings.get("metadata", {}),
            )
        return {
            "summary": summary,
            "topUniversities": top_names,
            "metadata": rankings.get("metadata", {}),
            "focusEntity": focus_entity,
            "assistantReply": assistant_reply,
            "assistantReplyParagraphs": assistant_reply_paragraphs,
        }
