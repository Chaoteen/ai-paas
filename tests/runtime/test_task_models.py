from runtime.queue.task_models import (
    AgentTaskPayload,
    GenerationTaskPayload,
    TaskEnvelope,
    TaskStatus,
    TaskType,
)


def test_agent_task_payload_validates_required_fields() -> None:
    payload = AgentTaskPayload(
        prompt="hello world",
        model="test-agent-model",
        system_prompt="system",
        temperature=0.2,
        max_tokens=256,
        metadata={"source": "unit-test"},
    )

    assert payload.prompt == "hello world"
    assert payload.model == "test-agent-model"
    assert payload.system_prompt == "system"
    assert payload.temperature == 0.2
    assert payload.max_tokens == 256
    assert payload.metadata["source"] == "unit-test"


def test_generation_task_payload_validates_required_fields() -> None:
    payload = GenerationTaskPayload(
        prompt="draw a cat",
        model="test-generation-model",
        modality="image",
        size="1024x1024",
        duration_seconds=5,
        metadata={"style": "clean"},
    )

    assert payload.prompt == "draw a cat"
    assert payload.model == "test-generation-model"
    assert payload.modality == "image"
    assert payload.size == "1024x1024"
    assert payload.duration_seconds == 5
    assert payload.metadata["style"] == "clean"


def test_task_envelope_for_agent_builds_created_task() -> None:
    payload = AgentTaskPayload(
        prompt="run agent",
        model="agent-model",
        metadata={"agent_id": "echo"},
    )

    task = TaskEnvelope.for_agent(
        tenant_id="tenant-a",
        payload=payload,
        queue_name="agent_tasks",
        correlation_id="corr-1",
        idempotency_key="idem-1",
    )

    assert task.tenant_id == "tenant-a"
    assert task.task_type == TaskType.AGENT
    assert task.queue_name == "agent_tasks"
    assert task.status == TaskStatus.CREATED
    assert task.payload["prompt"] == "run agent"
    assert task.payload["model"] == "agent-model"
    assert task.payload["metadata"]["agent_id"] == "echo"
    assert task.correlation_id == "corr-1"
    assert task.idempotency_key == "idem-1"
    assert task.result is None
    assert task.error is None
    assert task.task_id


def test_task_envelope_for_generation_builds_created_task() -> None:
    payload = GenerationTaskPayload(
        prompt="make a short video",
        model="video-model",
        modality="video",
        duration_seconds=4,
        metadata={"job": "demo"},
    )

    task = TaskEnvelope.for_generation(
        tenant_id="tenant-b",
        payload=payload,
        queue_name="generation_tasks",
        correlation_id="corr-2",
        idempotency_key="idem-2",
    )

    assert task.tenant_id == "tenant-b"
    assert task.task_type == TaskType.GENERATION
    assert task.queue_name == "generation_tasks"
    assert task.status == TaskStatus.CREATED
    assert task.payload["prompt"] == "make a short video"
    assert task.payload["model"] == "video-model"
    assert task.payload["modality"] == "video"
    assert task.payload["duration_seconds"] == 4
    assert task.payload["metadata"]["job"] == "demo"
    assert task.correlation_id == "corr-2"
    assert task.idempotency_key == "idem-2"
    assert task.result is None
    assert task.error is None
    assert task.task_id


def test_task_envelope_lifecycle_transitions() -> None:
    task = TaskEnvelope.for_agent(
        tenant_id="tenant-c",
        payload=AgentTaskPayload(
            prompt="process me",
            model="agent-model",
        ),
    )

    assert task.status == TaskStatus.CREATED
    assert task.queued_at is None
    assert task.started_at is None
    assert task.finished_at is None

    task.mark_queued()
    assert task.status == TaskStatus.QUEUED
    assert task.queued_at is not None
    assert task.error is None

    task.mark_running()
    assert task.status == TaskStatus.RUNNING
    assert task.started_at is not None
    assert task.error is None

    task.mark_succeeded({"output": "done"})
    assert task.status == TaskStatus.SUCCEEDED
    assert task.result == {"output": "done"}
    assert task.error is None
    assert task.finished_at is not None


def test_task_envelope_mark_failed_from_string() -> None:
    task = TaskEnvelope.for_generation(
        tenant_id="tenant-d",
        payload=GenerationTaskPayload(
            prompt="generate image",
            model="image-model",
            modality="image",
        ),
    )

    task.mark_failed("provider timeout")

    assert task.status == TaskStatus.FAILED
    assert task.error == "provider timeout"
    assert task.finished_at is not None


def test_task_envelope_mark_failed_from_dict() -> None:
    task = TaskEnvelope.for_agent(
        tenant_id="tenant-e",
        payload=AgentTaskPayload(
            prompt="run",
            model="agent-model",
        ),
    )

    task.mark_failed(
        {
            "type": "RuntimeError",
            "message": "execution failed",
        }
    )

    assert task.status == TaskStatus.FAILED
    assert task.error == "RuntimeError: execution failed"
    assert task.finished_at is not None


def test_task_envelope_increment_retry() -> None:
    task = TaskEnvelope.for_agent(
        tenant_id="tenant-f",
        payload=AgentTaskPayload(
            prompt="retry me",
            model="agent-model",
        ),
    )

    assert task.retry_count == 0
    task.increment_retry()
    task.increment_retry()
    assert task.retry_count == 2


def test_task_envelope_roundtrip_serialization() -> None:
    original = TaskEnvelope.for_generation(
        tenant_id="tenant-g",
        payload=GenerationTaskPayload(
            prompt="draw landscape",
            model="image-model",
            modality="image",
            size="512x512",
            metadata={"style": "oil"},
        ),
        queue_name="generation_tasks",
        correlation_id="corr-3",
        idempotency_key="idem-3",
    )

    original.mark_queued()
    original.mark_running()
    original.mark_succeeded({"asset_url": "https://example.com/image.png"})

    dumped = original.model_dump(mode="json")
    restored = TaskEnvelope.model_validate(dumped)

    assert restored.task_id == original.task_id
    assert restored.tenant_id == "tenant-g"
    assert restored.task_type == TaskType.GENERATION
    assert restored.queue_name == "generation_tasks"
    assert restored.status == TaskStatus.SUCCEEDED
    assert restored.payload["prompt"] == "draw landscape"
    assert restored.payload["model"] == "image-model"
    assert restored.payload["modality"] == "image"
    assert restored.payload["size"] == "512x512"
    assert restored.payload["metadata"]["style"] == "oil"
    assert restored.result == {"asset_url": "https://example.com/image.png"}
    assert restored.correlation_id == "corr-3"
    assert restored.idempotency_key == "idem-3"