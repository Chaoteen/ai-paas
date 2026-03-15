import os

from fastapi.testclient import TestClient


def test_register_agent_and_list_in_memory():
    os.environ["AI_PAAS_USE_POSTGRES"] = "false"

    from main import app

    with TestClient(app) as client:
        register_resp = client.post(
            "/runtime/agents/register",
            json={
                "id": "agent-api-001",
                "name": "api-agent",
                "version": "1.0.0",
                "status": "active",
                "tenant_id": "tenant-a",
                "capabilities": {"kind": "demo"},
                "metadata": {"source": "api-test"},
                "endpoint": "http://localhost:9101",
            },
        )
        assert register_resp.status_code == 200
        body = register_resp.json()
        assert body["ok"] is True
        assert body["agent"]["id"] == "agent-api-001"

        list_resp = client.get("/runtime/agents")
        assert list_resp.status_code == 200
        list_body = list_resp.json()
        assert list_body["ok"] is True
        assert list_body["count"] == 1
        assert list_body["items"][0]["id"] == "agent-api-001"


def test_heartbeat_and_control_events_in_memory():
    os.environ["AI_PAAS_USE_POSTGRES"] = "false"

    from main import app

    with TestClient(app) as client:
        client.post(
            "/runtime/agents/register",
            json={
                "id": "agent-api-002",
                "name": "api-agent-2",
                "version": "1.0.0",
                "status": "active",
                "tenant_id": "tenant-a",
                "capabilities": {},
                "metadata": {},
                "endpoint": "http://localhost:9102",
            },
        )

        hb_resp = client.post("/runtime/agents/agent-api-002/heartbeat")
        assert hb_resp.status_code == 200
        hb_body = hb_resp.json()
        assert hb_body["ok"] is True

        events_resp = client.get("/runtime/control-events?event_type=agent.heartbeat")
        assert events_resp.status_code == 200
        events_body = events_resp.json()
        assert events_body["ok"] is True
        assert events_body["count"] == 1
        assert events_body["items"][0]["agent_id"] == "agent-api-002"


def test_publish_and_list_data_events_in_memory():
    os.environ["AI_PAAS_USE_POSTGRES"] = "false"

    from main import app

    with TestClient(app) as client:
        publish_resp = client.post(
            "/runtime/data-events/publish",
            json={
                "event_type": "task.created",
                "task_id": "task-api-001",
                "execution_id": "exec-api-001",
                "tenant_id": "tenant-a",
                "payload": {"input": "hello"},
            },
        )
        assert publish_resp.status_code == 200
        body = publish_resp.json()
        assert body["ok"] is True
        assert body["event"]["task_id"] == "task-api-001"

        list_resp = client.get("/runtime/data-events?task_id=task-api-001")
        assert list_resp.status_code == 200
        list_body = list_resp.json()
        assert list_body["ok"] is True
        assert list_body["count"] == 1
        assert list_body["items"][0]["execution_id"] == "exec-api-001"