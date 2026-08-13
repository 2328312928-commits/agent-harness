import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  CheckCircle2,
  Clock3,
  Coins,
  Database,
  FileCode2,
  GitBranch,
  Play,
  RotateCcw,
  Square,
  TerminalSquare,
} from "lucide-react";
import { useState } from "react";
import { api } from "../lib/api";
import type { Metrics, TaskSummary } from "../types";
import { StatusBadge } from "./StatusBadge";

const presets = [
  { label: "文件 + 计算", goal: "请读取 examples/demo.txt，然后计算 12 + 7", icon: FileCode2 },
  { label: "数据库", goal: "请通过 SQL 数据库健康检查确认连接可用", icon: Database },
  { label: "GitHub", goal: "请使用 GitHub 搜索仓库：agent runtime", icon: GitBranch },
];

export function RunsView({
  metrics,
  tasks,
  selectedTaskId,
  onSelectTask,
  onOpenTrace,
}: {
  metrics?: Metrics;
  tasks: TaskSummary[];
  selectedTaskId: string | null;
  onSelectTask: (taskId: string) => void;
  onOpenTrace: () => void;
}) {
  const queryClient = useQueryClient();
  const [goal, setGoal] = useState("请读取 examples/demo.txt，然后计算 12 + 7");
  const [provider, setProvider] = useState("fake");
  const [maxSteps, setMaxSteps] = useState(20);

  const createTask = useMutation({
    mutationFn: () => api.createTask({ goal, provider, max_steps: maxSteps }),
    onSuccess: async (state) => {
      await queryClient.invalidateQueries({ queryKey: ["tasks"] });
      onSelectTask(state.task_id);
      onOpenTrace();
    },
  });

  const cancelTask = useMutation({
    mutationFn: (taskId: string) => api.cancelTask(taskId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tasks"] }),
  });

  const resumeTask = useMutation({
    mutationFn: (taskId: string) => api.resumeTask(taskId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tasks"] }),
  });

  const completion = metrics?.tasks.completion_rate ?? 0;
  const totalLatency = tasks
    .map((task) => task.duration_ms)
    .filter((value): value is number => typeof value === "number");
  const averageLatency =
    totalLatency.length > 0
      ? totalLatency.reduce((sum, value) => sum + value, 0) / totalLatency.length
      : 0;

  return (
    <div className="view-stack">
      <section className="metric-strip">
        <Metric
          icon={CheckCircle2}
          label="Completion"
          value={`${(completion * 100).toFixed(1)}%`}
          detail={`${metrics?.tasks.total ?? 0} total runs`}
        />
        <Metric
          icon={Clock3}
          label="Mean latency"
          value={`${(averageLatency / 1000).toFixed(2)}s`}
          detail="P50/P95 available in eval"
        />
        <Metric
          icon={RotateCcw}
          label="Checkpoints"
          value={String(metrics?.checkpoints ?? 0)}
          detail={`${metrics?.memories ?? 0} memory records`}
        />
        <Metric
          icon={Coins}
          label="Cost"
          value="$0.0000"
          detail="Offline deterministic baseline"
        />
      </section>

      <section className="main-grid">
        <div className="column-stack">
          <div className="panel composer-panel">
            <div className="panel-heading">
              <div>
                <h2>New run</h2>
                <p>Agent Runtime execution</p>
              </div>
              <TerminalSquare size={19} />
            </div>
            <textarea
              value={goal}
              onChange={(event) => setGoal(event.target.value)}
              placeholder="输入任务目标"
              rows={4}
            />
            <div className="preset-row">
              {presets.map((preset) => {
                const Icon = preset.icon;
                return (
                  <button
                    type="button"
                    key={preset.label}
                    onClick={() => setGoal(preset.goal)}
                  >
                    <Icon size={14} />
                    {preset.label}
                  </button>
                );
              })}
            </div>
            <div className="composer-controls">
              <label>
                Provider
                <select value={provider} onChange={(event) => setProvider(event.target.value)}>
                  <option value="fake">Fake</option>
                  <option value="deepseek">DeepSeek</option>
                  <option value="openai-compatible">OpenAI-compatible</option>
                </select>
              </label>
              <label>
                Max steps
                <input
                  min={1}
                  max={100}
                  type="number"
                  value={maxSteps}
                  onChange={(event) => setMaxSteps(Number(event.target.value))}
                />
              </label>
              <button
                className="primary-button"
                disabled={!goal.trim() || createTask.isPending}
                onClick={() => createTask.mutate()}
                type="button"
              >
                <Play size={15} fill="currentColor" />
                {createTask.isPending ? "Starting" : "Run task"}
              </button>
            </div>
            {createTask.error ? (
              <div className="inline-error">{createTask.error.message}</div>
            ) : null}
          </div>

          <div className="panel runs-panel">
            <div className="panel-heading">
              <div>
                <h2>Recent runs</h2>
                <p>Latest task state from the persistent store</p>
              </div>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Goal</th>
                    <th>Status</th>
                    <th>Phase</th>
                    <th>Steps</th>
                    <th>Latency</th>
                    <th aria-label="Actions" />
                  </tr>
                </thead>
                <tbody>
                  {tasks.slice(0, 12).map((task) => (
                    <tr
                      className={selectedTaskId === task.task_id ? "selected" : ""}
                      key={task.task_id}
                      onClick={() => onSelectTask(task.task_id)}
                    >
                      <td>
                        <div className="goal-cell">
                          <strong>{task.goal}</strong>
                          <span>{task.task_id}</span>
                        </div>
                      </td>
                      <td>
                        <StatusBadge status={task.status} />
                      </td>
                      <td className="mono">{task.phase}</td>
                      <td>{task.step_count}</td>
                      <td>{task.duration_ms ? `${(task.duration_ms / 1000).toFixed(2)}s` : "-"}</td>
                      <td>
                        <div className="row-actions">
                          {["running", "queued", "waiting_for_tool"].includes(task.status) ? (
                            <button
                              aria-label="Cancel task"
                              title="Cancel task"
                              type="button"
                              onClick={(event) => {
                                event.stopPropagation();
                                cancelTask.mutate(task.task_id);
                              }}
                            >
                              <Square size={13} fill="currentColor" />
                            </button>
                          ) : (
                            <button
                              aria-label="Resume task"
                              title="Resume task"
                              type="button"
                              onClick={(event) => {
                                event.stopPropagation();
                                resumeTask.mutate(task.task_id);
                              }}
                            >
                              <RotateCcw size={14} />
                            </button>
                          )}
                          <button
                            aria-label="Open trace"
                            title="Open trace"
                            type="button"
                            onClick={(event) => {
                              event.stopPropagation();
                              onSelectTask(task.task_id);
                              onOpenTrace();
                            }}
                          >
                            <ArrowRight size={14} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                  {tasks.length === 0 ? (
                    <tr>
                      <td className="empty-cell" colSpan={6}>
                        No runs yet
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

function Metric({
  icon: Icon,
  label,
  value,
  detail,
}: {
  icon: typeof CheckCircle2;
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="metric">
      <div className="metric-icon">
        <Icon size={16} />
      </div>
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
        <small>{detail}</small>
      </div>
    </div>
  );
}
