from __future__ import annotations

from typing import Any, Dict

from runtime.queue.task_models import TaskEnvelope
from runtime.workers.worker_base import WorkerBase


class GenerationWorker(WorkerBase):
    """
    Queue worker for generation tasks.

    Current contract:
    - consumes from generation_tasks stream
    - executes generation task payloads
    - returns structured dict results
    """

    stream_name = "generation_tasks"
    group_name = "generation_workers"

    async def execute_task(self, task: TaskEnvelope) -> Dict[str, Any]:
        payload = task.payload

        modality = payload.get("modality")
        prompt = payload.get("prompt")
        model = payload.get("model")

        if not isinstance(modality, str) or not modality.strip():
            raise ValueError("generation task payload.modality must be a non-empty string")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("generation task payload.prompt must be a non-empty string")
        if not isinstance(model, str) or not model.strip():
            raise ValueError("generation task payload.model must be a non-empty string")

        result: Dict[str, Any] = {
            "status": "accepted",
            "modality": modality,
            "prompt": prompt,
            "model": model,
        }

        size = payload.get("size")
        if size is not None:
            result["size"] = size

        duration_seconds = payload.get("duration_seconds")
        if duration_seconds is not None:
            result["duration_seconds"] = duration_seconds

        metadata = payload.get("metadata")
        if isinstance(metadata, dict) and metadata:
            result["metadata"] = metadata

        return result