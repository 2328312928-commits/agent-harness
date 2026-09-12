# Benchmark Report

> This report is generated from the deterministic Fake Provider and measures the runtime, tool contracts, sandbox, checkpointing, and grading pipeline. It is a harness regression benchmark, not a model-quality claim.

## Run

| Field | Value |
| --- | --- |
| Run ID | `fake-benchmark-20260912-155841` |
| Provider | `fake` |
| Model | `fake-deterministic-v1` |
| Strategy | `plan-and-execute` |
| Tasks | 110 |
| Started | 2026-09-12T15:58:41.706573+00:00 |
| Completed | 2026-09-12T15:59:04.701405+00:00 |

## Headline Metrics

| Metric | Value |
| --- | ---: |
| Task success rate | 73.6% |
| Tool accuracy | 90.9% |
| P50 latency | 469.8 ms |
| P95 latency | 2453.2 ms |
| Prompt tokens | 431,070 |
| Completion tokens | 48,216 |
| Estimated cost | $0.0000 |
| Recovery success | 100.0% |

## By Category

| Category | Tasks | Success | Tool accuracy | P95 |
| --- | ---: | ---: | ---: | ---: |
| browser | 10 | 0.0% | 0.0% | 654 ms |
| coding | 10 | 100.0% | 100.0% | 489 ms |
| context | 10 | 0.0% | 100.0% | 1073 ms |
| database | 10 | 100.0% | 100.0% | 800 ms |
| filesystem_list | 10 | 100.0% | 100.0% | 2497 ms |
| filesystem_read | 10 | 100.0% | 100.0% | 1313 ms |
| github | 10 | 100.0% | 100.0% | 2400 ms |
| memory | 10 | 100.0% | 100.0% | 1632 ms |
| mixed | 10 | 100.0% | 100.0% | 1576 ms |
| reasoning | 10 | 10.0% | 100.0% | 1168 ms |
| recovery | 10 | 100.0% | 100.0% | 1099 ms |

## Reproducing

```bash
python scripts/build_eval_dataset.py
python scripts/run_benchmark.py \
  --provider fake \
  --model fake-deterministic-v1 \
  --categories browser,coding,context,database,filesystem_list,filesystem_read,github,memory,mixed,reasoning,recovery \
  --limit 110
```

The dataset contains 110 tasks across reasoning, filesystem, coding, database,
memory, recovery, context compaction, browser, GitHub, and mixed-tool workflows.
