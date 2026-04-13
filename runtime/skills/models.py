from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from runtime.skills.contracts import (
    DerivedFromContract,
    DraftDefinitionContract,
    ExecutionBindingContract,
    IoSchemaContract,
)


class RecordingSessionSourceType(str, Enum):
    DIALOGUE = "dialogue"
    UI_RECORDING = "ui_recording"


class RecordingSessionStatus(str, Enum):
    DRAFT = "draft"
    COLLECTING = "collecting"
    DISTILLED = "distilled"
    ARCHIVED = "archived"


class RecordingSessionDistillationMode(str, Enum):
    RECORD_ONLY = "record_only"
    DIALOGUE_ONLY = "dialogue_only"
    HYBRID = "hybrid"


class RecordingSessionPhase(str, Enum):
    CAPTURE = "capture"
    ORGANIZE = "organize"
    DISTILL = "distill"
    REVIEW = "review"


class RecordingActionEventType(str, Enum):
    DIALOGUE_STEP = "dialogue_step"
    UI_ACTION = "ui_action"
    SYSTEM_INFERENCE = "system_inference"


class RecordingActionActorType(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    RECORDER = "recorder"
    SYSTEM = "system"


class SkillDraftStatus(str, Enum):
    DRAFT = "draft"
    REVIEWING = "reviewing"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class SkillDraftDistillationSourceType(str, Enum):
    DIALOGUE = "dialogue"
    UI_RECORDING = "ui_recording"
    HYBRID = "hybrid"
    IMPORTED = "imported"


class RecordingSession(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recording_session_id: str
    tenant_id: str
    source_type: RecordingSessionSourceType
    status: RecordingSessionStatus = RecordingSessionStatus.DRAFT
    distillation_mode: RecordingSessionDistillationMode = RecordingSessionDistillationMode.DIALOGUE_ONLY
    current_phase: RecordingSessionPhase = RecordingSessionPhase.CAPTURE
    title: str
    description: Optional[str] = None
    context_json: dict[str, Any] = Field(default_factory=dict)
    source_metadata_json: dict[str, Any] = Field(default_factory=dict)
    latest_skill_draft_id: Optional[str] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("recording_session_id", "tenant_id", "title")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("value must be a non-empty string")
        return value.strip()


class RecordingActionEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recording_action_event_id: str
    recording_session_id: str
    tenant_id: str
    sequence_no: int
    idempotency_key: Optional[str] = None
    source_event_id: Optional[str] = None
    event_timestamp: Optional[datetime] = None
    event_type: RecordingActionEventType
    actor_type: RecordingActionActorType
    payload_json: dict[str, Any] = Field(default_factory=dict)
    source_ref_json: dict[str, Any] = Field(default_factory=dict)
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("recording_action_event_id", "recording_session_id", "tenant_id")
    @classmethod
    def validate_event_ids(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("value must be a non-empty string")
        return value.strip()


class SkillDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill_draft_id: str
    tenant_id: str
    recording_session_id: Optional[str] = None
    previous_skill_draft_id: Optional[str] = None
    promoted_skill_id: Optional[str] = None
    promoted_skill_version_id: Optional[str] = None
    draft_key: str
    draft_version: str
    status: SkillDraftStatus = SkillDraftStatus.DRAFT
    name: str
    intent_summary: Optional[str] = None
    distillation_source_type: SkillDraftDistillationSourceType
    input_schema: IoSchemaContract = Field(default_factory=IoSchemaContract)
    output_schema: IoSchemaContract = Field(default_factory=IoSchemaContract)
    draft_definition: DraftDefinitionContract
    distillation_notes_json: dict[str, Any] = Field(default_factory=dict)
    execution_binding: ExecutionBindingContract
    derived_from: DerivedFromContract
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("skill_draft_id", "tenant_id", "draft_key", "draft_version", "name")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("value must be a non-empty string")
        return value.strip()

    def to_persistence_payload(self) -> dict[str, Any]:
        return {
            "skill_draft_id": self.skill_draft_id,
            "tenant_id": self.tenant_id,
            "recording_session_id": self.recording_session_id,
            "previous_skill_draft_id": self.previous_skill_draft_id,
            "promoted_skill_id": self.promoted_skill_id,
            "promoted_skill_version_id": self.promoted_skill_version_id,
            "draft_key": self.draft_key,
            "draft_version": self.draft_version,
            "status": self.status.value,
            "name": self.name,
            "intent_summary": self.intent_summary,
            "distillation_source_type": self.distillation_source_type.value,
            "input_schema_json": self.input_schema.model_dump(mode="python"),
            "output_schema_json": self.output_schema.model_dump(mode="python"),
            "draft_definition_json": self.draft_definition.model_dump(mode="python"),
            "distillation_notes_json": self.distillation_notes_json,
            "execution_binding_json": self.execution_binding.model_dump(mode="python"),
            "derived_from_json": self.derived_from.model_dump(mode="python"),
            "metadata_json": self.metadata_json,
            "created_by": self.created_by,
            "updated_by": self.updated_by,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_persistence_payload(cls, payload: dict[str, Any]) -> "SkillDraft":
        return cls(
            skill_draft_id=payload["skill_draft_id"],
            tenant_id=payload["tenant_id"],
            recording_session_id=payload.get("recording_session_id"),
            previous_skill_draft_id=payload.get("previous_skill_draft_id"),
            promoted_skill_id=payload.get("promoted_skill_id"),
            promoted_skill_version_id=payload.get("promoted_skill_version_id"),
            draft_key=payload["draft_key"],
            draft_version=payload["draft_version"],
            status=payload["status"],
            name=payload["name"],
            intent_summary=payload.get("intent_summary"),
            distillation_source_type=payload["distillation_source_type"],
            input_schema=IoSchemaContract.model_validate(payload.get("input_schema_json") or {}),
            output_schema=IoSchemaContract.model_validate(payload.get("output_schema_json") or {}),
            draft_definition=DraftDefinitionContract.model_validate(
                payload.get("draft_definition_json")
                or {
                    "draft_type": "task_skill",
                    "steps": [],
                    "inputs": [],
                    "outputs": [],
                    "guardrails": {},
                    "hints": {},
                }
            ),
            distillation_notes_json=payload.get("distillation_notes_json") or {},
            execution_binding=ExecutionBindingContract.model_validate(
                payload.get("execution_binding_json")
                or {
                    "binding_type": "unbound",
                    "target_ref": {"object_type": None, "object_id": None},
                    "config_json": {},
                }
            ),
            derived_from=DerivedFromContract.model_validate(
                payload.get("derived_from_json")
                or {
                    "recording_session_id": None,
                    "source_event_range": {"from_sequence_no": None, "to_sequence_no": None},
                    "source_kind": "imported",
                }
            ),
            metadata_json=payload.get("metadata_json") or {},
            created_by=payload.get("created_by"),
            updated_by=payload.get("updated_by"),
            created_at=payload["created_at"],
            updated_at=payload["updated_at"],
        )