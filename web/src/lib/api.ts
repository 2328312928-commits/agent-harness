import type {
  AgentState,
  EvalRun,
  Metrics,
  ProviderInfo,
  TaskSummary,
  ToolSpec,
  TraceEvent,
} from "../types";

const API_BASE = import.meta.env.VITE_API_URL || "/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  tasks: () => request<{ items: TaskSummary[] }>("/tasks"),
  task: (taskId: string) => request<AgentState>(`/tasks/${taskId}`),
  events: (taskId: string, after = 0) =>
    request<{ items: TraceEvent[] }>(`/tasks/${taskId}/events?after=${after}`),
  createTask: (payload: {
    goal: string;
    provider?: string;
    model?: string;
    max_steps?: number;
    token_budget?: number;
    metadata?: Record<string, unknown>;
  }) =>
    request<AgentState>("/tasks", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  cancelTask: (taskId: string) =>
    request<{ status: string }>(`/tasks/${taskId}/cancel`, { method: "POST" }),
  resumeTask: (taskId: string) =>
    request<AgentState>(`/tasks/${taskId}/resume`, { method: "POST" }),
  metrics: () => request<Metrics>("/metrics"),
  tools: () => request<{ items: ToolSpec[] }>("/tools"),
  providers: () => request<{ items: ProviderInfo[] }>("/providers"),
  evalRuns: () => request<{ items: EvalRun[] }>("/evals/runs"),
  startEval: (payload: {
    provider?: string;
    strategy?: string;
    limit?: number;
    categories?: string[];
    concurrency?: number;
  }) =>
    request<{ run_id: string; status: string }>("/evals/runs", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};

export function eventStreamUrl(taskId: string) {
  return `${API_BASE}/tasks/${taskId}/events/stream`;
}

