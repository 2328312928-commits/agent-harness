import { CircleAlert, CircleCheck, CircleDashed, CircleStop, LoaderCircle } from "lucide-react";
import type { TaskStatus } from "../types";

const statusMeta: Record<
  TaskStatus,
  { label: string; className: string; icon: typeof CircleCheck }
> = {
  queued: { label: "Queued", className: "neutral", icon: CircleDashed },
  running: { label: "Running", className: "info", icon: LoaderCircle },
  waiting_for_tool: { label: "Tool", className: "warning", icon: LoaderCircle },
  interrupted: { label: "Interrupted", className: "warning", icon: CircleAlert },
  completed: { label: "Completed", className: "success", icon: CircleCheck },
  partial: { label: "Partial", className: "warning", icon: CircleAlert },
  failed: { label: "Failed", className: "danger", icon: CircleAlert },
  cancelled: { label: "Cancelled", className: "neutral", icon: CircleStop },
};

export function StatusBadge({ status }: { status: TaskStatus }) {
  const meta = statusMeta[status];
  const Icon = meta.icon;
  return (
    <span className={`status-badge ${meta.className}`}>
      <Icon size={13} className={status === "running" ? "spin" : ""} />
      {meta.label}
    </span>
  );
}

