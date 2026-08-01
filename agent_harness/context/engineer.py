from __future__ import annotations

from pydantic import BaseModel, Field

from agent_harness.domain.models import AgentState, Message, MessageRole, ToolSpec
from agent_harness.memory.service import MemoryService, TokenEstimator


class ContextPack(BaseModel):
    messages: list[Message]
    estimated_tokens: int
    compacted: bool = False
    retrieved_memories: list[dict[str, object]] = Field(default_factory=list)
    dropped_messages: int = 0


class ContextEngineer:
    def __init__(
        self,
        *,
        token_budget: int,
        summary_trigger_tokens: int,
        memory: MemoryService,
    ) -> None:
        self.token_budget = token_budget
        self.summary_trigger_tokens = min(summary_trigger_tokens, token_budget)
        self.memory = memory

    async def build(
        self,
        state: AgentState,
        *,
        phase: str,
        tools: list[ToolSpec],
        system_prompt: str,
    ) -> ContextPack:
        available_for_context = max(
            1024,
            self.token_budget - state.token_budget.total_tokens,
        )
        memories = await self.memory.recall(
            task_id=state.task_id,
            query=self._memory_query(state),
            limit=6,
        )
        messages = [Message(role=MessageRole.SYSTEM, content=system_prompt)]
        if memories:
            memory_text = "\n".join(
                f"- [{item['kind']}] {item['content']}" for item in memories
            )
            messages.append(
                Message(
                    role=MessageRole.SYSTEM,
                    content=f"Relevant long-term memory:\n{memory_text}",
                )
            )
        if state.plan:
            plan_text = "\n".join(
                f"{index + 1}. [{step.status}] {step.title}: {step.description}"
                for index, step in enumerate(state.plan.steps)
            )
            messages.append(
                Message(
                    role=MessageRole.SYSTEM,
                    content=f"Current plan (revision {state.plan.revision}):\n{plan_text}",
                )
            )
        messages.append(Message(role=MessageRole.USER, content=state.goal))
        messages.extend(state.messages)

        if state.observations:
            observation_messages = [
                Message(
                    role=MessageRole.TOOL,
                    name=result.tool_name,
                    tool_call_id=result.call_id,
                    content=self._serialize_tool_result(result),
                )
                for result in state.observations[-8:]
            ]
            messages.extend(observation_messages)

        if state.reflections:
            messages.append(
                Message(
                    role=MessageRole.SYSTEM,
                    content="Recent reflections:\n"
                    + "\n".join(f"- {item}" for item in state.reflections[-4:]),
                )
            )
        messages.append(
            Message(
                role=MessageRole.SYSTEM,
                content=f"Current phase: {phase}. Available tools: "
                + (", ".join(tool.name for tool in tools) or "none"),
            )
        )

        estimated = TokenEstimator.estimate_messages(messages)
        compacted = False
        dropped = 0
        if estimated > min(available_for_context, self.summary_trigger_tokens):
            messages, dropped = self._compact(messages, available_for_context)
            compacted = dropped > 0
            estimated = TokenEstimator.estimate_messages(messages)
        return ContextPack(
            messages=messages,
            estimated_tokens=estimated,
            compacted=compacted,
            retrieved_memories=memories,
            dropped_messages=dropped,
        )

    def _compact(self, messages: list[Message], budget: int) -> tuple[list[Message], int]:
        if len(messages) <= 6:
            return messages, 0
        system_messages = [
            message for message in messages[:4] if message.role == MessageRole.SYSTEM
        ]
        head = messages[:2]
        tail = messages[-4:]
        middle = messages[len(head) : -len(tail)]
        summary = self._summarize(middle)
        compacted = [
            *head,
            Message(
                role=MessageRole.SYSTEM,
                content=f"Compacted context summary:\n{summary}",
            ),
            *system_messages,
            *tail,
        ]
        seen: set[tuple[str, str, str | None]] = set()
        unique: list[Message] = []
        for message in compacted:
            key = (message.role.value, message.content, message.tool_call_id)
            if key not in seen:
                seen.add(key)
                unique.append(message)
        while TokenEstimator.estimate_messages(unique) > budget and len(unique) > 4:
            removable_index = next(
                (
                    index
                    for index, message in enumerate(unique)
                    if message.role == MessageRole.SYSTEM
                    and "Compacted context summary" not in message.content
                ),
                None,
            )
            if removable_index is None:
                break
            unique.pop(removable_index)
        return unique, len(messages) - len(tail)

    @staticmethod
    def _summarize(messages: list[Message]) -> str:
        if not messages:
            return "No earlier messages."
        summaries: list[str] = []
        for message in messages[-24:]:
            text = " ".join(message.content.split())
            if not text:
                if message.tool_calls:
                    text = "Requested tools: " + ", ".join(call.name for call in message.tool_calls)
                else:
                    continue
            summaries.append(f"{message.role.value}: {text[:400]}")
        return "\n".join(summaries)

    @staticmethod
    def _serialize_tool_result(result: object) -> str:
        return str(getattr(result, "output", None) or getattr(result, "error", ""))[:8000]

    @staticmethod
    def _memory_query(state: AgentState) -> str:
        text = state.goal
        if state.reflections:
            text += " " + state.reflections[-1]
        return text[:2000]
