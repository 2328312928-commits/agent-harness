from __future__ import annotations

import pytest

from agent_harness.domain.models import AgentState, EvalTask, TokenBudgetState
from agent_harness.evals.graders import grade_task


def test_grader_requires_tool_and_answer() -> None:
    task = EvalTask(
        id="task",
        category="mixed",
        difficulty="easy",
        goal="test",
        expected={
            "required_tools": ["filesystem.read_file"],
            "answer_contains": ["19"],
            "min_observations": 1,
        },
    )
    state = AgentState(
        goal="test",
        token_budget=TokenBudgetState(limit=1000),
        final_answer="答案是 19",
    )
    success, score, tool_accuracy = grade_task(task, state)
    assert not success
    assert score == pytest.approx(0.5)
    assert tool_accuracy == 0
