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


def wait_for_task_state(task_id: str, timeout: float = 20.0) -> dict:
    deadline = time.time() + timeout
    last_item = None

    while time.time() < deadline:
        resp = requests.get(
            f"{BASE_URL}/runtime/tasks/{task_id}/state",
            timeout=(2, 5),
            headers={"Connection": "close"},
        )
        if resp.status_code == 200:
            item = resp.json()["item"]
            last_item = item
            if item["status"] in {"completed", "failed"}:
                return item
        time.sleep(0.5)

    raise AssertionError(f"Timed out waiting for task state. last_item={last_item}")


def test_phase11_submit_idempotency_live():
    wait_for_service()

    tenant_id = "tenant-live-idem"
    agent_id = f"agent-{uuid.uuid4().hex[:8]}"
    task_id = f"task-{uuid.uuid4().hex[:8]}"
    workflow_id = f"wf-{uuid.uuid4().hex[:8]}"

    reg_resp = requests.post(
        f"{BASE_URL}/runtime/agents/register",
        json={
            "id": agent_id,
            "tenant_id": tenant_id,
            "name": "Live Idempotency Agent",
            "status": "healthy",
            "capabilities": {"skills": ["echo"]},
            "metadata": {"source": "pytest-live-phase11-idem"},
        },
        timeout=(2, 10),
        headers={"Connection": "close"},
    )
    assert reg_resp.status_code == 200, reg_resp.text

    payload = {
        "tenant_id": tenant_id,
        "task_id": task_id,
        "workflow_id": workflow_id,
        "correlation_id": f"corr-{uuid.uuid4().hex[:8]}",
        "required_capability": "echo",
        "input": {"text": "hello idem"},
        "metadata": {"source": "pytest-live-phase11-idem"},
    }

    first = requests.post(
        f"{BASE_URL}/runtime/tasks/submit",
        json=payload,
        timeout=(2, 10),
        headers={"Connection": "close"},
    )
    assert first.status_code == 200, first.text
    first_data = first.json()
    assert first_data["deduplicated"] is False
    assert first_data["event"] is not None

    second = requests.post(
        f"{BASE_URL}/runtime/tasks/submit",
        json=payload,
        timeout=(2, 10),
        headers={"Connection": "close"},
    )
    assert second.status_code == 200, second.text
    second_data = second.json()
    assert second_data["deduplicated"] is True
    assert second_data["event"] is None
    assert second_data["task_state"]["task_id"] == task_id

    state = wait_for_task_state(task_id=task_id, timeout=20.0)
    assert state["task_id"] == task_id
    assert state["status"] == "completed"

    data_events = requests.get(
        f"{BASE_URL}/runtime/data-events",
        params={"limit": 200},
        timeout=(2, 10),
        headers={"Connection": "close"},
    )
    assert data_events.status_code == 200, data_events.text
    items = data_events.json()["items"]
    matched_submits = [
        x for x in items
        if x.get("task_id") == task_id and x.get("event_type") == "task.submitted"
    ]
    assert len(matched_submits) == 1

    workflow_resp = requests.get(
        f"{BASE_URL}/runtime/workflows/{workflow_id}/state",
        timeout=(2, 10),
        headers={"Connection": "close"},
    )
    assert workflow_resp.status_code == 200, workflow_resp.text
    workflow = workflow_resp.json()["item"]
    assert workflow["workflow_id"] == workflow_id
    assert task_id in workflow["task_ids"]
    assert workflow["status"] == "completed"