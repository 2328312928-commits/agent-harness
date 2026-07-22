from __future__ import annotations

import json
import re
import time

from agent_harness.domain.models import (
    Message,
    MessageRole,
    ProviderResponse,
    ToolCall,
    Usage,
)
from agent_harness.providers.base import LLMProvider, ProviderRequest


class FakeProvider(LLMProvider):
    """Deterministic provider for offline demos, tests, and harness regression runs."""

    name = "fake"
    default_model = "fake-deterministic-v1"

    async def complete(self, request: ProviderRequest) -> ProviderResponse:
        started = time.perf_counter()
        model = request.model or self.default_model
        latest_user = next(
            (
                message.content
                for message in reversed(request.messages)
                if message.role == MessageRole.USER
            ),
            "",
        )
        tool_messages = [
            message for message in request.messages if message.role == MessageRole.TOOL
        ]

        if request.phase == "plan":
            response = self._plan(latest_user, model)
        elif request.phase == "reflect":
            response = ProviderResponse(
                content="The observation was checked. Continue with the next unresolved step.",
                finish_reason="stop",
                model=model,
            )
        else:
            response = self._act(latest_user, tool_messages, model)

        response.latency_ms = (time.perf_counter() - started) * 1000 + 5
        response.usage = Usage(
            prompt_tokens=self._estimate_tokens(request.messages),
            completion_tokens=max(1, len(response.content) // 4) + len(response.tool_calls) * 20,
        )
        response.usage.total_tokens = (
            response.usage.prompt_tokens + response.usage.completion_tokens
        )
        return response

    def _plan(self, goal: str, model: str) -> ProviderResponse:
        tools = self._expected_tools(goal)
        steps = [
            {
                "title": "Inspect the task and collect required facts",
                "description": "Use registered tools only when they provide evidence.",
                "expected_tools": tools[:1],
            }
        ]
        if tools:
            steps.append(
                {
                    "title": "Execute the selected capability",
                    "description": f"Call and validate: {', '.join(tools)}.",
                    "expected_tools": tools,
                }
            )
        steps.append(
            {
                "title": "Validate and summarize the result",
                "description": "Check tool output and return a concise final answer.",
                "expected_tools": [],
            }
        )
        payload = {
            "objective": goal,
            "assumptions": ["The local demo uses deterministic model reasoning."],
            "steps": steps,
        }
        return ProviderResponse(
            content=json.dumps(payload, ensure_ascii=False),
            finish_reason="stop",
            model=model,
        )

    def _act(
        self,
        goal: str,
        tool_messages: list[Message],
        model: str,
    ) -> ProviderResponse:
        called_tools = {message.name for message in tool_messages if message.name}

        if "filesystem.read_file" not in called_tools and self._mentions_file_read(goal):
            path = self._extract_path(goal) or "examples/demo.txt"
            return self._tool_call("filesystem.read_file", {"path": path}, model)

        if "filesystem.list" not in called_tools and any(
            token in goal.lower() for token in ("list files", "目录", "文件列表")
        ):
            return self._tool_call("filesystem.list", {"path": "."}, model)

        if "sandbox.run_python" not in called_tools and any(
            token in goal.lower() for token in ("calculate", "compute", "计算", "python")
        ):
            expression = self._extract_expression(goal)
            code = f"print({expression})" if expression else "print('sandbox-ok')"
            return self._tool_call("sandbox.run_python", {"code": code}, model)

        if "database.query" not in called_tools and any(
            token in goal.lower() for token in ("sql", "database", "数据库")
        ):
            return self._tool_call(
                "database.query",
                {"query": "SELECT 1 AS healthy", "parameters": {}},
                model,
            )

        if "browser.fetch" not in called_tools and any(
            token in goal.lower() for token in ("browse", "browser", "http", "网页", "抓取")
        ):
            url_match = re.search(r"https?://[^\s]+", goal)
            return self._tool_call(
                "browser.fetch",
                {"url": url_match.group(0) if url_match else "https://example.com"},
                model,
            )

        if "github.search_repositories" not in called_tools and "github" in goal.lower():
            query_match = re.search(r"(?:github|仓库|repository)\s*[:：]?\s*([\w.-]+)", goal, re.I)
            return self._tool_call(
                "github.search_repositories",
                {"query": query_match.group(1) if query_match else "agent runtime"},
                model,
            )

        if "memory.remember" not in called_tools and any(
            token in goal.lower() for token in ("remember", "记住", "长期记忆")
        ):
            return self._tool_call(
                "memory.remember",
                {
                    "content": goal,
                    "kind": "semantic",
                    "importance": 0.8,
                },
                model,
            )

        observation_count = len(tool_messages)
        if observation_count:
            latest_observation = tool_messages[-1].content[:800]
            answer = (
                "任务已完成。工具输出已通过观察与检查阶段，演示运行时完成了 "
                f"{observation_count} 次工具调用。Observed result: {latest_observation}"
            )
        else:
            answer = (
                "任务已分析完成。此请求不需要外部工具；离线 Provider 返回了确定性结果。"
            )
        return ProviderResponse(content=answer, finish_reason="stop", model=model)

    @staticmethod
    def _tool_call(
        name: str,
        arguments: dict[str, object],
        model: str,
    ) -> ProviderResponse:
        return ProviderResponse(
            content="",
            tool_calls=[ToolCall(name=name, arguments=arguments)],
            finish_reason="tool_calls",
            model=model,
        )

    @staticmethod
    def _mentions_file_read(goal: str) -> bool:
        lowered = goal.lower()
        return any(
            token in lowered
            for token in ("read file", "read ", "读取", "查看文件", "打开文件")
        ) and any(token in lowered for token in (".txt", ".md", ".json", ".py", "文件"))

    @staticmethod
    def _extract_path(goal: str) -> str | None:
        match = re.search(r"([A-Za-z0-9_./\\-]+\.(?:txt|md|json|py|yaml|yml|toml))", goal)
        return match.group(1).replace("\\", "/") if match else None

    @staticmethod
    def _extract_expression(goal: str) -> str | None:
        match = re.search(r"([0-9][0-9\s+\-*/().%]*)", goal)
        if not match:
            return None
        expression = match.group(1).strip()
        if not re.fullmatch(r"[0-9+\-*/().%\s]+", expression):
            return None
        return expression

    @staticmethod
    def _expected_tools(goal: str) -> list[str]:
        lowered = goal.lower()
        tools: list[str] = []
        if any(token in lowered for token in ("read file", "读取", "文件")):
            tools.append("filesystem.read_file")
        if any(token in lowered for token in ("calculate", "compute", "计算", "python")):
            tools.append("sandbox.run_python")
        if any(token in lowered for token in ("sql", "database", "数据库")):
            tools.append("database.query")
        if any(token in lowered for token in ("browse", "browser", "网页", "抓取")):
            tools.append("browser.fetch")
        if "github" in lowered:
            tools.append("github.search_repositories")
        if any(token in lowered for token in ("remember", "记住")):
            tools.append("memory.remember")
        return tools

    @staticmethod
    def _estimate_tokens(messages: list[Message]) -> int:
        return max(1, sum(len(message.content) for message in messages) // 4)
