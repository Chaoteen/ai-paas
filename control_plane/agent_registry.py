from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse


class InMemoryAgentRepository:
    """
    默认内存版 Agent 仓库
    """

    def __init__(self):
        self._agents: dict[str, dict[str, Any]] = {}

    async def save(self, agent: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(timezone.utc)

        existing = self._agents.get(agent["id"])
        if existing:
            existing.update(agent)
            existing["updated_at"] = now
            self._agents[agent["id"]] = existing
            return existing

        record = {
            **agent,
            "created_at": agent.get("created_at", now),
            "updated_at": now,
        }
        self._agents[agent["id"]] = record
        return record

    async def get(self, agent_id: str) -> dict[str, Any] | None:
        return self._agents.get(agent_id)

    async def list(self, tenant_id: str | None = None) -> list[dict[str, Any]]:
        agents = list(self._agents.values())
        if tenant_id:
            agents = [a for a in agents if a.get("tenant_id") == tenant_id]
        return agents

    async def update_status(self, agent_id: str, status: str) -> bool:
        agent = self._agents.get(agent_id)
        if not agent:
            return False
        agent["status"] = status
        agent["updated_at"] = datetime.now(timezone.utc)
        return True

    async def touch_heartbeat(self, agent_id: str, at: datetime | None = None) -> bool:
        agent = self._agents.get(agent_id)
        if not agent:
            return False
        agent["heartbeat_at"] = at or datetime.now(timezone.utc)
        agent["updated_at"] = datetime.now(timezone.utc)
        return True

    async def delete(self, agent_id: str) -> bool:
        return self._agents.pop(agent_id, None) is not None


class AgentRegistry:
    """
    Agent 注册中心

    支持：
    - 默认内存仓库
    - 注入 PostgreSQL repository
    - 注入 ControlBus，自动发布控制事件
    """

    def __init__(self, repository=None, control_bus=None):
        self._repository = repository or InMemoryAgentRepository()
        self._control_bus = control_bus

    async def register_agent(self, agent: dict[str, Any]) -> dict[str, Any]:
        self._validate_agent(agent)

        normalized = {
            "id": agent["id"],
            "name": agent["name"],
            "version": agent.get("version", "1.0.0"),
            "status": agent.get("status", "active"),
            "tenant_id": agent.get("tenant_id"),
            "capabilities": agent.get("capabilities", {}),
            "metadata": agent.get("metadata", {}),
            "heartbeat_at": agent.get("heartbeat_at"),
        }

        if "endpoint" in agent:
            normalized["metadata"]["endpoint"] = agent["endpoint"]

        saved = await self._repository.save(normalized)

        if self._control_bus:
            await self._control_bus.publish(
                event_type="agent.registered",
                agent_id=saved["id"],
                tenant_id=saved.get("tenant_id"),
                payload={
                    "name": saved["name"],
                    "version": saved["version"],
                    "status": saved["status"],
                },
            )

        return saved

    async def heartbeat(self, agent_id: str) -> bool:
        ok = await self._repository.touch_heartbeat(agent_id)
        if not ok:
            return False

        agent = await self._repository.get(agent_id)
        if self._control_bus and agent:
            await self._control_bus.publish(
                event_type="agent.heartbeat",
                agent_id=agent_id,
                tenant_id=agent.get("tenant_id"),
                payload={"heartbeat": "ok"},
            )
        return True

    async def update_status(self, agent_id: str, status: str) -> bool:
        ok = await self._repository.update_status(agent_id, status)
        if not ok:
            return False

        agent = await self._repository.get(agent_id)
        if self._control_bus and agent:
            await self._control_bus.publish(
                event_type="agent.status.changed",
                agent_id=agent_id,
                tenant_id=agent.get("tenant_id"),
                payload={"status": status},
            )
        return True

    async def get_agent(self, agent_id: str) -> dict[str, Any] | None:
        return await self._repository.get(agent_id)

    async def list_agents(self, tenant_id: str | None = None) -> list[dict[str, Any]]:
        return await self._repository.list(tenant_id=tenant_id)

    @staticmethod
    def _validate_agent(agent: dict[str, Any]) -> None:
        required_fields = ["id", "name"]
        for field in required_fields:
            if field not in agent or not agent[field]:
                raise ValueError(f"Missing required field: {field}")

        endpoint = agent.get("endpoint")
        if endpoint:
            parsed = urlparse(endpoint)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError(f"Invalid agent endpoint: {endpoint}")