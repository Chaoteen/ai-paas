from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from bootstrap.runtime_bootstrap import build_runtime_state


class AgentRegisterRequest(BaseModel):
    id: str
    tenant_id: str
    name: str
    version: str = "1.0.0"
    status: str = "healthy"
    capabilities: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TaskSubmitRequest(BaseModel):
    tenant_id: str
    task_id: str
    workflow_id: Optional[str] = None
    correlation_id: Optional[str] = None
    required_capability: str
    input: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


@asynccontextmanager
async def lifespan(app: FastAPI):
    runtime_state = await build_runtime_state()

    app.state.runtime_state = runtime_state
    app.state.agent_registry = runtime_state["agent_registry"]
    app.state.control_bus = runtime_state["control_bus"]
    app.state.data_bus = runtime_state["data_bus"]
    app.state.agent_runtime = runtime_state.get("agent_runtime")
    app.state.state_store = runtime_state.get("state_store")
    app.state.idempotency_store = runtime_state.get("idempotency_store")
    app.state.trace_store = runtime_state.get("trace_store")
    app.state.runtime_metrics = runtime_state.get("runtime_metrics")
    app.state.router_worker = runtime_state.get("router_worker")
    app.state.agent_worker = runtime_state.get("agent_worker")

    background_tasks = []

    if app.state.router_worker is not None:
        background_tasks.append(asyncio.create_task(app.state.router_worker.start()))
    if app.state.agent_worker is not None:
        background_tasks.append(asyncio.create_task(app.state.agent_worker.start()))

    try:
        yield
    finally:
        if app.state.router_worker is not None:
            await app.state.router_worker.stop()
        if app.state.agent_worker is not None:
            await app.state.agent_worker.stop()

        for task in background_tasks:
            task.cancel()
        if background_tasks:
            await asyncio.gather(*background_tasks, return_exceptions=True)

        db = runtime_state.get("db")
        if db is not None:
            await db.dispose()


app = FastAPI(title="AI-PaaS Runtime", lifespan=lifespan)


@app.get("/health")
async def health() -> Dict[str, Any]:
    runtime_state = app.state.runtime_state
    return {
        "status": "ok",
        "runtime_mode": runtime_state["mode"],
        "router_worker": app.state.router_worker is not None,
        "agent_worker": app.state.agent_worker is not None,
    }


@app.get("/runtime/info")
async def runtime_info() -> Dict[str, Any]:
    runtime_state = app.state.runtime_state
    return {
        "ok": True,
        "mode": runtime_state["mode"],
        "has_agent_runtime": app.state.agent_runtime is not None,
        "has_state_store": app.state.state_store is not None,
        "has_idempotency_store": app.state.idempotency_store is not None,
        "has_trace_store": app.state.trace_store is not None,
        "has_runtime_metrics": app.state.runtime_metrics is not None,
        "router_worker": app.state.router_worker is not None,
        "agent_worker": app.state.agent_worker is not None,
    }


@app.post("/runtime/agents/register")
async def register_agent(req: AgentRegisterRequest) -> Dict[str, Any]:
    agent_registry = app.state.agent_registry

    agent = await agent_registry.register_agent(
        {
            "id": req.id,
            "tenant_id": req.tenant_id,
            "name": req.name,
            "version": req.version,
            "status": req.status,
            "capabilities": req.capabilities,
            "metadata": req.metadata,
        }
    )
    return {
        "ok": True,
        "agent": agent,
    }


@app.get("/runtime/agents")
async def list_agents(
    tenant_id: Optional[str] = Query(default=None),
) -> Dict[str, Any]:
    items = await app.state.agent_registry.list_agents(tenant_id=tenant_id)
    return {
        "ok": True,
        "items": items,
        "count": len(items),
    }


