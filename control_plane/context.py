# ai-os/control_plane/context.py

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional
import uuid


@dataclass(frozen=True)
class ExecutionContext:
    """
    冻结的执行上下文（Control Plane 内部标准结构）
    约束：
    - 下游只读（Data Plane / adapters 不允许修改）
    - ABAC 要素完整：subject / action / resource / environment / input
    """

    # 追踪
    request_id: str

    # ABAC 四要素 + 输入
    subject: Dict[str, Any]                 # {type,id,tenant_id,attributes...}
    action: str                              # e.g. "prompt.execute"
    resource: Dict[str, Any]                # {type,id,attributes...}
    environment: Dict[str, Any]             # {region,compliance,timestamp,source...}
    input: Dict[str, Any]                   # 业务输入（如 user_message 等）

    # 可选扩展字段（仍视作冻结上下文的一部分，只读）
    extensions: Dict[str, Any] = field(default_factory=dict)

    @property
    def tenant_id(self) -> Optional[str]:
        return (self.subject or {}).get("tenant_id")

    @staticmethod
    def new(
        *,
        subject: Dict[str, Any],
        action: str,
        resource: Dict[str, Any],
        environment: Dict[str, Any],
        input_payload: Dict[str, Any],
        request_id: Optional[str] = None,
        extensions: Optional[Dict[str, Any]] = None,
    ) -> "ExecutionContext":
        rid = request_id or f"req_{uuid.uuid4().hex}"
        env = dict(environment or {})
        env.setdefault("timestamp", datetime.utcnow().isoformat())

        return ExecutionContext(
            request_id=rid,
            subject=subject or {},
            action=action or "prompt.execute",
            resource=resource or {"type": "prompt", "id": "default", "attributes": {}},
            environment=env,
            input=input_payload or {},
            extensions=extensions or {},
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "subject": self.subject,
            "action": self.action,
            "resource": self.resource,
            "environment": self.environment,
            "input": self.input,
            "extensions": self.extensions,
        }
