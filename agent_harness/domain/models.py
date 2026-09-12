from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(UTC)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:16]}"


class RuntimeStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_FOR_TOOL = "waiting_for_tool"
    INTERRUPTED = "interrupted"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RunPhase(StrEnum):
    PLAN = "plan"
    ACT = "act"
    OBSERVE = "observe"
    REFLECT = "reflect"
    FINALIZE = "finalize"
    RECOVERY = "recovery"


class MessageRole(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ToolPermission(StrEnum):
    READ = "read"
    WRITE = "write"
    NETWORK = "network"
    EXECUTE = "execute"
    DATABASE = "database"
    GITHUB = "github"
    BROWSER = "browser"


class TraceEventType(StrEnum):
    TASK_CREATED = "task.created"
    TASK_STARTED = "task.started"
    PHASE_STARTED = "phase.started"
    PHASE_COMPLETED = "phase.completed"
    MODEL_REQUEST = "model.request"
    MODEL_RESPONSE = "model.response"
    TOOL_REQUEST = "tool.request"
    TOOL_RETRY = "tool.retry"
    TOOL_RESPONSE = "tool.response"
    CHECKPOINT_SAVED = "checkpoint.saved"
    RECOVERY_STARTED = "recovery.started"
    TASK_COMPLETED = "task.completed"
    TASK_PARTIAL = "task.partial"
    TASK_FAILED = "task.failed"
    TASK_CANCELLED = "task.cancelled"
    LOG = "log"


class Message(BaseModel):
    model_config = ConfigDict(extra="ignore")

    role: MessageRole
    content: str = ""
    reasoning_content: str | None = None
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class ToolCall(BaseModel):
    id: str = Field(default_factory=lambda: new_id("call"))
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolSpec(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]
    permissions: list[ToolPermission] = Field(default_factory=list)
    timeout_seconds: float | None = None
    max_retries: int | None = None
    idempotent: bool = False
    source: Literal["builtin", "mcp", "plugin"] = "builtin"

    def as_openai_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def add(self, other: Usage) -> None:
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        self.total_tokens += other.total_tokens


class ProviderResponse(BaseModel):
    content: str = ""
    reasoning_content: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    usage: Usage = Field(default_factory=Usage)
    finish_reason: str | None = None
    model: str = ""
    latency_ms: float = 0
    provider_request_id: str | None = None
    raw: dict[str, Any] | None = None


class ToolResult(BaseModel):
    call_id: str
    tool_name: str
    ok: bool
    output: Any = None
    error: str | None = None
    error_type: str | None = None
    latency_ms: float = 0
    attempts: int = 1
    retryable: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class PlanStep(BaseModel):
    id: str = Field(default_factory=lambda: new_id("step"))
    title: str
    description: str = ""
    expected_tools: list[str] = Field(default_factory=list)
    status: Literal["pending", "in_progress", "completed", "failed", "skipped"] = "pending"
    result_summary: str | None = None


class AgentPlan(BaseModel):
    objective: str
    assumptions: list[str] = Field(default_factory=list)
    steps: list[PlanStep] = Field(default_factory=list)
    revision: int = 1


class TokenBudgetState(BaseModel):
    limit: int
    prompt_tokens: int = 0
    completion_tokens: int = 0
    compaction_count: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.total_tokens)


class AgentState(BaseModel):
    model_config = ConfigDict(extra="ignore")

    task_id: str = Field(default_factory=lambda: new_id("task"))
    goal: str
    status: RuntimeStatus = RuntimeStatus.QUEUED
    phase: RunPhase = RunPhase.PLAN
    provider: str = "fake"
    model: str = ""
    messages: list[Message] = Field(default_factory=list)
    plan: AgentPlan | None = None
    current_step_index: int = 0
    observations: list[ToolResult] = Field(default_factory=list)
    reflections: list[str] = Field(default_factory=list)
    final_answer: str | None = None
    error: str | None = None
    token_budget: TokenBudgetState
    step_count: int = 0
    max_steps: int = 20
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    checkpoint_version: int = 0


class TraceEvent(BaseModel):
    id: str = Field(default_factory=lambda: new_id("evt"))
    task_id: str
    event_type: TraceEventType
    phase: RunPhase | None = None
    step: int = 0
    timestamp: datetime = Field(default_factory=utc_now)
    duration_ms: float | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class TaskSummary(BaseModel):
    task_id: str
    goal: str
    status: RuntimeStatus
    phase: RunPhase
    provider: str
    model: str
    step_count: int
    total_tokens: int
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    duration_ms: float | None = None


class EvalTask(BaseModel):
    id: str
    category: str
    difficulty: Literal["easy", "medium", "hard"]
    goal: str
    expected: dict[str, Any]
    max_steps: int = 12
    tags: list[str] = Field(default_factory=list)
    fixture: dict[str, Any] = Field(default_factory=dict)


class EvalResult(BaseModel):
    task_id: str
    category: str
    success: bool
    score: float
    runtime_status: RuntimeStatus
    latency_ms: float
    tool_calls: int
    tool_accuracy: float
    prompt_tokens: int
    completion_tokens: int
    estimated_cost_usd: float
    cost_known: bool = False
    recovered: bool = False
    error: str | None = None
    answer: str | None = None


class EvalRunSummary(BaseModel):
    run_id: str = Field(default_factory=lambda: new_id("eval"))
    provider: str
    model: str
    strategy: str
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
    total_tasks: int = 0
    passed_tasks: int = 0
    task_success_rate: float = 0
    tool_accuracy: float = 0
    p50_latency_ms: float = 0
    p95_latency_ms: float = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_cost_usd: float = 0
    recovery_success_rate: float = 0
    results: list[EvalResult] = Field(default_factory=list)

