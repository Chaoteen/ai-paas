# AI-PaaS Runtime 系统交接文档
## Phase 8 Checkpoint

更新时间：2026-03-17

代码仓库：
https://github.com/Chaoteen/ai-paas

当前开发分支：
wip/integration-split-commits

---

## 一、Phase 8 目标

Phase 8 的目标是打通 Data Plane 的基础路由链路，使系统从“事件可写入”推进到“事件可被路由”。

目标链路：

API / Task Submit
→ DataBus.publish()
→ PostgreSQL data_events_v2
→ Redis Stream data.events
→ RouterWorker.consume()
→ Agent capability routing
→ router.success / router.failed
→ PostgreSQL data_events_v2

---

## 二、Phase 8 已完成内容

### 1. 新增任务提交接口

接口：

POST /runtime/tasks/submit

请求字段：

- tenant_id
- task_id
- workflow_id
- correlation_id
- required_capability
- input
- metadata

作用：

提交 task.submitted 事件到 DataBus。

---

### 2. Data Events 统一事件结构落地

当前 Data Plane 事件统一字段：

- id
- event_type
- stream
- source
- tenant_id
- correlation_id
- task_id
- workflow_id
- payload
- occurred_at
- schema_version
- retry_count
- headers

说明：

本阶段确定采用方案 A：
事件唯一主键统一为 id，使用 UUID。

不再长期保留 event_id 作为并行主标识。

---

### 3. 新增 PostgreSQL 表 data_events_v2

表用途：

- Data Plane 事件持久化
- 审计
- 路由结果查询
- 后续 workflow / worker 回放基础

核心字段：

- id UUID PRIMARY KEY
- event_type
- stream
- source
- tenant_id
- correlation_id
- task_id
- workflow_id
- payload JSONB
- occurred_at
- created_at
- schema_version
- retry_count
- headers JSONB

---

### 4. DataBus 已实现双通道写入

DataBus.publish() 当前行为：

1. 构建 EventEnvelope
2. 写 PostgreSQL data_events_v2
3. 写 Redis Stream data.events

已验证 task.submitted 可同时写入 PostgreSQL 和 Redis。

---

### 5. RouterWorker 已实现

模块：

data_plane/router_worker.py

职责：

- 消费 Redis Stream data.events
- 处理 task.submitted
- 基于 tenant_id / status / capabilities 选择 Agent
- 发布 router.success 或 router.failed

当前筛选规则：

- tenant_id 必须一致
- status 必须在 healthy / online / ready / active
- capabilities.skills 必须包含 required_capability

当前排序规则：

- heartbeat_at / last_heartbeat_at / updated_at 取最大时间，最新优先

---

### 6. 成功路径已验证

测试任务：

task_002

结果：

- task.submitted 成功写入
- RouterWorker 成功消费
- 成功选中 agent_translation_001
- 成功写入 router.success

---

### 7. 失败路径已验证

测试任务：

task_003

required_capability：

non_existing_skill

结果：

- task.submitted 成功写入
- RouterWorker 成功消费
- 无符合条件 Agent
- 成功写入 router.failed

---

### 8. 单元测试已通过

测试文件：

- tests/test_data_bus.py
- tests/test_router_worker.py

结果：

全部通过。

---

## 三、Phase 8 中修复过的问题

### 1. data_events 历史表主键类型不一致

现象：

旧表中 id 为整数类型，和 UUID 事件主键设计冲突。

处理：

不再继续沿用旧 data_events 表，
新增标准表 data_events_v2，统一采用 UUID 主键。

---

### 2. occurred_at 写库类型错误

现象：

asyncpg 报错：
expected datetime.date or datetime.datetime instance, got 'str'

原因：

occurred_at 以字符串形式传给 PostgreSQL TIMESTAMPTZ 参数。

处理：

在 PostgresDataEventRepository 中先将 ISO 字符串转换为 datetime 对象后再写库。

---

### 3. RouterWorker 时间比较异常

现象：

消息进入 DLQ，原因：
can't compare offset-naive and offset-aware datetimes

原因：

RouterWorker 在 agent 时间排序时混用了 naive datetime 和 aware datetime。

处理：

统一将 _parse_dt() 返回值规范为 timezone-aware datetime。

---

## 四、当前系统状态

当前 Phase 8 状态：

已完成并验证通过。

已验证能力：

- task.submitted
- router.success
- router.failed
- PostgreSQL data_events_v2 持久化
- Redis Streams 发布与消费
- RouterWorker 基础路由

---

## 五、当前遗留项

### 1. 历史调试数据

早期 task_001 属于 datetime 修复前的调试数据，
存在 task.submitted，但没有对应 router.success。

这不影响当前 Phase 8 验收结果。

### 2. 历史 DLQ 数据

data.events.dlq 中可能存在历史调试消息，
其原因已定位并修复，不影响当前主链路。

---

## 六、下一阶段建议

下一阶段建议进入 Phase 9。

### Phase 9 目标

新增 AgentWorker，打通真正执行链路：

router.success
→ AgentWorker.consume()
→ task.executing
→ agent execution
→ task.completed / task.failed

建议开发顺序：

1. 新增 agent_worker.py
2. 监听 router.success
3. 实现执行事件 task.executing
4. 实现 task.completed / task.failed
5. 增加测试与验收接口

---

## 七、Phase 8 验收结论

Phase 8 已通过。

Data Plane 已具备基础事件路由能力，可进入下一阶段开发。