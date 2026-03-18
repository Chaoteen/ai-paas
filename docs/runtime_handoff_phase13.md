AI-PaaS Runtime
Developer Handoff Document (Phase 10–13)

Repository
https://github.com/Chaoteen/ai-paas

Branch

wip/integration-split-commits

Author
Runtime Development AI

1 Project Vision

本项目的目标是构建一个 AI-PaaS 平台（AI Platform-as-a-Service）。

平台定位：

一个让 AI 程序员构建 AI 应用的平台。

同时需要兼容现有 AI Agent 生态，例如：

OpenClaw

各类 Agent Framework

云厂商 Agent Runtime

最终形态：

AI OS Runtime

或

AI-Native Application Platform

该平台提供：

Agent Runtime

Skill execution

Tool orchestration

Model abstraction

Workflow execution

Security isolation

Observability

目标是成为：

OpenClaw Compatible AI-PaaS Runtime Kernel
2 Platform Design Goals

平台设计有三个核心目标。

2.1 AI-PaaS 应用开发平台

平台必须允许 AI 开发者通过 API 构建 AI 应用。

系统调用关系：

AI Developer
   ↓
AI-PaaS Runtime
   ↓
Agent
   ↓
Skill
   ↓
Tool / Model

开发者可以：

注册 Agent

调用 Skill

调用 Tool

调用 LLM

构建 Workflow

典型 API：

POST /runtime/agents/register
POST /runtime/tasks/submit
GET  /runtime/tasks/{task_id}/state

开发者 不需要关心底层系统实现：

worker

event bus

runtime execution

security isolation

sandbox

这些全部由 Runtime Kernel 管理。

2.2 OpenClaw Compatibility

平台必须兼容 OpenClaw Agent 生态。

原因：

OpenClaw 已经存在大量：

Agents

Skills

Tools

如果平台不兼容这些生态：

开发者迁移成本会非常高。

因此 Runtime 设计为：

OpenClaw Compatible Runtime

兼容层包括：

Skill registry

Tool execution

Capability model

Skill resolution

Skill 来源支持：

bundled skills
local skills
workspace skills
external skills

统一由：

SkillResolver

负责解析。

2.3 Model Abstraction Layer

Runtime 必须支持：

本地模型

Ollama

vLLM

TensorRT-LLM

云模型

OpenAI

Anthropic

Qwen API

DeepSeek API

Azure OpenAI

Runtime 通过统一接口调用模型：

LLMAdapter

当前实现：

NoopLLMAdapter

未来计划：

OllamaAdapter
OpenAIAdapter
QwenAdapter
DeepSeekAdapter
3 Platform Architecture

整个系统架构如下：

                 +----------------------+
                 |       Web UI         |
                 |   SDK / API Client   |
                 +-----------+----------+
                             |
                             v

                     +-------+-------+
                     |    Gateway    |
                     | Auth / ABAC   |
                     +-------+-------+
                             |
            +----------------+----------------+
            |                                 |
            v                                 v

     +-------------+                   +--------------+
     | ControlPlane|                   |   DataPlane  |
     |-------------|                   |--------------|
     |AgentRegistry|                   |RouterWorker  |
     |PolicyEngine |                   |AgentWorker   |
     |Config Mgmt  |                   |DataBus       |
     +------+------+
            |
            v

        +---+----------------------+
        |      Runtime Kernel      |
        |--------------------------|
        | AgentRuntime             |
        | SkillResolver            |
        | ToolExecutor             |
        | CapabilityGuard          |
        | LLMAdapter               |
        +-------------+------------+
                      |
                      v
            +----------------------+
            | Skill / Tool / LLM  |
            +----------------------+

Runtime Kernel 是整个系统核心。

4 Runtime Execution Flow

Runtime 使用 事件驱动架构。

任务执行流程：

Client
  |
  v

POST /runtime/tasks/submit
  |
  v

RouterWorker
  |
  v

AgentWorker
  |
  v

AgentRuntime.execute()
  |
  +---- SkillResolver
  |
  +---- CapabilityGuard
  |
  +---- ToolExecutor
  |
  +---- LLMAdapter
  |
  v

Task Result

事件流：

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
5 Platform Layer Model

系统分为五层：

Control Plane
Data Plane
Runtime Kernel
Security Layer
Observability Layer
5.1 Control Plane

负责：

Agent 管理

Control events

配置管理

目录：

control_plane/

核心组件：

