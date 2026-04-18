from __future__ import annotations

import re

from crawlernest.agent.web_agent.interpretation.models import ResolvedReference, RewriteResult


class QueryRewriter:
    def rewrite(
        self,
        *,
        original_input: str,
        task_kind: str,
        resolved_reference: ResolvedReference,
    ) -> RewriteResult:
        if task_kind == "recommendation":
            return RewriteResult(
                original_input=original_input,
                rewritten_query=None,
                rewrite_applied=False,
                rewrite_reason="Recommendation requests keep the original query unless the user states entities explicitly.",
            )

        if not resolved_reference.detected or not resolved_reference.resolved_entities:
            return RewriteResult(
                original_input=original_input,
                rewritten_query=None,
                rewrite_applied=False,
                rewrite_reason="No safe reference resolution was available.",
            )

        if resolved_reference.input_type == "explicit_entity":
            return RewriteResult(
                original_input=original_input,
                rewritten_query=None,
                rewrite_applied=False,
                rewrite_reason="Current input already contains explicit entities.",
            )

        if resolved_reference.input_type == "pronoun_followup":
            anchor = resolved_reference.resolved_entities[0]
            cleaned = self._strip_followup_pronouns(original_input).strip()
            rewritten = f"{anchor} {cleaned}".strip() if cleaned else anchor
            return RewriteResult(
                original_input=original_input,
                rewritten_query=rewritten,
                rewrite_applied=True,
                rewrite_reason="Resolved pronoun-style follow-up with recent entity context.",
            )

        if resolved_reference.input_type == "compare_followup":
            entities = resolved_reference.resolved_entities[:2]
            if len(entities) >= 2:
                rewritten = f"{entities[0]} 跟 {entities[1]} 比較"
            else:
                rewritten = entities[0]
            return RewriteResult(
                original_input=original_input,
                rewritten_query=rewritten,
                rewrite_applied=True,
                rewrite_reason="Completed comparison query with recent entity context.",
            )

        return RewriteResult(
            original_input=original_input,
            rewritten_query=None,
            rewrite_applied=False,
            rewrite_reason="No rewrite rule matched.",
        )

    def _strip_followup_pronouns(self, text: str) -> str:
        cleaned = text.strip()
        patterns = [
            r"^\s*那它(?:呢)?",
            r"^\s*它(?:呢)?",
            r"^\s*那間學校(?:呢)?",
            r"^\s*那所學校(?:呢)?",
            r"^\s*那個學校(?:呢)?",
            r"^\s*那間(?:呢)?",
            r"^\s*那所(?:呢)?",
            r"^\s*what about it\b",
            r"^\s*how about it\b",
            r"^\s*compare it with\b",
        ]
        for pattern in patterns:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()
        return cleaned
