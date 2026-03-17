这份文档的目标是：

让下一位开发人员快速理解系统

明确当前开发进度

明确下一阶段开发内容

避免再次踩到本轮调试中遇到的坑

AI-PaaS Runtime 系统交接文档

Phase 7 Checkpoint

更新时间：2026-03-16
代码仓库：

https://github.com/Chaoteen/ai-paas

当前开发分支：

wip/integration-split-commits
一、项目总体目标

本项目目标是构建一个 可扩展的 AI-PaaS 平台，核心能力包括：

多 Agent 协作

多模型调度

事件驱动架构

Control Plane / Data Plane 解耦

Redis Streams 作为事件总线

PostgreSQL 作为 Runtime 持久化

系统最终形态：

                AI-PaaS Platform

                ┌─────────────┐
                │   API Layer │
                └──────┬──────┘
                       │
                ┌──────▼──────┐
                │ ControlPlane │
                │ AgentRegistry│
                │ ControlBus   │
                └──────┬──────┘
                       │
           ┌───────────▼───────────┐
           │      Redis Streams    │
           │   control.events      │
           │   data.events         │
           └───────────┬───────────┘
                       │
                ┌──────▼──────┐
                │  DataPlane  │
                │   Router    │
                │   Workflow  │
                │   Workers   │
                └──────┬──────┘
                       │
               ┌───────▼────────┐
               │ PostgreSQL DB  │
               │ runtime state  │
               └────────────────┘
二、系统架构概览

系统采用 事件驱动架构。

核心组件：

1 Control Plane

负责管理 Agent 生命周期与控制事件。

模块：

control_plane/
 ├─ agent_registry.py
 ├─ control_bus.py
 └─ repositories/
     └─ postgres_control_event_repository.py

职责：

Agent 注册

Agent 心跳

Agent 状态管理

发布 control events

事件流：

Agent API
   │
   ▼
AgentRegistry
   │
   ▼
ControlBus
   │
   ├── Redis Streams
   │
   └── PostgreSQL
2 Data Plane

负责任务执行与工作流。

模块：

data_plane/
 ├─ data_bus.py
 ├─ event_envelope.py
 └─ redis_stream_bus.py

职责：

任务事件发布

Router 任务分发

Workflow 运行

Worker 执行

3 Runtime Persistence

数据库：

PostgreSQL
database: ai_paas_runtime

作用：

持久化 Agent

持久化事件

提供审计能力

支持事件回放

三、当前数据库结构

数据库：

ai_paas_runtime

核心表：

agents
agents

字段：

id
name
version
status
tenant_id
capabilities
metadata
heartbeat_at
created_at
updated_at

用途：

Agent 注册信息

Agent 状态

control_events
control_events

字段：

id
event_type
agent_id
tenant_id
payload
occurred_at

说明：

payload 存储完整事件
agent_id / tenant_id 用于索引查询
四、Redis Streams 事件总线

当前系统使用 Redis Streams 作为事件总线。

Streams：

control.events
data.events

示例：

redis-cli XINFO STREAM control.events

事件结构：

{
  event_id
  event_type
  stream
  source
  payload
  tenant_id
  correlation_id
  occurred_at
  schema_version
}
五、Phase 6 开发内容

Phase 6 主要完成：

PostgreSQL Runtime Persistence

新增：

bootstrap/runtime_bootstrap.py

功能：

初始化数据库连接

创建 AsyncSession

提供 RuntimeDB

重要修复：

AsyncSession commit/rollback 自动管理

避免：

flush 后未 commit 导致数据未落库
六、Phase 7 开发内容

Phase 7 主要目标：

Redis Streams Event Bus

新增模块：

data_plane/event_envelope.py
data_plane/redis_stream_bus.py
bootstrap/event_bus_factory.py

新增能力：

事件统一封装
Redis Streams 发布
事件 schema version
ControlBus 修复

修复问题：

agent_id 未写入 control_events 列
只存在 payload 中

修复方式：

在 publish 时提升字段：

payload.agent_id → event.agent_id

现在结构：

control_events
 ├─ agent_id
 └─ payload.agent_id

两者同时存在。

七、已验证接口

API：

注册 Agent
POST /runtime/agents/register

示例：

curl -X POST http://127.0.0.1:8000/runtime/agents/register

返回：

{
  ok: true
}
查询 Agent
GET /runtime/agents
查询 Control Events
GET /runtime/control-events
八、当前系统状态

当前系统已完成：

Postgres Runtime Persistence
Redis Streams ControlBus
Agent Registry
control_events schema alignment

事件链路：

API
 │
AgentRegistry
 │
ControlBus
 │
 ├─ Redis Streams
 └─ PostgreSQL

系统稳定。

九、下一阶段开发

下一阶段：

Phase 8

目标：

DataPlane Router
Phase 8 任务
1 Data Events Schema

新增表：

data_events

字段建议：

id
event_type
task_id
workflow_id
tenant_id
payload
occurred_at
2 DataBus Persistence

对齐：

data_bus.py

要求：

task_id
workflow_id
写入数据库列

避免字段仅存在 payload。

3 Router Worker

新增模块：

router_worker.py

职责：

消费 data.events
任务路由
选择 Agent
发布 router.success
4 Worker Execution

Worker：

agent_worker

消费：

router.success

执行：

模型调用
工具调用
十、推荐开发顺序

建议严格按照顺序开发：

Phase 8
 ├─ data_events schema
 ├─ DataBus persistence
 ├─ Router Worker
 └─ Router events

然后进入：

Phase 9
Workflow Engine
十一、关键经验（本轮调试总结）

开发中遇到的主要问题：

1 PostgreSQL session 未 commit

问题：

flush 之后未 commit
数据未落库

解决：

RuntimeDB session 自动 commit
2 事件字段未映射

问题：

agent_id 在 payload 中
但 DB 列为空

解决：

publish 时提升字段
3 数据库旧结构冲突

解决：

新建 runtime 数据库
ai_paas_runtime

避免旧表干扰。

十二、当前代码关键目录
ai-paas/
 ├─ bootstrap/
 │   ├─ runtime_bootstrap.py
 │   └─ event_bus_factory.py
 │
 ├─ control_plane/
 │   ├─ agent_registry.py
 │   ├─ control_bus.py
 │   └─ repositories/
 │
 ├─ data_plane/
 │   ├─ data_bus.py
 │   ├─ event_envelope.py
 │   └─ redis_stream_bus.py
 │
 ├─ migrations_runtime/
 │   └─ 001_runtime_init.sql
 │
 ├─ tests/
 │
 └─ main.py
十三、系统启动方式

进入项目：

cd ~/work/ai-paas

启动服务：

uvicorn main:app --reload

验证：

curl http://127.0.0.1:8000/runtime/info
十四、下一位开发者需要做的事情

第一步：

阅读本文件

第二步：

检查数据库 ai_paas_runtime

第三步：

验证 Redis Streams

第四步：

实现 data_events + Router Worker
十五、阶段总结

当前完成阶段：

Phase 7
Redis Streams Event Bus

系统状态：

稳定
可继续开发

下一阶段：

Phase 8
Router Worker