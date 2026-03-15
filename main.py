from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from bootstrap.runtime_bootstrap import build_runtime_state


@asynccontextmanager
async def lifespan(app: FastAPI):
    runtime_state = await build_runtime_state()

    app.state.runtime_mode = runtime_state["mode"]
    app.state.db = runtime_state["db"]
    app.state.agent_registry = runtime_state["agent_registry"]
    app.state.control_bus = runtime_state["control_bus"]
    app.state.data_bus = runtime_state["data_bus"]

    yield

    db = runtime_state.get("db")
    if db is not None:
        await db.dispose()


app = FastAPI(
    title="AI-PaaS Runtime",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "runtime_mode": app.state.runtime_mode,
    }


@app.get("/runtime/info")
async def runtime_info():
    return {
        "runtime_mode": app.state.runtime_mode,
        "persistence": "postgres" if app.state.runtime_mode == "postgres" else "memory",
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
    agent_id: str | None = None,
    limit: int = 100,
):
    events = await app.state.control_bus.list_events(
        event_type=event_type,
        agent_id=agent_id,
        limit=limit,
    )
    return {
        "ok": True,
        "items": events,
        "count": len(events),
    }


@app.post("/runtime/data-events/publish")
async def publish_data_event(payload: dict):
    event = await app.state.data_bus.publish(
        event_type=payload["event_type"],
        task_id=payload.get("task_id"),
        execution_id=payload.get("execution_id"),
        tenant_id=payload.get("tenant_id"),
        payload=payload.get("payload", {}),
    )
    return {
        "ok": True,
        "event": event,
    }


@app.get("/runtime/data-events")
async def list_data_events(
    event_type: str | None = None,
    task_id: str | None = None,
    execution_id: str | None = None,
    limit: int = 100,
):
    events = await app.state.data_bus.list_events(
        event_type=event_type,
        task_id=task_id,
        execution_id=execution_id,
        limit=limit,
    )
    return {
        "ok": True,
        "items": events,
        "count": len(events),
    }