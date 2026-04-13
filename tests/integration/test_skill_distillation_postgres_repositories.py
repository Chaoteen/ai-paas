from __future__ import annotations

import os
from datetime import datetime

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from persistence.repositories.recording_action_event_repository import (
    RecordingActionEventRepository,
)
from persistence.repositories.recording_session_repository import (
    RecordingSessionRepository,
)
from persistence.repositories.skill_draft_repository import SkillDraftRepository
from runtime.skills.contracts import (
    DerivedFromContract,
    DraftDefinitionContract,
    ExecutionBindingContract,
    IoSchemaContract,
)
from runtime.skills.models import (
    RecordingActionActorType,
    RecordingActionEvent,
    RecordingActionEventType,
    RecordingSession,
    RecordingSessionDistillationMode,
    RecordingSessionPhase,
    RecordingSessionSourceType,
    RecordingSessionStatus,
    SkillDraft,
    SkillDraftDistillationSourceType,
    SkillDraftStatus,
)


pytestmark = pytest.mark.integration


def _database_url() -> str:
    value = os.getenv("DATABASE_URL")
    if not value:
        pytest.skip("DATABASE_URL is not set")
    return value


async def _truncate_phase1_tables(session_factory: async_sessionmaker) -> None:
    async with session_factory() as session:
        await session.execute(
            text(
                "TRUNCATE TABLE skill_drafts, recording_action_events, recording_sessions "
                "RESTART IDENTITY CASCADE"
            )
        )
        await session.commit()


@pytest.mark.asyncio
async def test_postgres_repositories_session_event_draft_roundtrip() -> None:
    engine = create_async_engine(_database_url(), future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        await _truncate_phase1_tables(session_factory)

        async with session_factory() as session:
            session_repo = RecordingSessionRepository(session)
            event_repo = RecordingActionEventRepository(session)
            draft_repo = SkillDraftRepository(session)

            created_session = await session_repo.create(
                RecordingSession(
                    recording_session_id="rec_repo_pg_1",
                    tenant_id="tenant-pg",
                    source_type=RecordingSessionSourceType.DIALOGUE,
                    status=RecordingSessionStatus.DRAFT,
                    distillation_mode=RecordingSessionDistillationMode.DIALOGUE_ONLY,
                    current_phase=RecordingSessionPhase.CAPTURE,
                    title="PG Repository Session",
                    description="repository integration",
                    context_json={},
                    source_metadata_json={},
                    created_by="tester",
                    updated_by="tester",
                )
            )
            await session.commit()
            assert created_session.recording_session_id == "rec_repo_pg_1"

        async with session_factory() as session:
            session_repo = RecordingSessionRepository(session)
            got = await session_repo.get_by_id(
                tenant_id="tenant-pg",
                recording_session_id="rec_repo_pg_1",
            )
            assert got is not None
            assert got.title == "PG Repository Session"
            assert got.status.value == "draft"

        async with session_factory() as session:
            event_repo = RecordingActionEventRepository(session)
            created_event = await event_repo.append_with_allocated_sequence(
                RecordingActionEvent(
                    recording_action_event_id="evt_repo_pg_1",
                    recording_session_id="rec_repo_pg_1",
                    tenant_id="tenant-pg",
                    sequence_no=0,
                    idempotency_key="repo-pg-evt-1",
                    source_event_id=None,
                    event_timestamp=datetime.utcnow(),
                    event_type=RecordingActionEventType.DIALOGUE_STEP,
                    actor_type=RecordingActionActorType.USER,
                    payload_json={"text": "第一步：读取客户需求"},
                    source_ref_json={},
                    metadata_json={},
                )
            )
            await session.commit()
            assert created_event.sequence_no == 1

        async with session_factory() as session:
            event_repo = RecordingActionEventRepository(session)
            rows = await event_repo.list_by_session(
                tenant_id="tenant-pg",
                recording_session_id="rec_repo_pg_1",
            )
            assert len(rows) == 1
            assert rows[0].idempotency_key == "repo-pg-evt-1"

            idem = await event_repo.get_by_idempotency_key(
                tenant_id="tenant-pg",
                recording_session_id="rec_repo_pg_1",
                idempotency_key="repo-pg-evt-1",
            )
            assert idem is not None
            assert idem.sequence_no == 1

        async with session_factory() as session:
            draft_repo = SkillDraftRepository(session)
            next_version = await draft_repo.allocate_next_version(
                tenant_id="tenant-pg",
                draft_key="quote_repo_skill",
            )
            assert next_version == "v1"

            created_draft = await draft_repo.create(
                SkillDraft(
                    skill_draft_id="sd_repo_pg_1",
                    tenant_id="tenant-pg",
                    recording_session_id="rec_repo_pg_1",
                    previous_skill_draft_id=None,
                    promoted_skill_id=None,
                    promoted_skill_version_id=None,
                    draft_key="quote_repo_skill",
                    draft_version="v1",
                    status=SkillDraftStatus.DRAFT,
                    name="Quote Repo Skill",
                    intent_summary="repository path",
                    distillation_source_type=SkillDraftDistillationSourceType.DIALOGUE,
                    input_schema=IoSchemaContract(
                        type="object",
                        properties={},
                        required=[],
                    ),
                    output_schema=IoSchemaContract(
                        type="object",
                        properties={},
                        required=[],
                    ),
                    draft_definition=DraftDefinitionContract(
                        draft_type="task_skill",
                        steps=[],
                        inputs=[],
                        outputs=[],
                        guardrails={},
                        hints={},
                    ),
                    distillation_notes_json={},
                    execution_binding=ExecutionBindingContract(
                        binding_type="unbound",
                        target_ref={"object_type": None, "object_id": None},
                        config_json={},
                    ),
                    derived_from=DerivedFromContract(
                        recording_session_id="rec_repo_pg_1",
                        source_event_range={"from_sequence_no": 1, "to_sequence_no": 1},
                        source_kind="dialogue",
                    ),
                    metadata_json={},
                    created_by="tester",
                    updated_by="tester",
                )
            )
            await session.commit()
            assert created_draft.draft_version == "v1"

        async with session_factory() as session:
            draft_repo = SkillDraftRepository(session)
            session_repo = RecordingSessionRepository(session)

            await session_repo.set_latest_skill_draft_id(
                tenant_id="tenant-pg",
                recording_session_id="rec_repo_pg_1",
                skill_draft_id="sd_repo_pg_1",
                actor_user_id="tester",
            )
            await session.commit()

        async with session_factory() as session:
            session_repo = RecordingSessionRepository(session)
            draft_repo = SkillDraftRepository(session)

            session_detail = await session_repo.get_by_id(
                tenant_id="tenant-pg",
                recording_session_id="rec_repo_pg_1",
            )
            assert session_detail is not None
            assert session_detail.latest_skill_draft_id == "sd_repo_pg_1"

            draft_detail = await draft_repo.get_by_id(
                tenant_id="tenant-pg",
                skill_draft_id="sd_repo_pg_1",
            )
            assert draft_detail is not None
            assert draft_detail.recording_session_id == "rec_repo_pg_1"

            next_version = await draft_repo.allocate_next_version(
                tenant_id="tenant-pg",
                draft_key="quote_repo_skill",
            )
            assert next_version == "v2"

    finally:
        await engine.dispose()