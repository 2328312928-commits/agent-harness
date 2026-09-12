# Benchmark Report

> This report is generated from the deterministic Fake Provider and measures the runtime, tool contracts, sandbox, checkpointing, and grading pipeline. It is a harness regression benchmark, not a model-quality claim.

## Run

| Field | Value |
| --- | --- |
| Run ID | `fake-benchmark-20260912-150606` |
| Provider | `fake` |
| Model | `fake-deterministic-v1` |
| Strategy | `plan-and-execute` |
| Tasks | 110 |
| Started | 2026-09-12T15:06:06.846672+00:00 |
| Completed | 2026-09-12T15:06:28.658288+00:00 |

## Headline Metrics

| Metric | Value |
| --- | ---: |
| Task success rate | 73.6% |
| Tool accuracy | 90.9% |
| P50 latency | 553.0 ms |
| P95 latency | 2083.0 ms |
| Prompt tokens | 427,987 |
| Completion tokens | 47,609 |
| Estimated cost | $0.0000 |
| Recovery success | 100.0% |

## By Category

| Category | Tasks | Success | Tool accuracy | P95 |
| --- | ---: | ---: | ---: | ---: |
| browser | 10 | 0.0% | 0.0% | 1607 ms |
| coding | 10 | 100.0% | 100.0% | 1179 ms |
| context | 10 | 0.0% | 100.0% | 1015 ms |
| database | 10 | 100.0% | 100.0% | 1320 ms |
| filesystem_list | 10 | 100.0% | 100.0% | 1384 ms |
| filesystem_read | 10 | 100.0% | 100.0% | 553 ms |
| github | 10 | 100.0% | 100.0% | 3173 ms |
| memory | 10 | 100.0% | 100.0% | 1533 ms |
| mixed | 10 | 100.0% | 100.0% | 1074 ms |
| reasoning | 10 | 10.0% | 100.0% | 1089 ms |
| recovery | 10 | 100.0% | 100.0% | 849 ms |

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
