from __future__ import annotations

from typing import Dict, List, Optional

from control_plane.agent_admission import AgentAdmission, AdmissionDecision
from control_plane.agent_manifest import AgentManifest, AgentRecord
from control_plane.control_bus import ControlBus
from control_plane.control_events import ControlEvent


class AgentRegistry:
    """
    第三轮版本：
    - 内存注册中心
    - 控制事件发布
    """

    def __init__(
        self,
        admission: Optional[AgentAdmission] = None,
        control_bus: Optional[ControlBus] = None,
    ):
        self._records: Dict[str, AgentRecord] = {}
        self._name_index: Dict[str, str] = {}
        self.admission = admission or AgentAdmission()
        self.control_bus = control_bus or ControlBus()

    def register(self, manifest: AgentManifest) -> AgentRecord:
        decision: AdmissionDecision = self.admission.evaluate(manifest)
        if not decision.allow:
            raise ValueError(decision.reason or "AGENT_ADMISSION_DENIED")

        existing_id = self._name_index.get(manifest.name)
        if existing_id and existing_id in self._records:
            record = self._records[existing_id]
            previous_status = record.status

            record.manifest = manifest
            record.status = "online"
            record.touch()

            self.control_bus.publish(
                ControlEvent.new(
                    event_type="agent.registered",
                    aggregate_type="agent",
                    aggregate_id=record.agent_id,
                    payload={
                        "agent_id": record.agent_id,
                        "name": record.manifest.name,
                        "version": record.manifest.version,
                        "vendor": record.manifest.vendor,
                        "endpoint": record.manifest.endpoint,
                        "capabilities": list(record.manifest.capabilities),
                        "supported_models": list(record.manifest.supported_models),
                    },
                    metadata={
                        "mode": "update",
                    },
                )
            )

            if previous_status != record.status:
                self.control_bus.publish(
                    ControlEvent.new(
                        event_type="agent.status.changed",
                        aggregate_type="agent",
                        aggregate_id=record.agent_id,
                        payload={
                            "agent_id": record.agent_id,
                            "before": previous_status,
                            "after": record.status,
                        },
                    )
                )

            return record

        record = AgentRecord.new(manifest)
        record.touch()
        self._records[record.agent_id] = record
        self._name_index[manifest.name] = record.agent_id

        self.control_bus.publish(
            ControlEvent.new(
                event_type="agent.registered",
                aggregate_type="agent",
                aggregate_id=record.agent_id,
                payload={
                    "agent_id": record.agent_id,
                    "name": record.manifest.name,
                    "version": record.manifest.version,
                    "vendor": record.manifest.vendor,
                    "endpoint": record.manifest.endpoint,
                    "capabilities": list(record.manifest.capabilities),
                    "supported_models": list(record.manifest.supported_models),
                },
                metadata={
                    "mode": "create",
                },
            )
        )

        self.control_bus.publish(
            ControlEvent.new(
                event_type="agent.status.changed",
                aggregate_type="agent",
                aggregate_id=record.agent_id,
                payload={
                    "agent_id": record.agent_id,
                    "before": None,
                    "after": record.status,
                },
            )
        )

        return record

    def heartbeat(self, agent_id: str) -> AgentRecord:
        record = self._records.get(agent_id)
        if not record:
            raise KeyError(f"AGENT_NOT_FOUND: {agent_id}")

        previous_status = record.status
        record.status = "online"
        record.touch()

        self.control_bus.publish(
            ControlEvent.new(
                event_type="agent.heartbeat",
                aggregate_type="agent",
                aggregate_id=record.agent_id,
                payload={
                    "agent_id": record.agent_id,
                    "name": record.manifest.name,
                    "status": record.status,
                    "last_heartbeat": record.last_heartbeat,
                },
            )
        )

        if previous_status != record.status:
            self.control_bus.publish(
                ControlEvent.new(
                    event_type="agent.status.changed",
                    aggregate_type="agent",
                    aggregate_id=record.agent_id,
                    payload={
                        "agent_id": record.agent_id,
                        "before": previous_status,
                        "after": record.status,
                    },
                )
            )

        return record

    def list_agents(self) -> List[AgentRecord]:
        return sorted(
            self._records.values(),
            key=lambda r: (r.manifest.name, r.created_at),
        )

    def get_agent(self, agent_id: str) -> Optional[AgentRecord]:
        return self._records.get(agent_id)

    def list_control_events(
        self,
        *,
        event_type: Optional[str] = None,
        aggregate_id: Optional[str] = None,
    ):
        return self.control_bus.list_events(
            event_type=event_type,
            aggregate_id=aggregate_id,
        )