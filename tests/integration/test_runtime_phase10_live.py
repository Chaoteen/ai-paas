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
                timeout=(2, 5),  # connect timeout, read timeout
                headers={"Connection": "close"},
            )
            print("health status:", resp.status_code, "body:", resp.text)

            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "ok":
                    return

        except Exception as exc:
            last_error = exc
            print("health check error:", repr(exc))

        time.sleep(0.5)

    raise RuntimeError(f"Service did not become ready in time. last_error={last_error}")


def wait_for_task_events(task_id: str, timeout: float = 20.0) -> list[dict]:
    deadline = time.time() + timeout
    last_items = []

    while time.time() < deadline:
        resp = requests.get(
            f"{BASE_URL}/runtime/data-events",
            params={"limit": 200},
            timeout=(2, 10),
            headers={"Connection": "close"},
        )
        resp.raise_for_status()
        data = resp.json()
        items = data["items"]
        matched = [x for x in items if x.get("task_id") == task_id]
        last_items = matched

        event_types = {x.get("event_type") for x in matched}
        print("task events:", task_id, sorted(event_types))

        if "task.completed" in event_types or "task.failed" in event_types:
            return matched

        time.sleep(0.5)

    raise AssertionError(f"Timed out waiting for final task event. current_events={last_items}")


def test_phase10_live_chain():
    wait_for_service()

    health_resp = requests.get(
        f"{BASE_URL}/health",
        timeout=(2, 5),
        headers={"Connection": "close"},
    )
    assert health_resp.status_code == 200, health_resp.text

    health = health_resp.json()
    print("health json:", health)

    assert health["status"] == "ok"
    assert health["router_worker"] is True
    assert health["agent_worker"] is True

    tenant_id = "tenant-live-a"
    agent_id = f"agent-{uuid.uuid4().hex[:8]}"
    task_id = f"task-{uuid.uuid4().hex[:8]}"

    register_payload = {
        "id": agent_id,
        "tenant_id": tenant_id,
        "name": "Live Echo Agent",
        "status": "healthy",
        "capabilities": {
            "skills": ["echo"]
        },
        "metadata": {
            "source": "pytest-live-phase10"
        },
    }

    reg_resp = requests.post(
        f"{BASE_URL}/runtime/agents/register",
        json=register_payload,
        timeout=(2, 10),
        headers={"Connection": "close"},
    )
    print("register:", reg_resp.status_code, reg_resp.text)
    assert reg_resp.status_code == 200, reg_resp.text

    submit_payload = {
        "tenant_id": tenant_id,
        "task_id": task_id,
        "workflow_id": None,
        "correlation_id": f"corr-{uuid.uuid4().hex[:8]}",
        "required_capability": "echo",
        "input": {
            "text": "hello from phase10 live test"
        },
        "metadata": {
            "source": "pytest-live-phase10"
        },
    }

    sub_resp = requests.post(
        f"{BASE_URL}/runtime/tasks/submit",
        json=submit_payload,
        timeout=(2, 10),
        headers={"Connection": "close"},
    )
    print("submit:", sub_resp.status_code, sub_resp.text)
    assert sub_resp.status_code == 200, sub_resp.text

    items = wait_for_task_events(task_id=task_id, timeout=20.0)
    event_types = [x.get("event_type") for x in items]
    print("final event types:", event_types)

    assert "task.submitted" in event_types
    assert "router.success" in event_types
    assert "task.executing" in event_types
    assert "skill.selected" in event_types
    assert "tool.invoking" in event_types
    assert "tool.completed" in event_types
    assert "task.completed" in event_types