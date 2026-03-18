from __future__ import annotations

from typing import Any, Dict

from runtime.queue.task_models import TaskEnvelope
from runtime.workers.worker_base import WorkerBase


class AgentWorker(WorkerBase):
    """
    Queue worker for agent tasks.

    Current contract:
    - consumes from agent_tasks stream
    - executes agent runtime payloads
    - returns structured dict results
    """

    stream_name = "agent_tasks"
    group_name = "agent_workers"

    async def execute_task(self, task: TaskEnvelope) -> Dict[str, Any]:
        payload = task.payload

        prompt = payload.get("prompt")
        model = payload.get("model")

        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("agent task payload.prompt must be a non-empty string")
        if not isinstance(model, str) or not model.strip():
            raise ValueError("agent task payload.model must be a non-empty string")

        result: Dict[str, Any] = {
            "status": "accepted",
            "prompt": prompt,
            "model": model,
            "output": f"processed: {prompt}",
        }

        system_prompt = payload.get("system_prompt")
        if system_prompt is not None:
            result["system_prompt"] = system_prompt

        temperature = payload.get("temperature")
        if temperature is not None:
            result["temperature"] = temperature

        max_tokens = payload.get("max_tokens")
        if max_tokens is not None:
            result["max_tokens"] = max_tokens

        metadata = payload.get("metadata")
        if isinstance(metadata, dict) and metadata:
            result["metadata"] = metadata

        return result