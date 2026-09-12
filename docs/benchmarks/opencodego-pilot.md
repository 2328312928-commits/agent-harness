# Benchmark Report

> This report was generated with provider `openai-compatible` and model `deepseek-v4.1-flash`. Model version, endpoint, prompt strategy, and dataset revision should be kept fixed when comparing results. This is a deterministic Runtime contract benchmark, not a broad model-quality or public leaderboard.

## Run

| Field | Value |
| --- | --- |
| Run ID | `openai-compatible-benchmark-20260912-154504` |
| Provider | `openai-compatible` |
| Model | `deepseek-v4.1-flash` |
| Strategy | `plan-and-execute` |
| Tasks | 3 |
| Started | 2026-09-12T15:45:04.158885+00:00 |
| Completed | 2026-09-12T15:45:57.047438+00:00 |

## Headline Metrics

| Metric | Value |
| --- | ---: |
| Task Pass@1 | 100.0% |
| Tool accuracy | 100.0% |
| P50 latency | 17305.6 ms |
| P95 latency | 20532.3 ms |
| Prompt tokens | 34,174 |
| Completion tokens | 4,319 |
| Estimated cost | $0.0000 |
| Recovery success | 100.0% |

## By Category

| Category | Tasks | Success | Tool accuracy | P95 |
| --- | ---: | ---: | ---: | ---: |
| mixed | 3 | 100.0% | 100.0% | 17306 ms |

## Reproducing

```bash
python scripts/build_eval_dataset.py
python scripts/run_benchmark.py \
  --provider openai-compatible \
  --model deepseek-v4.1-flash \
  --categories mixed \
  --limit 3
```

The dataset contains 110 tasks across reasoning, filesystem, coding, database,
memory, recovery, context compaction, browser, GitHub, and mixed-tool workflows.
