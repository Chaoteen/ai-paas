AI-PaaS Runtime 交接文档（Enhanced）

Project
AI-PaaS Platform

Repository

https://github.com/Chaoteen/ai-paas

Branch

wip/integration-split-commits

当前开发阶段

Phase 14C-3
Multimodal Generation Integrated into Agent Runtime
一、平台目标

本项目目标是构建一个 AI-PaaS（AI Platform-as-a-Service）平台。

定位：

AI OS for AI applications

平台希望实现：

1 AI程序员开发平台

提供统一 runtime：

LLM
Tool
Skill
Generation
Agent

AI开发者只需要：

定义 agent

定义 skill

定义 prompt

即可构建 AI 应用。

2 多模型统一调度

支持：

OpenAI
Qwen
DeepSeek
Kimi
Minimax
Doubao
Ollama (local)

统一接口：

ModelService
3 多模态 AI 能力

当前支持：

Text generation
Image generation
Video generation

未来：

Audio generation
3D generation
4 构建统一 Agent Runtime

统一执行链：

Agent
 ↓
LLM
 ↓
Tool
 ↓
Skill
 ↓
Generation
二、代码 Repo 结构

项目结构如下：

ai-paas
│
├─ bootstrap/
│   ├─ runtime_bootstrap.py
│   └─ generation_bootstrap.py
│
├─ runtime/
│   │
│   ├─ agent_runtime.py
│   │
│   ├─ models/
│   │   ├─ model_registry.py
│   │   ├─ model_selector.py
│   │   ├─ model_service.py
│   │   └─ adapters/
│   │
│   ├─ generation/
│   │   ├─ generation_registry.py
│   │   ├─ generation_selector.py
│   │   ├─ generation_service.py
│   │   └─ adapters/
│   │
│   ├─ tools/
│   │   └─ generation_tools.py
│   │
│   ├─ tool_executor.py
│   └─ tool_capability_guard.py
│
├─ data_plane/
│   ├─ data_bus.py
│   └─ data_events.py
│
├─ control_plane/
│
├─ tests/
│
└─ webapp/
三、模块职责说明
bootstrap

负责系统启动与依赖注入。

runtime_bootstrap.py

构建：

AgentRuntime

注入：

ModelService
ToolExecutor
GenerationToolSet
TraceStore
RuntimeMetrics
generation_bootstrap.py

构建：

GenerationRegistry
GenerationToolSet

注册：

seedance adapter
mock image adapter
runtime 模块

核心 Runtime Kernel。

agent_runtime.py

负责：

Agent执行流程

职责：

接收任务
执行 LLM
执行 tool
返回结果
runtime/models

实现 LLM 调度层。

结构：

ModelRegistry
ModelSelector
ModelService
Adapters
ModelRegistry

负责：

注册所有模型
alias解析
ModelSelector

根据：

routing_policy
capabilities

选择模型。

支持策略：

local_first
cloud_first
cost_optimized
balanced
ModelService

统一调用模型：

provider adapter
adapters

实现各 provider：

openai_adapter
qwen_adapter
deepseek_adapter
kimi_adapter
minimax_adapter
doubao_adapter
ollama_adapter
runtime/generation

实现 多模态生成能力。

模块：

GenerationRegistry
GenerationSelector
GenerationService
GenerationRegistry

注册：

image models
video models
GenerationSelector

选择：

image provider
video provider
GenerationService

统一执行：

image generation
video generation
runtime/tools

工具层。

当前：

generation_tools.py

提供：

generation.image
generation.video
runtime/tool_executor

执行工具。

执行流程：

ToolExecutor
 ↓
CapabilityGuard
 ↓
SandboxExecutor
 ↓
Tool execution
四、Runtime 执行流程

完整执行流程：

User Request
    │
    ▼
Gateway API
    │
    ▼
AgentRuntime
    │
    ├─ LLM call
    │
    ├─ Tool call
    │
    └─ Generation call
            │
            ▼
      GenerationService
            │
            ▼
      GenerationAdapter
