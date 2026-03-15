import os

from fastapi.testclient import TestClient


def test_runtime_bootstrap_postgres_mode():
    os.environ["AI_PAAS_USE_POSTGRES"] = "true"
    os.environ["POSTGRES_HOST"] = os.getenv("TEST_POSTGRES_HOST", "127.0.0.1")
    os.environ["POSTGRES_PORT"] = os.getenv("TEST_POSTGRES_PORT", "5432")
    os.environ["POSTGRES_DB"] = os.getenv("TEST_POSTGRES_DB", "ai_paas_test")
    os.environ["POSTGRES_USER"] = os.getenv("TEST_POSTGRES_USER", "postgres")
    os.environ["POSTGRES_PASSWORD"] = os.getenv("TEST_POSTGRES_PASSWORD", "postgres")

    from main import app

    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["runtime_mode"] == "postgres"


def test_register_agent_and_query_in_postgres():
    os.environ["AI_PAAS_USE_POSTGRES"] = "true"
    os.environ["POSTGRES_HOST"] = os.getenv("TEST_POSTGRES_HOST", "127.0.0.1")
    os.environ["POSTGRES_PORT"] = os.getenv("TEST_POSTGRES_PORT", "5432")
    os.environ["POSTGRES_DB"] = os.getenv("TEST_POSTGRES_DB", "ai_paas_test")
    os.environ["POSTGRES_USER"] = os.getenv("TEST_POSTGRES_USER", "postgres")
    os.environ["POSTGRES_PASSWORD"] = os.getenv("TEST_POSTGRES_PASSWORD", "postgres")

    from main import app

    with TestClient(app) as client:
        register_resp = client.post(
            "/runtime/agents/register",
            json={
                "id": "agent-pg-api-001",
                "name": "postgres-api-agent",
                "version": "1.0.0",
                "status": "active",
                "tenant_id": "tenant-a",
                "capabilities": {"kind": "worker"},
                "metadata": {"source": "postgres-api-test"},
                "endpoint": "http://localhost:9201",
            },
        )
        assert register_resp.status_code == 200
        register_body = register_resp.json()
        assert register_body["ok"] is True
        assert register_body["agent"]["id"] == "agent-pg-api-001"

        list_resp = client.get("/runtime/agents")
        assert list_resp.status_code == 200
        list_body = list_resp.json()
        assert list_body["ok"] is True
        assert list_body["count"] >= 1

        ids = [item["id"] for item in list_body["items"]]
        assert "agent-pg-api-001" in ids


def test_heartbeat_and_control_event_in_postgres():
    os.environ["AI_PAAS_USE_POSTGRES"] = "true"
    os.environ["POSTGRES_HOST"] = os.getenv("TEST_POSTGRES_HOST", "127.0.0.1")
    os.environ["POSTGRES_PORT"] = os.getenv("TEST_POSTGRES_PORT", "5432")
    os.environ["POSTGRES_DB"] = os.getenv("TEST_POSTGRES_DB", "ai_paas_test")
    os.environ["POSTGRES_USER"] = os.getenv("TEST_POSTGRES_USER", "postgres")
    os.environ["POSTGRES_PASSWORD"] = os.getenv("TEST_POSTGRES_PASSWORD", "postgres")

    from main import app

    with TestClient(app) as client:
        client.post(
            "/runtime/agents/register",
            json={
                "id": "agent-pg-api-002",
                "name": "postgres-heartbeat-agent",
                "version": "1.0.0",
                "status": "active",
                "tenant_id": "tenant-a",
                "capabilities": {},
                "metadata": {},
                "endpoint": "http://localhost:9202",
            },
        )

        hb_resp = client.post("/runtime/agents/agent-pg-api-002/heartbeat")
        assert hb_resp.status_code == 200
        hb_body = hb_resp.json()
        assert hb_body["ok"] is True

        events_resp = client.get("/runtime/control-events?event_type=agent.heartbeat")
        assert events_resp.status_code == 200
        events_body = events_resp.json()
        assert events_body["ok"] is True
        assert events_body["count"] >= 1

        matched = [item for item in events_body["items"] if item["agent_id"] == "agent-pg-api-002"]
        assert len(matched) == 1


def test_publish_and_query_data_events_in_postgres():
    os.environ["AI_PAAS_USE_POSTGRES"] = "true"
    os.environ["POSTGRES_HOST"] = os.getenv("TEST_POSTGRES_HOST", "127.0.0.1")
    os.environ["POSTGRES_PORT"] = os.getenv("TEST_POSTGRES_PORT", "5432")
    os.environ["POSTGRES_DB"] = os.getenv("TEST_POSTGRES_DB", "ai_paas_test")
    os.environ["POSTGRES_USER"] = os.getenv("TEST_POSTGRES_USER", "postgres")
    os.environ["POSTGRES_PASSWORD"] = os.getenv("TEST_POSTGRES_PASSWORD", "postgres")

    from main import app

    with TestClient(app) as client:
        publish_resp = client.post(
            "/runtime/data-events/publish",
            json={
                "event_type": "task.created",
                "task_id": "task-pg-api-001",
                "execution_id": "exec-pg-api-001",
                "tenant_id": "tenant-a",
                "payload": {"input": "hello-postgres"},
            },
        )
        assert publish_resp.status_code == 200
        publish_body = publish_resp.json()
        assert publish_body["ok"] is True
        assert publish_body["event"]["task_id"] == "task-pg-api-001"

        list_resp = client.get("/runtime/data-events?task_id=task-pg-api-001")
        assert list_resp.status_code == 200
        list_body = list_resp.json()
        assert list_body["ok"] is True
        assert list_body["count"] >= 1

        matched = [item for item in list_body["items"] if item["task_id"] == "task-pg-api-001"]
        assert len(matched) == 1