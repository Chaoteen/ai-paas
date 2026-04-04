# AI OS Phase18 Workflow 交接文档

## 1. 项目基本信息

- 项目名称：AI-PaaS / AI OS
- GitHub 仓库：`https://github.com/Chaoteen/ai-paas`
- 当前开发分支：`wip/integration-split-commits`
- 当前 Phase18 里程碑提交：`d1f350c`
- 提交信息：`feat(workflow): add phase18 sequential runtime mainline and failure path` :contentReference[oaicite:0]{index=0}

当前 `docs/` 目录下已存在的正式文档主要仍围绕 Phase17 durable runtime 主线，包括：
- `phase17_runtime_handover.md`
- `runtime_mainline_handover.md`
- `runtime_startup_guide.md`
- `platform_service_layers_and_startup.md`
- `CONTEXT_SUMMARY_FOR_NEW_CHAT.md` :contentReference[oaicite:1]{index=1}

本交接文档是在这些文档基础上，补充 **Phase18 Workflow Runtime** 的正式进展和下一阶段开发要求。

---

## 2. 平台目标

本项目不是单纯的 Agent 调用层，也不是单一模型接口层，而是一个面向 AI 程序员、面向业务应用交付的 **AI OS / AI-PaaS 平台**。

平台目标可以概括为四层：

### 2.1 平台定位
1. 让 AI 程序员能够通过统一接口和统一运行时，快速构建 AI 应用
2. 让平台兼容本地模型、云模型、第三方 Skill / Agent / Connector
3. 让 Workflow 成为行业 know-how、执行编排和可复用资产的落脚点
4. 最终形成 Agent / Skill / Workflow / Model / Generation / Connector 的统一操作系统

### 2.2 当前正式主线
当前正式异步主线已经稳定为：

`Gateway API -> TaskSubmissionService -> runtime_tasks / runtime_outbox_events -> OutboxRelay -> Redis Streams -> Worker -> Runtime Service`

Phase18 不是另起炉灶，而是把 Workflow 正式接入这条 durable mainline。

### 2.3 Workflow 在平台中的角色
Workflow 不是附属功能，而是未来 AI OS 的核心能力层之一，作用包括：

- 将原子能力（Agent / Skill / Generation / Connector）组织成可执行业务流程
- 沉淀行业 know-how
- 形成可交付、可复用、可治理的执行资产
- 为后续的应用市场、模板市场、行业方案库提供资产载体

---

## 3. Phase18 的目标定义

Phase18 的目标不是做“演示级 workflow”，而是把 **Workflow Runtime 正式接入平台主线**，形成第一版可运行的 Workflow 主干。

本阶段目标分为两个层次：

### 3.1 已完成的目标
1. Workflow 进入现有 durable task mainline
2. Workflow 具备正式持久层
3. Workflow 具备正式 API
4. Workflow 具备正式 Worker
5. Workflow 具备正式 Runtime Service
6. Workflow 成功路径与失败路径均已打通
7. 顺序 capability node 的执行闭环已经建立

### 3.2 尚未完成但已明确的终态方向
1. Retry / attempt 语义
2. 多 step 顺序链
3. decision node
4. parallel / join
5. subworkflow
6. capability executor 接真实 agent runtime
7. workflow version lifecycle / activate / deprecate
8. BPMN 映射 / designer / registry / marketplace

---

## 4. Phase18 当前已完成的开发内容

### 4.1 Workflow 领域模型与持久层
本迭代新增了 Workflow 相关核心模型、repository 和 migration：

- `runtime/workflows/models.py`
- `persistence/repositories/workflow_definition_repository.py`
- `persistence/repositories/workflow_execution_repository.py`
- `persistence/repositories/workflow_step_execution_repository.py`
- `persistence/repositories/workflow_execution_event_repository.py`
- `migrations_runtime/006_workflow_foundation.sql`
- `migrations_runtime/007_allow_workflow_task_type.sql`

对应数据对象：
- `workflow_definitions`
- `workflow_executions`
- `workflow_step_executions`
- `workflow_execution_events`

同时，为了让老的 durable task 主线接受 workflow task，又补了：
- `runtime_tasks.task_type` 支持 `workflow`

### 4.2 Workflow API
本迭代已接入正式 API：

- `POST /api/v1/workflow/submit`
- `POST /api/v1/workflow/definitions`
- `GET /api/v1/workflow/definitions/{workflow_key}/active`
- `GET /api/v1/workflow/definitions/{workflow_key}/{workflow_version}`
- `GET /api/v1/workflow/executions/by-task/{task_id}`
- `GET /api/v1/workflow/executions/{workflow_execution_id}`

对应文件：
- `gateway/api/tasks.py`
- `gateway/api/workflow_definitions.py`
- `gateway/api/workflow_executions.py`
- `gateway/main.py`

### 4.3 Workflow Worker 与 Runtime Service
本迭代新增：

