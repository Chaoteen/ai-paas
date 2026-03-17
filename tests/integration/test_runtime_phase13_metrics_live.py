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


def get_metrics() -> dict:
    resp = requests.get(
        f"{BASE_URL}/runtime/metrics",
        timeout=(2, 5),
        headers={"Connection": "close"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["items"]


def wait_for_completed_increment(before_completed: int, timeout: float = 20.0) -> dict:
    deadline = time.time() + timeout
    last_snapshot = {}

    while time.time() < deadline:
        snapshot = get_metrics()
        last_snapshot = snapshot
        if snapshot.get("tasks_completed", 0) > before_completed:
            return snapshot
        time.sleep(0.5)

    raise AssertionError(f"Timed out waiting for metrics increment. last_snapshot={last_snapshot}")


def test_phase13_metrics_live():
    wait_for_service()

    before = get_metrics()
    before_submitted = before.get("tasks_submitted", 0)
    before_completed = before.get("tasks_completed", 0)
    before_tool = before.get("tool_invocations", 0)

    tenant_id = "tenant-live-metrics"
    agent_id = f"agent-{uuid.uuid4().hex[:8]}"
    task_id = f"task-{uuid.uuid4().hex[:8]}"

    reg_resp = requests.post(
        f"{BASE_URL}/runtime/agents/register",
        json={
            "id": agent_id,
            "tenant_id": tenant_id,
            "name": "Live Metrics Agent",
            "status": "healthy",
            "capabilities": {"skills": ["echo"]},
            "metadata": {"source": "pytest-live-phase13-metrics"},
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
            "input": {"text": "hello metrics"},
            "metadata": {"source": "pytest-live-phase13-metrics"},
        },
        timeout=(2, 10),
        headers={"Connection": "close"},
    )
    assert sub_resp.status_code == 200, sub_resp.text

    after = wait_for_completed_increment(before_completed=before_completed, timeout=20.0)

    assert after.get("tasks_submitted", 0) >= before_submitted + 1
    assert after.get("tasks_completed", 0) >= before_completed + 1
    assert after.get("tool_invocations", 0) >= before_tool + 1