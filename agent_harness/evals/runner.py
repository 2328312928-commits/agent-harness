from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime
from pathlib import Path

from agent_harness.domain.models import (
    EvalResult,
    EvalRunSummary,
    EvalTask,
    Message,
    MessageRole,
)
from agent_harness.evals.graders import grade_task
from agent_harness.observability.metrics import CostCalculator, percentile
from agent_harness.runtime.agent import AgentRunner
from agent_harness.storage.repository import HarnessRepository


class EvalRunner:
    def __init__(
        self,
        *,
        runner: AgentRunner,
        repository: HarnessRepository,
        dataset_path: Path,
    ) -> None:
        self.runner = runner
        self.repository = repository
        self.dataset_path = dataset_path
        self.background_tasks: dict[str, asyncio.Task[EvalRunSummary]] = {}

    def load_tasks(self) -> list[EvalTask]:
        path = self.dataset_path
        if not path.is_absolute():
            path = Path.cwd() / path
        tasks: list[EvalTask] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    tasks.append(EvalTask.model_validate(json.loads(line)))
        return tasks

    async def start_background(
        self,
        *,
        provider: str | None,
        model: str | None,
        strategy: str,
        categories: list[str],
        limit: int,
        offset: int,
        concurrency: int,
    ) -> str:
        tasks = [
            task
            for task in self.load_tasks()
            if not categories or task.category in set(categories)
        ][offset : offset + limit]
        run_id = f"eval_{int(time.time()):x}"
        task = asyncio.create_task(
            self.run(
                tasks,
                provider=provider,
                model=model,
                strategy=strategy,
                concurrency=concurrency,
                run_id=run_id,
            )
        )
        self.background_tasks[run_id] = task
        task.add_done_callback(lambda _: self.background_tasks.pop(run_id, None))
        return run_id

    async def run(
        self,
        tasks: list[EvalTask],
        *,
        provider: str | None,
        model: str | None,
        strategy: str,
        concurrency: int,
        run_id: str,
    ) -> EvalRunSummary:
        selected_provider = self.runner.providers.get(provider)
        summary = EvalRunSummary(
            run_id=run_id,
            provider=selected_provider.name,
            model=model or selected_provider.default_model,
            strategy=strategy,
            total_tasks=len(tasks),
        )
        semaphore = asyncio.Semaphore(concurrency)

        async def execute(task: EvalTask) -> EvalResult:
            async with semaphore:
                return await self._execute_task(
                    task,
                    provider=provider,
                    model=model,
                    strategy=strategy,
                )

        try:
            summary.results = list(await asyncio.gather(*(execute(task) for task in tasks)))
        except Exception as exc:  # noqa: BLE001 - eval run itself is persisted even on failure.
            summary.results.append(
                EvalResult(
                    task_id="runner",
                    category="runner",
                    success=False,
                    score=0,
                    runtime_status="failed",
                    latency_ms=0,
                    tool_calls=0,
                    tool_accuracy=0,
                    prompt_tokens=0,
                    completion_tokens=0,
                    estimated_cost_usd=0,
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
        summary.completed_at = datetime.now(UTC)
        self._aggregate(summary)
        await self.repository.save_eval_run(summary)
        return summary

    async def _execute_task(
        self,
        task: EvalTask,
        *,
        provider: str | None,
        model: str | None,
        strategy: str,
    ) -> EvalResult:
        started = time.perf_counter()
        state = self.runner.create_state(
            task.goal,
            provider=provider,
            model=model,
            max_steps=task.max_steps,
            token_budget=self.runner.default_token_budget,
            metadata={
                "eval_task_id": task.id,
                "eval_category": task.category,
                "strategy": strategy,
                **task.fixture,
            },
        )
        await self.repository.create_task(state)
        if task.fixture.get("long_context"):
            state.messages.extend(
                Message(
                    role=MessageRole.USER,
                    content=(
                        f"Historical context chunk {index}: "
                        + ("background evidence and constraints " * 180)
                    ),
                )
                for index in range(18)
            )
        result_state = await self.runner.run(state, asyncio.Event())
        success, score, tool_accuracy = grade_task(task, result_state)
        cost = CostCalculator.estimate_usd(
            result_state.model,
            result_state.token_budget.prompt_tokens,
            result_state.token_budget.completion_tokens,
        )
        cost_known = CostCalculator.is_known(result_state.model)
        return EvalResult(
            task_id=task.id,
            category=task.category,
            success=success,
            score=score,
            runtime_status=result_state.status,
            latency_ms=(time.perf_counter() - started) * 1000,
            tool_calls=len(result_state.observations),
            tool_accuracy=tool_accuracy,
            prompt_tokens=result_state.token_budget.prompt_tokens,
            completion_tokens=result_state.token_budget.completion_tokens,
            estimated_cost_usd=cost,
            cost_known=cost_known,
            recovered=int(result_state.metadata.get("recovery_count", 0)) > 0,
            error=result_state.error,
            answer=result_state.final_answer,
        )

    @staticmethod
    def _aggregate(summary: EvalRunSummary) -> None:
        results = summary.results
        summary.passed_tasks = sum(1 for result in results if result.success)
        summary.total_tasks = len(results) if results else summary.total_tasks
        summary.task_success_rate = (
            summary.passed_tasks / summary.total_tasks if summary.total_tasks else 0
        )
        summary.tool_accuracy = (
            sum(result.tool_accuracy for result in results) / len(results) if results else 0
        )
        latencies = [result.latency_ms for result in results]
        summary.p50_latency_ms = percentile(latencies, 0.50)
        summary.p95_latency_ms = percentile(latencies, 0.95)
        summary.total_prompt_tokens = sum(result.prompt_tokens for result in results)
        summary.total_completion_tokens = sum(result.completion_tokens for result in results)
        summary.total_cost_usd = sum(result.estimated_cost_usd for result in results)
        recovery_results = [
            result
            for result in results
            if result.recovered or result.runtime_status.value in {"failed", "cancelled"}
        ]
        summary.recovery_success_rate = (
            sum(1 for result in recovery_results if result.recovered)
            / len(recovery_results)
            if recovery_results
            else 1.0
        )

