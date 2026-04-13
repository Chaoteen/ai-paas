from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class DialogueDistillationService:
    session_service: object
    event_service: object
    draft_service: object

    @staticmethod
    def _slugify(value: str) -> str:
        text = (value or "").strip().lower()
        text = re.sub(r"[^a-z0-9]+", "_", text)
        text = re.sub(r"_+", "_", text).strip("_")
        return text or "dialogue_skill"

    @staticmethod
    def _normalize_turns(dialogue_turns: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for index, turn in enumerate(dialogue_turns, start=1):
            speaker = str(turn.get("speaker") or "user").strip().lower()
            text = str(turn.get("text") or "").strip()
            if not text:
                continue
            actor_type = "user" if speaker == "user" else "assistant"
            normalized.append(
                {
                    "turn_no": index,
                    "speaker": speaker,
                    "actor_type": actor_type,
                    "text": text,
                }
            )
        return normalized

    async def distill_from_dialogue(
        self,
        *,
        tenant_id: str,
        actor_user_id: Optional[str],
        session_title: str,
        draft_name: str,
        intent_summary: Optional[str],
        dialogue_turns: list[dict[str, Any]],
        recording_session_id: Optional[str],
        draft_key: Optional[str],
        input_schema_json: dict[str, Any],
        output_schema_json: dict[str, Any],
        draft_definition_json: dict[str, Any],
        execution_binding_json: dict[str, Any],
        metadata_json: dict[str, Any],
    ) -> dict[str, Any]:
        turns = self._normalize_turns(dialogue_turns)
        if not turns:
            raise ValueError("dialogue_turns must contain at least one non-empty turn")

        session_created = False
        if recording_session_id:
            session = await self.session_service.get_session(
                tenant_id=tenant_id,
                recording_session_id=recording_session_id,
            )
            session_id = session.recording_session_id
            if session.status.value == "draft":
                await self.session_service.transition_status(
                    tenant_id=tenant_id,
                    recording_session_id=session_id,
                    action="start_collecting",
                    actor_user_id=actor_user_id,
                )
        else:
            session = await self.session_service.create_session(
                tenant_id=tenant_id,
                source_type="dialogue",
                distillation_mode="dialogue_only",
                title=session_title,
                description="Generated from dialogue distillation API",
                context_json={"distillation_entry": "dialogue_api"},
                source_metadata_json={"source": "dialogue_api"},
                actor_user_id=actor_user_id,
            )
            session_id = session.recording_session_id
            session_created = True
            await self.session_service.transition_status(
                tenant_id=tenant_id,
                recording_session_id=session_id,
                action="start_collecting",
                actor_user_id=actor_user_id,
            )

        first_sequence_no: Optional[int] = None
        last_sequence_no: Optional[int] = None

        for turn in turns:
            event = await self.event_service.append_event(
                tenant_id=tenant_id,
                recording_session_id=session_id,
                idempotency_key=f"dlg-{session_id}-{turn['turn_no']}",
                source_event_id=None,
                event_timestamp=None,
                event_type="dialogue_step",
                actor_type=turn["actor_type"],
                payload_json={
                    "speaker": turn["speaker"],
                    "text": turn["text"],
                    "turn_no": turn["turn_no"],
                },
                source_ref_json={},
                metadata_json={"distillation_source": "dialogue_api"},
            )
            if first_sequence_no is None:
                first_sequence_no = event.sequence_no
            last_sequence_no = event.sequence_no

        if session_created or True:
            await self.session_service.transition_status(
                tenant_id=tenant_id,
                recording_session_id=session_id,
                action="mark_distilled",
                actor_user_id=actor_user_id,
            )

        resolved_draft_key = draft_key or self._slugify(draft_name or session_title)

        draft = await self.draft_service.create_draft(
            tenant_id=tenant_id,
            recording_session_id=session_id,
            previous_skill_draft_id=None,
            draft_key=resolved_draft_key,
            name=draft_name,
            intent_summary=intent_summary,
            distillation_source_type="dialogue",
            input_schema_json=input_schema_json,
            output_schema_json=output_schema_json,
            draft_definition_json=draft_definition_json,
            distillation_notes_json={
                "distilled_from": "dialogue",
                "turn_count": len(turns),
            },
            execution_binding_json=execution_binding_json,
            derived_from_json={
                "recording_session_id": session_id,
                "source_event_range": {
                    "from_sequence_no": first_sequence_no,
                    "to_sequence_no": last_sequence_no,
                },
                "source_kind": "dialogue",
            },
            metadata_json=metadata_json or {},
            actor_user_id=actor_user_id,
        )

        session_detail = await self.session_service.get_session(
            tenant_id=tenant_id,
            recording_session_id=session_id,
        )

        return {
            "recording_session": session_detail,
            "skill_draft": draft,
            "dialogue_turn_count": len(turns),
        }