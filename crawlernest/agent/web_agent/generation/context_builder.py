from __future__ import annotations

from typing import Any

from crawlernest.agent.web_agent.generation.intent_detection import (
    detect_lookup_intents,
    detect_ranking_intents,
)
from crawlernest.agent.web_agent.generation.models import RetrievedContext


class WebContextBuilder:
    def build(
        self,
        *,
        task_kind: str,
        user_input: str,
        original_input: str | None = None,
        rewritten_query: str | None = None,
        resolved_reference: dict[str, Any] | None = None,
        raw_data: dict[str, Any],
        request_context: dict[str, Any],
        long_term_memory: list[dict[str, Any]] | None = None,
    ) -> RetrievedContext:
        metadata = (
            dict(raw_data.get("metadata", {}))
            if isinstance(raw_data.get("metadata"), dict)
            else {}
        )
        focus_entity = self._extract_focus_entity(raw_data, request_context)
        records = self._extract_records(task_kind, raw_data)
        summary_facts = self._build_summary_facts(
            task_kind=task_kind,
            user_input=user_input,
            original_input=original_input or user_input,
            rewritten_query=rewritten_query,
            resolved_reference=resolved_reference,
            raw_data=raw_data,
            metadata=metadata,
            focus_entity=focus_entity,
            long_term_memory=long_term_memory or [],
        )
        source_hints = self._build_source_hints(task_kind, raw_data)
        if long_term_memory:
            source_hints = list(source_hints) + ["long-term memory"]

        return RetrievedContext(
            task_kind=task_kind,
            user_input=user_input,
            original_input=original_input or user_input,
            rewritten_query=rewritten_query,
            resolved_reference=resolved_reference,
            focus_entity=focus_entity,
            summary_facts=summary_facts,
            records=records,
            metadata=metadata,
            source_hints=source_hints,
            long_term_memory=list(long_term_memory or []),
        )

    def _extract_focus_entity(
        self,
        raw_data: dict[str, Any],
        request_context: dict[str, Any],
    ) -> str | None:
        candidates = [
            raw_data.get("focusEntity"),
            raw_data.get("universityDisplayName"),
            raw_data.get("university_display_name"),
            request_context.get("search"),
            request_context.get("university_name"),
        ]
        for candidate in candidates:
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        return None

    def _extract_records(
        self,
        task_kind: str,
        raw_data: dict[str, Any],
    ) -> list[dict[str, Any]]:
        if task_kind == "data_query" and isinstance(raw_data.get("items"), list):
            return [
                self._compact_ranking_record(item)
                for item in raw_data["items"][:8]
                if isinstance(item, dict)
            ]

        if task_kind == "recommendation" and isinstance(raw_data.get("items"), list):
            return [
                self._compact_recommendation_record(item)
                for item in raw_data["items"][:8]
                if isinstance(item, dict)
            ]

        if task_kind == "ranking_explain":
            ranking_items = raw_data.get("items")
            if isinstance(ranking_items, list) and ranking_items:
                return [
                    self._compact_ranking_record(item)
                    for item in ranking_items[:8]
                    if isinstance(item, dict)
                ]

            names = raw_data.get("topUniversities")
            if isinstance(names, list):
                return [{"universityName": str(name)} for name in names[:8] if str(name).strip()]

        if task_kind == "university_lookup":
            preview = self._compact_preview_record(raw_data)
            return [preview] if preview else []

        return []

    def _build_summary_facts(
        self,
        *,
        task_kind: str,
        user_input: str,
        original_input: str,
        rewritten_query: str | None,
        resolved_reference: dict[str, Any] | None,
        raw_data: dict[str, Any],
        metadata: dict[str, Any],
        focus_entity: str | None,
        long_term_memory: list[dict[str, Any]],
    ) -> list[str]:
        facts: list[str] = []

        if rewritten_query and rewritten_query.strip() and rewritten_query.strip() != original_input.strip():
            facts.append(f"Interpretation hint: rewritten query = {rewritten_query}")

        if isinstance(resolved_reference, dict) and resolved_reference.get("detected"):
            entities = resolved_reference.get("resolved_entities")
            if isinstance(entities, list) and entities:
                facts.append(
                    "Resolved reference entities: "
                    + ", ".join(str(entity) for entity in entities[:3])
                )

        if long_term_memory:
            facts.append("Long-term memory signals:")
            for entry in long_term_memory[:3]:
                content = entry.get("content")
                if content:
                    facts.append(f"Memory: {content}")

        if focus_entity:
            facts.append(f"Focus entity: {focus_entity}")

        summary = raw_data.get("summary")
        if isinstance(summary, str) and summary.strip():
            facts.append(summary.strip())

        total_count = metadata.get("totalCount")
        page = metadata.get("page")
        page_size = metadata.get("pageSize")
        if isinstance(total_count, int):
            facts.append(f"Total count: {total_count}")
        if isinstance(page, int) and isinstance(page_size, int):
            facts.append(f"Page: {page}, page size: {page_size}")

        if task_kind == "university_lookup":
            facts.extend(self._lookup_facts(user_input, raw_data))

        if task_kind == "ranking_explain":
            facts.extend(self._ranking_facts(user_input, raw_data, focus_entity, total_count, page_size))

        if task_kind == "recommendation" and isinstance(raw_data.get("items"), list):
            facts.extend(self._recommendation_facts(raw_data, total_count, page_size))

        return facts[:12]

    def _lookup_facts(self, user_input: str, raw_data: dict[str, Any]) -> list[str]:
        out: list[str] = []
        question_intents = self._detect_lookup_intents(user_input)
        if question_intents:
            out.append("Likely user intent: " + ", ".join(question_intents))

        display_name = raw_data.get("universityDisplayName") or raw_data.get(
            "university_display_name"
        )
        if display_name:
            out.append(f"University preview available for: {display_name}")

        aliases = raw_data.get("aliases")
        if isinstance(aliases, list) and aliases:
            out.append("Aliases: " + ", ".join(str(alias) for alias in aliases[:5]))

        identity_summary = raw_data.get("identitySummary")
        city_name = None
        website_url = None
        if isinstance(identity_summary, dict):
            city_name = identity_summary.get("cityName")
            website_url = identity_summary.get("websiteUrl")
            matched_by = identity_summary.get("matchedBy")
            matched_value = identity_summary.get("matchedValue")
            if matched_by and matched_value:
                out.append(f"Identity match: {matched_by} = {matched_value}")
            if website_url:
                out.append(f"Website signal: {website_url}")

        ranking_summary = raw_data.get("rankingSummary")
        if isinstance(ranking_summary, dict):
            best_rank = ranking_summary.get("bestRank")
            best_source = ranking_summary.get("bestSource")
            if best_rank is not None:
                out.append(
                    f"Best ranking signal: rank {best_rank}"
                    + (f" via {best_source}" if best_source else "")
                )

        admission_summary = raw_data.get("admissionSummary")
        countries: list[str] = []
        if isinstance(admission_summary, dict):
            raw_countries = admission_summary.get("countries")
            if isinstance(raw_countries, list):
                countries = [str(country) for country in raw_countries[:3] if str(country).strip()]
            ielts = admission_summary.get("bestIeltsRequirement")
            toefl = admission_summary.get("bestToeflRequirement")
            admission_bits = []
            if ielts is not None:
                admission_bits.append(f"IELTS {ielts}")
            if toefl is not None:
                admission_bits.append(f"TOEFL {toefl}")
            if admission_bits:
                out.append("Admission hints: " + ", ".join(admission_bits))

        location_bits = []
        if city_name:
            location_bits.append(str(city_name))
        if countries:
            location_bits.extend(countries)
        if location_bits:
            out.append("Location signal: " + ", ".join(location_bits))

        data_availability = raw_data.get("dataAvailability")
        missing_sections: list[str] = []
        has_ranking_data = None
        has_admission_data = None
        if isinstance(data_availability, dict):
            missing_raw = data_availability.get("missingSections")
            if isinstance(missing_raw, list):
                missing_sections = [str(section) for section in missing_raw if str(section).strip()]
            has_ranking_data = data_availability.get("hasRankingData")
            has_admission_data = data_availability.get("hasAdmissionData")
            if missing_sections:
                out.append("Missing sections: " + ", ".join(missing_sections))

        if "location" in question_intents and not location_bits:
            out.append("Location is not directly available in the current preview data.")

        if "admission" in question_intents:
            has_admission_hints = isinstance(admission_summary, dict) and any(
                admission_summary.get(key) is not None
                for key in ["bestIeltsRequirement", "bestToeflRequirement"]
            )
            if not has_admission_hints:
                out.append(
                    "Admission threshold is not directly available in the current preview data."
                )

        if "ranking" in question_intents and not isinstance(ranking_summary, dict):
            out.append("Ranking summary is not directly available in the current preview data.")

        if has_admission_data is False:
            out.append("Admission preview data is currently missing for this university.")
        if has_ranking_data is False:
            out.append("Ranking preview data is currently missing for this university.")

        return out

    def _ranking_facts(
        self,
        user_input: str,
        raw_data: dict[str, Any],
        focus_entity: str | None,
        total_count: Any,
        page_size: Any,
    ) -> list[str]:
        out: list[str] = []
        ranking_intents = self._detect_ranking_intents(user_input)
        if ranking_intents:
            out.append("Likely ranking intent: " + ", ".join(ranking_intents))

        ranking_items = raw_data.get("items")
        compact_items = [
            item for item in ranking_items[:5]
            if isinstance(item, dict)
        ] if isinstance(ranking_items, list) else []
        top_names = raw_data.get("topUniversities")
        if isinstance(top_names, list) and top_names:
            out.append(
                "Top matched universities: "
                + ", ".join(str(name) for name in top_names[:5])
            )
        elif compact_items:
            matched_names = [
                str(item.get("universityName"))
                for item in compact_items
                if item.get("universityName")
            ]
            if matched_names:
                out.append(
                    "Top matched universities: "
                    + ", ".join(matched_names[:5])
                )

        if focus_entity and compact_items:
            exact_match = next(
                (
                    item for item in compact_items
                    if isinstance(item.get("universityName"), str)
                    and focus_entity.lower() in str(item.get("universityName")).lower()
                ),
                None,
            )
            if exact_match:
                match_bits = []
                if exact_match.get("universityName"):
                    match_bits.append(str(exact_match["universityName"]))
                if exact_match.get("aggregatedRank") is not None:
                    match_bits.append(f"aggregated rank {exact_match['aggregatedRank']}")
                if exact_match.get("primarySource"):
                    match_bits.append(f"source {exact_match['primarySource']}")
                if match_bits:
                    out.append("Direct match signal: " + ", ".join(match_bits))

        if "compare" in ranking_intents:
            compare_candidates = []
            if isinstance(top_names, list):
                compare_candidates = [str(name) for name in top_names[:3] if str(name).strip()]
            elif compact_items:
                compare_candidates = [
                    str(item.get("universityName"))
                    for item in compact_items[:3]
                    if item.get("universityName")
                ]
            if compare_candidates:
                out.append(
                    "Comparison candidates in current slice: "
                    + ", ".join(compare_candidates)
                )

        if isinstance(total_count, int):
            if isinstance(page_size, int) and total_count > page_size:
                out.append(
                    "Current evidence is page-level and may not cover the full result set."
                )
            elif total_count <= 5:
                out.append("Current evidence is narrow and based on a small result slice.")

        if "rank_position" in ranking_intents and compact_items:
            first_rank = compact_items[0].get("aggregatedRank")
            if first_rank is not None:
                out.append(f"Strongest visible rank signal on this page: {first_rank}")

        if "why_high" in ranking_intents:
            out.append(
                "Use ranking evidence as support, but do not infer broader causal reasons that are not in the data."
            )

        return out

    def _recommendation_facts(
        self,
        raw_data: dict[str, Any],
        total_count: Any,
        page_size: Any,
    ) -> list[str]:
        out: list[str] = []
        items = [
            item for item in raw_data["items"][:5] if isinstance(item, dict)
        ]
        if items:
            out.append(f"Recommendation candidates returned: {len(items)}")
            countries = sorted(
                {
                    str(item.get("country")).strip()
                    for item in items
                    if item.get("country") not in (None, "")
                }
            )
            if countries:
                out.append(
                    "Countries represented in recommendation slice: "
                    + ", ".join(countries[:5])
                )

            categories = sorted(
                {
                    str(item.get("category")).strip()
                    for item in items
                    if item.get("category") not in (None, "")
                }
            )
            if categories:
                out.append(
                    "Recommendation categories present: "
                    + ", ".join(categories[:5])
                )

            positive_reasons = [
                str(item.get("reason")).strip()
                for item in items
                if item.get("reason") not in (None, "")
            ]
            if positive_reasons:
                out.append("Example recommendation reason: " + positive_reasons[0])

        user_profile = raw_data.get("profile")
        if isinstance(user_profile, dict):
            profile_bits = []
            for key in [
                "country",
                "countryPolicy",
                "ielts",
                "toefl",
                "targetRank",
                "riskProfile",
                "preferredRankingSource",
            ]:
                value = user_profile.get(key)
                if value not in (None, "", [], {}):
                    profile_bits.append(f"{key}={value}")
            if profile_bits:
                out.append("Recommendation profile: " + ", ".join(profile_bits))

        if isinstance(total_count, int) and isinstance(page_size, int) and total_count > page_size:
            out.append("Current recommendation evidence is page-level and may not include all candidates.")

        return out

    def _detect_lookup_intents(self, user_input: str) -> list[str]:
        return detect_lookup_intents(user_input)

    def _detect_ranking_intents(self, user_input: str) -> list[str]:
        return detect_ranking_intents(user_input)

    def _build_source_hints(self, task_kind: str, raw_data: dict[str, Any]) -> list[str]:
        hints: list[str] = []
        if task_kind in {"data_query", "ranking_explain"}:
            hints.append("ranking")
        if task_kind == "recommendation":
            hints.append("recommendation")
        if task_kind == "university_lookup":
            hints.append("preview")

        ranking_summary = raw_data.get("rankingSummary")
        if isinstance(ranking_summary, dict):
            sources = ranking_summary.get("sources")
            if isinstance(sources, list) and sources:
                hints.extend(str(source) for source in sources[:3])

        return hints[:6]

    def _compact_ranking_record(self, item: dict[str, Any]) -> dict[str, Any]:
        keys = [
            "universityName",
            "country",
            "aggregatedRank",
            "globalRank",
            "scopeRank",
            "primarySource",
            "sourceCount",
            "rankingYear",
        ]
        return {key: item.get(key) for key in keys if item.get(key) not in (None, "", [], {})}

    def _compact_recommendation_record(self, item: dict[str, Any]) -> dict[str, Any]:
        preferred_keys = [
            "universityName",
            "country",
            "category",
            "band",
            "decision",
            "reason",
            "confidence",
            "riskLevel",
            "fitSummary",
            "ieltsRequirement",
            "toeflRequirement",
            "tuitionBand",
            "rankingSource",
            "rank",
        ]
        compact = {
            key: item.get(key)
            for key in preferred_keys
            if item.get(key) not in (None, "", [], {})
        }
        if not compact:
            compact = {
                key: value
                for key, value in item.items()
                if value not in (None, "", [], {})
            }
        return compact

    def _compact_preview_record(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        preview: dict[str, Any] = {}
        if raw_data.get("canonicalUniversityId") is not None:
            preview["canonicalUniversityId"] = raw_data.get("canonicalUniversityId")
        if raw_data.get("universityDisplayName") or raw_data.get("university_display_name"):
            preview["universityDisplayName"] = raw_data.get("universityDisplayName") or raw_data.get(
                "university_display_name"
            )
        if raw_data.get("normalizedUniversityName"):
            preview["normalizedUniversityName"] = raw_data.get("normalizedUniversityName")

        aliases = raw_data.get("aliases")
        if isinstance(aliases, list) and aliases:
            preview["aliases"] = aliases[:5]

        identity_summary = raw_data.get("identitySummary")
        if isinstance(identity_summary, dict):
            identity_bits = {
                key: identity_summary.get(key)
                for key in [
                    "matchedBy",
                    "matchedValue",
                    "cityName",
                    "websiteUrl",
                ]
                if identity_summary.get(key) not in (None, "", [], {})
            }
            if identity_bits:
                preview["identitySummary"] = identity_bits

        ranking_summary = raw_data.get("rankingSummary")
        if isinstance(ranking_summary, dict):
            ranking_bits = {
                key: ranking_summary.get(key)
                for key in [
                    "bestRank",
                    "bestSource",
                    "bestRankingYear",
                    "sourceCount",
                ]
                if ranking_summary.get(key) not in (None, "", [], {})
            }
            if ranking_bits:
                preview["rankingSummary"] = ranking_bits

        admission_summary = raw_data.get("admissionSummary")
        if isinstance(admission_summary, dict):
            admission_bits = {
                key: admission_summary.get(key)
                for key in [
                    "countries",
                    "bestIeltsRequirement",
                    "bestToeflRequirement",
                ]
                if admission_summary.get(key) not in (None, "", [], {})
            }
            if admission_bits:
                preview["admissionSummary"] = admission_bits

        data_availability = raw_data.get("dataAvailability")
        if isinstance(data_availability, dict):
            availability_bits = {
                key: data_availability.get(key)
                for key in [
                    "hasRankingData",
                    "hasAdmissionData",
                    "missingSections",
                ]
                if data_availability.get(key) not in (None, "", [], {})
            }
            if availability_bits:
                preview["dataAvailability"] = availability_bits

        return preview
