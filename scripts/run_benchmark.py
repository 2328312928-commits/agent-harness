from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from agent_harness.api.container import AppContainer
from agent_harness.config import get_settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Agent Harness benchmark suite.")
    parser.add_argument("--provider", default="fake", help="Provider name.")
    parser.add_argument("--model", default=None, help="Optional provider model override.")
    parser.add_argument("--strategy", default="plan-and-execute")
    parser.add_argument("--limit", type=int, default=110)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument(
        "--categories",
        default="",
        help="Comma-separated category filter.",
    )
    parser.add_argument("--output-dir", default="evals/results")
    parser.add_argument(
        "--report",
        default=None,
        help=(
            "Report path. Defaults to docs/benchmark-report.md for fake, "
            "otherwise docs/benchmarks."
        ),
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    container = AppContainer(get_settings())
    await container.startup()
    try:
        categories = {item for item in args.categories.split(",") if item}
        tasks = [
            task
            for task in container.evals.load_tasks()
            if not categories or task.category in categories
        ][args.offset : args.offset + args.limit]
        started = datetime.now(UTC)
        summary = await container.evals.run(
            tasks,
            provider=args.provider,
            model=args.model,
            strategy=args.strategy,
            concurrency=args.concurrency,
            run_id=f"{args.provider}-benchmark-{started:%Y%m%d-%H%M%S}",
        )
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        raw_path = output_dir / f"{summary.run_id}.json"
        raw_path.write_text(summary.model_dump_json(indent=2), encoding="utf-8")
        report = render_report(summary)
        if args.report:
            report_path = Path(args.report)
        elif args.provider == "fake":
            report_path = Path("docs/benchmark-report.md")
        else:
            report_path = Path("docs/benchmarks") / f"{summary.run_id}.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report, encoding="utf-8")
        print(
            json.dumps(
                {
                    "run_id": summary.run_id,
                    "tasks": summary.total_tasks,
                    "task_success_rate": summary.task_success_rate,
                    "tool_accuracy": summary.tool_accuracy,
                    "p50_latency_ms": summary.p50_latency_ms,
                    "p95_latency_ms": summary.p95_latency_ms,
                    "total_cost_usd": summary.total_cost_usd,
                    "recovery_success_rate": summary.recovery_success_rate,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        print(f"Wrote {raw_path} and {report_path}")
    finally:
        await container.shutdown()


def render_report(summary) -> str:
    categories: dict[str, list] = {}
    for result in summary.results:
        categories.setdefault(result.category, []).append(result)
    rows = []
    for category, results in sorted(categories.items()):
        success = sum(1 for result in results if result.success) / len(results)
        p95 = sorted(result.latency_ms for result in results)[
            max(0, int(len(results) * 0.95) - 1)
        ]
        rows.append(
            f"| {category} | {len(results)} | {success:.1%} | "
            f"{sum(result.tool_accuracy for result in results) / len(results):.1%} | {p95:.0f} ms |"
        )
    if summary.provider == "fake":
        interpretation = (
            "This report is generated from the deterministic Fake Provider and measures "
            "the runtime, tool contracts, sandbox, checkpointing, and grading pipeline. "
            "It is a harness regression benchmark, not a model-quality claim."
        )
    else:
        interpretation = (
            f"This report was generated with provider `{summary.provider}` and model "
            f"`{summary.model}`. Model version, endpoint, prompt strategy, and dataset "
            "revision should be kept fixed when comparing results."
        )
    return f"""# Benchmark Report

> {interpretation}

## Run

| Field | Value |
| --- | --- |
| Run ID | `{summary.run_id}` |
| Provider | `{summary.provider}` |
| Model | `{summary.model}` |
| Strategy | `{summary.strategy}` |
| Tasks | {summary.total_tasks} |
| Started | {summary.started_at.isoformat()} |
| Completed | {summary.completed_at.isoformat() if summary.completed_at else ""} |

## Headline Metrics

| Metric | Value |
| --- | ---: |
| Task success rate | {summary.task_success_rate:.1%} |
| Tool accuracy | {summary.tool_accuracy:.1%} |
| P50 latency | {summary.p50_latency_ms:.1f} ms |
| P95 latency | {summary.p95_latency_ms:.1f} ms |
| Prompt tokens | {summary.total_prompt_tokens:,} |
| Completion tokens | {summary.total_completion_tokens:,} |
| Estimated cost | ${summary.total_cost_usd:.4f} |
| Recovery success | {summary.recovery_success_rate:.1%} |

## By Category

| Category | Tasks | Success | Tool accuracy | P95 |
| --- | ---: | ---: | ---: | ---: |
{chr(10).join(rows)}

## Reproducing

```bash
python scripts/build_eval_dataset.py
python scripts/run_benchmark.py --provider {summary.provider} --limit {len(results)}
```

The dataset contains 110 tasks across reasoning, filesystem, coding, database,
memory, recovery, context compaction, browser, GitHub, and mixed-tool workflows.
"""


if __name__ == "__main__":
    asyncio.run(main())
