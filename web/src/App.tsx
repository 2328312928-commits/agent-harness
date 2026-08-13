import { useQuery } from "@tanstack/react-query";
import { Bell, Command, Search } from "lucide-react";
import { useState } from "react";
import { EvalsView } from "./components/EvalsView";
import { RunsView } from "./components/RunsView";
import { Sidebar, type ViewName } from "./components/Sidebar";
import { ToolsView } from "./components/ToolsView";
import { TraceView } from "./components/TraceView";
import { api } from "./lib/api";

function App() {
  const [view, setView] = useState<ViewName>("runs");
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);

  const tasksQuery = useQuery({
    queryKey: ["tasks"],
    queryFn: api.tasks,
    refetchInterval: 2000,
  });
  const metricsQuery = useQuery({
    queryKey: ["metrics"],
    queryFn: api.metrics,
    refetchInterval: 3000,
  });
  const toolsQuery = useQuery({
    queryKey: ["tools"],
    queryFn: api.tools,
  });
  const evalRunsQuery = useQuery({
    queryKey: ["eval-runs"],
    queryFn: api.evalRuns,
    refetchInterval: view === "evals" ? 3000 : false,
  });

  const tasks = tasksQuery.data?.items ?? [];
  const activeTaskId = selectedTaskId ?? tasks[0]?.task_id ?? null;

  return (
    <div className="app-shell">
      <Sidebar active={view} onChange={setView} />
      <div className="workspace">
        <header className="topbar">
          <div className="breadcrumbs">
            <span>Harness</span>
            <i>/</i>
            <strong>{view}</strong>
          </div>
          <div className="topbar-actions">
            <button type="button" title="Search">
              <Search size={16} />
            </button>
            <button type="button" title="Command menu">
              <Command size={16} />
            </button>
            <button type="button" title="Notifications">
              <Bell size={16} />
              <i className="notification-dot" />
            </button>
            <div className="avatar">AH</div>
          </div>
        </header>

        <main className="content">
          {view === "runs" ? (
            <RunsView
              metrics={metricsQuery.data}
              tasks={tasks}
              selectedTaskId={activeTaskId}
              onSelectTask={(taskId) => setSelectedTaskId(taskId)}
              onOpenTrace={() => setView("trace")}
            />
          ) : null}
          {view === "trace" ? <TraceView taskId={activeTaskId} /> : null}
          {view === "evals" ? <EvalsView runs={evalRunsQuery.data?.items ?? []} /> : null}
          {view === "tools" ? <ToolsView tools={toolsQuery.data?.items ?? []} /> : null}
        </main>
      </div>
    </div>
  );
}

export default App;
