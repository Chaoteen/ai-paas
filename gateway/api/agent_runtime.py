from __future__ import annotations

import asyncio
import inspect
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from bootstrap.runtime_bootstrap import build_runtime_state
from runtime.execution_context import ExecutionContext

router = APIRouter(tags=["agent-runtime"])


class AgentRunRequest(BaseModel):
    agent_id: str = Field(..., description="Agent or preferred skill identifier")
    input: Any = Field(..., description="User input payload")
    tenant_id: Optional[str] = Field(default=None)
    user_id: Optional[str] = Field(default=None)
    session_id: Optional[str] = Field(default=None)
    workflow_id: Optional[str] = Field(default=None)
    correlation_id: Optional[str] = Field(default=None)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    routing_policy: Optional[str] = Field(default=None)
    required_capability: Optional[str] = Field(default=None)
    requested_capabilities: list[str] = Field(default_factory=list)
    allowed_capabilities: list[str] = Field(default_factory=list)
    secrets_scope: list[str] = Field(default_factory=list)
    workspace_root: Optional[str] = Field(default=None)
    preferred_skill: Optional[str] = Field(default=None)


class AgentRunResponse(BaseModel):
    success: bool
    agent_id: str
    status: str
    execution_id: Optional[str] = None
    output: Any = None
    error: Optional[Dict[str, Any]] = None


_runtime_state: Optional[Dict[str, Any]] = None
_runtime_lock = asyncio.Lock()


async def get_runtime() -> Any:
    global _runtime_state

    if _runtime_state is None:
        async with _runtime_lock:
            if _runtime_state is None:
                _runtime_state = await build_runtime_state()

    runtime = _runtime_state.get("agent_runtime")
    if runtime is None:
        raise RuntimeError("build_runtime_state() returned no 'agent_runtime'")
    return runtime


def _build_input_payload(user_input: Any) -> Dict[str, Any]:
    if isinstance(user_input, dict):
        payload = dict(user_input)
        if "input" not in payload:
            payload["input"] = user_input
        if "text" not in payload and isinstance(payload.get("input"), str):
            payload["text"] = payload["input"]
        return payload

    if isinstance(user_input, str):
        return {
            "input": user_input,
            "text": user_input,
        }

    return {
        "input": user_input,
    }


def _build_execution_context(request: AgentRunRequest) -> ExecutionContext:
    return ExecutionContext(
        task_id=str(uuid.uuid4()),
        tenant_id=request.tenant_id or "dev",
        workflow_id=request.workflow_id or request.session_id,
        correlation_id=request.correlation_id or str(uuid.uuid4()),
        user_id=request.user_id,
        selected_agent_id=request.agent_id,
        required_capability=request.required_capability,
        workspace_root=request.workspace_root,
        requested_capabilities=list(request.requested_capabilities),
        allowed_capabilities=list(request.allowed_capabilities),
        secrets_scope=list(request.secrets_scope),
        metadata={
            **dict(request.metadata),
            "session_id": request.session_id,
            "routing_policy": request.routing_policy,
            "gateway_source": "gateway.api.agent_runtime",
        },
        input_payload=_build_input_payload(request.input),
    )


async def _call_runtime(runtime: Any, request: AgentRunRequest) -> Any:
    execute = getattr(runtime, "execute", None)
    if callable(execute):
        context = _build_execution_context(request)
        preferred_skill = request.preferred_skill or request.agent_id
        if inspect.iscoroutinefunction(execute):
            return await execute(context=context, preferred_skill=preferred_skill)
        return execute(context=context, preferred_skill=preferred_skill)

    for method_name in ("run_agent", "run", "invoke"):
        method = getattr(runtime, method_name, None)
        if callable(method):
            payload = request.model_dump()
            if inspect.iscoroutinefunction(method):
                return await method(**payload)
            return method(**payload)

    raise RuntimeError("No supported runtime execution method found")


def _normalize_response(agent_id: str, raw: Any) -> Dict[str, Any]:
    if raw is None:
        return {
            "success": False,
            "agent_id": agent_id,
            "status": "failed",
            "execution_id": None,
            "output": None,
            "error": {"message": "Runtime returned None"},
        }

    if hasattr(raw, "to_dict") and callable(raw.to_dict):
        raw = raw.to_dict()

    if isinstance(raw, dict):
        status = raw.get("status", "completed")
        error = raw.get("error")
        success = raw.get("success")
        if success is None:
            success = status == "completed" and not error

        normalized_error = error

        if isinstance(error, str):
            normalized_error = {"message": error}

        if isinstance(normalized_error, dict):
            message = str(normalized_error.get("message", ""))
            lowered = message.lower()

            if "preferred skill not found" in lowered:
                normalized_error = {
                    "type": "SkillNotFound",
                    "message": f"Preferred skill '{agent_id}' not found",
                    "hint": "Use an existing bundled/local/workspace skill, e.g. 'echo'",
                }
            elif "skill" in lowered and "not found" in lowered:
                normalized_error = {
                    "type": "SkillNotFound",
                    "message": message,
                    "hint": "Check skills/bundled, ~/.ai-paas/skills, or workspace skill directories",
                }

        return {
            "success": bool(success),
            "agent_id": agent_id,
            "status": status,
            "execution_id": raw.get("execution_id") or raw.get("task_id") or raw.get("id"),
            "output": raw.get("output", raw.get("result")),
            "error": normalized_error,
        }

    return {
        "success": True,
        "agent_id": agent_id,
        "status": "completed",
        "execution_id": None,
        "output": raw,
        "error": None,
    }


@router.post("/agent/run", response_model=AgentRunResponse)
async def run_agent(request: AgentRunRequest):
    try:
        runtime = await get_runtime()
        raw = await _call_runtime(runtime, request)
        return AgentRunResponse(**_normalize_response(request.agent_id, raw))
    except Exception as exc:
        message = str(exc)
        error_type = exc.__class__.__name__

        normalized_error = {
            "type": error_type,
            "message": message,
        }

        lowered = message.lower()

        if "preferred skill" in lowered and "not found" in lowered:
            normalized_error = {
                "type": "SkillNotFound",
                "message": f"Preferred skill '{request.agent_id}' not found",
                "hint": "Use an existing bundled/local/workspace skill, e.g. 'echo'",
            }
        elif "skill" in lowered and "not found" in lowered:
            normalized_error = {
                "type": "SkillNotFound",
                "message": message,
                "hint": "Check skills/bundled, ~/.ai-paas/skills, or workspace skill directories",
            }

        return AgentRunResponse(
            success=False,
            agent_id=request.agent_id,
            status="failed",
            execution_id=None,
            output={},
            error=normalized_error,
        )