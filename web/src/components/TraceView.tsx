import { useQuery } from "@tanstack/react-query";
import {
  BrainCircuit,
  Check,
  Circle,
  CircleDot,
  FileJson2,
  Flag,
  LoaderCircle,
  RefreshCcw,
  RotateCcw,
  Terminal,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api, eventStreamUrl } from "../lib/api";
import type { AgentState, RunPhase, TraceEvent } from "../types";
import { StatusBadge } from "./StatusBadge";

const phaseIcons: Record<RunPhase, typeof BrainCircuit> = {
  plan: BrainCircuit,
  act: Terminal,
  observe: CircleDot,
  reflect: RefreshCcw,
  finalize: Flag,
  recovery: RotateCcw,
};

const eventLabels: Record<string, string> = {
  "task.created": "Task created",
  "task.started": "Run started",
  "phase.started": "Phase started",
  "model.request": "Model request",
  "model.response": "Model response",
  "tool.request": "Tool request",
  "tool.response": "Tool response",
  "checkpoint.saved": "Checkpoint saved",
  "recovery.started": "Recovery started",
  "task.completed": "Task completed",
  "task.failed": "Task failed",
  "task.cancelled": "Task cancelled",
};

export function TraceView({ taskId }: { taskId: string | null }) {
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const taskQuery = useQuery({
    queryKey: ["task", taskId],
    queryFn: () => api.task(taskId!),
    enabled: Boolean(taskId),
    refetchInterval: (query) => {
      const state = query.state.data as AgentState | undefined;
      return state?.status === "completed" || state?.status === "failed" ? false : 1500;
    },
  });
  const eventQuery = useQuery({
    queryKey: ["events", taskId],
    queryFn: () => api.events(taskId!),
    enabled: Boolean(taskId),
  });

  useEffect(() => {
    setEvents(eventQuery.data?.items ?? []);
  }, [eventQuery.data]);

  useEffect(() => {
    if (!taskId) return;
    const stream = new EventSource(eventStreamUrl(taskId));
    stream.onmessage = (message) => {
      const event = JSON.parse(message.data) as TraceEvent;
      setEvents((current) => {
        if (current.some((item) => item.id === event.id)) return current;
        return [...current, event];
      });
    };
    stream.onerror = () => stream.close();
    return () => stream.close();
  }, [taskId]);

  const task = taskQuery.data;
  const latestEventByPhase = useMemo(() => {
    const result = new Map<RunPhase, TraceEvent>();
    events.forEach((event) => {
      if (event.phase) result.set(event.phase, event);
    });
    return result;
  }, [events]);

  if (!taskId) {
    return <EmptyTrace />;
  }

  return (
    <div className="trace-layout">
      <section className="trace-main">
        <div className="panel task-header">
          <div className="task-title">
            <span>RUN / {taskId}</span>
            <h2>{task?.goal ?? "Loading task"}</h2>
          </div>
          {task ? <StatusBadge status={task.status} /> : null}
        </div>

        <div className="phase-rail">
          {(["plan", "act", "observe", "reflect", "finalize"] as RunPhase[]).map(
            (phase, index) => {
              const Icon = phaseIcons[phase];
              const event = latestEventByPhase.get(phase);
              const active = task?.phase === phase;
              return (
                <div className={`phase-item ${active ? "active" : ""}`} key={phase}>
                  <div className="phase-node">
                    {event ? <Check size={14} /> : <Icon size={14} />}
                  </div>
                  <div>
                    <strong>{phase}</strong>
                    <span>{event ? formatTime(event.timestamp) : "pending"}</span>
                  </div>
                  {index < 4 ? <div className="phase-line" /> : null}
                </div>
              );
            },
          )}
        </div>

        <div className="panel timeline-panel">
          <div className="panel-heading">
            <div>
              <h2>Trace</h2>
              <p>{events.length} persisted events</p>
            </div>
            <FileJson2 size={18} />
          </div>
          <div className="timeline">
            {events.map((event) => (
              <TraceRow key={event.id} event={event} />
            ))}
            {events.length === 0 ? <div className="empty-cell">Waiting for events</div> : null}
          </div>
        </div>
      </section>

      <aside className="trace-side">
        <div className="panel">
          <div className="panel-heading">
            <div>
              <h2>Execution</h2>
              <p>Runtime state</p>
            </div>
          </div>
          {task ? (
            <div className="detail-list">
              <Detail label="Provider" value={task.provider} />
              <Detail label="Model" value={task.model} />
              <Detail label="Step" value={`${task.step_count} / ${task.max_steps}`} />
              <Detail label="Checkpoint" value={`v${task.checkpoint_version}`} />
              <Detail
                label="Tokens"
                value={`${task.token_budget.prompt_tokens + task.token_budget.completion_tokens}`}
              />
              <Detail label="Recoveries" value={String(task.metadata.recovery_count ?? 0)} />
            </div>
          ) : null}
        </div>

        <div className="panel">
          <div className="panel-heading">
            <div>
              <h2>Plan</h2>
              <p>Revision {task?.plan?.revision ?? 0}</p>
            </div>
          </div>
          <div className="plan-list">
            {task?.plan?.steps.map((step) => (
              <div className="plan-step" key={step.id}>
                <span className={`step-status ${step.status}`}>
                  {step.status === "completed" ? <Check size={12} /> : <Circle size={10} />}
                </span>
                <div>
                  <strong>{step.title}</strong>
                  <span>{step.description}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="panel">
          <div className="panel-heading">
            <div>
              <h2>Observations</h2>
              <p>Latest tool results</p>
            </div>
          </div>
          <div className="observation-list">
            {task?.observations
              .slice()
              .reverse()
              .slice(0, 6)
              .map((result) => (
                <div className="observation" key={result.call_id}>
                  <div>
                    {result.ok ? <Check size={13} /> : <X size={13} />}
                    <strong>{result.tool_name}</strong>
                  </div>
                  <span>{result.latency_ms.toFixed(0)} ms</span>
                  <code>{compact(result.error ?? result.output)}</code>
                </div>
              ))}
          </div>
        </div>
      </aside>
    </div>
  );
}

function TraceRow({ event }: { event: TraceEvent }) {
  const Icon = event.phase ? phaseIcons[event.phase] : CircleDot;
  const isFailure = event.event_type.includes("failed") || Boolean(event.error);
  return (
    <div className={`trace-row ${isFailure ? "failure" : ""}`}>
      <div className="trace-time">{formatTime(event.timestamp)}</div>
      <div className="trace-icon">
        {event.event_type === "checkpoint.saved" ? <Check size={14} /> : <Icon size={14} />}
      </div>
      <div className="trace-content">
        <div>
          <strong>{eventLabels[event.event_type] ?? event.event_type}</strong>
          <span>{event.phase ?? "runtime"}</span>
          {event.duration_ms ? <span>{event.duration_ms.toFixed(1)} ms</span> : null}
        </div>
        <code>{compact(event.payload)}</code>
      </div>
    </div>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function EmptyTrace() {
  return (
    <div className="empty-state">
      <LoaderCircle size={24} className="spin" />
      <h2>Select a run</h2>
      <p>Trace data is loaded from the persistent event stream.</p>
    </div>
  );
}

function formatTime(timestamp: string) {
  return new Date(timestamp).toLocaleTimeString("zh-CN", {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function compact(value: unknown) {
  const text = typeof value === "string" ? value : JSON.stringify(value);
  return text.length > 220 ? `${text.slice(0, 220)}...` : text;
}
