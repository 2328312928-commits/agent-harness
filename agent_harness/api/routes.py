from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse

from agent_harness.api.container import AppContainer
from agent_harness.api.schemas import EvalRunRequest, PlaygroundRequest, TaskCreateRequest
from agent_harness.api.security import request_key, require_write_access
from agent_harness.domain.errors import HarnessError
from agent_harness.domain.models import ToolPermission
from agent_harness.tools.base import ToolContext

router = APIRouter(prefix="/api")


def container(request: Request) -> AppContainer:
    return request.app.state.container


@router.get("/health")
async def health(request: Request) -> dict[str, Any]:
    app = container(request)
    mcp_health = [
        {
            "namespace": client.name,
            "initialized": client._initialized,
            "server": client.server_info,
        }
        for client in app.mcp_clients
    ]
    return {
        "status": "ok",
        "app": app.settings.app_name,
        "environment": app.settings.app_env,
        "capabilities": {
            "public_demo_mode": app.settings.public_demo_mode,
            "tool_playground_enabled": app.settings.allow_tool_playground,
            "write_auth_required": bool(app.settings.api_auth_token),
        },
        "providers": app.providers.catalog(),
        "tools": len(app.tools.specs()),
        "mcp": mcp_health,
    }


@router.get("/providers")
async def providers(request: Request) -> dict[str, Any]:
    app = container(request)
    return {"items": app.providers.catalog()}


@router.get("/tools")
async def tools(request: Request) -> dict[str, Any]:
    app = container(request)
    return {"items": [spec.model_dump(mode="json") for spec in app.tools.specs()]}


@router.post("/tools/playground")
async def tool_playground(
    request: Request,
    body: PlaygroundRequest,
    _auth: None = Depends(require_write_access),
) -> dict[str, Any]:
    app = container(request)
    if not app.settings.allow_tool_playground:
        raise HTTPException(status_code=403, detail="Tool playground is disabled")
    context = ToolContext(
        task_id="playground",
        call_id="playground",
        permissions=set(ToolPermission),
        workspace_root=app.settings.resolved_workspace_root,
        metadata={"tool_name": body.tool},
    )
    result = await app.tools.execute(body.tool, body.arguments, context)
    return result.model_dump(mode="json")


@router.post("/tasks", status_code=status.HTTP_202_ACCEPTED)
async def create_task(
    request: Request,
    body: TaskCreateRequest,
    _auth: None = Depends(require_write_access),
) -> dict[str, Any]:
    app = container(request)
    provider = body.provider
    max_steps = body.max_steps
    token_budget = body.token_budget
    metadata = dict(body.metadata)
    if app.settings.public_demo_mode:
        if not await app.rate_limiter.allow(f"task:{request_key(request)}"):
            raise HTTPException(status_code=429, detail="Public demo rate limit exceeded")
        if provider not in {None, "fake"}:
            raise HTTPException(
                status_code=403,
                detail="Public demo only allows the fake provider",
            )
        provider = "fake"
        max_steps = min(max_steps, app.settings.public_demo_max_steps)
        token_budget = min(token_budget, app.settings.public_demo_token_budget)
        metadata["tool_permissions"] = [
            "read",
            "network",
            "database",
            "github",
            "browser",
        ]
    try:
        state = await app.runtime.start(
            body.goal,
            provider=provider,
            model=body.model,
            max_steps=max_steps,
            token_budget=token_budget,
            metadata=metadata,
        )
    except HarnessError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    return state.model_dump(mode="json")


