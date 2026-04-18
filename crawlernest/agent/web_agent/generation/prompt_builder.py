from __future__ import annotations

import re
from typing import TYPE_CHECKING

from crawlernest.agent.web_agent.generation.models import PromptPayload, RetrievedContext
from crawlernest.agent.web_agent.policy.web_agent_policy import WebAgentPolicy

if TYPE_CHECKING:
    from crawlernest.agent.web_agent.memory.conversation_store import ConversationTurn


class WebPromptBuilder:
    def build(
        self,
        *,
        user_input: str,
        original_input: str | None = None,
        rewritten_query: str | None = None,
        resolved_reference: dict | None = None,
        retrieved: RetrievedContext,
        policy: WebAgentPolicy,
        generation_mode: str = "hybrid",
        conversation_history: list[ConversationTurn] | None = None,
        prompt_patches: list[str] | None = None,
    ) -> PromptPayload:
        effective_original_input = original_input or user_input
        language = self._detect_language(effective_original_input)
        lookup_intents = self._detect_lookup_intents(user_input) if retrieved.task_kind == "university_lookup" else []
        ranking_intents = self._detect_ranking_intents(user_input) if retrieved.task_kind == "ranking_explain" else []
        system_instruction = self._build_system_instruction(
            task_kind=retrieved.task_kind,
            language=language,
            lookup_intents=lookup_intents,
            ranking_intents=ranking_intents,
            generation_mode=generation_mode,
        )
        response_constraints = self._build_response_constraints(
            task_kind=retrieved.task_kind,
            language=language,
            policy=policy,
            lookup_intents=lookup_intents,
            ranking_intents=ranking_intents,
            generation_mode=generation_mode,
            prompt_patches=prompt_patches or [],
        )

        context_parts: list[str] = self._build_context_parts(
            retrieved=retrieved,
            policy=policy,
            original_input=effective_original_input,
            rewritten_query=rewritten_query,
            resolved_reference=resolved_reference,
            generation_mode=generation_mode,
            prompt_patches=prompt_patches or [],
        )

        context_block = "\n".join(context_parts).strip()
        if len(context_block) > policy.max_context_chars:
            context_block = context_block[: policy.max_context_chars].rstrip() + "..."

        conversation_turns: list[dict[str, str]] = []
        if conversation_history:
            conversation_turns = [
                {"role": turn.role, "content": turn.content}
                for turn in conversation_history
            ]

        return PromptPayload(
            system_instruction=system_instruction,
            user_message=effective_original_input,
            context_block=context_block,
            response_constraints=response_constraints,
            conversation_turns=conversation_turns,
        )

    def _detect_language(self, user_input: str) -> str:
        return "zh" if re.search(r"[\u4e00-\u9fff]", user_input) else "en"

    def _build_system_instruction(
        self,
        *,
        task_kind: str,
        language: str,
        lookup_intents: list[str],
        ranking_intents: list[str],
        generation_mode: str,
    ) -> str:
        base = (
            "You are CrawlerNest Web Agent. Answer in a helpful, natural, user-facing way. "
            "Use the retrieved education data as your factual grounding. "
            "Do not invent rankings, admissions thresholds, locations, or university facts that are not in the retrieved context. "
            "If the available context is insufficient, say so clearly and suggest a sensible next question."
        )

        task_overrides = {
            "data_query": (
                "Prioritize helping the user understand the returned slice of data, including filters, counts, and notable results."
            ),
            "recommendation": (
                "Prioritize decision guidance. Explain why suggested universities fit the user's profile and where uncertainty remains."
            ),
        }
        if task_kind == "ranking_explain":
            if "compare" in ranking_intents:
                task_overrides["ranking_explain"] = (
                    "Prioritize comparison. Explain how the retrieved ranking evidence separates the most relevant schools, "
                    "where the evidence is thin, and what additional comparison signal would help."
                )
            elif "rank_position" in ranking_intents:
                task_overrides["ranking_explain"] = (
                    "Prioritize rank position. Answer where the university appears in the ranking data, which source supports that position, "
                    "and what the current result slice can and cannot confirm."
                )
            elif "why_high" in ranking_intents:
                task_overrides["ranking_explain"] = (
                    "Prioritize why-this-school-ranks-high explanations. Explain what the current ranking evidence actually shows, "
                    "what remains unknown, and whether the match is direct or approximate."
                )
            else:
                task_overrides["ranking_explain"] = (
                    "Prioritize explaining what the current ranking evidence says, what it does not say, "
                    "and whether the match is direct or approximate."
                )
        if task_kind == "university_lookup":
            if "location" in lookup_intents:
                task_overrides["university_lookup"] = (
                    "Prioritize locating the university: answer with city or country first when the context supports it, "
                    "then add a short identity anchor such as aliases or website if useful."
                )
            elif "admission" in lookup_intents:
                task_overrides["university_lookup"] = (
                    "Prioritize admissions guidance: answer with IELTS, TOEFL, or other threshold hints when they are present. "
                    "If the preview lacks enough admissions data, say that clearly instead of guessing."
                )
            elif "ranking" in lookup_intents:
                task_overrides["university_lookup"] = (
                    "Prioritize the ranking summary for the university: explain the strongest ranking signal and any limitations in the retrieved evidence."
                )
            else:
                task_overrides["university_lookup"] = (
                    "Prioritize giving a compact university profile: identity, aliases, location, ranking summary, and admissions hints when available."
                )

        language_hint = (
            "Respond in Traditional Chinese unless the user clearly asks in another language."
            if language == "zh"
            else "Respond in English."
        )
        mode_hint = (
            "Use the retrieved context as the primary basis for the answer."
            if generation_mode == "hybrid"
            else "You may answer more freely, but stay conservative and clearly signal uncertainty when the retrieved context is weak."
        )

        return " ".join(
            part
            for part in [base, task_overrides.get(task_kind, ""), mode_hint, language_hint]
            if part
        )

    def _build_response_constraints(
        self,
        *,
        task_kind: str,
        language: str,
        policy: WebAgentPolicy,
        lookup_intents: list[str],
        ranking_intents: list[str],
        generation_mode: str,
        prompt_patches: list[str],
    ) -> list[str]:
        constraints = [
            "Prefer concise natural language over rigid templates.",
            "Stay grounded in the retrieved context.",
            "Do not mention internal tool names, traces, or implementation details.",
        ]

        if task_kind == "ranking_explain":
            constraints.extend(
                [
                    "Do not simply restate the top rows. Explain what the ranking data implies for the user's question.",
                    "If the user is really asking about admissions, location, or identity rather than rank quality, say that explicitly.",
                ]
            )
            if "compare" in ranking_intents:
                constraints.extend(
                    [
                        "Keep the answer focused on the comparison the user is implicitly asking for.",
                        "Do not pretend you have a full side-by-side dataset if the current retrieval only shows one page or partial matches.",
                    ]
                )
            if "rank_position" in ranking_intents:
                constraints.extend(
                    [
                        "State the strongest supported rank signal clearly before adding caveats.",
                        "If the current result is only page-level evidence, say so instead of overstating certainty.",
                    ]
                )
            if "why_high" in ranking_intents:
                constraints.extend(
                    [
                        "Do not claim causal reasons that are not present in the retrieved context.",
                        "Frame the answer as what the ranking evidence suggests, not as a complete explanation of the institution.",
                    ]
                )
        elif task_kind == "data_query":
            constraints.extend(
                [
                    "Summarize the most relevant rows rather than dumping all records.",
                    "Mention pagination or total count only when it helps answer the question.",
                ]
            )
        elif task_kind == "university_lookup":
            constraints.extend(
                [
                    "Start with the school identity before moving into supporting details.",
                    "If ranking or admission data is missing, say so plainly instead of filling gaps.",
                ]
            )
            if "location" in lookup_intents:
                constraints.extend(
                    [
                        "Answer the location question directly before giving extra background.",
                        "If the current preview only provides partial location evidence, say that the answer is based on current preview signals.",
                    ]
                )
            if "admission" in lookup_intents:
                constraints.extend(
                    [
                        "Do not treat preview admissions hints as definitive policy unless the data clearly says so.",
                        "If the user asks for thresholds and the context is thin, say that the current preview is only a hint.",
                    ]
                )
            if "ranking" in lookup_intents:
                constraints.extend(
                    [
                        "Keep the explanation focused on the university in question, not the whole ranking page.",
                        "Mention missing ranking evidence if the preview does not provide enough support.",
                    ]
                )
        elif task_kind == "recommendation":
            constraints.extend(
                [
                    "Explain the fit, not just the names.",
                    "Be explicit about uncertainty, tradeoffs, and missing evidence.",
                ]
            )

        if policy.response_style == "user_facing":
            constraints.append(
                "Write as a user-facing assistant, not as an engineering report."
            )

        if generation_mode == "hybrid":
            constraints.append("Anchor the answer to the retrieved context whenever possible.")
        elif generation_mode == "llm":
            constraints.append("Do not present speculation as confirmed fact when retrieval support is weak.")

        if prompt_patches:
            constraints.extend(f"Prompt patch: {patch}" for patch in prompt_patches[:4])

        if language == "zh":
            constraints.append("Keep the tone natural in Traditional Chinese.")

        return constraints

    def _build_context_parts(
        self,
        *,
        retrieved: RetrievedContext,
        policy: WebAgentPolicy,
        original_input: str,
        rewritten_query: str | None,
        resolved_reference: dict | None,
        generation_mode: str,
        prompt_patches: list[str],
    ) -> list[str]:
        context_parts: list[str] = []
        context_parts.append(f"Original user question: {original_input}")
        if rewritten_query and rewritten_query.strip() and rewritten_query.strip() != original_input.strip():
            context_parts.append(f"Interpretation hint: normalized retrieval query = {rewritten_query}")
        if isinstance(resolved_reference, dict) and resolved_reference.get("detected"):
            resolved_entities = resolved_reference.get("resolved_entities")
            if isinstance(resolved_entities, list) and resolved_entities:
                context_parts.append(
                    "Resolved reference: "
                    + ", ".join(str(entity) for entity in resolved_entities[:3])
                )
            input_type = resolved_reference.get("input_type")
            if input_type:
                context_parts.append(f"Reference type: {input_type}")
        if retrieved.summary_facts:
            context_parts.append("Summary facts:")
            context_parts.extend(f"- {fact}" for fact in retrieved.summary_facts)

        if retrieved.records and generation_mode != "llm":
            context_parts.append("Retrieved records:")
            for index, record in enumerate(retrieved.records[: policy.max_context_items], start=1):
                compact_record = ", ".join(
                    f"{key}={value}"
                    for key, value in record.items()
                    if value not in (None, "", [], {})
                )
                if compact_record:
                    context_parts.append(f"{index}. {compact_record}")

        if retrieved.source_hints:
            context_parts.append(
                "Source hints: " + ", ".join(retrieved.source_hints[:4])
            )
        if retrieved.long_term_memory:
            context_parts.append("Long-term memory:")
            for memory in retrieved.long_term_memory[:4]:
                content = memory.get("content")
                confidence = memory.get("confidence")
                if content:
                    suffix = f" (confidence={confidence:.2f})" if isinstance(confidence, (int, float)) else ""
                    context_parts.append(f"- {content}{suffix}")
        if retrieved.strategy_hints:
            context_parts.append("Behavior strategy hints:")
            context_parts.extend(f"- {hint}" for hint in retrieved.strategy_hints[:4])
        if prompt_patches:
            context_parts.append("Prompt optimization patches:")
            context_parts.extend(f"- {patch}" for patch in prompt_patches[:4])
        if generation_mode == "llm" and retrieved.summary_facts:
            context_parts.append("Minimal retrieval hints:")
            context_parts.extend(f"- {fact}" for fact in retrieved.summary_facts[:3])
        return context_parts

    def _detect_lookup_intents(self, user_input: str) -> list[str]:
        lowered = user_input.lower()
        intents: list[str] = []

        location_patterns = [
            r"\bwhere\b",
            r"\blocated\b",
            r"在哪",
            r"哪裡",
            r"位於",
            r"位在",
            r"哪個國家",
            r"哪个国家",
            r"城市",
        ]
        admission_patterns = [
            r"錄取門檻",
            r"录取门槛",
            r"申請門檻",
            r"申请门槛",
            r"admission",
            r"requirement",
            r"ielts",
            r"toefl",
        ]
        ranking_patterns = [
            r"排名",
            r"\brank\b",
            r"\branking\b",
            r"qs",
            r"\bthe\b",
            r"arwu",
        ]

        if any(re.search(pattern, lowered, re.IGNORECASE) for pattern in location_patterns):
            intents.append("location")
        if any(re.search(pattern, lowered, re.IGNORECASE) for pattern in admission_patterns):
            intents.append("admission")
        if any(re.search(pattern, lowered, re.IGNORECASE) for pattern in ranking_patterns):
            intents.append("ranking")

        if not intents:
            intents.append("identity")
        return intents

    def _detect_ranking_intents(self, user_input: str) -> list[str]:
        lowered = user_input.lower()
        intents: list[str] = []

        compare_patterns = [
            r"比較",
            r"比较",
            r"\bcompare\b",
            r"\bvs\b",
            r"versus",
            r"差別",
            r"差异",
        ]
        rank_position_patterns = [
            r"第幾",
            r"第几",
            r"幾名",
            r"几名",
            r"排名多少",
            r"ranked",
            r"\bwhat rank\b",
            r"\brank\b",
            r"\bposition\b",
        ]
        why_high_patterns = [
            r"為什麼",
            r"为什么",
            r"\bwhy\b",
            r"原因",
            r"為何",
            r"为何",
            r"ranks highly",
            r"ranks so high",
        ]

        if any(re.search(pattern, lowered, re.IGNORECASE) for pattern in compare_patterns):
            intents.append("compare")
        if any(re.search(pattern, lowered, re.IGNORECASE) for pattern in rank_position_patterns):
            intents.append("rank_position")
        if any(re.search(pattern, lowered, re.IGNORECASE) for pattern in why_high_patterns):
            intents.append("why_high")

        if not intents:
            intents.append("general_explain")
        return intents
