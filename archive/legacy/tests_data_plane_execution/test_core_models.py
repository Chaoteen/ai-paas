from control_plane.context import ExecutionContext
from control_plane.decision import PolicyDecision
from data_plane.result import ExecutionResult


def test_execution_context_input_alias():
    ctx = ExecutionContext(
        request_id="req_1",
        subject={"tenant_id": "t1"},
        action="prompt.execute",
        resource={"type": "prompt", "id": "default"},
        environment={"region": "default"},
        input_payload={"text": "hello"},
    )
    assert ctx.input == {"text": "hello"}
    assert ctx.to_dict()["input"] == {"text": "hello"}


def test_policy_decision_to_dict():
    decision = PolicyDecision.allow_decision(
        capabilities={"allowed_agents": ["agent.default"]}
    )
    data = decision.to_dict()
    assert data["allow"] is True
    assert data["capabilities"]["allowed_agents"] == ["agent.default"]


def test_execution_result_compatibility_fields():
    result = ExecutionResult.success_result(output={"text": "ok"})
    assert result.ok is True
    assert result.success is True
    assert result.status == "success"

    data = result.to_dict()
    assert data["ok"] is True
    assert data["success"] is True
    assert data["status"] == "success"
    assert data["output"] == {"text": "ok"}


def test_execution_result_error():
    result = ExecutionResult.error_result("boom")
    assert result.ok is False
    assert result.success is False
    assert result.status == "error"
    assert result.error == "boom"