# Failure Cases and Fixes

These cases were encountered while building and running the project.

## 1. SQLite Write Lock Under Concurrent Evaluation

**Symptom**

During the first 110-task benchmark at concurrency 4, one task failed while inserting a
`model.response` event:

```text
sqlite3.OperationalError: database is locked
```

**Root cause**

The default SQLite journal mode serializes writers aggressively, and concurrent event
inserts exceeded the default busy timeout.

**Fix**

The database initializer now enables WAL mode, sets a 30-second busy timeout, and enables
foreign keys. PostgreSQL remains the recommended backend for production.

**Regression**

The full benchmark is rerun at concurrency 4 and the report records the exact provider,
task count, and latency distribution.

## 2. Repeated Tool Calls Until Max Steps

**Symptom**

The offline provider repeatedly called `filesystem.read_file` until the 20-step limit.

**Root cause**

The provider checked short names such as `read_file`, while the registry used the fully
qualified name `filesystem.read_file`.

**Fix**

Tool identity is now compared using the complete registry name. A full-loop test asserts
that a mixed task performs exactly one filesystem call and one sandbox call.

## 3. MCP Wrapper Did Not Satisfy the Tool Contract

**Symptom**

Starting the API failed while constructing `MCPTool`:

```text
TypeError: Can't instantiate abstract class MCPTool without an implementation for abstract method 'spec'
```

**Root cause**

`spec` was assigned as an instance attribute, which does not implement the abstract
property inherited from `Tool`.

**Fix**

`MCPTool` now stores `_spec` and implements the `spec` property. The MCP integration test
initializes the server, discovers all five tools, and calls one through stdio.

## 4. Local Code Execution Could Be Enabled Accidentally

**Symptom**

Choosing `SANDBOX_BACKEND=local` bypassed container isolation even when
`ALLOW_LOCAL_CODE_EXECUTION` was false.

**Root cause**

The setting was present but not enforced during container startup.

**Fix**

Startup now fails unless local execution is explicitly enabled. Docker remains the
default backend and is the only backend represented as a security boundary.

## 5. SSE Reconnect After Task Completion

**Symptom**

A client that opened the event stream after finalization could wait forever because the
close notification had already been published.

**Root cause**

The Event Bus kept active subscribers but no closed-task state.

**Fix**

Completed task IDs are retained in a closed set. New subscribers receive persisted
history and terminate immediately instead of blocking.

## 6. Browser Tool SSRF Surface

**Symptom**

An unrestricted fetch tool could be used to read localhost or private network services.

**Root cause**

URL scheme validation alone does not prevent DNS resolution to private addresses.

**Fix**

The Browser tool resolves the hostname and rejects loopback, private, link-local, and
reserved addresses before issuing the request.

## 7. Windows Console Encoding

**Symptom**

The benchmark completed and wrote valid JSON, then failed while printing a Unicode-heavy
summary to a GBK terminal.

**Root cause**

The report script printed the full result payload to a terminal with a legacy code page.

**Fix**

The CLI prints a compact ASCII-safe metric summary. Full UTF-8 results remain in the
persisted JSON artifact.

