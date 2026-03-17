import pytest

from runtime.runtime_metrics import InMemoryRuntimeMetrics


@pytest.mark.asyncio
async def test_runtime_metrics_counts_core_events():
    metrics = InMemoryRuntimeMetrics()

    await metrics.record_event({"event_type": "task.submitted"})
    await metrics.record_event({"event_type": "tool.invoking"})
    await metrics.record_event({"event_type": "tool.invoking"})
    await metrics.record_event({"event_type": "task.completed"})
    await metrics.record_event({"event_type": "security.denied"})

    snapshot = await metrics.snapshot()

    assert snapshot["events_total"] == 5
    assert snapshot["tasks_submitted"] == 1
    assert snapshot["tool_invocations"] == 2
    assert snapshot["tasks_completed"] == 1
    assert snapshot["security_denied"] == 1