# Design Notes

## Goals

- Make the complete agent loop inspectable rather than hidden behind a framework.
- Make every failure resumable from a durable checkpoint.
- Keep providers, tools, memory, context, and execution backends replaceable.
- Measure the runtime with reproducible tasks instead of relying on a polished README.

## Non-Goals

- Competitive model quality on broad open-domain benchmarks.
- Multi-tenant authorization and billing.
- A fully managed production control plane.
- Claiming that deterministic regression numbers represent DeepSeek performance.

## Key Decisions

### Explicit phases instead of one large ReAct loop

Plan, Act, Observe, Reflect, and Finalize are separate phases because they have different
prompts, model routing requirements, checkpoint boundaries, and failure semantics. This
also makes the UI and benchmark data easier to interpret.

### Persistent state before event fan-out

Trace events are stored before subscribers receive them. A browser disconnect therefore
does not create gaps in the trace. On reconnect, the API replays events after the last
sequence number.

### Registry-controlled tool execution

Tool implementations do not receive unrestricted task state. They receive a `ToolContext`
with only task identity, workspace root, explicit permissions, cancellation signal, and
metadata. Validation and authorization happen before execution.

### Separate Fake and model providers

`FakeProvider` is deterministic and exists to test the harness. Model providers use the
same `ProviderRequest` and `ProviderResponse` contracts. The benchmark report labels the
provider explicitly so runtime regressions are not confused with model quality.

### Container sandbox by default

Code execution uses a non-root, network-disabled container with a read-only root,
capability drop, PID limit, memory limit, CPU limit, and timeout. The local process
sandbox exists only for tests and requires explicit opt-in.

### Bounded recovery

Every failed observation triggers reflection. Recovery rebuilds the plan and increments
`recovery_count`. Recovery is capped so a broken provider or tool cannot create an
infinite loop.

## Context Strategy

The Context Engineer combines:

1. System prompt for the current phase.
2. Relevant long-term memory.
3. Current plan revision.
4. Original goal.
5. Recent assistant/tool messages.
6. Recent observations and reflections.
7. Phase-specific instructions and tool names.

When the estimated context exceeds the configured threshold, older messages are replaced
with a compact summary while preserving the goal, latest plan, and recent observations.

## Evaluation Strategy

The 110-task seed suite is designed to exercise runtime behavior rather than model
knowledge:

- Tool selection and argument construction
- Multi-step and mixed-tool execution
- Filesystem boundary behavior
- Sandbox execution
- Read-only database access
- Memory writes and recall
- Permission failure recovery
- Context compaction
- Browser and GitHub integration paths

The grader checks status, required tools, observations, recovery count, and expected
answer fragments. Reports include task success, tool accuracy, P50/P95 latency, token
usage, estimated cost, and recovery success.

## Tradeoffs

- The in-process scheduler is simple and observable, but not horizontally durable.
- SQLite is excellent for local demos and tests; PostgreSQL is the production default.
- The JSON-based context compaction is deterministic but less semantic than a model-based
  summarizer.
- Tool permissions are task-level in the current API; production would add user, tenant,
  resource, and approval scopes.
- The Docker socket provides strong local isolation but should be replaced by a remote
  sandbox worker in a multi-tenant deployment.

