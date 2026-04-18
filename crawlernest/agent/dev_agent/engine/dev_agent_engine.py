from __future__ import annotations

from pathlib import Path

from crawlernest.agent.autonomous.evaluator import AutonomousEvaluator
from crawlernest.agent.autonomous.loop_controller import LoopController
from crawlernest.agent.autonomous.step_executor import StepExecutor
from crawlernest.agent.autonomous.stop_policy import StopPolicy
from crawlernest.agent.autonomous.task_graph import TaskGraphBuilder
from crawlernest.agent.dev_agent.policy.dev_agent_policy import DevAgentPolicy
from crawlernest.agent.dev_agent.repo.change_summary import ChangeSummaryBuilder
from crawlernest.agent.dev_agent.repo.file_resolver import FileResolver
from crawlernest.agent.dev_agent.repo.patch_builder import PatchBuilder
from crawlernest.agent.dev_agent.repo.repo_indexer import RepoIndexer
from crawlernest.agent.meta.meta_controller import MetaController
from crawlernest.agent.self_rewrite.patch_executor import PatchExecutor
from crawlernest.agent.self_rewrite.patch_generator import PatchGenerator
from crawlernest.agent.self_rewrite.patch_store import PatchStore
from crawlernest.agent.self_rewrite.patch_validator import PatchValidator
from crawlernest.agent.self_improvement.experience_store import ExperienceStore
from crawlernest.agent.self_improvement.improvement_engine import ImprovementEngine
from crawlernest.agent.self_improvement.performance_tracker import PerformanceTracker
from crawlernest.agent.self_improvement.strategy_store import StrategyStore
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
        repo_indexer: RepoIndexer | None = None,
        file_resolver: FileResolver | None = None,
        patch_builder: PatchBuilder | None = None,
        change_summary: ChangeSummaryBuilder | None = None,
        loop_controller: LoopController | None = None,
        experience_store: ExperienceStore | None = None,
        strategy_store: StrategyStore | None = None,
        performance_tracker: PerformanceTracker | None = None,
        improvement_engine: ImprovementEngine | None = None,
        meta_controller: MetaController | None = None,
        patch_generator: PatchGenerator | None = None,
        patch_validator: PatchValidator | None = None,
        patch_executor: PatchExecutor | None = None,
        patch_store: PatchStore | None = None,
    ) -> None:
        self._planner = planner or SharedPlanner()
        self._tools = tool_router or DevToolRouter()
        self._policy = policy or DevAgentPolicy()
        self._repo_indexer = repo_indexer or RepoIndexer()
        self._file_resolver = file_resolver or FileResolver()
        self._patch_builder = patch_builder or PatchBuilder()
        self._change_summary = change_summary or ChangeSummaryBuilder()
        self._experience_store = experience_store or ExperienceStore()
        self._strategy_store = strategy_store or StrategyStore()
        self._performance_tracker = performance_tracker or PerformanceTracker()
        self._improvement_engine = improvement_engine or ImprovementEngine()
        self._meta_controller = meta_controller or MetaController(strategy_store=self._strategy_store)
        self._patch_generator = patch_generator or PatchGenerator(patch_builder=self._patch_builder)
        self._patch_validator = patch_validator or PatchValidator()
        self._patch_executor = patch_executor or PatchExecutor()
        self._patch_store = patch_store or PatchStore()
        self._loop_controller = loop_controller or LoopController(
            task_graph=TaskGraphBuilder(),
            step_executor=StepExecutor(
                dev_tools=self._tools.dev_tools,
                file_resolver=self._file_resolver,
                patch_builder=self._patch_builder,
                patch_generator=self._patch_generator,
                patch_validator=self._patch_validator,
                patch_executor=self._patch_executor,
                root_dir=str(Path(__file__).resolve().parents[4]),
            ),
            evaluator=AutonomousEvaluator(),
            stop_policy=StopPolicy(success_threshold=self._policy.autonomous_success_threshold),
            max_iterations=self._policy.autonomous_max_iterations,
        )

    def execute(self, request: TaskRequest) -> TaskResponse:
        plan = self._planner.build_plan(request)

        if request.kind == "dev_refinement":
            repo_index = self._repo_indexer.build_index()
            pre_resolution = self._file_resolver.resolve(
                user_input=request.user_input,
                context=request.context,
                repo_index=repo_index,
            )
            target_hint = pre_resolution.get("symbol") or pre_resolution.get("file_path") or request.context.get("target")
            applied_strategy_entries = self._strategy_store.query(
                engine="dev",
                task_kind=request.kind,
                target=str(target_hint) if isinstance(target_hint, str) and target_hint.strip() else None,
                min_confidence=self._policy.self_improvement_strategy_confidence,
                limit=2,
                strategy_type="behavior",
            )
            strategy_hints = [
                hint
                for entry in applied_strategy_entries
                for hint in entry.get("strategy", [])
                if isinstance(hint, str) and hint.strip()
            ]
            anti_pattern_entries = self._strategy_store.query(
                engine="dev",
                task_kind=request.kind,
                target=str(target_hint) if isinstance(target_hint, str) and target_hint.strip() else None,
                min_confidence=0.6,
                limit=2,
                strategy_type="anti_pattern",
            )
            anti_pattern_hints = [
                f"Avoid: {hint}"
                for entry in anti_pattern_entries
                for hint in entry.get("strategy", [])
                if isinstance(hint, str) and hint.strip()
            ]
            effective_context = dict(request.context)
            if strategy_hints:
                effective_context["strategy_hints"] = strategy_hints
            if anti_pattern_hints:
                effective_context["strategy_hints"] = list(
                    dict.fromkeys(list(effective_context.get("strategy_hints", [])) + anti_pattern_hints)
                )
            meta_resolution = self._meta_controller.resolve_for_request(
                engine="dev",
                task_kind=request.kind,
                request_signature=f"{request.task_id}::{request.user_input}",
                target=str(target_hint) if isinstance(target_hint, str) and target_hint.strip() else None,
            )
            meta_tool_strategies = [
                hint
                for hint in meta_resolution.get("tool_strategies", [])
                if isinstance(hint, str) and hint.strip()
            ]
            if meta_tool_strategies:
                effective_context["strategy_hints"] = list(
                    dict.fromkeys(list(effective_context.get("strategy_hints", [])) + meta_tool_strategies)
                )
            loop_trace = self._loop_controller.run(
                goal=request.user_input,
                context=effective_context,
                repo_index=repo_index,
                validation_builder=self._build_validation,
            )
            resolution_result = self._extract_resolution_from_loop(loop_trace) or self._file_resolver.resolve(
                user_input=request.user_input,
                context=effective_context,
                repo_index=repo_index,
            )
            file_patch = self._extract_file_patch_from_loop(loop_trace) or self._patch_builder.build(
                task=request.user_input,
                resolution_result=resolution_result,
                repo_index=repo_index,
            )
            patch_candidate = self._extract_patch_candidate_from_loop(loop_trace) or self._patch_generator.generate(
                task=request.user_input,
                resolution_result=resolution_result,
                repo_index=repo_index,
            )
            validation = self._extract_validation_from_loop(loop_trace) or self._build_validation(
                resolution_result=resolution_result,
                repo_index=repo_index,
            )
            patch_validation = self._extract_patch_validation_from_loop(loop_trace) or self._patch_validator.validate(
                patch_candidate=patch_candidate,
                repo_index=repo_index,
                root_dir=str(Path(__file__).resolve().parents[4]),
            )
            patch_execution = self._extract_patch_execution_from_loop(loop_trace) or self._patch_executor.execute_in_sandbox(
                patch_candidate=patch_candidate,
                patch_validation=patch_validation,
                resolution_result=resolution_result,
            )
            patch_record = self._patch_store.append(
                task=request.user_input,
                patch_candidate=patch_candidate,
                patch_validation=patch_validation,
                patch_execution=patch_execution,
            )
            normalized_target = str(target_hint) if isinstance(target_hint, str) and target_hint.strip() else None
            if patch_record.get("status") == "approved":
                patch_hint = str(patch_candidate.get("patch") or "").strip()
                if patch_hint:
                    self._strategy_store.upsert(
                        engine="dev",
                        task_kind=request.kind,
                        strategy=[
                            patch_hint,
                            "Prefer sandbox-approved semantic patches before broadening change scope.",
                        ],
                        confidence=0.82,
                        reason="sandbox approved patch outcome",
                        target=normalized_target,
                        strategy_type="tool_strategy",
                        source="patch_approval",
                        rollout_percent=100,
                        status="active",
                    )
            elif patch_record.get("status") in {"discarded", "rejected"}:
                patch_hint = str(patch_candidate.get("patch") or patch_candidate.get("reason") or "").strip()
                if patch_hint:
                    self._strategy_store.upsert(
                        engine="dev",
                        task_kind=request.kind,
                        strategy=[
                            patch_hint,
                            "Avoid broad or unsafe semantic patch scopes when sandbox validation is weak.",
                        ],
                        confidence=0.74,
                        reason="sandbox rejected or discarded patch outcome",
                        target=normalized_target,
                        strategy_type="anti_pattern",
                        source="patch_failure",
                        rollout_percent=100,
                        status="active",
                    )
            refinement = self._tools.dev_tools.suggest_refinement_loop(
                request.user_input,
                effective_context,
            )
            performance = self._performance_tracker.analyze(
                experiences=self._experience_store.recent(
                    engine="dev",
                    task_kind=request.kind,
                    target=str(target_hint) if isinstance(target_hint, str) and target_hint.strip() else None,
                    limit=self._policy.self_improvement_sample_limit,
                ),
                task_kind=request.kind,
            )
            experience = self._experience_store.append(
                engine="dev",
                task_kind=request.kind,
                task=request.user_input,
                status=loop_trace.get("final_status", "partial"),
                final_score=float(loop_trace.get("best_score", 0.0)),
                tools_used=["dev_refinement", "code_validation", "repo_indexer"],
                steps=[
                    {
                        "step": step.get("step"),
                        "score": step.get("score"),
                        "status": step.get("status"),
                    }
                    for step in loop_trace.get("steps", [])
                    if isinstance(step, dict)
                ],
                metadata={
                    "target": resolution_result.get("symbol") or resolution_result.get("file_path"),
                    "validation_status": validation.get("status"),
                    "stop_reason": loop_trace.get("stop_reason"),
                    "rewrite_status": patch_record.get("status"),
                },
            )
            recent_dev_experiences = self._experience_store.recent(
                engine="dev",
                task_kind=request.kind,
                target=str(target_hint) if isinstance(target_hint, str) and target_hint.strip() else None,
                limit=self._policy.self_improvement_sample_limit,
            )
            performance = self._performance_tracker.analyze(
                experiences=recent_dev_experiences,
                task_kind=request.kind,
            )
            new_strategy = self._improvement_engine.generate(
                engine="dev",
                task_kind=request.kind,
                performance=performance,
                experiences=recent_dev_experiences,
                target=str(target_hint) if isinstance(target_hint, str) and target_hint.strip() else None,
            )
            if new_strategy is not None:
                self._strategy_store.upsert(
                    engine="dev",
                    task_kind=request.kind,
                    strategy=list(new_strategy.get("strategy", [])),
                    confidence=float(new_strategy.get("confidence", 0.6)),
                    reason=str(new_strategy.get("reason", "generated from recent dev performance")),
                    target=str(target_hint) if isinstance(target_hint, str) and target_hint.strip() else None,
                    strategy_type="behavior",
                )
            meta_update = self._meta_controller.update_from_performance(
                engine="dev",
                task_kind=request.kind,
                performance=performance,
                experiences=recent_dev_experiences,
                target=str(target_hint) if isinstance(target_hint, str) and target_hint.strip() else None,
            )
            meta_outcome = self._meta_controller.record_outcome(
                applied_entries=list(meta_resolution.get("applied_entries", [])),
                final_score=float(loop_trace.get("best_score", 0.0)),
            )
            data = {
                "task": request.user_input,
                "plan": [step.get("step", "") for step in plan],
                "loop": refinement.get("loop", []),
                "context": refinement.get("context", {}),
                "filePatch": file_patch,
                "changeSummary": self._change_summary.build(
                    task=request.user_input,
                    resolution_result=resolution_result,
                    file_patch=file_patch,
                    validation=validation,
                ),
                "validation": validation,
                "patchCandidate": patch_candidate,
                "patchValidation": patch_validation,
                "patchExecution": patch_execution,
                "patchRecord": patch_record,
                "autonomousDebug": loop_trace,
                "repoDebug": {
                    "resolved_file": resolution_result.get("file_path"),
                    "resolved_symbol": resolution_result.get("symbol"),
                    "confidence": resolution_result.get("confidence"),
                    "reason": resolution_result.get("reason"),
                },
                "selfImprovementDebug": {
                    "performance": performance,
                    "new_strategy_generated": new_strategy is not None,
                    "strategy_applied": bool(strategy_hints),
                    "strategy_source": (
                        "stored"
                        if strategy_hints
                        else ("newly_generated" if new_strategy is not None else "none")
                    ),
                    "reason": (
                        str(new_strategy.get("reason"))
                        if isinstance(new_strategy, dict)
                        else ("applied stored strategy hints" if strategy_hints else "recent performance stayed within threshold")
                    ),
                    "applied_strategies": strategy_hints[:4],
                    "anti_patterns": anti_pattern_hints[:4],
                    "last_experience": {
                        "status": experience.get("status"),
                        "final_score": experience.get("final_score"),
                    },
                },
                "rewriteDebug": {
                    "patch_generated": bool(patch_candidate),
                    "patch_valid": bool(patch_validation.get("valid")) if isinstance(patch_validation, dict) else False,
                    "applied_in_sandbox": bool(patch_execution.get("applied_in_sandbox")) if isinstance(patch_execution, dict) else False,
                    "improved": bool(patch_execution.get("improvement")) if isinstance(patch_execution, dict) else False,
                    "score_delta": patch_execution.get("score_delta") if isinstance(patch_execution, dict) else 0.0,
                    "status": patch_record.get("status"),
                },
                "metaDebug": {
                    **meta_resolution.get("debug", {}),
                    "generated": [
                        {
                            "id": entry.get("id"),
                            "strategy_type": entry.get("strategy_type"),
                            "confidence": entry.get("confidence"),
                            "source": entry.get("source"),
                            "version": entry.get("version"),
                        }
                        for entry in meta_update.get("generated_entries", [])
                    ],
                    "rolled_back": meta_outcome.get("rolled_back", []),
                },
            }
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

    def _build_validation(
        self,
        *,
        resolution_result: dict,
        repo_index: dict,
    ) -> dict:
        file_path = resolution_result.get("file_path")
        symbol = resolution_result.get("symbol")
        files = repo_index.get("files", []) if isinstance(repo_index, dict) else []

        checks: list[dict[str, object]] = []
        matched_file = None
        if file_path:
            for item in files:
                if item.get("path") == file_path:
                    matched_file = item
                    break

        checks.append(
            {
                "name": "file_exists_in_index",
                "passed": matched_file is not None,
            }
        )

        if symbol:
            symbol_found = any(
                entry.get("name") == symbol for entry in (matched_file or {}).get("symbols", [])
            )
            checks.append(
                {
                    "name": "symbol_exists_in_index",
                    "passed": symbol_found,
                }
            )
        else:
            checks.append(
                {
                    "name": "symbol_exists_in_index",
                    "passed": matched_file is not None,
                }
            )

        supported_language = bool((matched_file or {}).get("language"))
        checks.append(
            {
                "name": "language_supported",
                "passed": supported_language,
            }
        )

        status = "pass" if all(check["passed"] for check in checks) else "review"
        return {
            "status": status,
            "checks": checks,
        }

    def _extract_resolution_from_loop(self, loop_trace: dict) -> dict | None:
        for step in loop_trace.get("steps", []):
            if not isinstance(step, dict):
                continue
            result = step.get("result")
            if isinstance(result, dict) and isinstance(result.get("resolution"), dict):
                return result.get("resolution")
        return None

    def _extract_file_patch_from_loop(self, loop_trace: dict) -> dict | None:
        for step in loop_trace.get("steps", []):
            if not isinstance(step, dict):
                continue
            result = step.get("result")
            if isinstance(result, dict) and isinstance(result.get("filePatch"), dict):
                return result.get("filePatch")
        return None

    def _extract_validation_from_loop(self, loop_trace: dict) -> dict | None:
        for step in loop_trace.get("steps", []):
            if not isinstance(step, dict):
                continue
            result = step.get("result")
            if isinstance(result, dict) and isinstance(result.get("validation"), dict):
                return result.get("validation")
        return None

    def _extract_patch_candidate_from_loop(self, loop_trace: dict) -> dict | None:
        for step in loop_trace.get("steps", []):
            if not isinstance(step, dict):
                continue
            result = step.get("result")
            if isinstance(result, dict) and isinstance(result.get("patchCandidate"), dict):
                return result.get("patchCandidate")
        return None

    def _extract_patch_validation_from_loop(self, loop_trace: dict) -> dict | None:
        for step in loop_trace.get("steps", []):
            if not isinstance(step, dict):
                continue
            result = step.get("result")
            if isinstance(result, dict) and isinstance(result.get("patchValidation"), dict):
                return result.get("patchValidation")
        return None

    def _extract_patch_execution_from_loop(self, loop_trace: dict) -> dict | None:
        for step in loop_trace.get("steps", []):
            if not isinstance(step, dict):
                continue
            result = step.get("result")
            if isinstance(result, dict) and isinstance(result.get("patchExecution"), dict):
                return result.get("patchExecution")
        return None
