from runtime.queue.task_models import (
    AgentTaskPayload,
    GenerationTaskKind,
    GenerationTaskPayload,
    TaskEnvelope,
    TaskPriority,
    TaskStatus,
    TaskType,
)


def test_new_agent_task_defaults():
    payload = AgentTaskPayload(
        agent_id="echo",
        input="hello ai-paas",
        tenant_id="tenant-a",
        user_id="user-a",
        correlation_id="corr-123",
    )

    task = TaskEnvelope.new_agent_task(payload)

    assert task.task_type == TaskType.AGENT
    assert task.status == TaskStatus.PENDING
    assert task.queue_name == "agent"
    assert task.priority == TaskPriority.NORMAL
    assert task.tenant_id == "tenant-a"
    assert task.user_id == "user-a"
    assert task.correlation_id == "corr-123"
    assert task.payload.agent_id == "echo"
    assert task.payload.input == "hello ai-paas"


def test_new_generation_task_defaults():
    payload = GenerationTaskPayload(
        kind=GenerationTaskKind.IMAGE,
        prompt="A futuristic AI-PaaS dashboard",
        provider="mock_image",
        tenant_id="tenant-a",
    )

    task = TaskEnvelope.new_generation_task(payload)

    assert task.task_type == TaskType.GENERATION
    assert task.status == TaskStatus.PENDING
    assert task.queue_name == "generation"
    assert task.tenant_id == "tenant-a"
    assert task.payload.kind == GenerationTaskKind.IMAGE
    assert task.payload.provider == "mock_image"


def test_task_status_transitions():
    payload = AgentTaskPayload(agent_id="echo", input="hello")
    task = TaskEnvelope.new_agent_task(payload)

    task.mark_queued()
    assert task.status == TaskStatus.QUEUED
    assert task.queued_at is not None

    task.mark_running()
    assert task.status == TaskStatus.RUNNING
    assert task.started_at is not None

    task.mark_succeeded({"ok": True})
    assert task.status == TaskStatus.SUCCEEDED
    assert task.result == {"ok": True}
    assert task.finished_at is not None
    assert task.error is None


def test_task_failure_and_retry():
    payload = AgentTaskPayload(agent_id="echo", input="hello")
    task = TaskEnvelope.new_agent_task(payload, max_retries=2)

    assert task.can_retry is True

    task.increment_retry()
    assert task.retry_count == 1
    assert task.can_retry is True

    task.increment_retry()
    assert task.retry_count == 2
    assert task.can_retry is False

    task.mark_failed({"type": "RuntimeError", "message": "boom"})
    assert task.status == TaskStatus.FAILED
    assert task.error["type"] == "RuntimeError"


def test_agent_task_roundtrip_serialization():
    payload = AgentTaskPayload(
        agent_id="echo",
        input={"text": "hello"},
        tenant_id="tenant-a",
        metadata={"source": "pytest"},
    )
    task = TaskEnvelope.new_agent_task(payload, metadata={"channel": "gateway"})

    data = task.to_dict()
    restored = TaskEnvelope.from_dict(data)

    assert restored.task_id == task.task_id
    assert restored.task_type == TaskType.AGENT
    assert restored.payload.agent_id == "echo"
    assert restored.payload.input == {"text": "hello"}
    assert restored.metadata["channel"] == "gateway"
    assert restored.payload.metadata["source"] == "pytest"


def test_generation_task_roundtrip_serialization():
    payload = GenerationTaskPayload(
        kind=GenerationTaskKind.VIDEO,
        prompt="A robot entering a smart factory",
        provider="seedance",
        duration_seconds=5,
        metadata={"source": "pytest"},
    )
    task = TaskEnvelope.new_generation_task(payload)

    data = task.to_dict()
    restored = TaskEnvelope.from_dict(data)

    assert restored.task_type == TaskType.GENERATION
    assert restored.payload.kind == GenerationTaskKind.VIDEO
    assert restored.payload.prompt == "A robot entering a smart factory"
    assert restored.payload.provider == "seedance"
    assert restored.payload.duration_seconds == 5
    assert restored.payload.metadata["source"] == "pytest"