AgentRegistry
ControlBus
5.2 Data Plane

负责：

Task execution

Event streaming

Worker execution

目录：

data_plane/

核心模块：

RouterWorker
AgentWorker
DataBus
RedisStreamBus
5.3 Runtime Kernel

Runtime Kernel 是整个系统核心。

目录：

runtime/

核心模块：

agent_runtime.py
skill_registry.py
skill_resolver.py
tool_executor.py

职责：

Agent 执行

Skill 解析

Tool 调用

LLM 调用

5.4 Security Layer

安全控制层。

模块：

capability_guard.py
tool_capability_guard.py
sandbox_executor.py

执行链：

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
5.5 Observability Layer

可观测系统。

模块：

trace_store.py
runtime_metrics.py

API：

/runtime/trace/{task_id}
/runtime/metrics
6 Current Development Status

Runtime 已完成：

Phase 10
Phase 11
Phase 12
Phase 13
Phase 10
AgentRuntime Execution Engine

新增模块：

AgentRuntime
SkillResolver
ToolExecutor

职责：

解析 skill

执行 skill

调用 tool

调用 llm

测试：

tests/runtime/test_agent_runtime.py
Phase 11
Runtime State Management

新增模块：

state_store.py
workflow_state.py
idempotency.py

能力：

Task lifecycle

Workflow lifecycle

Submit idempotency

API：

GET /runtime/tasks/{task_id}/state
GET /runtime/workflows/{workflow_id}/state

测试：

test_runtime_state_api.py
test_runtime_phase11_state_live.py
Phase 12
Runtime Security Model

新增模块：

capability_guard.py
tool_capability_guard.py
sandbox_executor.py

提供：

Tool capability control

Sandbox execution

Security policy enforcement

测试：

test_capability_guard.py
test_tool_executor.py
test_sandbox_executor.py
Phase 13
Runtime Observability

新增模块：

trace_store.py
runtime_metrics.py

API：

/runtime/trace/{task_id}
/runtime/metrics

Integration tests：

test_runtime_phase13_trace_live.py
test_runtime_phase13_metrics_live.py
7 Runtime Capabilities

当前 Runtime 已具备：

执行系统：

AgentRuntime
SkillResolver
ToolExecutor

状态系统：

StateStore
WorkflowState
IdempotencyStore

安全系统：

CapabilityGuard
ToolCapabilityGuard
SandboxExecutor

可观测系统：

TraceStore
RuntimeMetrics

事件系统：

DataBus
ControlBus
RedisStreamBus
8 Repository Structure

核心目录：

runtime/
data_plane/
control_plane/
bootstrap/
tests/

Runtime 目录：

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
trace_store.py
runtime_metrics.py
9 Development Startup Guide
1 启动基础组件

Redis

docker run -d -p 6379:6379 redis:7

OPA

docker run -d -p 8181:8181 openpolicyagent/opa run --server
2 启动 Runtime

进入项目目录：

cd ai-paas

启动 runtime：

python main.py
3 启动 Worker
python data_plane/router_worker.py
python data_plane/agent_worker.py
4 运行测试
pytest tests/
10 Next Development Roadmap

建议继续以下迭代。

Phase 14

Model Adapter Layer

新增：

llm_adapters/

支持：

Ollama
OpenAI
Qwen
DeepSeek
Phase 15

OpenClaw Compatibility Layer

新增：

openclaw_skill_loader
openclaw_agent_adapter
Phase 16

Audit Trail

新增：

audit_store.py

API：

/runtime/audit
/runtime/security-events

记录：

security.denied
policy.denied
sandbox.denied
Phase 17

Skill Marketplace

新增：

skill_package_manager
skill_install
skill_versioning
11 First Steps for Next Developer

下一位开发者接手时，请先：

1 阅读 GitHub 仓库代码
2 理解 Runtime 执行链
3 阅读 runtime/ 目录
4 阅读 data_plane/ worker

重点阅读：

runtime/agent_runtime.py
runtime/tool_executor.py
runtime/state_store.py
data_plane/router_worker.py
data_plane/agent_worker.py

理解执行流程后，再开始下一阶段开发。

12 Final Platform Goal

本项目最终目标：

构建一个

OpenClaw Compatible AI-PaaS

支持：

Agent
Skill
Tool
Workflow
Model

成为：

AI OS Runtime Kernel

一个能够运行 AI 原生应用（AI-Native Applications） 的平台。