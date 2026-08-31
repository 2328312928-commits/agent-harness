# Benchmark Report

> This report was generated with provider `deepseek` and model `deepseek-chat`. Model version, endpoint, prompt strategy, and dataset revision should be kept fixed when comparing results.

## Run

| Field | Value |
| --- | --- |
| Run ID | `deepseek-benchmark-20260912-104643` |
| Provider | `deepseek` |
| Model | `deepseek-chat` |
| Strategy | `plan-and-execute` |
| Tasks | 100 |
| Started | 2026-09-12T10:46:43.698447+00:00 |
| Completed | 2026-09-12T10:51:20.982110+00:00 |

## Headline Metrics

| Metric | Value |
| --- | ---: |
| Task success rate | 100.0% |
| Tool accuracy | 100.0% |
| P50 latency | 7322.6 ms |
| P95 latency | 15433.5 ms |
| Prompt tokens | 1,360,777 |
| Completion tokens | 80,799 |
| Estimated cost | $0.4563 |
| Recovery success | 100.0% |

## By Category

| Category | Tasks | Success | Tool accuracy | P95 |
| --- | ---: | ---: | ---: | ---: |
| coding | 10 | 100.0% | 100.0% | 4805 ms |
| context | 10 | 100.0% | 100.0% | 5455 ms |
| database | 10 | 100.0% | 100.0% | 8941 ms |
| filesystem_list | 10 | 100.0% | 100.0% | 9311 ms |
| filesystem_read | 10 | 100.0% | 100.0% | 29384 ms |
| github | 10 | 100.0% | 100.0% | 7585 ms |
| memory | 10 | 100.0% | 100.0% | 7622 ms |
| mixed | 10 | 100.0% | 100.0% | 10293 ms |
| reasoning | 10 | 100.0% | 100.0% | 9079 ms |
| recovery | 10 | 100.0% | 100.0% | 16327 ms |

## Reproducing

```bash
python scripts/build_eval_dataset.py
python scripts/run_benchmark.py \
  --provider deepseek \
  --model deepseek-chat \
  --categories coding,context,database,filesystem_list,filesystem_read,github,memory,mixed,reasoning,recovery \
  --limit 100
```

The dataset contains 110 tasks across reasoning, filesystem, coding, database,
memory, recovery, context compaction, browser, GitHub, and mixed-tool workflows.
