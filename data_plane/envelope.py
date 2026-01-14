# ai-os/data_plane/envelope.py
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class ExecutionEnvelope:
    """
    Data Plane 冻结信封：Control Plane -> Data Plane

    设计原则：
    - Data Plane 不修改它（只读）
    - 多租户/权限核心要素显式字段（语义清晰）
    - 允许 context 作为只读扩展（例如 capabilities / tracing）
    """
    envelope_id: str
    request_id: str
    tenant_id: str

    # ABAC 核心要素（显式）
    subject: Dict[str, Any]
    action: str
    resource: Dict[str, Any]
    environment: Dict[str, Any]

    # 执行目标：agent / model / promptflow
    target_type: str  # "agent" | "model" | "promptflow"
    target: str       # e.g. "agent.default" | "deepseek-r1-latest" | "pf.default"

    # 执行输入
    payload: Dict[str, Any]

    # 只读扩展信息（例如 policy capabilities / tracing）
    context: Dict[str, Any] = field(default_factory=dict)

    created_at: float = field(default_factory=lambda: time.time())

    @staticmethod
    def new(
        *,
        request_id: str,
        tenant_id: str,
        subject: Dict[str, Any],
        action: str,
        resource: Dict[str, Any],
        environment: Dict[str, Any],
        target_type: str,
        target: str,
        payload: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        envelope_id: Optional[str] = None,
    ) -> "ExecutionEnvelope":
        return ExecutionEnvelope(
            envelope_id=envelope_id or f"env_{uuid.uuid4().hex}",
            request_id=request_id,
            tenant_id=tenant_id,
            subject=subject,
            action=action,
            resource=resource,
            environment=environment,
            target_type=target_type,
            target=target,
            payload=payload,
            context=context or {},
        )
