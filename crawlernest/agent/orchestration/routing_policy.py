from __future__ import annotations

import re

from crawlernest.agent.orchestration.handoff_types import RoutingDecision, RoutingSignals
from crawlernest.agent.shared.models.task_request import TaskRequest

_DEV_KEYWORD_RE = re.compile(
    r"\b(fix|bug|error|improve|refactor|function|code|file|patch|parser|extractor)\b"
    r"|修|錯|壞|bug|函式|函數|程式|代碼|檔案|重構|抽取器|解析器",
    re.IGNORECASE,
)


class RoutingPolicy:
    def decide(self, request: TaskRequest) -> RoutingDecision:
        explicit_dev_kind = request.kind == "dev_refinement"
        has_code_keywords = bool(_DEV_KEYWORD_RE.search(request.user_input))
        is_dev_intent = explicit_dev_kind or has_code_keywords

        # A caller that wants data and disclosures, and nothing else, can say
        # so. Without this the keyword scan above decides for it: a perfectly
        # ordinary question that happens to contain "error" or "壞" would hand
        # the turn to the dev agent, which plans file changes and returns
        # through format_dev_handoff_result -- a path that carries no
        # response-level disclosures at all. Honoured only for web-sourced
        # requests, and only towards "web": pinning cannot be used to reach the
        # dev agent from somewhere that could not already route there.
        if (
            request.source == "web"
            and not explicit_dev_kind
            and str(request.constraints.get("route", "")).strip().lower() == "web"
        ):
            return RoutingDecision(
                route="web",
                reason="caller pinned the web route; no development handoff",
                signals=RoutingSignals(
                    is_dev_intent=is_dev_intent,
                    has_code_keywords=has_code_keywords,
                    explicit_dev_kind=explicit_dev_kind,
                ),
            )

        if request.source != "web":
            if is_dev_intent:
                return RoutingDecision(
                    route="dev",
                    reason="non-web source keeps development-oriented requests on Dev Agent",
                    signals=RoutingSignals(
                        is_dev_intent=is_dev_intent,
                        has_code_keywords=has_code_keywords,
                        explicit_dev_kind=explicit_dev_kind,
                    ),
                )
            return RoutingDecision(
                route="dev",
                reason="non-web sources remain on Dev Agent to preserve current execution boundaries",
                signals=RoutingSignals(
                    is_dev_intent=is_dev_intent,
                    has_code_keywords=has_code_keywords,
                    explicit_dev_kind=explicit_dev_kind,
                ),
            )

        if is_dev_intent:
            return RoutingDecision(
                route="web_to_dev",
                reason="detected development intent in a web request",
                signals=RoutingSignals(
                    is_dev_intent=is_dev_intent,
                    has_code_keywords=has_code_keywords,
                    explicit_dev_kind=explicit_dev_kind,
                ),
            )

        return RoutingDecision(
            route="web",
            reason="request looks like a standard web-facing data or conversational task",
            signals=RoutingSignals(
                is_dev_intent=is_dev_intent,
                has_code_keywords=has_code_keywords,
                explicit_dev_kind=explicit_dev_kind,
            ),
        )
