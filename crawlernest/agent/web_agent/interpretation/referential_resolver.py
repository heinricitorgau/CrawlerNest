from __future__ import annotations

import re

from crawlernest.agent.web_agent.interpretation.models import ResolvedReference
from crawlernest.agent.web_agent.memory.conversation_store import ConversationTurn
from crawlernest.agent.web_agent.memory.memory_policy import (
    _FOLLOWUP_RE,
    _extract_entity_tokens,
)


class ReferentialResolver:
    _GENERIC_ENTITY_TOKENS = {
        "比較",
        "排名",
        "學校",
        "学校",
        "大學",
        "大学",
        "university",
        "college",
        "institute",
        "united",
        "kingdom",
        "ielts",
        "toefl",
        "qs",
        "the",
        "arwu",
    }
    _GENERIC_CJK_SUBSTRINGS = [
        "那它",
        "它",
        "哪裡",
        "哪里",
        "哪個國家",
        "哪个国家",
        "排名",
        "比較",
        "相比",
        "推薦",
        "推荐",
        "學校",
        "学校",
        "錄取",
        "录取",
        "門檻",
        "门槛",
        "申請",
        "申请",
        "如何",
        "多少",
        "幾分",
        "几分",
        "在",
    ]

    def resolve(
        self,
        *,
        current_input: str,
        task_kind: str,
        history: list[ConversationTurn],
    ) -> ResolvedReference:
        explicit_entities = self._extract_entities_in_order(current_input)
        followup_detected = bool(_FOLLOWUP_RE.search(current_input))
        compare_detected = self._is_compare_query(current_input)

        if task_kind == "recommendation":
            if explicit_entities:
                return ResolvedReference(
                    detected=True,
                    input_type="explicit_entity",
                    resolved_entities=explicit_entities,
                    confidence="high",
                    reason="Explicit entity found in current recommendation request.",
                )
            return ResolvedReference(
                detected=False,
                input_type="none",
                resolved_entities=[],
                confidence="low",
                reason="Recommendation requests do not inherit lookup entities without explicit mention.",
            )

        if explicit_entities and (not compare_detected or len(explicit_entities) >= 2):
            return ResolvedReference(
                detected=True,
                input_type="explicit_entity",
                resolved_entities=explicit_entities,
                confidence="high",
                reason="Explicit entity found in current input.",
            )

        recent_entity_hint = (
            self._extract_recent_entity_hint(history)
            if history and followup_detected
            else None
        )

        if compare_detected:
            compare_entities = self._resolve_compare_entities(
                explicit_entities=explicit_entities,
                recent_entity_hint=recent_entity_hint,
            )
            if compare_entities and len(compare_entities) > len(explicit_entities):
                return ResolvedReference(
                    detected=True,
                    input_type="compare_followup",
                    resolved_entities=compare_entities,
                    confidence="high" if len(compare_entities) > 1 else "medium",
                    reason=(
                        "Explicit comparison target found in the current input."
                        if explicit_entities
                        else "Recent entity carry-over used to complete the comparison target."
                    ),
                )

        if not explicit_entities and followup_detected and recent_entity_hint:
            return ResolvedReference(
                detected=True,
                input_type="pronoun_followup",
                resolved_entities=[recent_entity_hint],
                confidence="medium",
                reason="Recent entity carry-over used for follow-up interpretation.",
            )

        if explicit_entities:
            return ResolvedReference(
                detected=True,
                input_type="explicit_entity",
                resolved_entities=explicit_entities,
                confidence="high",
                reason="Explicit entity found in current input.",
            )

        return ResolvedReference(
            detected=False,
            input_type="none",
            resolved_entities=[],
            confidence="low",
            reason="No explicit or safely reusable entity was found.",
        )

    def _resolve_compare_entities(
        self,
        *,
        explicit_entities: list[str],
        recent_entity_hint: str | None,
    ) -> list[str]:
        entities: list[str] = []

        if recent_entity_hint and recent_entity_hint not in entities and all(
            recent_entity_hint.lower() != entity.lower() for entity in explicit_entities
        ):
            entities.append(recent_entity_hint)

        for entity in explicit_entities:
            if entity.lower() not in {value.lower() for value in entities}:
                entities.append(entity)

        return entities

    def _extract_recent_entity_hint(
        self,
        history: list[ConversationTurn],
    ) -> str | None:
        assistant_seen = 0
        user_seen = 0

        for turn in reversed(history):
            if turn.role == "assistant" and assistant_seen < 2:
                assistant_seen += 1
                hint = self._pick_recent_entity_from_text(turn.content)
                if hint:
                    return hint

        for turn in reversed(history):
            if turn.role == "user" and user_seen < 2:
                user_seen += 1
                hint = self._pick_recent_entity_from_text(turn.content)
                if hint:
                    return hint

        return None

    def _pick_recent_entity_from_text(self, text: str) -> str | None:
        entities = self._extract_entities_in_order(text)
        if entities:
            lowered = text.lower()
            ranked = sorted(
                entities,
                key=lambda entity: (
                    lowered.count(entity.lower()),
                    lowered.rfind(entity.lower()),
                    len(entity),
                ),
                reverse=True,
            )
            return ranked[0]

        tokens = _extract_entity_tokens(text)
        if not tokens:
            return None

        lowered = text.lower()
        ranked = sorted(
            tokens,
            key=lambda token: (lowered.rfind(token.lower()), len(token)),
            reverse=True,
        )
        return ranked[0] if ranked else None

    def _extract_entities_in_order(self, text: str) -> list[str]:
        if not text.strip():
            return []

        tokens = _extract_entity_tokens(text)
        if not tokens:
            return []

        filtered_tokens = {
            token for token in tokens if self._is_valid_entity_token(token)
        }
        if not filtered_tokens:
            return []

        lowered = text.lower()
        ordered = sorted(
            ((token, lowered.find(token.lower())) for token in filtered_tokens),
            key=lambda item: (item[1] if item[1] >= 0 else 10**6, len(item[0])),
        )

        entities: list[str] = []
        seen: set[str] = set()
        for token, _ in ordered:
            normalized = token.lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            entities.append(self._normalise_entity_token(token))
        return entities

    def _normalise_entity_token(self, token: str) -> str:
        if re.fullmatch(r"[a-z]{2,}", token):
            return " ".join(part.capitalize() for part in token.split())
        return token

    def _is_valid_entity_token(self, token: str) -> bool:
        normalized = token.strip().lower()
        if not normalized:
            return False
        if normalized in self._GENERIC_ENTITY_TOKENS:
            return False
        if re.fullmatch(r"[\u4e00-\u9fff]{2,}", token):
            if any(fragment in token for fragment in self._GENERIC_CJK_SUBSTRINGS):
                return False
        return True

    def _is_compare_query(self, text: str) -> bool:
        return bool(
            re.search(
                r"(比較|相比|對比|compare|compared to|versus|\bvs\.?\b)",
                text,
                re.IGNORECASE,
            )
        )
