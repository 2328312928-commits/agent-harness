import { useMutation } from "@tanstack/react-query";
import {
  Box,
  Braces,
  Database,
  FileText,
  Github,
  Globe2,
  Play,
  ServerCog,
  ShieldCheck,
  TerminalSquare,
} from "lucide-react";
import { useState } from "react";
import { api } from "../lib/api";
import type { ToolSpec } from "../types";

const toolIcons: Record<string, typeof Box> = {
  "filesystem.read_file": FileText,
  "filesystem.write_file": FileText,
  "filesystem.list": Box,
  "github.search_repositories": Github,
  "browser.fetch": Globe2,
  "database.query": Database,
  "sandbox.run_python": TerminalSquare,
};

export function ToolsView({ tools }: { tools: ToolSpec[] }) {
  const [selected, setSelected] = useState<ToolSpec | null>(null);
  const [argumentsText, setArgumentsText] = useState("{}");
  const playground = useMutation({
    mutationFn: () =>
      api.createTask({
        goal: `请调用工具 ${selected?.name}，参数为 ${argumentsText}`,
        provider: "fake",
      }),
  });

  return (
    <div className="tools-layout">
      <section>
        <div className="section-heading">
          <div>
            <h2>Registered tools</h2>
            <p>{tools.length} contracts from built-in and MCP sources</p>
          </div>
          <div className="source-legend">
            <span><i className="builtin" /> Built-in</span>
            <span><i className="mcp" /> MCP</span>
          </div>
        </div>
        <div className="tool-grid">
          {tools.map((tool) => {
            const Icon = toolIcons[tool.name] ?? ServerCog;
            return (
              <button
                className={`tool-card ${selected?.name === tool.name ? "selected" : ""}`}
                key={tool.name}
                onClick={() => {
                  setSelected(tool);
                  setArgumentsText("{}");
                }}
                type="button"
              >
                <div className="tool-card-head">
                  <div className={`tool-icon ${tool.source}`}>
                    <Icon size={18} />
                  </div>
                  <span className={`source-tag ${tool.source}`}>{tool.source}</span>
                </div>
                <strong>{tool.name}</strong>
                <p>{tool.description}</p>
                <div className="permission-row">
                  {tool.permissions.slice(0, 4).map((permission) => (
                    <span key={permission}>{permission}</span>
                  ))}
                </div>
                <div className="tool-meta">
                  <span>
                    <ShieldCheck size={13} />
                    {tool.idempotent ? "idempotent" : "single-shot"}
                  </span>
                  <span>{tool.timeout_seconds ?? 30}s</span>
                </div>
              </button>
            );
          })}
        </div>
      </section>

      <aside className="panel contract-panel">
        <div className="panel-heading">
          <div>
            <h2>Tool contract</h2>
            <p>{selected?.name ?? "Select a tool"}</p>
          </div>
          <Braces size={18} />
        </div>
        {selected ? (
          <>
            <pre>{JSON.stringify(selected.input_schema, null, 2)}</pre>
            <label className="field-label">
              Arguments
              <textarea
                rows={7}
                value={argumentsText}
                onChange={(event) => setArgumentsText(event.target.value)}
              />
            </label>
            <button
              className="primary-button full"
              disabled={playground.isPending}
              onClick={() => playground.mutate()}
              type="button"
            >
              <Play size={15} fill="currentColor" />
              {playground.isPending ? "Created" : "Create tool run"}
            </button>
            {playground.data ? (
              <div className="inline-success">Run {playground.data.task_id} created</div>
            ) : null}
          </>
        ) : (
          <div className="contract-empty">
            <ServerCog size={24} />
            <span>No tool selected</span>
          </div>
        )}
      </aside>
    </div>
  );
}

