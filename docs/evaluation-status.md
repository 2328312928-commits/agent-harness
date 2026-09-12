# Evaluation Status

## Current Status

The repository contains a 110-task deterministic Runtime contract suite covering
tool selection, successful tool execution, answer checks, recovery behavior,
checkpointing, context compaction, and mixed workflows.

The previous `100%` DeepSeek result used an earlier Grader that did not require
successful tool execution and had no answer check for several reasoning tasks. That
report has been removed because it was not strong enough evidence for model quality.

## Strict Grader

The current Grader requires:

- Expected runtime status, including `partial` for bounded recovery exhaustion.
- Required tools to execute successfully, not merely be requested.
- Required answer fragments or one-of answer fragments.
- Minimum observation and successful-observation counts.
- Expected recovery count.

## Model Benchmark

The official DeepSeek endpoint returned:

```text
402 Insufficient Balance
```

That incomplete run is not published as a model metric. A strict 100-task run was
subsequently completed through OpenCodeGo with `deepseek-v4.1-flash`:

| Metric | Value |
| --- | ---: |
| Pass@1 | 91.0% |
| Tool accuracy | 100.0% |
| P50 | 16.23s |
| P95 | 36.93s |
| Prompt tokens | 1,785,869 |
| Completion tokens | 161,965 |
| Recovery success | 92.9% |
| Cost | N/A |

The dominant failure category was Recovery: several tasks exhausted the 32k Token
budget while trying alternative tools after permission denial. This is a real runtime
and policy limitation, not hidden by the report.

## Reporting Rule

Do not describe this suite as a public leaderboard or as proof of general model
reasoning. It is a Runtime contract benchmark. A larger independent model-quality
dataset with hidden tasks and external review is still a future work item.
