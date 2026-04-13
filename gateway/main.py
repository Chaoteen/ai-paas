from __future__ import annotations

from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, Request
from fastapi.responses import Response

from gateway.api.agent_runtime import router as agent_runtime_router
from gateway.api.generation import router as generation_router
from gateway.api.health import router as health_router
from gateway.api.recording_sessions import router as recording_sessions_router
from gateway.api.skill_drafts import router as skill_drafts_router
from gateway.api.tasks import router as tasks_router
from gateway.api.ui import router as ui_router
from gateway.api.workflow_definitions import router as workflow_definitions_router
from gateway.api.workflow_executions import router as workflow_executions_router
from gateway.api.workflow_products import router as workflow_products_router
from gateway.ui_bootstrap import build_bootstrap
from persistence.db import get_async_engine, get_async_session_factory
from runtime.queue.task_store import shutdown_task_store_runtime_state


@asynccontextmanager
async def lifespan(_: FastAPI):
    get_async_engine()
    get_async_session_factory()
    try:
        yield
    finally:
        await shutdown_task_store_runtime_state()


app = FastAPI(lifespan=lifespan)


def get_user_ctx():
    return {
        "user_id": "dev",
        "tenant_id": "dev",
        "is_admin": True,
        "display_name": "dev",
    }


def get_tenant_ctx():
    return {"tenant_id": "dev"}


app.include_router(health_router, prefix="/api")
app.include_router(ui_router, prefix="/api")
app.include_router(agent_runtime_router, prefix="/api/v1")
app.include_router(generation_router, prefix="/api/v1")
app.include_router(tasks_router, prefix="/api/v1")
app.include_router(workflow_definitions_router, prefix="/api/v1")
app.include_router(workflow_executions_router, prefix="/api/v1")
app.include_router(workflow_products_router, prefix="/api/v1")
app.include_router(recording_sessions_router, prefix="/api/v1")
app.include_router(skill_drafts_router, prefix="/api/v1")


@app.get("/api/ui/bootstrap-legacy")
async def ui_bootstrap_legacy(
    user_ctx=Depends(get_user_ctx),
    tenant_ctx=Depends(get_tenant_ctx),
):
    return await build_bootstrap(user_ctx, tenant_ctx)


FLOWISE_BASE = "http://127.0.0.1:3000"


@app.api_route(
    "/external/flowise/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
)
async def proxy_flowise(path: str, request: Request):
    url = f"{FLOWISE_BASE}/{path}"
    async with httpx.AsyncClient(follow_redirects=True) as client:
        resp = await client.request(
            method=request.method,
            url=url,
            headers={k: v for k, v in request.headers.items() if k.lower() != "host"},
            content=await request.body(),
        )
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=dict(resp.headers),
    )