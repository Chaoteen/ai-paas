Phase 12
目标

构建 Runtime Security Model

实现三层安全控制：

Skill Capability
Tool Capability
Execution Sandbox
Phase 12 安全架构

安全执行链：

AgentRuntime
 ↓
CapabilityGuard
 ↓
PolicyEngine
 ↓
ToolCapabilityGuard
 ↓
SandboxExecutor
 ↓
ToolExecutor
CapabilityGuard

文件：

runtime/capability_guard.py

职责：

校验 skill 所需 capability。

示例：

network
filesystem
shell

若 context 未授权：

Skill execution denied
ToolCapabilityGuard

文件：

runtime/tool_capability_guard.py

职责：

限制 tool 使用能力。

示例：

http_fetch → network
shell_run → shell
SandboxExecutor

文件：

runtime/sandbox_executor.py

职责：

定义 execution boundary。

模式：

default sandbox
inline sandbox

默认模式：

禁止 shell_run
Phase 12 安全控制矩阵
Skill	Capability	Sandbox
echo	none	allowed
http_fetch	network	allowed
shell_run	shell	blocked by default
Phase 12 测试

新增测试：

tests/runtime/test_capability_guard.py
tests/runtime/test_tool_executor.py
tests/runtime/test_sandbox_executor.py

覆盖：

capability validation
tool authorization
sandbox enforcement
Runtime 当前能力

截至 Phase 12：

Runtime Kernel 已具备：

执行能力
AgentRuntime
SkillResolver
ToolExecutor
状态管理
TaskState
WorkflowState
StateStore
IdempotencyStore
安全能力
CapabilityGuard
ToolCapabilityGuard
SandboxExecutor
Worker 系统
RouterWorker
AgentWorker
事件系统
ControlBus
DataBus
RedisStreamBus
Runtime 事件流

完整执行链：

task.submitted
 ↓
router.success
 ↓
task.executing
 ↓
skill.selected
 ↓
tool.invoking
 ↓
tool.completed
 ↓
task.completed
Runtime 目录结构

核心模块：

runtime/
 agent_runtime.py
 skill_registry.py
 skill_resolver.py
 tool_executor.py
 capability_guard.py
 tool_capability_guard.py
 sandbox_executor.py
 state_store.py
 idempotency.py
Data Plane
data_plane/
 data_bus.py
 router_worker.py
 agent_worker.py
 redis_stream_bus.py
Control Plane
control_plane/
 agent_registry.py
 control_bus.py
 repositories/
Bootstrap
bootstrap/runtime_bootstrap.py

职责：

构建 runtime
注入组件
启动 worker
API

入口：

main.py

主要接口：

/health
/runtime/info
/runtime/agents/register
/runtime/tasks/submit
/runtime/tasks/{task_id}/state
/runtime/workflows/{workflow_id}/state
/runtime/data-events
/runtime/control-events
当前 Runtime 成熟度

当前 Runtime 已达到：

Production-ready prototype

具备：

execution kernel
state management
security boundary
event pipeline