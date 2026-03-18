from fastapi import FastAPI, Depends, Request
from fastapi.responses import Response
import httpx

from gateway.ui_bootstrap import build_bootstrap
from gateway.api.ui import router as ui_router
from gateway.api.health import router as health_router
from gateway.api.agent_runtime import router as agent_runtime_router
from gateway.api.generation import router as generation_router
from gateway.api.tasks import router as tasks_router
app = FastAPI()


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