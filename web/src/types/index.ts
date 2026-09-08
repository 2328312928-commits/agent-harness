export type TaskStatus =
  | "queued"
  | "running"
  | "waiting_for_tool"
  | "interrupted"
  | "completed"
  | "partial"
  | "failed"
  | "cancelled";

export type RunPhase = "plan" | "act" | "observe" | "reflect" | "finalize" | "recovery";

export interface TaskSummary {
  task_id: string;
  goal: string;
  status: TaskStatus;
  phase: RunPhase;
  provider: string;
  model: string;
  step_count: number;
  total_tokens: number;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
  duration_ms?: number | null;
}

export interface ToolResult {
  call_id: string;
  tool_name: string;
  ok: boolean;
  output?: unknown;
  error?: string | null;
  error_type?: string | null;
  latency_ms: number;
  attempts: number;
}

export interface AgentState {
  task_id: string;
  goal: string;
  status: TaskStatus;
  phase: RunPhase;
  provider: string;
  model: string;
  messages: Array<{
    role: string;
    content: string;
    tool_calls: Array<{ id: string; name: string; arguments: Record<string, unknown> }>;
  }>;
  plan?: {
    objective: string;
    revision: number;
    steps: Array<{
      id: string;
      title: string;
      description: string;
      status: string;
      expected_tools: string[];
    }>;
  } | null;
  observations: ToolResult[];
  reflections: string[];
  final_answer?: string | null;
  error?: string | null;
  token_budget: {
    limit: number;
    prompt_tokens: number;
    completion_tokens: number;
    compaction_count: number;
  };
  step_count: number;
  max_steps: number;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
  metadata: Record<string, unknown>;
  checkpoint_version: number;
}

export interface TraceEvent {
  sequence: number;
  id: string;
  task_id: string;
  event_type: string;
  phase?: RunPhase | null;
  step: number;
  timestamp: string;
  duration_ms?: number | null;
  payload: Record<string, unknown>;
  error?: string | null;
}

export interface ToolSpec {
  name: string;
  description: string;
  input_schema: Record<string, unknown>;
  permissions: string[];
  timeout_seconds?: number | null;
  max_retries?: number | null;
  idempotent: boolean;
  source: "builtin" | "mcp" | "plugin";
}

export interface Metrics {
  tasks: {
    total: number;
    by_status: Record<string, number>;
    completion_rate: number;
  };
  checkpoints: number;
  memories: number;
  events: Record<string, number>;
  eval_runs: EvalRun[];
  sandbox: {
    backend: string;
    network_disabled: boolean;
  };
}

export interface EvalResult {
  task_id: string;
  category: string;
  success: boolean;
  score: number;
  runtime_status: TaskStatus;
  latency_ms: number;
  tool_calls: number;
  tool_accuracy: number;
  prompt_tokens: number;
  completion_tokens: number;
  estimated_cost_usd: number;
  recovered: boolean;
  error?: string | null;
  answer?: string | null;
}

export interface EvalRun {
  run_id: string;
  provider: string;
  model: string;
  strategy: string;
  started_at: string;
  completed_at?: string | null;
  total_tasks: number;
  passed_tasks: number;
  task_success_rate: number;
  tool_accuracy: number;
  p50_latency_ms: number;
  p95_latency_ms: number;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  total_cost_usd: number;
  recovery_success_rate: number;
  results: EvalResult[];
}

export interface ProviderInfo {
  name: string;
  configured: boolean;
  default_model: string;
  purpose: string;
}

