import {
  Activity,
  Boxes,
  ChartNoAxesCombined,
  ListChecks,
  RadioTower,
} from "lucide-react";

export type ViewName = "runs" | "trace" | "evals" | "tools";

const items: Array<{
  id: ViewName;
  label: string;
  icon: typeof Activity;
}> = [
  { id: "runs", label: "运行", icon: ListChecks },
  { id: "trace", label: "Trace", icon: RadioTower },
  { id: "evals", label: "评测", icon: ChartNoAxesCombined },
  { id: "tools", label: "工具", icon: Boxes },
];

export function Sidebar({
  active,
  onChange,
}: {
  active: ViewName;
  onChange: (view: ViewName) => void;
}) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">
          <Activity size={18} strokeWidth={2.4} />
        </div>
        <div>
          <strong>Agent Harness</strong>
          <span>Runtime Console</span>
        </div>
      </div>
      <nav className="nav">
        {items.map((item) => {
          const Icon = item.icon;
          return (
            <button
              className={active === item.id ? "nav-item active" : "nav-item"}
              key={item.id}
              onClick={() => onChange(item.id)}
              type="button"
            >
              <Icon size={17} />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>
      <div className="sidebar-foot">
        <span className="status-dot" />
        <div>
          <strong>API connected</strong>
          <span>Fake provider ready</span>
        </div>
      </div>
    </aside>
  );
}