- `runtime/workers/workflow_worker.py`
- `runtime/workflow_runtime_service.py`
- `runtime/workflows/registry.py`
- `runtime/workflows/capability_executor.py`

当前运行逻辑：

1. worker 消费 `workflow_tasks`
2. runtime service 解析 workflow definition
3. 创建 `workflow_execution`
4. 创建 `workflow_step_execution`
5. 追加 `workflow_execution_event`
6. 顺序执行 capability node
7. 更新 step 状态
8. 更新 execution 状态
9. 成功时 task 最终 `succeeded`
10. 失败时 task 最终 `failed`

### 4.4 Capability Executor
当前 capability executor 使用的是 **deterministic executor**，不是接真实 agent runtime。

目的不是偷懒，而是为了先把 Workflow Runtime 的正式状态机、持久层、事件流、成功/失败语义建立起来。

当前 deterministic executor 具备两类行为：
- 正常成功执行
- 基于 `workflow_input["force_fail_node_id"]` 或 node metadata 的确定性失败注入

这为成功/失败路径的集成测试提供了稳定基础。

---

## 5. 本迭代已验证通过的内容

### 5.1 Repository / Postgres 基础验证
以下内容已通过单测与真实 Postgres 集成测试：

- Workflow definition repository
- Workflow execution repository
- Workflow step execution repository
- Workflow execution event repository
- workflow foundation postgres integration

### 5.2 Gateway / API 验证
以下内容已通过 gateway 测试：

- workflow definition API
- workflow execution API
- workflow submit 入口
- workflow task query 回读

### 5.3 Mainline 集成验证
以下两条主链已经真实跑通：

#### 成功路径
`submit -> outbox relay -> redis -> workflow worker -> runtime service -> execution/step/event -> task succeeded`

#### 失败路径
`submit -> outbox relay -> redis -> workflow worker -> runtime service -> capability failure -> step failed -> execution failed -> task failed`

从本次测试日志可以确认：
- success mainline 已通过
- failure mainline 已通过
- runtime service 成功/失败单测均通过 

此外，workflow foundation 的真实 Postgres 集成测试已通过，说明 workflow 持久层正式路径已经跑通。:contentReference[oaicite:3]{index=3}

---

## 6. 当前 Phase18 的准确状态判断

当前 Phase18 已完成到：

# Workflow Sequential Runtime Mainline + Failure Path Foundation

这不是只有 definition/step 占位的 bootstrap 版本，而是已经具备：

- workflow definitions
- workflow executions
- workflow step executions
- workflow execution events
- workflow submit/query API
- workflow execution query API
- workflow worker
- workflow runtime service
- success mainline
- failure mainline

可以认为，Workflow 已正式进入平台主线，不再是概念设计或脚手架状态。

---

## 7. 本迭代中间遇到的问题与解决方式

本迭代中间遇到的问题较多，主要集中在三类：

### 7.1 Repository 与 fake test 环境兼容问题
问题表现：
- `select(FakeRecord)` 在单测里直接触发 SQLAlchemy `ArgumentError`
- fake session 下 step record / event record 存储互相污染
- 测试中读取不到真实 step，或者 event 混进 step 读路径

根因：
- 新增 repository 最初过度绑定 SQLAlchemy ORM class
- fake session 并不具备真实 ORM 查询语义
- fake session 的存储行为会把 event record 覆盖 step record

解决方式：
- repository 显式区分正式 ORM 路径与 fake test 路径
- 为 fake session 增加 repository 自己的内部真相源
- 让 step repository 和 event repository 各自持有独立 internal store

注意：
这部分修复的是 **新开发的 Workflow Repository 实现问题**，不是旧平台字段问题。

### 7.2 Postgres integration test 运行方式问题
问题表现：
- skipped：缺少 `POSTGRES_*` 环境变量
- `async_generator` not callable
- `Future attached to a different loop`
- 测试间数据污染，第二个测试看到前一个测试残留 execution

根因：
- pytest 进程没有环境变量
- async fixture 写法与当前 `pytest-asyncio strict` 模式不完全匹配
- session factory / engine 生命周期和 event loop 绑定方式不稳定
- autouse 清表 fixture 未按最稳妥方式声明

解决方式：
- 显式导出 `POSTGRES_HOST / PORT / DB / USER / PASSWORD`
- 测试中按需直接构造 `Database(PostgresSettings())`
- 使用 `pytest_asyncio.fixture`
- 真实 Postgres 集成测试采用“每测试清表 + 每测试独立 engine/session factory”的方式

### 7.3 Workflow runtime 顺序执行问题
问题表现：
- `runtime/workflow_runtime_service.py` 语法错误
- JSONB 持久化时报 `Circular reference detected`
- success mainline 最初只做 bootstrap，没有真正执行 step
- failure path 最初没有形成正式 task.failed / execution.failed / step.failed 双路径

根因：
- 函数调用处误用了 `*`
- `step_outputs` 活对象被直接写入 input/output，形成 JSON 自引用
- 顺序执行状态机不完整
- failure path 没有先建 execution 再落失败状态

