# AI OS Phase 18 Workflow 迭代总结

## 一、文档目的

本文档用于总结 AI OS 在 Phase 18 迭代中，围绕 Workflow 能力建设已经完成的工作、当前已经达到的真实能力边界，以及后续迭代在 Workflow 层面必须继续推进的开发方向。

本文档不是概念性说明，而是基于当前仓库实际开发、实际测试和实际跑通的主线进行总结。

---

## 二、Phase 18 的核心目标

Phase 18 的目标，不是做一个演示级 workflow，也不是只完成 definition/step/event 的表结构搭建，而是要把 **Workflow 正式接入 AI OS 的 durable runtime mainline**，让 Workflow 从概念层、脚手架层，进入平台正式运行能力层。

本阶段的核心目标可以概括为三点：

1. **让 Workflow 接入平台统一任务主线**
   - `Gateway -> TaskSubmissionService -> runtime_tasks/runtime_outbox_events -> Outbox Relay -> Redis Streams -> Worker -> Workflow Runtime Service`

2. **让 Workflow 具备产品化封装能力**
   - 对外暴露 Product Contract
   - 对内执行 Workflow Definition
   - 用户不直接接触内部节点配置

3. **把 Workflow 的正式执行语义做扎实**
   - success
   - failure
   - retry success
   - retry exhausted

---

## 三、Phase 18 已完成的工作

---

### 3.1 Workflow 基础持久层正式建立

本轮已经建立了 Workflow 的正式持久化基础，包括：

- `workflow_definitions`
- `workflow_executions`
- `workflow_step_executions`
- `workflow_execution_events`

这意味着：

- Workflow definition 不再只是临时对象，而是正式定义资产
- Workflow execution 有了正式运行实例模型
- step execution 有了正式节点执行模型
- execution event 有了正式事件轨迹模型

这一步为后续以下能力提供了基础：

- 版本化
- 运行回放
- retry 历史
- execution timeline
- 产品化封装
- 治理与审计

---

### 3.2 Workflow API 基础层正式建立

本轮已经完成了 Workflow 的基础 API 层，包括：

- Workflow Definition 创建与查询
- Workflow Execution 查询
- Workflow submit 入口
- Workflow Product create / submit

这意味着 Workflow 已不再只是内部模块，而具备了正式 API 面。

这一层的价值在于：

- 后端 contract 已经形成
- 前端未来可以围绕这些 API 构建管理界面
- Workflow 已经具备接入产品层、管理层、运维层的接口基础

---

### 3.3 Workflow Product 封装层正式建立

这是 Phase 18 最关键的成果之一。

平台没有把 workflow 直接暴露给最终用户，而是建立了 **Workflow Product 模型**，使对外调用变成：

- 创建 Product
- Product 绑定内部 workflow_key / workflow_version
- 用户按 product contract 提交执行

即：

#### 对外
用户调用的是：

- `workflow product`

#### 对内
平台运行的是：

- `workflow definition + runtime execution`

这一步把平台目标中的关键要求落地了一部分：

> 对外封装成产品，不暴露后端流程和节点配置

Workflow 不再只是编排引擎，而是开始成为未来产品化交付和资产沉淀的底层。

---

### 3.4 Workflow Product Submit 已正式接入 Durable Mainline

本轮已经把 workflow product submit 正式接入平台 durable task 主线。

已经真实验证通过的链路包括：

`workflow product submit -> runtime_tasks -> runtime_outbox_events`

这意味着：

- Workflow 提交不是临时执行
- 不是内存态调用
- 而是进入平台正式 durable task 模型

这一层的意义在于：

- Workflow 与 agent / generation 进入同一任务模型
- 能被 outbox relay 和 queue 统一处理
- 能被 worker runtime 统一消费
- 能进入正式失败恢复路径

这一步是 Workflow 平台化的关键，不是简单的接口接入。

---

### 3.5 Outbox Relay -> Redis -> Worker -> Runtime Service 异步执行主链已经跑通

本轮已经真实验证通过：

`Product Submit -> Outbox Relay -> Redis Streams -> Workflow Worker -> Workflow Runtime Service -> workflow_execution / workflow_step_execution / workflow_execution_event`

这说明 Workflow 已经从“提交成功”升级为“执行成功”。

这一层已经具备：

- relay 能发布 workflow 任务
- worker 能消费 workflow_tasks
- runtime service 能执行 workflow
- execution / step / event 都能正式落库
- task 状态能正式回写

这说明 Workflow 已经从设计层进入平台正式运行层。

---

### 3.6 Success Mainline 已完成

本轮已经真实跑通 Workflow success path：

- capability node 正常执行
- step -> succeeded
- execution -> succeeded
- task -> succeeded

这条 success mainline 不是伪闭环，而是完整经过了：

- product submit
- durable task
- relay
- queue
- worker
- runtime
- persistence

因此它具备真实工程价值。

---

### 3.7 Failure Mainline 已完成

