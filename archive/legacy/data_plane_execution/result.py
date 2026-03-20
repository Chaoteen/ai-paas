from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ExecutionResult:
    """
    Data Plane 统一返回结果。

    统一真相字段：
    - ok
    - output
    - error
    - metrics

    为兼容旧代码，额外提供：
    - success -> ok
    - status -> "success" / "error"
    """

    ok: bool
    output: Any = None
    error: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return self.ok

    @property
    def status(self) -> str:
        return "success" if self.ok else "error"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "success": self.success,
            "status": self.status,
            "output": self.output,
            "error": self.error,
            "metrics": self.metrics,
            "metadata": self.metadata,
        }

    @classmethod
    def from_exception(
        cls,
        exc: Exception,
        metrics: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "ExecutionResult":
        return cls(
            ok=False,
            output=None,
            error=str(exc),
            metrics=metrics or {},
            metadata=metadata or {},
        )

    @classmethod
    def success_result(
        cls,
        output: Any = None,
        metrics: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "ExecutionResult":
        return cls(
            ok=True,
            output=output,
            error=None,
            metrics=metrics or {},
            metadata=metadata or {},
        )

    @classmethod
    def error_result(
        cls,
        error: str,
        output: Any = None,
        metrics: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "ExecutionResult":
        return cls(
            ok=False,
            output=output,
            error=error,
            metrics=metrics or {},
            metadata=metadata or {},
        )