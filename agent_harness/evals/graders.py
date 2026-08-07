from __future__ import annotations

import json
from typing import Any

from agent_harness.domain.models import AgentState, EvalTask


def grade_task(task: EvalTask, state: AgentState) -> tuple[bool, float, float]:
    required_tools = {str(item) for item in task.expected.get("required_tools", [])}
    used_tools = {result.tool_name for result in state.observations}
    tool_accuracy = (
        len(required_tools & used_tools) / len(required_tools) if required_tools else 1.0
    )

    status_ok = state.status.value == task.expected.get("status", "completed")
    minimum_observations = int(task.expected.get("min_observations", 0))
    observation_ok = len(state.observations) >= minimum_observations
    answer_ok = _answer_matches(
        state.final_answer or "",
        task.expected.get("answer_contains", []),
    )
    recovery_expected = int(task.expected.get("min_recoveries", 0))
    recovery_ok = int(state.metadata.get("recovery_count", 0)) >= recovery_expected
    tools_ok = required_tools.issubset(used_tools)

    checks = [status_ok, observation_ok, answer_ok, recovery_ok, tools_ok]
    score = sum(1 for check in checks if check) / len(checks)
    success = all(checks)
    return success, score, tool_accuracy


def _answer_matches(answer: str, expected_parts: Any) -> bool:
    if not expected_parts:
        return True
    if isinstance(expected_parts, str):
        expected_parts = [expected_parts]
    normalized = answer.casefold()
    return all(str(part).casefold() in normalized for part in expected_parts)


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

