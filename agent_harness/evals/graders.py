from __future__ import annotations

import json
from typing import Any

from agent_harness.domain.models import AgentState, EvalTask


def grade_task(task: EvalTask, state: AgentState) -> tuple[bool, float, float]:
    required_tools = {str(item) for item in task.expected.get("required_tools", [])}
    successful_tools = {
        result.tool_name for result in state.observations if result.ok
    }
    tool_accuracy = (
        len(required_tools & successful_tools) / len(required_tools)
        if required_tools
        else 1.0
    )

    expected_status = task.expected.get("status", "completed")
    expected_statuses = (
        {str(item) for item in expected_status}
        if isinstance(expected_status, list)
        else {str(expected_status)}
    )
    status_ok = state.status.value in expected_statuses
    minimum_observations = int(task.expected.get("min_observations", 0))
    observation_ok = len(state.observations) >= minimum_observations
    minimum_successful_observations = int(
        task.expected.get("min_successful_observations", 0)
    )
    successful_observation_ok = (
        sum(1 for result in state.observations if result.ok)
        >= minimum_successful_observations
    )
    answer_ok = _answer_matches(
        state.final_answer or "",
        task.expected.get("answer_contains", []),
        task.expected.get("answer_contains_any", []),
    )
    recovery_expected = int(task.expected.get("min_recoveries", 0))
    recovery_ok = int(state.metadata.get("recovery_count", 0)) >= recovery_expected
    tools_ok = required_tools.issubset(successful_tools)

    checks = [
        status_ok,
        observation_ok,
        successful_observation_ok,
        answer_ok,
        recovery_ok,
        tools_ok,
    ]
    score = sum(1 for check in checks if check) / len(checks)
    success = all(checks)
    return success, score, tool_accuracy


def _answer_matches(answer: str, expected_parts: Any, expected_any: Any) -> bool:
    normalized = answer.casefold()
    if expected_parts:
        if isinstance(expected_parts, str):
            expected_parts = [expected_parts]
        if not all(str(part).casefold() in normalized for part in expected_parts):
            return False
    if expected_any:
        if isinstance(expected_any, str):
            expected_any = [expected_any]
        if not any(str(part).casefold() in normalized for part in expected_any):
            return False
    return True


def compact_state(state: AgentState) -> dict[str, Any]:
    return {
        "task_id": state.task_id,
        "status": state.status.value,
        "final_answer": state.final_answer,
        "step_count": state.step_count,
        "checkpoint_version": state.checkpoint_version,
        "recovery_count": state.metadata.get("recovery_count", 0),
        "observations": [
            {
                "tool": result.tool_name,
                "ok": result.ok,
                "latency_ms": result.latency_ms,
                "attempts": result.attempts,
                "error": result.error,
            }
            for result in state.observations
        ],
    }


def result_as_json(result: Any) -> str:
    return json.dumps(result.model_dump(mode="json"), ensure_ascii=False)

