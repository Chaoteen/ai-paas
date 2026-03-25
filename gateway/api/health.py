from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from runtime.preflight import collect_runtime_preflight

router = APIRouter()


@router.get("/health")
async def health() -> JSONResponse:
    report = await collect_runtime_preflight()
    status_code = 200 if report["ok"] else 503
    return JSONResponse(status_code=status_code, content=report)