@router.get("/tasks")
async def list_tasks(
    request: Request,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    items = await container(request).repository.list_tasks(limit=limit, offset=offset)
    return {"items": [item.model_dump(mode="json") for item in items]}


@router.get("/tasks/{task_id}")
async def get_task(request: Request, task_id: str) -> dict[str, Any]:
    state = await container(request).repository.get_task(task_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return state.model_dump(mode="json")


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(
    request: Request,
    task_id: str,
    _auth: None = Depends(require_write_access),
) -> dict[str, str]:
    app = container(request)
    if await app.repository.get_task(task_id) is None:
        raise HTTPException(status_code=404, detail="Task not found")
    await app.runtime.cancel(task_id)
    return {"status": "cancelled", "task_id": task_id}


@router.post("/tasks/{task_id}/resume")
async def resume_task(
    request: Request,
    task_id: str,
    _auth: None = Depends(require_write_access),
) -> dict[str, Any]:
    try:
        state = await container(request).runtime.resume(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Task not found") from exc
    return state.model_dump(mode="json")


@router.get("/tasks/{task_id}/checkpoint")
async def latest_checkpoint(request: Request, task_id: str) -> dict[str, Any]:
    checkpoint = await container(request).repository.latest_checkpoint(task_id)
    if checkpoint is None:
        raise HTTPException(status_code=404, detail="Checkpoint not found")
    return checkpoint


@router.get("/tasks/{task_id}/events")
async def list_events(
    request: Request,
    task_id: str,
    after: int = Query(default=0, ge=0),
    limit: int = Query(default=1000, ge=1, le=5000),
) -> dict[str, Any]:
    events = await container(request).repository.list_events(
        task_id,
        after_sequence=after,
        limit=limit,
    )
    return {"items": events}


@router.get("/tasks/{task_id}/events/stream")
async def stream_events(
    request: Request,
    task_id: str,
    after: int = Query(default=0, ge=0),
) -> StreamingResponse:
    app = container(request)

    async def generate() -> AsyncIterator[str]:
        for event in await app.repository.list_events(task_id, after_sequence=after):
            data = json.dumps(event, default=str, ensure_ascii=False)
            yield f"id: {event['sequence']}\ndata: {data}\n\n"
        async for event in app.tracer.bus.subscribe(task_id):
            yield f"data: {json.dumps(event, default=str, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/metrics")
async def metrics(request: Request) -> dict[str, Any]:
    app = container(request)
    database_metrics = await app.repository.metrics()
    eval_runs = await app.repository.list_eval_runs(limit=5)
    return {
        **database_metrics,
        "eval_runs": [run.model_dump(mode="json") for run in eval_runs],
        "sandbox": {
            "backend": app.settings.sandbox_backend,
            "network_disabled": app.settings.sandbox_network_disabled,
        },
    }


@router.get("/evals/tasks")
async def list_eval_tasks(request: Request, limit: int = 300) -> dict[str, Any]:
    tasks = container(request).evals.load_tasks()
    return {"count": len(tasks), "items": [task.model_dump(mode="json") for task in tasks[:limit]]}


@router.post("/evals/runs", status_code=status.HTTP_202_ACCEPTED)
async def create_eval_run(
    request: Request,
    body: EvalRunRequest,
    _auth: None = Depends(require_write_access),
) -> dict[str, str]:
    app = container(request)
    if app.settings.public_demo_mode:
        if not await app.rate_limiter.allow(f"eval:{request_key(request)}"):
            raise HTTPException(status_code=429, detail="Public demo rate limit exceeded")
        if body.provider not in {None, "fake"}:
            raise HTTPException(
                status_code=403,
                detail="Public demo only allows the fake provider",
            )
        body.provider = "fake"
        body.limit = min(body.limit, app.settings.public_demo_eval_limit)
        body.concurrency = min(body.concurrency, 2)
    run_id = await app.evals.start_background(
        provider=body.provider,
        model=body.model,
        strategy=body.strategy,
        categories=body.categories,
        limit=body.limit,
        offset=body.offset,
        concurrency=body.concurrency,
    )
    return {"run_id": run_id, "status": "queued"}


@router.get("/evals/runs")
async def list_eval_runs(request: Request) -> dict[str, Any]:
    runs = await container(request).repository.list_eval_runs()
    return {"items": [run.model_dump(mode="json") for run in runs]}


@router.get("/evals/runs/{run_id}")
async def get_eval_run(request: Request, run_id: str) -> dict[str, Any]:
    runs = await container(request).repository.list_eval_runs(limit=500)
    for run in runs:
        if run.run_id == run_id:
            return run.model_dump(mode="json")
    raise HTTPException(status_code=404, detail="Eval run not found")