@app.post("/runtime/tasks/submit")
async def submit_task(req: TaskSubmitRequest) -> Dict[str, Any]:
    if app.state.state_store is not None:
        existing = await app.state.state_store.get_task(req.task_id)
        if existing is not None:
            return {
                "ok": True,
                "deduplicated": True,
                "event": None,
                "task_state": existing.to_dict(),
            }

    event = await app.state.data_bus.publish(
        event_type="task.submitted",
        source="runtime.api",
        tenant_id=req.tenant_id,
        correlation_id=req.correlation_id,
        task_id=req.task_id,
        workflow_id=req.workflow_id,
        payload={
            "required_capability": req.required_capability,
            "input": req.input,
            "metadata": req.metadata,
        },
    )

    if app.state.state_store is not None:
        task_state = await app.state.state_store.create_task(
            task_id=req.task_id,
            tenant_id=req.tenant_id,
            workflow_id=req.workflow_id,
            correlation_id=req.correlation_id,
            input_payload=req.input,
            metadata=req.metadata,
        )
        return {
            "ok": True,
            "deduplicated": False,
            "event": event,
            "task_state": task_state.to_dict(),
        }

    return {
        "ok": True,
        "deduplicated": False,
        "event": event,
    }


@app.get("/runtime/data-events")
async def list_data_events(
    event_type: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> Dict[str, Any]:
    items = await app.state.data_bus.list_events(
        event_type=event_type,
        limit=limit,
    )
    return {
        "ok": True,
        "items": items,
        "count": len(items),
    }


@app.get("/runtime/control-events")
async def list_control_events(
    event_type: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> Dict[str, Any]:
    items = await app.state.control_bus.list_events(
        event_type=event_type,
        limit=limit,
    )
    return {
        "ok": True,
        "items": items,
        "count": len(items),
    }


@app.get("/runtime/tasks/{task_id}/state")
async def get_task_state(task_id: str) -> Dict[str, Any]:
    state_store = app.state.state_store
    if state_store is None:
        raise HTTPException(status_code=503, detail="state_store_not_configured")

    task_state = await state_store.get_task(task_id)
    if task_state is None:
        raise HTTPException(status_code=404, detail="task_state_not_found")

    return {
        "ok": True,
        "item": task_state.to_dict(),
    }


@app.get("/runtime/task-states")
async def list_task_states(
    tenant_id: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
) -> Dict[str, Any]:
    state_store = app.state.state_store
    if state_store is None:
        raise HTTPException(status_code=503, detail="state_store_not_configured")

    items = await state_store.list_tasks(
        tenant_id=tenant_id,
        status=status,
    )
    return {
        "ok": True,
        "items": [x.to_dict() for x in items],
        "count": len(items),
    }


@app.get("/runtime/workflows/{workflow_id}/state")
async def get_workflow_state(workflow_id: str) -> Dict[str, Any]:
    state_store = app.state.state_store
    if state_store is None:
        raise HTTPException(status_code=503, detail="state_store_not_configured")

    workflow_state = await state_store.get_workflow(workflow_id)
    if workflow_state is None:
        raise HTTPException(status_code=404, detail="workflow_state_not_found")

    return {
        "ok": True,
        "item": workflow_state.to_dict(),
    }


@app.get("/runtime/trace/{task_id}")
async def get_trace(task_id: str) -> Dict[str, Any]:
    trace_store = app.state.trace_store
    if trace_store is None:
        raise HTTPException(status_code=503, detail="trace_store_not_configured")

    items = await trace_store.get_trace(task_id)
    return {
        "ok": True,
        "items": [x.to_dict() for x in items],
        "count": len(items),
    }


@app.get("/runtime/metrics")
async def get_metrics() -> Dict[str, Any]:
    runtime_metrics = app.state.runtime_metrics
    if runtime_metrics is None:
        raise HTTPException(status_code=503, detail="runtime_metrics_not_configured")

    snapshot = await runtime_metrics.snapshot()
    return {
        "ok": True,
        "items": snapshot,
    }