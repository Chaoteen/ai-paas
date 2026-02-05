from fastapi import APIRouter, Depends
from gateway.core.auth import get_current_user, UserContext
from gateway.ui_bootstrap import build_bootstrap

router = APIRouter()

@router.get("/api/ui/bootstrap")
async def ui_bootstrap(user: UserContext = Depends(get_current_user)):
    return await build_bootstrap(user)