解决方式：
- 修复语法错误
- 对持久化前的 dict 做 `deepcopy`
- capability executor 只返回快照，不返回 live object
- runtime service 中明确建：
  - `step.created`
  - `step.running`
  - `step.succeeded` / `step.failed`
  - `execution.created`
  - `execution.running`
  - `execution.succeeded` / `execution.failed`
- 让 worker 沿用 `WorkerBase` 统一处理 task success / task failure

### 7.4 workflow task type 进入 durable transaction 的数据库约束问题
问题表现：
- `POST /api/v1/workflow/submit` 在 durable transaction 时返回 503

高概率根因：
- 老的 `runtime_tasks.task_type` 约束未放行 `workflow`

解决方式：
- 新增 `migrations_runtime/007_allow_workflow_task_type.sql`
- 显式让 `runtime_tasks.task_type` 支持 `agent / generation / workflow`

---

## 8. 当前代码分布（下一个程序员重点关注）

### 8.1 Workflow 领域模型
- `runtime/workflows/models.py`

### 8.2 Workflow Registry / Resolver
- `runtime/workflows/registry.py`

### 8.3 Workflow Runtime
- `runtime/workflow_runtime_service.py`
- `runtime/workflows/capability_executor.py`
- `runtime/workers/workflow_worker.py`

### 8.4 Workflow API
- `gateway/api/workflow_definitions.py`
- `gateway/api/workflow_executions.py`
- `gateway/api/tasks.py`
- `gateway/main.py`

### 8.5 Workflow Persistence
- `persistence/repositories/workflow_definition_repository.py`
- `persistence/repositories/workflow_execution_repository.py`
- `persistence/repositories/workflow_step_execution_repository.py`
- `persistence/repositories/workflow_execution_event_repository.py`
- `migrations_runtime/006_workflow_foundation.sql`
- `migrations_runtime/007_allow_workflow_task_type.sql`

### 8.6 测试
- `tests/runtime/workflows/test_workflow_definition_repository.py`
- `tests/runtime/workflows/test_workflow_execution_repository.py`
- `tests/integration/test_workflow_foundation_postgres.py`
- `tests/runtime/test_workflow_runtime_service.py`
- `tests/integration/test_workflow_runtime_mainline.py`
- `tests/integration/test_workflow_runtime_failure_mainline.py`
- `tests/gateway/test_workflow_definition_api.py`
- `tests/gateway/test_workflow_execution_api.py`

---

## 9. 下一个程序员接手后应继续做什么

### 优先级 1：Retry Mainline
这是下一阶段最应该做的，不建议跳去 parallel / BPMN。

原因：
- 当前已有 `attempt_no`
- 当前已有 `retry_policy_json`
- 当前已有 success / failure 双主链
- 但 retry 语义还没真正生效

下一个程序员应优先完成：

1. capability node 失败后按 retry policy 重试
2. `attempt_no` 递增
3. event 增加 `step.retrying`
4. 达到最大次数前不结束 execution
5. 尝试成功则继续后续流程
6. 尝试耗尽才最终 execution.failed / task.failed

建议文件：
- `runtime/workflow_runtime_service.py`
- `tests/runtime/test_workflow_runtime_service.py`
- 新增 `tests/integration/test_workflow_runtime_retry_mainline.py`

### 优先级 2：多 step 顺序链
当前成功/失败路径只验证了一个 capability node。  
下一步要把顺序链扩到 2~3 个 node，验证：

- 上一个 step output 能进入下一个 step input
- execution active_node_ids 推进正确
- event 顺序正确
- 最终 end node 到达后 execution succeeded

### 优先级 3：decision node
在顺序链稳定后，再做：
- 基于条件选择边
- 非目标分支跳过
- decision 事件记录

### 优先级 4：parallel / join
在 decision 稳定后，再进入：
- 多 active nodes
- join 收敛
- execution frontier 管理

### 优先级 5：Capability Executor 接真实 Agent Runtime
当前 executor 是 deterministic executor。  
后续要引入 adapter，让 capability node 能按统一 contract 调真实 agent runtime，但不要破坏当前状态机和持久层。

---

## 10. 不建议下一个程序员立刻做的事情

以下方向当前不应优先：

1. BPMN import/export
2. 可视化 workflow designer
3. marketplace UI
4. 大规模 connector 接入
5. subworkflow 深入展开
6. compensation/saga 全实现

原因不是不重要，而是现在最关键的是先把 **Runtime Execution Semantics** 做扎实。

---

## 11. 当前开发与验证命令（接手人员可直接使用）

### 11.1 必要环境变量
Postgres integration test 需要：

```bash
export POSTGRES_HOST=127.0.0.1
export POSTGRES_PORT=5432
export POSTGRES_DB=ai_paas
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=postgres
export REDIS_URL=redis://127.0.0.1:6379