AI-PaaS Runtime 交接文档

Phase 15 – Phase 16

Repository
https://github.com/Chaoteen/ai-paas

Current branch

wip/integration-split-commits

Latest milestone

Phase 16D
Async Queue + Worker Runtime Integrated
一、项目总体目标

本项目目标是构建一个 AI-PaaS（AI Platform-as-a-Service）平台。

平台定位：

AI OS for AI Applications

核心设计理念：

AI程序员通过平台模块快速构建 AI 应用

平台需要同时支持：

1 AI开发者能力

统一 runtime

LLM
Tool
Skill
Agent
Generation
Workflow

开发者可以：

调用 Agent
调用 Generation
调用 Skill
组合 AI Workflow
2 模型统一调度

平台必须支持多模型：

OpenAI
Qwen
DeepSeek
Kimi
Minimax
Doubao
Ollama

同时支持：

本地模型
云模型
多 provider
3 多模态能力

平台 Generation Engine 支持：

Text
Image
Video
Future: Audio / 3D
4 兼容 Agent 生态

平台未来需要兼容：

OpenClaw
IronClaw
第三方 Skill

目标：

Skill 可以跨平台运行
二、Runtime 架构设计

Runtime 是 AI-PaaS 平台核心。

整体结构：

Client
   │
Gateway API
   │
TaskEnvelope
   │
Redis Queue
   │
Worker Runtime
   │
Runtime Engine
   │
Model / Skill

完整架构：

                ┌──────────────┐
                │   Gateway    │
                │   FastAPI    │
                └──────┬───────┘
                       │
                Task Submit API
                       │
                ┌──────▼───────┐
                │ TaskEnvelope │
                └──────┬───────┘
                       │
                ┌──────▼───────┐
                │ Redis Stream │
                │   Queue      │
                └──────┬───────┘
                       │
           ┌───────────┼───────────┐
           │                       │
     ┌─────▼─────┐          ┌─────▼─────┐
     │AgentWorker│          │GenWorker  │
     └─────┬─────┘          └─────┬─────┘
           │                       │
           └───────────┬───────────┘
                       ▼
                Runtime Engine
                       │
                Model / Skill
三、Repo 结构（关键）

当前 Runtime 相关结构：

gateway
 ├─ api
 │   ├─ agent_runtime.py
 │   ├─ generation.py
 │   ├─ tasks.py
 │   ├─ ui.py
 │   └─ health.py
 └─ core

runtime
 ├─ queue
 │   ├─ task_models.py
 │   ├─ task_store.py
 │   └─ redis_queue.py
 │
 ├─ workers
 │   ├─ worker_base.py
 │   ├─ agent_worker.py
 │   └─ generation_worker.py
 │
 ├─ generation
 ├─ agent
 └─ execution_context.py

tests
 ├─ gateway
 │   ├─ test_agent_api.py
 │   ├─ test_generation_api.py
 │   └─ test_tasks_api.py
 │
 └─ runtime
     ├─ test_task_models.py
     ├─ test_redis_queue.py
     └─ test_workers.py
四、Phase15：Gateway Runtime API

新增 API：

Agent
POST /api/v1/agent/run

同步执行 Agent。

Generation
POST /api/v1/generation/image
POST /api/v1/generation/video

同步执行生成任务。

Health
GET /api/health

用于系统健康检查。

五、Phase16：Async Runtime

Phase16 的目标：

引入 Queue + Worker
实现异步 Runtime
Phase16A：TaskEnvelope

新增：

runtime/queue/task_models.py

定义：

TaskEnvelope
TaskStatus

AgentTaskPayload
GenerationTaskPayload

任务生命周期：

CREATED
QUEUED
RUNNING
SUCCEEDED
FAILED
Phase16B：Task Submit API

新增 API：

POST /api/v1/agent/submit
POST /api/v1/generation/image/submit
POST /api/v1/generation/video/submit
GET  /api/v1/tasks/{task_id}

功能：

提交任务
查询任务状态

实现文件：

gateway/api/tasks.py
Phase16C：Redis Queue Client

新增模块：

runtime/queue/redis_queue.py

核心能力：

publish_task()
read_tasks()
ack_task()
ensure_consumer_group()

使用 Redis Streams：

XADD
XREADGROUP
XACK
Phase16D：Worker Runtime

新增模块：

runtime/workers
WorkerBase

统一消费循环：

poll queue
execute task
update store
ack queue
AgentWorker

执行：

AgentRuntime.execute()

消费：

agent queue
GenerationWorker

执行：

GenerationService.generate()

消费：

generation queue
六、测试覆盖

当前测试覆盖：

Gateway：

tests/gateway/test_agent_api.py
tests/gateway/test_generation_api.py
tests/gateway/test_tasks_api.py
tests/gateway/test_health_api.py

Runtime：

tests/runtime/test_task_models.py
tests/runtime/test_redis_queue.py
tests/runtime/test_workers.py

当前测试结果：

13 passed
七、系统启动方式

当前开发模式：

启动 Gateway
uvicorn gateway.main:app --host 0.0.0.0 --port 8000
Redis

开发环境：

redis-server

默认连接：

redis://127.0.0.1:6379/0
Worker（未来）

Worker 将作为独立进程运行：

python -m runtime.workers.agent_worker
python -m runtime.workers.generation_worker

（Phase16E 实现）

八、当前限制

当前系统仍有一些限制：

TaskStore

当前实现：

InMemoryTaskStore

未来需要：

Redis / PostgreSQL
Worker 入口

目前 Worker 只有 runtime 类，没有启动入口。

需要：

worker main
supervisor
systemd
Retry策略

当前：

简单 retry_count

未来需要：

指数退避
dead letter queue
九、下一阶段开发计划

推荐路线：

Phase16E

Worker 启动入口

新增：

runtime/workers/run_agent_worker.py
runtime/workers/run_generation_worker.py

实现：

worker main loop
Phase16F

Task 持久化

新增：

task_result_store

存储：

PostgreSQL
Phase17

External Connectors

Feishu
Slack
Email
Webhook
十、当前平台能力总结

当前 AI-PaaS Runtime 已具备：

Gateway API
agent runtime
generation
task submit
task query
Async Runtime
TaskEnvelope
Redis Queue
Worker Runtime
AI Runtime Engine
Agent Runtime
Generation Engine

平台已完成 核心 Runtime 架构搭建。

下一阶段重点：

worker orchestration
task persistence
connector integration


六、当前正式启动口径（重要）

当前仓库正式主线启动口径如下：

基础设施：
- Redis
- OPA

后端主线：
- Gateway / Main App
- 默认访问地址：http://localhost:8000

前端主线：
- webapp + Vite
- 默认访问地址：http://localhost:5173

说明：
- Flowise 可以作为历史集成组件或外部能力存在
- 但不再作为当前正式主线前端
- `start_frontend.sh` 的正式语义应指向 webapp/Vite，而不是 Flowise:3000

