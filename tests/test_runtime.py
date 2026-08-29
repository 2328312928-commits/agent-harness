from __future__ import annotations

from agent_harness.api.container import AppContainer
from agent_harness.domain.models import RuntimeStatus, ToolCall
from agent_harness.runtime.agent import provider_safe_tool_name


async def wait_for_terminal(container: AppContainer, task_id: str) -> dict:
    while True:
        state = await container.repository.get_task(task_id)
        assert state is not None
        if state.status.value in {"completed", "failed", "cancelled"}:
            return state.model_dump(mode="json")
        await __import__("asyncio").sleep(0.02)


async def test_full_agent_loop_with_two_tools(container: AppContainer) -> None:
    state = await container.runtime.start(
        "请读取 examples/demo.txt，然后计算 12 + 7",
        provider="fake",
    )
    result = await wait_for_terminal(container, state.task_id)
    assert result["status"] == "completed"
    assert [item["tool_name"] for item in result["observations"]] == [
        "filesystem.read_file",
        "sandbox.run_python",
    ]
    assert "19" in result["final_answer"]
    assert result["checkpoint_version"] >= 8
    events = await container.repository.list_events(state.task_id)
    event_types = {event["event_type"] for event in events}
    assert {"phase.started", "tool.request", "tool.response", "checkpoint.saved"} <= event_types


async def test_permission_failure_recovers(container: AppContainer) -> None:
    state = await container.runtime.start(
        "请读取 examples/demo.txt",
        provider="fake",
        metadata={"tool_permissions": []},
    )
    result = await wait_for_terminal(container, state.task_id)
    assert result["status"] == "completed"
    assert result["metadata"]["recovery_count"] == 1
    assert result["observations"][0]["error_type"] == "tool_permission_denied"


async def test_recovery_limit_returns_final_reflection(container: AppContainer) -> None:
    container.runtime.runner.max_recoveries = 0
    state = await container.runtime.start(
        "请读取 examples/demo.txt",
        provider="fake",
        metadata={"tool_permissions": []},
    )
    result = await wait_for_terminal(container, state.task_id)
    assert result["status"] == "completed"
    assert result["metadata"]["recovery_exhausted"] is True
    assert result["final_answer"]


async def test_resume_from_persisted_interrupted_state(container: AppContainer) -> None:
    state = container.runtime.runner.create_state(
        "请列出目录 . 下的文件列表",
        provider="fake",
    )
    state.status = RuntimeStatus.INTERRUPTED
    await container.repository.create_task(state)

    resumed = await container.runtime.resume(state.task_id)
    result = await wait_for_terminal(container, resumed.task_id)

    assert result["status"] == "completed"
    events = await container.repository.list_events(state.task_id)
    assert any(event["event_type"] == "recovery.started" for event in events)


def test_provider_tool_names_are_function_call_safe() -> None:
    assert provider_safe_tool_name("filesystem.read_file") == "filesystem_read_file"
    assert provider_safe_tool_name("demo.github-search") == "demo_github-search"


async def test_provider_tool_calls_map_back_to_registry_names(
    container: AppContainer,
) -> None:
    calls = container.runtime.runner._map_provider_tool_calls(
        [ToolCall(name="filesystem_read_file", arguments={"path": "examples/demo.txt"})]
    )
    assert calls[0].name == "filesystem.read_file"
