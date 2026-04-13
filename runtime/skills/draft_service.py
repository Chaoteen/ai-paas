from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import uuid4

from runtime.skills.contracts import (
    DerivedFromContract,
    DraftDefinitionContract,
    ExecutionBindingContract,
    IoSchemaContract,
)
from runtime.skills.errors import InvalidPatchError, InvalidStateTransitionError, NotFoundError
from runtime.skills.models import SkillDraft, SkillDraftDistillationSourceType, SkillDraftStatus


@dataclass
class SkillDraftService:
    session_repo: object
    draft_repo: object

    async def create_draft(
        self,
        *,
        tenant_id: str,
        recording_session_id: Optional[str],
        previous_skill_draft_id: Optional[str],
        draft_key: str,
        name: str,
        intent_summary: Optional[str],
        distillation_source_type: str,
        input_schema_json: dict,
        output_schema_json: dict,
        draft_definition_json: dict,
        distillation_notes_json: dict,
        execution_binding_json: dict,
        derived_from_json: dict,
        metadata_json: dict,
        actor_user_id: Optional[str],
    ) -> SkillDraft:
        if recording_session_id is not None:
            session = await self.session_repo.get_by_id(
                tenant_id=tenant_id,
                recording_session_id=recording_session_id,
            )
            if session is None:
                raise NotFoundError(f"recording session not found: {recording_session_id}")

        if previous_skill_draft_id is not None:
            previous = await self.draft_repo.get_by_id(
                tenant_id=tenant_id,
                skill_draft_id=previous_skill_draft_id,
            )
            if previous is None:
                raise NotFoundError(f"previous skill draft not found: {previous_skill_draft_id}")

        input_schema = IoSchemaContract.model_validate(
            input_schema_json or {"type": "object", "properties": {}, "required": []}
        )
        output_schema = IoSchemaContract.model_validate(
            output_schema_json or {"type": "object", "properties": {}, "required": []}
        )
        draft_definition = DraftDefinitionContract.model_validate(
            draft_definition_json
            or {
                "draft_type": "task_skill",
                "steps": [],
                "inputs": [],
                "outputs": [],
                "guardrails": {},
                "hints": {},
            }
        )
        execution_binding = ExecutionBindingContract.model_validate(
            execution_binding_json
            or {
                "binding_type": "unbound",
                "target_ref": {"object_type": None, "object_id": None},
                "config_json": {},
            }
        )
        derived_from = DerivedFromContract.model_validate(
            derived_from_json
            or {
                "recording_session_id": recording_session_id,
                "source_event_range": {"from_sequence_no": None, "to_sequence_no": None},
                "source_kind": distillation_source_type,
            }
        )

        next_version = await self.draft_repo.allocate_next_version(
            tenant_id=tenant_id,
            draft_key=draft_key,
        )

        draft = SkillDraft(
            skill_draft_id=f"sd_{uuid4().hex}",
            tenant_id=tenant_id,
            recording_session_id=recording_session_id,
            previous_skill_draft_id=previous_skill_draft_id,
            promoted_skill_id=None,
            promoted_skill_version_id=None,
            draft_key=draft_key,
            draft_version=next_version,
            status=SkillDraftStatus.DRAFT,
            name=name,
            intent_summary=intent_summary,
            distillation_source_type=SkillDraftDistillationSourceType(distillation_source_type),
            input_schema=input_schema,
            output_schema=output_schema,
            draft_definition=draft_definition,
            distillation_notes_json=distillation_notes_json or {},
            execution_binding=execution_binding,
            derived_from=derived_from,
            metadata_json=metadata_json or {},
            created_by=actor_user_id,
            updated_by=actor_user_id,
        )

        created = await self.draft_repo.create(draft)

        if recording_session_id is not None:
            await self.session_repo.set_latest_skill_draft_id(
                tenant_id=tenant_id,
                recording_session_id=recording_session_id,
                skill_draft_id=created.skill_draft_id,
                actor_user_id=actor_user_id,
            )

        return created

    async def get_draft(
        self,
        *,
        tenant_id: str,
        skill_draft_id: str,
    ) -> SkillDraft:
        draft = await self.draft_repo.get_by_id(
            tenant_id=tenant_id,
            skill_draft_id=skill_draft_id,
        )
        if draft is None:
            raise NotFoundError(f"skill draft not found: {skill_draft_id}")
        return draft

    async def list_drafts(
        self,
        *,
        tenant_id: str,
        status: Optional[str] = None,
        recording_session_id: Optional[str] = None,
    ) -> list[SkillDraft]:
        return await self.draft_repo.list_by_tenant(
            tenant_id=tenant_id,
            status=status,
            recording_session_id=recording_session_id,
        )

    async def patch_draft(
        self,
        *,
        tenant_id: str,
        skill_draft_id: str,
        patch: dict,
        actor_user_id: Optional[str],
    ) -> SkillDraft:
        forbidden = {
            "skill_draft_id",
            "tenant_id",
            "recording_session_id",
            "previous_skill_draft_id",
            "promoted_skill_id",
            "promoted_skill_version_id",
            "draft_key",
            "draft_version",
            "status",
            "distillation_source_type",
            "created_at",
            "created_by",
        }
        invalid = forbidden.intersection(patch.keys())
        if invalid:
            raise InvalidPatchError(
                f"skill draft patch contains forbidden fields: {sorted(invalid)}"
            )

        draft = await self.get_draft(
            tenant_id=tenant_id,
            skill_draft_id=skill_draft_id,
        )

        next_data = draft.model_dump(mode="python")

        if "input_schema_json" in patch:
            next_data["input_schema"] = IoSchemaContract.model_validate(patch["input_schema_json"])
            patch = {k: v for k, v in patch.items() if k != "input_schema_json"}

        if "output_schema_json" in patch:
            next_data["output_schema"] = IoSchemaContract.model_validate(patch["output_schema_json"])
            patch = {k: v for k, v in patch.items() if k != "output_schema_json"}

        if "draft_definition_json" in patch:
            next_data["draft_definition"] = DraftDefinitionContract.model_validate(
                patch["draft_definition_json"]
            )
            patch = {k: v for k, v in patch.items() if k != "draft_definition_json"}

        if "execution_binding_json" in patch:
            next_data["execution_binding"] = ExecutionBindingContract.model_validate(
                patch["execution_binding_json"]
            )
            patch = {k: v for k, v in patch.items() if k != "execution_binding_json"}

        if "derived_from_json" in patch:
            next_data["derived_from"] = DerivedFromContract.model_validate(
                patch["derived_from_json"]
            )
            patch = {k: v for k, v in patch.items() if k != "derived_from_json"}

        next_data.update(patch)
        next_data["updated_by"] = actor_user_id
        next_data["updated_at"] = datetime.utcnow()

        updated = SkillDraft.model_validate(next_data)
        return await self.draft_repo.update_mutable_fields(updated)

    async def transition_status(
        self,
        *,
        tenant_id: str,
        skill_draft_id: str,
        action: str,
        actor_user_id: Optional[str],
    ) -> SkillDraft:
        draft = await self.get_draft(
            tenant_id=tenant_id,
            skill_draft_id=skill_draft_id,
        )

        transitions = {
            SkillDraftStatus.DRAFT: {
                "submit_review": SkillDraftStatus.REVIEWING,
            },
            SkillDraftStatus.REVIEWING: {
                "accept": SkillDraftStatus.ACCEPTED,
                "reject": SkillDraftStatus.REJECTED,
            },
            SkillDraftStatus.ACCEPTED: {
                "archive": SkillDraftStatus.ARCHIVED,
            },
            SkillDraftStatus.REJECTED: {
                "restore_draft": SkillDraftStatus.DRAFT,
                "archive": SkillDraftStatus.ARCHIVED,
            },
            SkillDraftStatus.ARCHIVED: {},
        }

        next_status = transitions[draft.status].get(action)
        if next_status is None:
            raise InvalidStateTransitionError(
                f"invalid skill draft transition: {draft.status.value} -> {action}"
            )

        updated = draft.model_copy(
            update={
                "status": next_status,
                "updated_by": actor_user_id,
                "updated_at": datetime.utcnow(),
            }
        )
        return await self.draft_repo.transition_status(updated)