五、数据库 Schema

数据库：

PostgreSQL

ORM：

SQLAlchemy Async
Execution 表
CREATE TABLE executions (
    execution_id UUID PRIMARY KEY,
    agent_id TEXT,
    tenant_id TEXT,
    status TEXT,
    input JSONB,
    output JSONB,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

用途：

记录Agent执行
支持审计
支持Replay
Trace 表
CREATE TABLE traces (
    trace_id UUID PRIMARY KEY,
    execution_id UUID,
    span_name TEXT,
    payload JSONB,
    created_at TIMESTAMP
);

记录：

LLM调用
Tool调用
Generation调用
Data Events
CREATE TABLE data_events (
    event_id UUID PRIMARY KEY,
    event_type TEXT,
    payload JSONB,
    timestamp TIMESTAMP
);

用途：

Runtime events
Router events
Telemetry
六、系统启动方式

当前系统需要：

PostgreSQL
Redis
OPA
1 启动依赖

PostgreSQL

docker run -p 5432:5432 postgres

Redis

docker run -p 6379:6379 redis

OPA

opa run --server
2 启动 Runtime
python main.py
3 Worker（未来）
python runtime/worker/worker.py
4 前端
cd webapp

npm install

npm run dev
七、Phase 13 开发内容

Phase 13 目标：

统一模型调用架构

新增模块：

runtime/models

核心组件：

ModelRegistry
ModelSelector
RoutingPolicy
ModelService
ModelBackedLLMAdapter

支持 provider：

OpenAI
Qwen
DeepSeek
Kimi
Minimax
Doubao
Ollama
八、Phase 14 开发内容

Phase14目标：

多模态生成能力
Phase 14C-1

Generation Engine

新增模块：

runtime/generation/

文件：

generation_registry.py
generation_selector.py
generation_service.py
Phase 14C-2

Adapters

runtime/generation/adapters/

新增：

seedance_adapter.py
mock_image_adapter.py
Phase 14C-3

Agent Integration

新增：

runtime/tools/generation_tools.py
bootstrap/generation_bootstrap.py

调用链：

AgentRuntime
 ↓
ToolExecutor
 ↓
GenerationToolSet
 ↓
GenerationService
九、未来 Roadmap
Phase 15

Gateway API

新增模块：

gateway/
    app.py
    agent_api.py
    generation_api.py

接口：

POST /v1/agent/run
POST /v1/generation/image
POST /v1/generation/video

职责：

HTTP → Runtime
Phase 16

Worker Runtime

使用：

Redis Streams

架构：

Gateway
  │
  ▼
Redis Streams
  │
  ▼
Worker Runtime
  │
  ▼
AgentRuntime

新增：

runtime/worker/
runtime/queue/
Phase 17

IM Connector

新增：

connectors/

支持：

Feishu
DingTalk
WeChat
十、架构优化建议

当前结构：

Tool
Generation

未来建议统一：

Tool
   ├─ llm tool
   ├─ generation tool
   ├─ api tool

这样 runtime 更统一。

十一、开发协作模式

开发分工：

架构负责人

负责：

系统架构
模块边界
API设计
Roadmap
程序员职责

负责：

模块实现
测试编写
Bug修复

必须遵守：

模块解耦

禁止跨模块依赖。

例如：

runtime/models
runtime/generation
runtime/tools
必须写测试

测试类型：

unit tests
integration tests
Provider Adapter 必须独立

例如：

kimi_adapter
minimax_adapter
doubao_adapter
Runtime 必须 async

禁止同步 IO。

十二、平台当前能力

当前 runtime 已具备：

LLM Engine
Model routing
Multi provider support
Image generation
Video generation
Agent runtime
Tool runtime

平台已经具备：

AI-PaaS Runtime Kernel

下一阶段重点：

Gateway
Worker runtime
IM integration
Skill marketplace