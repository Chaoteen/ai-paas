from __future__ import annotations

import os
import time
import uuid

import requests


BASE_URL = os.getenv("RUNTIME_BASE_URL", "http://127.0.0.1:8000")


def wait_for_service(timeout: float = 20.0) -> None:
    deadline = time.time() + timeout
    last_error = None

    while time.time() < deadline:
        try:
            resp = requests.get(
                f"{BASE_URL}/health",
                timeout=(2, 5),
                headers={"Connection": "close"},
            )
            if resp.status_code == 200 and resp.json().get("status") == "ok":
                return
        except Exception as exc:
            last_error = exc
        time.sleep(0.5)

    raise RuntimeError(f"Service did not become ready in time. last_error={last_error}")


def wait_for_trace(task_id: str, timeout: float = 20.0) -> list[dict]:
    deadline = time.time() + timeout
    last_items = []

    while time.time() < deadline:
        resp = requests.get(
            f"{BASE_URL}/runtime/trace/{task_id}",
            timeout=(2, 5),
            headers={"Connection": "close"},
        )
        if resp.status_code == 200:
            items = resp.json()["items"]
            last_items = items
            event_types = {x["event_type"] for x in items}
            if "task.completed" in event_types or "task.failed" in event_types:
                return items
        time.sleep(0.5)

    raise AssertionError(f"Timed out waiting for trace. last_items={last_items}")


def test_phase13_trace_live():
    wait_for_service()

    tenant_id = "tenant-live-trace"
    agent_id = f"agent-{uuid.uuid4().hex[:8]}"
    task_id = f"task-{uuid.uuid4().hex[:8]}"

    reg_resp = requests.post(
        f"{BASE_URL}/runtime/agents/register",
        json={
            "id": agent_id,
            "tenant_id": tenant_id,
            "name": "Live Trace Agent",
            "status": "healthy",
            "capabilities": {"skills": ["echo"]},
            "metadata": {"source": "pytest-live-phase13-trace"},
        },
        timeout=(2, 10),
        headers={"Connection": "close"},
    )
    assert reg_resp.status_code == 200, reg_resp.text

    sub_resp = requests.post(
        f"{BASE_URL}/runtime/tasks/submit",
        json={
            "tenant_id": tenant_id,
            "task_id": task_id,
            "workflow_id": None,
            "correlation_id": f"corr-{uuid.uuid4().hex[:8]}",
            "required_capability": "echo",
            "input": {"text": "hello trace"},
            "metadata": {"source": "pytest-live-phase13-trace"},
        },
        timeout=(2, 10),
        headers={"Connection": "close"},
    )
    assert sub_resp.status_code == 200, sub_resp.text

    items = wait_for_trace(task_id=task_id, timeout=20.0)
    event_types = [x["event_type"] for x in items]

    assert "task.submitted" in event_types
    assert "router.success" in event_types
    assert "task.executing" in event_types
    assert "skill.selected" in event_types
    assert "tool.invoking" in event_types
    assert "tool.completed" in event_types
    assert "task.completed" in event_types