本轮已经真实验证 Workflow failure path：

- capability deterministic fail injection
- step -> failed
- execution -> failed
- task -> failed

这一步非常关键，因为平台型 workflow 不能只验证成功路径，必须验证失败路径的状态传播是否一致。

这一层说明：

- worker 对执行异常的处理是可控的
- runtime 对失败传播的语义是清晰的
- step / execution / task 状态是一致的
- failure path 已纳入正式状态机

这为后续 retry、timeout、cancel、补偿等能力打下了基础。

---

### 3.8 Retry Mainline 已完成

这是 Phase 18 后半段的重点成果。

本轮不只是存在 retry policy 字段，而是已经把 **正式 retry 语义跑通**。

已经验证通过的两条路径如下：

#### 1）Retry Success Mainline
- 第一次失败
- step 进入 `retrying`
- 写入 `step.retrying` event
- 第二次成功
- task / execution 最终 `succeeded`

#### 2）Retry Exhausted Mainline
- 前几次失败
- 中间尝试状态为 `retrying`
- 最后一次失败状态为 `failed`
- 写入 `step.failed`
- execution / task 最终 `failed`

这说明 Workflow 已经不再只是“失败即结束”的简单执行器，而是开始具备真正可上线的 runtime 语义基础。

---

### 3.9 Execution / Step / Event 正式语义已经沉淀

本轮不仅是代码跑通，而且运行语义已经沉淀成正式对象：

#### execution
表示整个 workflow 运行实例

#### step execution
表示某个节点某次尝试的执行记录

#### execution event
表示运行过程中的状态变化轨迹

这一层为以下能力提供基础：

- execution timeline
- retry 历史
- 并发节点状态
- 决策分支记录
- 人工干预
- 审计与运维

---

### 3.10 数据库生命周期问题完成根修

本轮中间还修掉了一个很关键的基础问题。

#### 原问题
`task_store` 内部存在全局 `Database` 单例，导致 async engine / session factory 跨 loop 复用，测试与 gateway 生命周期不稳定。

#### 本轮修复
- 移除了 `task_store` 内部全局 `Database` 单例路径
- 统一收口到 `persistence.db`
- 由 `gateway lifespan` 统一托管 DB engine / session factory 生命周期

#### 这一步的意义
这不是简单的测试修复，而是平台资源生命周期治理。

如果这一步不修，后续 workflow 越复杂、异步链路越长，问题会越严重。

因此，这虽然不是 Workflow 的直接业务功能点，但实际上是 Workflow 能稳定运行的基础设施修复。

---

## 四、Phase 18 当前状态判断

当前可以对 Workflow 的状态做如下判断：

### 当前 Workflow 已达到的能力层级

**Workflow Productized Runtime Mainline + Success / Failure / Retry Foundation**

也就是说，Workflow 已经具备：

- Definition 层
- Product 封装层
- Durable submit 主线
- 异步执行主线
- Success 语义
- Failure 语义
- Retry 语义

Workflow 已经不再是脚手架，也不再只是占位系统，而是正式进入 AI OS 平台主线的 Workflow Foundation。

---

## 五、当前还没有完成，但方向已经明确的部分

虽然 Phase 18 已经把 Workflow 打到了正式 runtime foundation，但离完整 workflow 平台仍有较大距离。

以下能力当前仍未完成，但方向已经明确。

---

### 5.1 多 Step 顺序链
当前真正完整验证通过的仍然是“单 capability node”主链。

虽然 runtime 结构已经具备顺序推进雏形，但还没有把 2~3 个 capability step 的正式主链测试做实。

#### 为什么重要
只有多 step 顺序链跑通，Workflow 才真正脱离“单节点执行包装器”，进入真正的编排系统。

---

### 5.2 Step Output -> Next Input 传播
当前 `step_outputs` 已存在，但“前一节点输出进入后一节点输入”的正式机制还没有真正做扎实。

这一步不做实，后续复杂业务编排很难成立。

---

### 5.3 Decision Node
当前 runtime 仍然是顺序执行语义，还没有建立 decision / branch 的正式状态机。

这意味着当前 Workflow 还不具备条件分支能力。

---

### 5.4 Parallel / Join
当前尚未进入并行执行与汇合语义，因此还不支持复杂并行拓扑。

---

### 5.5 真实 Capability Adapter
当前 capability executor 仍然是 deterministic executor。

这一步当前是合理的，因为需要先保证状态机、持久层、success/failure/retry 语义正确。

但后续必须逐步接入：

- agent runtime
- skill runtime
- generation runtime
- connector runtime

否则 Workflow 仍然只是“运行时框架正确，但能力执行仍是 mock”。

---

### 5.6 Workflow Lifecycle / Version Governance
当前 definition 和 product 已具备基础版本、状态字段，但完整生命周期还未完成：

- activate
- deprecate
- rollback
- version policy
- compatibility rule

这部分是 Workflow 进入多团队、多租户场景时必须补齐的能力。

---

