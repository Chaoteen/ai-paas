from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class IoSchemaContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str = "object"
    properties: dict[str, Any] = Field(default_factory=dict)
    required: list[str] = Field(default_factory=list)

    @field_validator("type")
    @classmethod
    def validate_type(cls, value: str) -> str:
        if value != "object":
            raise ValueError("phase1 io schema only supports type=object")
        return value


class DraftDefinitionContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft_type: str
    steps: list[dict[str, Any]] = Field(default_factory=list)
    inputs: list[dict[str, Any]] = Field(default_factory=list)
    outputs: list[dict[str, Any]] = Field(default_factory=list)
    guardrails: dict[str, Any] = Field(default_factory=dict)
    hints: dict[str, Any] = Field(default_factory=dict)

    @field_validator("draft_type")
    @classmethod
    def validate_draft_type(cls, value: str) -> str:
        allowed = {"task_skill", "decision_skill", "composite_skill"}
        if value not in allowed:
            raise ValueError(f"draft_type must be one of {sorted(allowed)}")
        return value


class DerivedFromEventRange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_sequence_no: Optional[int] = None
    to_sequence_no: Optional[int] = None

    @model_validator(mode="after")
    def validate_range(self) -> "DerivedFromEventRange":
        if self.from_sequence_no is not None and self.from_sequence_no <= 0:
            raise ValueError("from_sequence_no must be > 0")
        if self.to_sequence_no is not None and self.to_sequence_no <= 0:
            raise ValueError("to_sequence_no must be > 0")
        if (
            self.from_sequence_no is not None
            and self.to_sequence_no is not None
            and self.from_sequence_no > self.to_sequence_no
        ):
            raise ValueError("from_sequence_no cannot be greater than to_sequence_no")
        return self


class DerivedFromContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recording_session_id: Optional[str] = None
    source_event_range: DerivedFromEventRange = Field(default_factory=DerivedFromEventRange)
    source_kind: str

    @field_validator("source_kind")
    @classmethod
    def validate_source_kind(cls, value: str) -> str:
        allowed = {"dialogue", "ui_recording", "hybrid", "imported"}
        if value not in allowed:
            raise ValueError(f"source_kind must be one of {sorted(allowed)}")
        return value


class ExecutionBindingTargetRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    object_type: Optional[str] = None
    object_id: Optional[str] = None


class ExecutionBindingContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    binding_type: str
    target_ref: ExecutionBindingTargetRef
    config_json: dict[str, Any] = Field(default_factory=dict)

    @field_validator("binding_type")
    @classmethod
    def validate_binding_type(cls, value: str) -> str:
        allowed = {"prompt_template", "tool_call", "workflow_ref", "agent_ref", "unbound"}
        if value not in allowed:
            raise ValueError(f"binding_type must be one of {sorted(allowed)}")
        return value

    @model_validator(mode="after")
    def validate_binding_semantics(self) -> "ExecutionBindingContract":
        if self.binding_type == "unbound":
            if self.target_ref.object_type is not None or self.target_ref.object_id is not None:
                raise ValueError("unbound binding requires null target_ref.object_type/object_id")
            return self

        if not self.target_ref.object_type or not self.target_ref.object_id:
            raise ValueError("bound binding requires non-empty target_ref.object_type and object_id")
        return self