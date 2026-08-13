import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  CheckCircle2,
  Gauge,
  Play,
  Target,
  Timer,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../lib/api";
import type { EvalRun } from "../types";
import { StatusBadge } from "./StatusBadge";

export function EvalsView({ runs }: { runs: EvalRun[] }) {
  const queryClient = useQueryClient();
  const startEval = useMutation({
    mutationFn: () =>
      api.startEval({
        provider: "fake",
        strategy: "plan-and-execute",
        limit: 110,
        concurrency: 4,
      }),
    onSuccess: () => {
      window.setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ["eval-runs"] });
      }, 1500);
    },
  });
  const latest = runs[0];
  const categoryData =
    latest?.results.reduce<Array<{ category: string; success: number }>>((items, result) => {
      const existing = items.find((item) => item.category === result.category);
      if (existing) {
        existing.success += result.success ? 1 : 0;
        return items;
      }
      items.push({ category: result.category, success: result.success ? 1 : 0 });
      return items;
    }, []) ?? [];
  const categoryCounts = latest?.results.reduce<Record<string, number>>((counts, result) => {
    counts[result.category] = (counts[result.category] ?? 0) + 1;
    return counts;
  }, {});
  const chartData = categoryData.map((item) => ({
    ...item,
    rate: categoryCounts?.[item.category] ? item.success / categoryCounts[item.category] : 0,
  }));

  return (
    <div className="view-stack">
      <section className="metric-strip">
        <EvalMetric
          icon={Target}
          label="Success"
          value={latest ? `${(latest.task_success_rate * 100).toFixed(1)}%` : "-"}
        />
        <EvalMetric
          icon={Gauge}
          label="Tool accuracy"
          value={latest ? `${(latest.tool_accuracy * 100).toFixed(1)}%` : "-"}
        />
        <EvalMetric
          icon={Timer}
          label="P95 latency"
          value={latest ? `${(latest.p95_latency_ms / 1000).toFixed(2)}s` : "-"}
        />
        <EvalMetric
          icon={Activity}
          label="Recovery"
          value={latest ? `${(latest.recovery_success_rate * 100).toFixed(1)}%` : "-"}
        />
      </section>

      <section className="eval-grid">
        <div className="panel">
          <div className="panel-heading">
            <div>
              <h2>Benchmark</h2>
              <p>110-task deterministic regression suite</p>
            </div>
            <button
              className="primary-button"
              disabled={startEval.isPending}
              onClick={() => startEval.mutate()}
              type="button"
            >
              <Play size={15} fill="currentColor" />
              {startEval.isPending ? "Starting" : "Run benchmark"}
            </button>
          </div>
          <div className="chart-box">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 10, right: 10, bottom: 20, left: 0 }}>
                <CartesianGrid stroke="#26303c" vertical={false} />
                <XAxis
                  dataKey="category"
                  tick={{ fill: "#8c99a8", fontSize: 11 }}
                  tickLine={false}
                  axisLine={false}
                  angle={-28}
                  textAnchor="end"
                />
                <YAxis
                  domain={[0, 1]}
                  tickFormatter={(value) => `${value * 100}%`}
                  tick={{ fill: "#8c99a8", fontSize: 11 }}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip
                  formatter={(value) => `${(Number(value) * 100).toFixed(1)}%`}
                  contentStyle={{
                    background: "#151b24",
                    border: "1px solid #2a3542",
                    borderRadius: 6,
                    color: "#e7edf5",
                  }}
                />
                <Bar dataKey="rate" fill="#e9a23b" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="panel">
          <div className="panel-heading">
            <div>
              <h2>Recent runs</h2>
              <p>Persisted evaluation summaries</p>
            </div>
            <CheckCircle2 size={18} />
          </div>
          <div className="eval-run-list">
            {runs.slice(0, 8).map((run) => (
              <div className="eval-run" key={run.run_id}>
                <div>
                  <strong>{run.run_id}</strong>
                  <span>
                    {run.provider} / {run.strategy}
                  </span>
                </div>
                <div className="eval-run-score">
                  <strong>{(run.task_success_rate * 100).toFixed(0)}%</strong>
                  <span>{run.total_tasks} tasks</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <h2>Task results</h2>
            <p>Per-task grading details</p>
          </div>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Task</th>
                <th>Category</th>
                <th>Result</th>
                <th>Score</th>
                <th>Tools</th>
                <th>Latency</th>
                <th>Recovered</th>
              </tr>
            </thead>
            <tbody>
              {latest?.results.slice(0, 20).map((result) => (
                <tr key={result.task_id}>
                  <td className="mono">{result.task_id}</td>
                  <td>{result.category}</td>
                  <td>
                    <StatusBadge status={result.runtime_status} />
                  </td>
                  <td>{(result.score * 100).toFixed(0)}%</td>
                  <td>{(result.tool_accuracy * 100).toFixed(0)}%</td>
                  <td>{(result.latency_ms / 1000).toFixed(2)}s</td>
                  <td>{result.recovered ? "yes" : "no"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function EvalMetric({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof Target;
  label: string;
  value: string;
}) {
  return (
    <div className="metric compact">
      <div className="metric-icon">
        <Icon size={16} />
      </div>
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
      </div>
    </div>
  );
}
