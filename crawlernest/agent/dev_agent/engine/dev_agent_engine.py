from __future__ import annotations

from crawlernest.agent.dev_agent.policy.dev_agent_policy import DevAgentPolicy
from crawlernest.agent.dev_agent.tool_router.dev_tool_router import DevToolRouter
from crawlernest.agent.shared.models.task_request import TaskRequest
from crawlernest.agent.shared.models.task_response import TaskResponse
from crawlernest.agent.shared.planner.shared_planner import SharedPlanner


class DevAgentEngine:
    def __init__(
        self,
        planner: SharedPlanner | None = None,
        tool_router: DevToolRouter | None = None,
        policy: DevAgentPolicy | None = None,
    ) -> None:
        self._planner = planner or SharedPlanner()
        self._tools = tool_router or DevToolRouter()
        self._policy = policy or DevAgentPolicy()

    def execute(self, request: TaskRequest) -> TaskResponse:
        plan = self._planner.build_plan(request)

        if request.kind == "dev_refinement":
            data = self._tools.dev_tools.suggest_refinement_loop(
                request.user_input,
                request.context,
            )
            return self._respond(
                request=request,
                message="Development refinement plan prepared.",
                data=data,
                traces=plan,
            )

        if request.kind == "data_query":
            data = self._tools.ranking_tools.list_rankings(
                request.context,
                user_input=request.user_input,
            )
            return self._respond(
                request=request,
                message="Engineering rankings query completed.",
                data=data,
                traces=plan,
            )

        if request.kind == "ranking_explain":
            data = self._tools.ranking_tools.explain_rankings(
                request.context,
                user_input=request.user_input,
            )
            return self._respond(
                request=request,
                message="Engineering ranking explanation prepared.",
                data=data,
                traces=plan,
            )

        if request.kind == "university_lookup":
            data = self._tools.university_tools.get_detail_preview(
                request.context,
                user_input=request.user_input,
            )
            return self._respond(
                request=request,
                message="University detail preview loaded for engineering inspection.",
                data=data,
                traces=plan,
            )

        return self._respond(
            request=request,
            status="rejected",
            message=f"Unsupported dev task kind: {request.kind}",
            traces=plan,
        )

    def _respond(
        self,
        *,
        request: TaskRequest,
        message: str,
        data: dict | None = None,
        traces: list[dict[str, str]] | None = None,
        status: str = "success",
    ) -> TaskResponse:
        return TaskResponse(
            task_id=request.task_id,
            status=status,  # type: ignore[arg-type]
            message=message,
            data=data or {},
            traces=traces or [],
        )
