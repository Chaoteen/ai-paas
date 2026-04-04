from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


WorkflowProductVisibility = Literal["tenant", "private", "public"]
WorkflowProductStatus = Literal["draft", "active", "deprecated", "disabled"]


class WorkflowProductExecutionBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workflow_key: str = Field(..., min_length=1)
    workflow_version: str = Field(..., min_length=1)
    default_input_json: dict[str, Any] = Field(default_factory=dict)
    default_context_json: dict[str, Any] = Field(default_factory=dict)
    input_mapping_json: dict[str, Any] = Field(default_factory=dict)

    @field_validator("workflow_key", "workflow_version")
    @classmethod
    def _validate_required_strings(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("value must be a non-empty string")
        return value.strip()


class WorkflowProduct(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_key: str = Field(..., min_length=1)
    product_version: str = Field(..., min_length=1)
    display_name: str = Field(..., min_length=1)
    status: WorkflowProductStatus = "draft"

    public_api_schema_json: dict[str, Any] = Field(default_factory=dict)
    ui_schema_json: dict[str, Any] = Field(default_factory=dict)

    execution_binding: WorkflowProductExecutionBinding

    governance_json: dict[str, Any] = Field(default_factory=dict)
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    visibility: WorkflowProductVisibility = "tenant"

    created_by: Optional[str] = None
    updated_by: Optional[str] = None

    @field_validator("product_key", "product_version", "display_name")
    @classmethod
    def _validate_required_strings(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("value must be a non-empty string")
        return value.strip()


class CreateWorkflowProductRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product: WorkflowProduct


class WorkflowProductResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product: WorkflowProduct


class SubmitWorkflowProductRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    tenant_id: str = Field(..., min_length=1)
    product_key: str = Field(..., min_length=1)
    product_version: Optional[str] = None

    input_json: dict[str, Any] = Field(default_factory=dict)
    context_json: dict[str, Any] = Field(default_factory=dict)
    metadata_json: dict[str, Any] = Field(default_factory=dict)

    trigger_source: str = "workflow_product_api"
    correlation_id: Optional[str] = None
    idempotency_key: Optional[str] = None

    @field_validator("tenant_id", "product_key")
    @classmethod
    def _validate_required_strings(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("value must be a non-empty string")
        return value.strip()

    @field_validator("product_version")
    @classmethod
    def _validate_optional_version(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        if not isinstance(value, str) or not value.strip():
            raise ValueError("product_version must be a non-empty string when provided")
        return value.strip()


class WorkflowProductSubmitResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    task_type: str
    queue_name: str
    stream_name: str
    status: str
    durable: bool = True
    outbox_event_id: int
    bound_workflow_key: str
    bound_workflow_version: str