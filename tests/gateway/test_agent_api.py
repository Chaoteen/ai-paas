from fastapi.testclient import TestClient

from gateway.main import app
import gateway.api.agent_runtime as agent_api


client = TestClient(app)


class FakeRuntimeSuccess:
    async def execute(self, context, preferred_skill=None):
        return {
            "success": True,
            "status": "completed",
            "output": {
                "mode": "tool",
                "tool_result": {
                    "tool_name": preferred_skill,
                    "status": "ok",
                    "result": {
                        "task_id": context.task_id,
                        "tenant_id": context.tenant_id,
                        "input": context.input_payload,
                        "metadata": context.metadata,
                        "skill_name": preferred_skill,
                    },
                    "metadata": {
                        "skill": preferred_skill,
                        "sandbox_mode": "deny_unsafe",
                    },
                },
                "granted_capabilities": [],
            },
            "error": None,
        }


class FakeRuntimeSkillMissing:
    async def execute(self, context, preferred_skill=None):
        return {
            "success": False,
            "status": "failed",
            "output": {},
            "error": {
                "message": f"Preferred skill not found: {preferred_skill}"
            },
        }


def test_agent_run_success(monkeypatch):
    async def fake_get_runtime():
        return FakeRuntimeSuccess()

    monkeypatch.setattr(agent_api, "get_runtime", fake_get_runtime)

    response = client.post(
        "/api/v1/agent/run",
        json={
            "agent_id": "echo",
            "input": "hello ai-paas",
        },
    )

    assert response.status_code == 200
    body = response.json()

    assert body["success"] is True
    assert body["agent_id"] == "echo"
    assert body["status"] == "completed"
    assert body["output"]["mode"] == "tool"
    assert body["output"]["tool_result"]["tool_name"] == "echo"
    assert body["output"]["tool_result"]["result"]["input"]["input"] == "hello ai-paas"
    assert body["error"] is None


def test_agent_run_skill_not_found_is_normalized(monkeypatch):
    async def fake_get_runtime():
        return FakeRuntimeSkillMissing()

    monkeypatch.setattr(agent_api, "get_runtime", fake_get_runtime)

    response = client.post(
        "/api/v1/agent/run",
        json={
            "agent_id": "demo_agent",
            "input": "hello ai-paas",
        },
    )

    assert response.status_code == 200
    body = response.json()

    assert body["success"] is False
    assert body["agent_id"] == "demo_agent"
    assert body["status"] == "failed"
    assert body["error"]["type"] == "SkillNotFound"
    assert "demo_agent" in body["error"]["message"]
    assert "echo" in body["error"]["hint"]