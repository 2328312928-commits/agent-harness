from __future__ import annotations

import asyncio
from pathlib import Path

import typer
import uvicorn

from agent_harness.api.container import AppContainer
from agent_harness.config import get_settings

app = typer.Typer(
    name="agent-harness",
    help="Run and evaluate the Agent Harness runtime.",
    no_args_is_help=True,
)


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", help="Bind host."),
    port: int = typer.Option(8000, help="Bind port."),
    reload: bool = typer.Option(False, help="Enable development reload."),
) -> None:
    """Start the FastAPI service."""
    uvicorn.run(
        "agent_harness.api.main:app",
        host=host,
        port=port,
        reload=reload,
    )


@app.command()
def task(
    goal: str = typer.Argument(..., help="Task goal."),
    provider: str = typer.Option("fake", help="Provider name."),
    max_steps: int = typer.Option(20, min=1, max=100),
) -> None:
    """Run one task to completion from the CLI."""
    asyncio.run(_run_task(goal, provider, max_steps))


@app.command()
def evaluate(
    limit: int = typer.Option(110, min=1, max=300),
    categories: str = typer.Option("", help="Comma-separated category filter."),
    provider: str = typer.Option("fake"),
    strategy: str = typer.Option("plan-and-execute"),
    concurrency: int = typer.Option(3, min=1, max=20),
    output: Path | None = typer.Option(None, help="Optional JSON result path."),
) -> None:
    """Run the benchmark suite."""
    asyncio.run(
        _evaluate(
            limit=limit,
            categories=[item for item in categories.split(",") if item],
            provider=provider,
            strategy=strategy,
            concurrency=concurrency,
            output=output,
        )
    )


@app.command("mcp-demo")
def mcp_demo() -> None:
    """Run the bundled MCP stdio server."""
    from agent_harness.mcp.demo_server import main

    main()


async def _run_task(goal: str, provider: str, max_steps: int) -> None:
    container = AppContainer(get_settings())
    await container.startup()
    try:
        state = await container.runtime.start(goal, provider=provider, max_steps=max_steps)
        while True:
            current = await container.repository.get_task(state.task_id)
            if current and current.status.value in {
                "completed",
                "partial",
                "failed",
                "cancelled",
            }:
                typer.echo(current.model_dump_json(indent=2))
                break
            await asyncio.sleep(0.25)
    finally:
        await container.shutdown()


async def _evaluate(
    *,
    limit: int,
    categories: list[str],
    provider: str,
    strategy: str,
    concurrency: int,
    output: Path | None,
) -> None:
    container = AppContainer(get_settings())
    await container.startup()
    try:
        tasks = [
            item
            for item in container.evals.load_tasks()
            if not categories or item.category in set(categories)
        ][:limit]
        summary = await container.evals.run(
            tasks,
            provider=provider,
            model=None,
            strategy=strategy,
            concurrency=concurrency,
            run_id=f"eval_cli_{len(tasks)}",
        )
        payload = summary.model_dump_json(indent=2)
        typer.echo(payload)
        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(payload, encoding="utf-8")
    finally:
        await container.shutdown()


if __name__ == "__main__":
    app()

