from __future__ import annotations

from dotenv import load_dotenv
load_dotenv(override=True)

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel, Field

from bootstrap.runtime_bootstrap import build_runtime_state


class TaskSubmitRequest(BaseModel):
    tenant_id: str
    task_id: str
    workflow_id: str | None = None
    correlation_id: str | None = None
    required_capability: str = Field(..., description="例如 translation / analysis / code_generation")
    input: dict = Field(default_factory=dict)
    metadata: dict = Field(default_factory=dict)


@asynccontextmanager
async def lifespan(app: FastAPI):
    runtime_state = await build_runtime_state()

    app.state.runtime_mode = runtime_state["mode"]
    app.state.db = runtime_state["db"]
    app.state.agent_registry = runtime_state["agent_registry"]
    app.state.control_bus = runtime_state["control_bus"]
    app.state.data_bus = runtime_state["data_bus"]
    app.state.router_worker = runtime_state.get("router_worker")

    router_task = None
    router_worker = app.state.router_worker
    if router_worker is not None:
        router_task = asyncio.create_task(router_worker.start())

    try:
        yield
    finally:
        if router_worker is not None:
            await router_worker.stop()

        if router_task is not None:
            router_task.cancel()
            try:
                await router_task
            except asyncio.CancelledError:
                pass

        db = runtime_state.get("db")
        if db is not None:
            await db.dispose()


app = FastAPI(
    title="AI-PaaS Runtime",
    version="0.2.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "runtime_mode": app.state.runtime_mode,
        "router_worker": app.state.router_worker is not None,
    }


@app.get("/runtime/info")
async def runtime_info():
    return {
        "runtime_mode": app.state.runtime_mode,
        "persistence": "postgres" if app.state.runtime_mode == "postgres" else "memory",
        "router_worker": app.state.router_worker is not None,
    }


@app.post("/runtime/agents/register")
async def register_agent(payload: dict):
    agent = await app.state.agent_registry.register_agent(payload)
    return {
        "ok": True,
        "agent": agent,
    }


@app.post("/runtime/agents/{agent_id}/heartbeat")
async def heartbeat_agent(agent_id: str):
    ok = await app.state.agent_registry.heartbeat(agent_id)
    return {
        "ok": ok,
        "agent_id": agent_id,
    }


@app.get("/runtime/agents")
async def list_agents(tenant_id: str | None = None):
    agents = await app.state.agent_registry.list_agents(tenant_id=tenant_id)
    return {
        "ok": True,
        "items": agents,
        "count": len(agents),
    }


@app.get("/runtime/control-events")
async def list_control_events(
    event_type: str | None = None,
    limit: int = 100,
):
    items = await app.state.control_bus.list_events(
        event_type=event_type,
        limit=limit,
    )
    return {
        "ok": True,
        "items": items,
        "count": len(items),
    }


@app.get("/runtime/data-events")
async def list_data_events(
    event_type: str | None = None,
    limit: int = 100,
):
    items = await app.state.data_bus.list_events(
        event_type=event_type,
        limit=limit,
    )
    return {
        "ok": True,
        "items": items,
        "count": len(items),
    }


@app.post("/runtime/tasks/submit")
async def submit_task(req: TaskSubmitRequest):
    event = await app.state.data_bus.publish(
        event_type="task.submitted",
        payload={
            "input": req.input,
            "metadata": req.metadata,
            "required_capability": req.required_capability,
        },
        source="runtime.api",
        tenant_id=req.tenant_id,
        correlation_id=req.correlation_id,
        task_id=req.task_id,
        workflow_id=req.workflow_id,
    )
    return {
        "ok": True,
        "event": event,
    }