### 5.7 Workflow 可观测层
当前 execution / step / event 数据已经具备，但还没有形成真正可运维的能力：

- execution timeline
- retry history
- queue lag
- failure reason summary
- correlation trace

商用后不可能只靠查数据库排查问题，这部分后续必须补。

---

### 5.8 Workflow Designer / BPMN / Compiler
这些能力当前不应抢在 runtime semantics 前面开发，但长期必须具备：

- workflow designer
- public contract -> executable graph compiler
- BPMN mapping

这些决定 Workflow 最终是否能够承载类似 Flowise / ComfyUI 风格的编排体验。

---

## 六、后续迭代在 Workflow 层面必须继续开发的内容

下面按优先级说明后续迭代在 Workflow 层面最应该开发的能力。

---

### 优先级 1：多 Step 顺序链

这是下一轮最应该做的能力。

#### 目标
- 至少支持 2~3 个 capability node 顺序执行
- 前一步 output 能进入下一步 input
- frontier 推进正确
- event 顺序正确
- end node 到达后 execution 成功

#### 原因
现在 retry 已经完成，单 step success / failure / retry 都已经成立。  
下一步最自然、最关键的就是把单 step runtime 扩展为真正的多 step workflow runtime。

---

### 优先级 2：Decision Node

在多 step 顺序链稳定后，补齐条件分支能力。

#### 目标
- condition evaluation
- branch edge choose
- 非命中分支跳过
- execution event 中记录 decision taken

#### 原因
真正业务流程几乎不可能全部是直线执行。  
Decision 是 Workflow 从“执行器”升级为“编排器”的关键一步。

---

### 优先级 3：真实 Capability Adapter

把 deterministic executor 抽象为正式 adapter，并逐步接入：

- agent runtime
- skill runtime
- generation runtime
- connector runtime

#### 目标
让 Workflow node 能真正调平台现有能力层，而不是只跑 deterministic success / failure。

---

### 优先级 4：Workflow Product Contract 编译增强

当前 product 主要还是静态 binding。  
后续需要增强：

- product contract -> executable graph compile
- input mapping
- context mapping
- default input / context merge policy
- schema validation

这样 product 层才真正具备“业务产品封装”的工程能力。

---

### 优先级 5：Execution Query / Timeline / Ops

把 execution / step / event 数据真正做成运维能力。

#### 至少需要补齐
- execution timeline API
- retry 历史视图
- step attempts 查询
- correlation / trace 查询
- failure reason 聚合

---

### 优先级 6：Workflow Lifecycle Governance

补齐 workflow / product 的治理层能力：

- activate / deactivate
- deprecate / rollback
- tenant isolation
- permission / ABAC
- audit trail
- quota / rate limit

---

### 优先级 7：Parallel / Join

在顺序链和 decision 稳定后，再进入并行语义。

---

### 优先级 8：Subworkflow / BPMN / Designer

这些属于更中后期的能力，不应该抢在前面的 runtime 语义之前完成。

---

## 七、建议的后续阶段划分

如果按照“做完整功能，不做最小闭环”的要求，后续 Workflow 开发建议按下面的子阶段推进：

### Phase 18A
多 Step 顺序链

### Phase 18B
Decision Node

### Phase 18C
真实 Capability Adapter 接入

### Phase 18D
Execution Query / Timeline / Ops

### Phase 18E
Product Contract Compiler 增强

### Phase 18F
Lifecycle / Governance

也就是说，后续的重点不是“继续加表和接口”，而是把 Workflow 从 runtime foundation 继续推进为真正可商用的编排平台。

---

## 八、一句话总结

**Phase 18 最大的成果，是让 Workflow 从概念设计、占位模型，真正进入了 AI OS 的正式运行主线。**

本轮已经完成：

- Product 封装
- Durable submit
- 异步执行主线
- Success / Failure / Retry 语义

后续迭代在 Workflow 层面最应该继续开发的是：

**多 Step 顺序链 -> Decision Node -> 真实 Capability Adapter -> 可观测与治理**

---

## 九、本轮建议重点存档的代码与测试范围

### 关键代码
- `runtime/workflow_runtime_service.py`
- `runtime/workflows/capability_executor.py`
- `gateway/api/workflow_products.py`
- `runtime/queue/task_store.py`
- `gateway/main.py`

### 关键测试
- `tests/runtime/test_task_store_lifecycle.py`
- `tests/gateway/test_gateway_db_lifespan.py`
- `tests/gateway/test_workflow_products_api.py`
- `tests/integration/test_workflow_product_submit_mainline.py`
- `tests/integration/test_workflow_product_execution_mainline.py`
- `tests/integration/test_workflow_product_execution_failure_mainline.py`
- `tests/integration/test_workflow_product_retry_mainline.py`
- `tests/integration/test_workflow_product_retry_exhausted_mainline.py`

### 本轮回归判断
当前 Phase 18 Workflow 基线已经稳定，可以作为下一轮开发的正式起点。