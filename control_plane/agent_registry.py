from __future__ import annotations

from typing import List, Optional

from control_plane.agent_admission import AgentAdmission, AdmissionDecision
from control_plane.agent_manifest import AgentManifest, AgentRecord
from control_plane.control_bus import ControlBus
from control_plane.control_events import ControlEvent
from control_plane.repositories.agent_repository import (
    AgentRepository,
    InMemoryAgentRepository,
)


class AgentRegistry:
    """
    第四轮版本：
    - AgentRegistry 不再直接持有 dict
    - 改为依赖 AgentRepository
    - 继续发布 control events
    """

    def __init__(
        self,
        admission: Optional[AgentAdmission] = None,
        control_bus: Optional[ControlBus] = None,
        agent_repository: Optional[AgentRepository] = None,
    ):
        self.admission = admission or AgentAdmission()
        self.control_bus = control_bus or ControlBus()
        self.agent_repository = agent_repository or InMemoryAgentRepository()

    def register(self, manifest: AgentManifest) -> AgentRecord:
        decision: AdmissionDecision = self.admission.evaluate(manifest)
        if not decision.allow:
            raise ValueError(decision.reason or "AGENT_ADMISSION_DENIED")

        existing = self.agent_repository.get_by_name(manifest.name)
        if existing:
            previous_status = existing.status

            existing.manifest = manifest
            existing.status = "online"
            existing.touch()
            record = self.agent_repository.save(existing)

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
                    metadata={"mode": "update"},
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
        record = self.agent_repository.save(record)

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
                metadata={"mode": "create"},
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
        record = self.agent_repository.get(agent_id)
        if not record:
            raise KeyError(f"AGENT_NOT_FOUND: {agent_id}")

        previous_status = record.status
        record.status = "online"
        record.touch()
        record = self.agent_repository.save(record)

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
        return self.agent_repository.list_all()

    def get_agent(self, agent_id: str) -> Optional[AgentRecord]:
        return self.agent_repository.get(agent_id)

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