Phase 11
目标

构建 Runtime 状态管理系统

支持：

task lifecycle
workflow lifecycle
submit idempotency
Phase 11 核心组件
RuntimeStateStore

文件

runtime/state_store.py

职责：

管理：

TaskState
WorkflowState
TaskState

任务生命周期：

submitted
executing
completed
failed

字段：

task_id
tenant_id
workflow_id
correlation_id
status
input_payload
result_payload
error
WorkflowState

支持：

multi-task workflow

字段：

workflow_id
tenant_id
status
task_ids
IdempotencyStore

文件

runtime/idempotency.py

职责：

保证：

submit task idempotency

同一 task_id 重复提交时：

不重复执行
Phase 11 API

新增接口：

GET /runtime/tasks/{task_id}/state
GET /runtime/task-states
GET /runtime/workflows/{workflow_id}/state
Phase 11 Worker 执行流程
task.submitted
 ↓
RouterWorker
 ↓
router.success
 ↓
AgentWorker
 ↓
task.executing
 ↓
AgentRuntime
 ↓
task.completed / task.failed
Phase 11 测试

单元测试：

tests/runtime/test_state_store.py
tests/runtime/test_idempotency.py
tests/test_runtime_state_api.py

Integration：

tests/integration/test_runtime_phase11_state_live.py
tests/integration/test_runtime_phase11_submit_idempotency_live.py