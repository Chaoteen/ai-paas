from dataclasses import asdict
from fastapi import APIRouter, Depends

from gateway.core.auth import UserContext, get_current_user
from gateway.ui_bootstrap import build_bootstrap

router = APIRouter(tags=["ui"])


@router.get("/ui/bootstrap")
async def ui_bootstrap(user: UserContext = Depends(get_current_user)):
    user_ctx = asdict(user)
    tenant_ctx = {
        "tenant_id": user.tenant_id,
    }
    return await build_bootstrap(
        user_ctx=user_ctx,
        tenant_ctx=tenant_ctx,
    )