# Benchmark Report

> This report was generated with provider `openai-compatible` and model `deepseek-v4.1-flash`. Model version, endpoint, prompt strategy, and dataset revision should be kept fixed when comparing results. This is a deterministic Runtime contract benchmark, not a broad model-quality or public leaderboard.

## Run

| Field | Value |
| --- | --- |
| Run ID | `openai-compatible-benchmark-20260912-154757` |
| Provider | `openai-compatible` |
| Model | `deepseek-v4.1-flash` |
| Strategy | `plan-and-execute` |
| Tasks | 100 |
| Started | 2026-09-12T15:47:57.184107+00:00 |
| Completed | 2026-09-12T15:58:00.684097+00:00 |

## Headline Metrics

| Metric | Value |
| --- | ---: |
| Task Pass@1 | 91.0% |
| Tool accuracy | 100.0% |
| P50 latency | 16231.1 ms |
| P95 latency | 36925.7 ms |
| Prompt tokens | 1,785,869 |
| Completion tokens | 161,965 |
| Estimated cost | N/A (provider pricing unavailable) |
| Recovery success | 92.9% |

## By Category

| Category | Tasks | Success | Tool accuracy | P95 |
| --- | ---: | ---: | ---: | ---: |
| coding | 10 | 100.0% | 100.0% | 10026 ms |
| context | 10 | 100.0% | 100.0% | 24107 ms |
| database | 10 | 90.0% | 100.0% | 25051 ms |
| filesystem_list | 10 | 100.0% | 100.0% | 21040 ms |
| filesystem_read | 10 | 90.0% | 100.0% | 17098 ms |
| github | 10 | 100.0% | 100.0% | 18419 ms |
| memory | 10 | 90.0% | 100.0% | 20634 ms |
| mixed | 10 | 100.0% | 100.0% | 19305 ms |
| reasoning | 10 | 100.0% | 100.0% | 14511 ms |
| recovery | 10 | 40.0% | 100.0% | 38148 ms |

## Reproducing

```bash
python scripts/build_eval_dataset.py
python scripts/run_benchmark.py \
  --provider openai-compatible \
  --model deepseek-v4.1-flash \
  --categories coding,context,database,filesystem_list,filesystem_read,github,memory,mixed,reasoning,recovery \
  --limit 100
```

The dataset contains 110 tasks across reasoning, filesystem, coding, database,
memory, recovery, context compaction, browser, GitHub, and mixed-tool workflows.
