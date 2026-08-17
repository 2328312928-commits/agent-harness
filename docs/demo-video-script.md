# 3-5 Minute Architecture and Demo Video

## 0:00-0:30 Problem

Show the README headline and architecture diagram.

Script:

> Most agent demos stop at a chat box. The hard engineering problem is not generating
> one response; it is controlling tools, preserving state, recovering from failure, and
> measuring the system. Agent Harness makes that runtime explicit.

## 0:30-1:10 Architecture

Show `docs/architecture.md`.

Script:

> A task moves through Plan, Act, Observe, Reflect, and Finalize. Each phase writes a
> checkpoint. Tools pass through JSON Schema validation, permissions, timeout,
> idempotent retry, and cancellation. Provider, memory, tools, and sandbox are all
> replaceable boundaries.

## 1:10-2:00 Interactive Demo

Open the React console.

1. Run the preset `读取 Demo 文件并计算 12 + 7`.
2. Open Trace.
3. Highlight the two tool calls and the checkpoints between phases.
4. Open Observations and show that the sandbox returned `19`.

Script:

> This is not a canned animation. The API created a task, the fake provider selected
> tools, the registry executed them, and every event was persisted. The Trace page is
> reading the same event records used by recovery.

## 2:00-2:40 MCP and Sandbox

Open Tools.

Script:

> The runtime has 14 registered tool contracts. Nine are built in, and five are loaded
> through MCP from the bundled stdio server: filesystem, GitHub, database, browser, and
> constrained Python execution. MCP calls still pass through the same validation and
> authorization pipeline.

Show the Docker sandbox settings.

> Production code execution uses a read-only, non-root container with networking off,
> capabilities dropped, and CPU, memory, PID, and time limits.

## 2:40-3:30 Evaluation

Open the Evaluation view and `docs/benchmark-report.md`.

Script:

> The checked-in deterministic baseline covers 110 tasks. The current harness regression
> result is 100 percent task success, 100 percent tool accuracy, a P50 of 484
> milliseconds, and a P95 of 2.18 seconds. This is explicitly labeled as a harness
> benchmark. Switching the provider to DeepSeek produces a model benchmark through the
> same runner and grader.

## 3:30-4:00 Failure and Recovery

Run a permission-restricted task or show `docs/failure-cases.md`.

Script:

> Recovery is tested, not just documented. With tool permissions removed, the first call
> fails, reflection records the failure, the runtime rebuilds the plan, and the task
> completes with a recovery count of one.

## 4:00-4:30 Close

Show the GitHub repository and release notes.

Script:

> The repository includes one-command Compose startup, API documentation, 110 eval
> tasks, persisted traces, MCP integration tests, sandbox controls, and failure cases
> discovered during development. The next step is running the same benchmark against
> DeepSeek and publishing the model comparison.

## Recording Checklist

- Use 1440p or 1080p, terminal font at least 16px.
- Keep the browser at 100 percent zoom.
- Record system audio or add narration in editing.
- Show a real new task; do not edit the JSON while recording.
- Keep the final video between 3:00 and 5:00.
