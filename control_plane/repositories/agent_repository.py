from __future__ import annotations

from typing import Dict, List, Optional

from control_plane.agent_manifest import AgentRecord


class AgentRepository:
    """
    Agent Repository 抽象基类。
    后续 PostgreSQL 版本直接实现同一接口。
    """

    def save(self, record: AgentRecord) -> AgentRecord:
        raise NotImplementedError

    def get(self, agent_id: str) -> Optional[AgentRecord]:
        raise NotImplementedError

    def get_by_name(self, name: str) -> Optional[AgentRecord]:
        raise NotImplementedError

    def list_all(self) -> List[AgentRecord]:
        raise NotImplementedError


class InMemoryAgentRepository(AgentRepository):
    """
    第四轮先提供内存仓储实现。
    """

    def __init__(self):
        self._records: Dict[str, AgentRecord] = {}
        self._name_index: Dict[str, str] = {}

    def save(self, record: AgentRecord) -> AgentRecord:
        self._records[record.agent_id] = record
        self._name_index[record.manifest.name] = record.agent_id
        return record

    def get(self, agent_id: str) -> Optional[AgentRecord]:
        return self._records.get(agent_id)

    def get_by_name(self, name: str) -> Optional[AgentRecord]:
        agent_id = self._name_index.get(name)
        if not agent_id:
            return None
        return self._records.get(agent_id)

    def list_all(self) -> List[AgentRecord]:
        return sorted(
            self._records.values(),
            key=lambda r: (r.manifest.name, r.created_at),
        )