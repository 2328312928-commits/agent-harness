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

## Model Benchmark Blocker

A strict DeepSeek rerun was started, but the provider later returned:

```text
402 Insufficient Balance
```

The incomplete run is not published as a model metric. A public model comparison
should be rerun only after the provider account has sufficient balance and the dataset
version, model version, prompt strategy, temperature, and concurrency are frozen.

## Reporting Rule

Do not describe this suite as a public leaderboard or as proof of general model
reasoning. It is a Runtime contract benchmark. A larger independent model-quality
dataset with hidden tasks and external review is still a future work item.

