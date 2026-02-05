from fastapi import FastAPI, Depends, Request
from fastapi.responses import Response
import httpx

from gateway.ui_bootstrap import build_bootstrap
from gateway.api.ui import router as ui_router
from gateway.api.health import router as health_router

app = FastAPI()


# ---------------------------------------------------------------------
# Mock ctx (后面你会换成 JWT / tenant 解析)
# ---------------------------------------------------------------------
def get_user_ctx():
    return {"user_id": "dev", "tenant_id": "dev", "is_admin": True, "display_name": "dev"}


def get_tenant_ctx():
    return {"tenant_id": "dev"}


# ---------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------
app.include_router(health_router, prefix="/api")
app.include_router(ui_router, prefix="/api")


# ---------------------------------------------------------------------
# UI Bootstrap endpoint
# ---------------------------------------------------------------------
@app.get("/api/ui/bootstrap")
async def ui_bootstrap(
    user_ctx=Depends(get_user_ctx),
    tenant_ctx=Depends(get_tenant_ctx),
):
    return await build_bootstrap(user_ctx, tenant_ctx)


# ---------------------------------------------------------------------
# External iframe proxy (Flowise)
# ---------------------------------------------------------------------
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
        headers={
            k: v
            for k, v in resp.headers.items()
            if k.lower() not in ("content-encoding", "transfer-encoding", "connection")
        },
        media_type=resp.headers.get("content-type"),
    )
