from __future__ import annotations

from typing import Dict, List, Optional

from control_plane.agent_admission import AgentAdmission, AdmissionDecision
from control_plane.agent_manifest import AgentManifest, AgentRecord


class AgentRegistry:
    """
    第二轮版本：内存注册中心
    后续第三轮/第四轮再落 PostgreSQL。
    """

    def __init__(self, admission: Optional[AgentAdmission] = None):
        self._records: Dict[str, AgentRecord] = {}
        self._name_index: Dict[str, str] = {}
        self.admission = admission or AgentAdmission()

    def register(self, manifest: AgentManifest) -> AgentRecord:
        decision: AdmissionDecision = self.admission.evaluate(manifest)
        if not decision.allow:
            raise ValueError(decision.reason or "AGENT_ADMISSION_DENIED")

        existing_id = self._name_index.get(manifest.name)
        if existing_id and existing_id in self._records:
            record = self._records[existing_id]
            record.manifest = manifest
            record.status = "online"
            record.touch()
            return record

        record = AgentRecord.new(manifest)
        record.touch()
        self._records[record.agent_id] = record
        self._name_index[manifest.name] = record.agent_id
        return record

    def heartbeat(self, agent_id: str) -> AgentRecord:
        record = self._records.get(agent_id)
        if not record:
            raise KeyError(f"AGENT_NOT_FOUND: {agent_id}")

        record.status = "online"
        record.touch()
        return record

    def list_agents(self) -> List[AgentRecord]:
        return sorted(
            self._records.values(),
            key=lambda r: (r.manifest.name, r.created_at),
        )

    def get_agent(self, agent_id: str) -> Optional[AgentRecord]:
        return self._records.get(agent_id)