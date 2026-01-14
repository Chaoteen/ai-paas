# ai-os/data_plane/result.py
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class ExecutionResult:
    """
    Data Plane 统一返回结构（同步）
    """
    ok: bool
    envelope_id: str
    request_id: str
    tenant_id: str

    output: Optional[Any] = None
    error: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)

    started_at: float = 0.0
    finished_at: float = field(default_factory=lambda: time.time())

    @staticmethod
    def success(
        *,
        envelope_id: str,
        request_id: str,
        tenant_id: str,
        output: Any,
        metrics: Optional[Dict[str, Any]] = None,
        started_at: float = 0.0,
    ) -> "ExecutionResult":
        return ExecutionResult(
            ok=True,
            envelope_id=envelope_id,
            request_id=request_id,
            tenant_id=tenant_id,
            output=output,
            error=None,
            metrics=metrics or {},
            started_at=started_at,
        )

    @staticmethod
    def fail(
        *,
        envelope_id: str,
        request_id: str,
        tenant_id: str,
        error: str,
        metrics: Optional[Dict[str, Any]] = None,
        started_at: float = 0.0,
    ) -> "ExecutionResult":
        return ExecutionResult(
            ok=False,
            envelope_id=envelope_id,
            request_id=request_id,
            tenant_id=tenant_id,
            output=None,
            error=error,
            metrics=metrics or {},
            started_at=started_at,
        )
