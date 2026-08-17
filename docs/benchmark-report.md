# Benchmark Report

> This report is generated from the deterministic Fake Provider and measures the
> runtime, tool contracts, sandbox, checkpointing, and grading pipeline. It is a
> harness regression benchmark, not a claim about DeepSeek or another model's quality.
> Replace `provider=fake` with a configured model to produce a model benchmark.

## Run

| Field | Value |
| --- | --- |
| Run ID | `offline-benchmark-20260912-090258` |
| Provider | `fake` |
| Model | `fake-deterministic-v1` |
| Strategy | `plan-and-execute` |
| Tasks | 110 |
| Started | 2026-09-12T09:02:58.772500+00:00 |
| Completed | 2026-09-12T09:03:21.909487+00:00 |

## Headline Metrics

| Metric | Value |
| --- | ---: |
| Task success rate | 100.0% |
| Tool accuracy | 100.0% |
| P50 latency | 484.4 ms |
| P95 latency | 2182.9 ms |
| Prompt tokens | 406,023 |
| Completion tokens | 45,822 |
| Estimated cost | $0.0000 |
| Recovery success | 100.0% |

## By Category

| Category | Tasks | Success | Tool accuracy | P95 |
| --- | ---: | ---: | ---: | ---: |
| browser | 10 | 100.0% | 100.0% | 2263 ms |
| coding | 10 | 100.0% | 100.0% | 902 ms |
| context | 10 | 100.0% | 100.0% | 1274 ms |
| database | 10 | 100.0% | 100.0% | 2056 ms |
| filesystem_list | 10 | 100.0% | 100.0% | 1140 ms |
| filesystem_read | 10 | 100.0% | 100.0% | 1301 ms |
| github | 10 | 100.0% | 100.0% | 2540 ms |
| memory | 10 | 100.0% | 100.0% | 898 ms |
| mixed | 10 | 100.0% | 100.0% | 1132 ms |
| reasoning | 10 | 100.0% | 100.0% | 1126 ms |
| recovery | 10 | 100.0% | 100.0% | 1245 ms |

## Reproducing

```bash
python scripts/build_eval_dataset.py
python scripts/run_benchmark.py
```

The dataset contains 110 tasks across reasoning, filesystem, coding, database,
memory, recovery, context compaction, browser, GitHub, and mixed-tool workflows.
