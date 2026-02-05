from fastapi import FastAPI
from gateway.ui_bootstrap import build_bootstrap

from gateway.api.ui import router as ui_router
from gateway.api.health import router as health_router

\1
# Mount API routers
app.include_router(ui_router, prefix=\"/api\")
@app.get("/api/ui/bootstrap")
async def ui_bootstrap(user_ctx=Depends(get_user_ctx), tenant_ctx=Depends(get_tenant_ctx)):
    return await build_bootstrap(user_ctx, tenant_ctx)
# ---------------------------------------------------------------------
# UI Bootstrap endpoint (added by patch)
# NOTE: Replace get_user_ctx/get_tenant_ctx with your existing Depends hooks.
# ---------------------------------------------------------------------
try:
    from fastapi import Depends
except Exception:
    Depends = None  # type: ignore

def get_user_ctx():
    # TODO: wire to your existing JWT claims extraction
    # should return dict like: {user_id, tenant_id, is_admin, display_name, ...}
    return {"user_id": "dev", "tenant_id": "dev", "is_admin": True, "display_name": "dev"}

def get_tenant_ctx():
    # TODO: wire to your tenant resolver
    return {"tenant_id": "dev"}

app.include_router(health_router)
app.include_router(ui_router)
# ---- External iframe proxies (temporary, minimal) ----
from fastapi import Request
from fastapi.responses import Response
import httpx

FLOWISE_BASE = "http://127.0.0.1:3000"

@app.api_route("/external/flowise/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
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
        headers={k: v for k, v in resp.headers.items()
                 if k.lower() not in ("content-encoding", "transfer-encoding", "connection")},
        media_type=resp.headers.get("content-type"),
    )
