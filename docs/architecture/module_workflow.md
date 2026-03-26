# Workflow 模块设计文档

## 1. 文档目的

本文档用于定义平台 Workflow 模块的职责、边界、当前实现形态、与平台主线的关系、与成熟工作流引擎的关系，以及后续演进重点。

Workflow 模块是平台中承接“跨步骤、可追踪、可治理、可复用”的业务能力编排层，不等同于单点 Agent 调用，也不等同于底层 BPMN 引擎本身。

---

## 2. 模块定位

Workflow 模块负责平台中的业务能力编排，主要承担以下职责：

- workflow definition 管理
- workflow execution 管理
- workflow runtime 执行
- AI-native capability node 承载
- context / governance / trace 的承接
- 后续 BPMN / workflow engine 集成入口

Workflow 模块在平台中承担“业务编排层”的角色，而不是“低层基础设施引擎”的角色。

---

## 3. 模块边界

### 3.1 Workflow 负责

Workflow 模块负责：

- workflow 定义的版本化管理
- workflow 执行实例的状态与查询
- capability node 编排
- workflow input / output schema 的承接
- workflow execution context / governance / trace 的承接
- 将 workflow 执行落到平台正式 durable mainline 上
- 为未来引入成熟 BPMN/workflow engine 预留边界

### 3.2 Workflow 不负责

Workflow 模块不应承担以下职责：

- 从零重造完整 BPMN 引擎
- 替代 durable task 主链路
- 替代 Agent Runtime 或 Tool Executor
- 替代模型层
- 把所有业务逻辑直接塞进 workflow 节点图中
- 让 workflow runtime 和产品设计器混成一体

---

## 4. 当前实现形态

从当前代码结构看，Workflow 已经进入平台主线，而不是停留在概念阶段。

当前已经存在：

- workflow definitions API
- workflow executions API
- workflow submit API
- workflow runtime service
- workflow state
- `runtime/workflows/` 子模块

这表明平台的 workflow 能力已经形成“定义 → 提交 → 执行 → 查询”的早期闭环。

---

## 5. 当前代码映射

### 5.1 Gateway 层

当前 Gateway 已具备：

- `workflow_definitions.py`
- `workflow_executions.py`

职责包括：

- workflow definition 创建与读取
- workflow execution 查询
- 为前端和外部系统暴露 workflow API 门户

### 5.2 Tasks API

当前 Tasks API 已支持：

- `/workflow/submit`

这说明 workflow 已正式进入 durable submit 主线，而不是旁路功能。

### 5.3 Runtime 层

当前 Runtime 已具备：

- `workflow_runtime_service.py`
- `workflow_state.py`
- `runtime/workflows/capability_executor.py`
- `runtime/workflows/models.py`
- `runtime/workflows/registry.py`

这说明 workflow 的执行层、状态层和 capability 映射层已经有明确代码位置。

---

## 6. 当前数据模型要点

从当前 API 形态看，workflow definition 已包含以下核心字段：

- `workflow_key`
- `workflow_version`
- `nodes`
- `edges`
- `policies`
- `governance`
- `input_schema`
- `output_schema`

这说明 workflow definition 已经不只是简单流程名称，而是包含：

- 节点结构
- 流向关系
- 输入输出契约
- 策略与治理信息

workflow execution 当前已具备以下查询维度：

- 按 `workflow_execution_id` 查询
- 按 `task_id` 查询 execution

workflow execution 当前已承接以下信息：

- definition snapshot
- context
- governance
- trace

这说明执行态不是只保留“是否成功”这类浅层信息，而是已经朝可追踪、可治理方向演进。

---

## 7. Workflow 在平台主线中的位置

Workflow 的正式主线关系应为：

**Workflow Definition / Workflow Submit → Durable Task Mainline → Worker Runtime → Workflow Runtime Service → Capability Executor → Agent / Tool / Generation**

Workflow 本身不是绕过主线的捷径，而是平台正式主线中的一种能力编排形态。

这意味着：

- workflow submit 必须走 durable mainline
- workflow execution 必须可查询、可恢复、可追踪
- workflow runtime 必须复用正式 runtime 执行面
- workflow 节点能力不应各走各路

---

## 8. Workflow 模块工程图

```mermaid id="ec12q7"
flowchart TB
    Client[Client / Console] --> WFDefAPI[/workflow definitions API/]
    Client --> WFExecAPI[/workflow executions API/]
    Client --> WFSubmit[/workflow submit API/]

    WFSubmit --> Durable[Durable Task Mainline]

    WFDefAPI --> DefRepo[Workflow Definition Repository]
    WFExecAPI --> ExecRepo[Workflow Execution Repository]

    Durable --> Worker[Worker Runtime]
    Worker --> WFRS[Workflow Runtime Service]
    WFRS --> WFState[Workflow State]
    WFRS --> CapExec[Capability Executor]

    CapExec --> Agent[Agent Capability]
    CapExec --> Tool[Tool Capability]
    CapExec --> Gen[Generation Capability]
9. 与成熟 Workflow / BPMN Engine 的关系

这是 Workflow 模块设计中最关键的原则之一。

9.1 Workflow 是业务核心，但底层引擎不应完全自研

Workflow 当然是业务核心，因为它承载：

跨节点编排
状态机逻辑
错误恢复语义
人机协同
长流程运行
业务可追踪与治理

但这并不意味着平台应该从零重造整个底层 workflow engine。

原因在于：

完整 workflow / BPMN engine 工程复杂度极高
商用品质不只是功能存在，而是长期运行稳定性
长流程状态一致性、异常恢复、边界条件处理非常难靠短期自研收敛
重造这类基础设施的差异化价值相对有限，但失败风险极高
9.2 平台应该掌握的是 AI-native orchestration layer

平台真正应该自研并掌握的是：

AI-native capability node
Agent / Skill / Tool 与 workflow 的映射协议
workflow 与 runtime 主线的集成方式
多租户、ABAC、审计、配额、计费
产品级 workflow studio / governance 面板
行业 know-how 沉淀方式
9.3 推荐的总体策略

建议采用：

成熟开源 workflow / BPMN engine 作为基础设施层
AI OS Runtime 作为 AI-native orchestration layer
Gateway / WebApp 作为平台产品面
Durable mainline 作为统一任务与执行主线

也就是说：

底层流程引擎复用，平台编排能力与治理能力自研。

10. 设计原则
原则 1：Workflow 是业务编排层，不是临时拼装层

Workflow 的目标是承接真实业务链路，而不是只用于 demo orchestration。

原则 2：Workflow 必须建立在 durable execution 之上

workflow 的执行必须复用正式任务主线，不能成为一条旁路系统。

原则 3：Workflow 不应从零重造底层引擎

平台必须明确区分：

workflow product layer
workflow runtime layer
workflow engine infrastructure layer
原则 4：Workflow 必须具备 versioning 与 execution query

否则无法进入真实商用与交付场景。

原则 5：Workflow 节点能力必须与 Runtime capability 体系统一

workflow 节点不应形成独立于 runtime 的第二套能力调用系统。

原则 6：Workflow 设计器、执行器、治理面必须分层

不要把“流程图编辑”“执行逻辑”“运维治理”全挤在一个模块里。

11. 当前已实现能力

当前 Workflow 模块已具备以下能力：

workflow definition 创建
workflow definition active version 查询
workflow definition 指定版本查询
workflow submit
workflow execution 按 workflow_execution_id 查询
workflow execution 按 task_id 查询
workflow definition 中的 nodes / edges / policies / governance / schema 基础结构
workflow runtime service
workflow state
capability executor
workflow registry / models 基础结构

这说明 Workflow 已经具备“正式主线基础骨架”，但还未形成完整产品面和完整引擎集成方案。

12. 当前工程判断
12.1 Workflow 已经不是未来规划，而是当前主线的一部分

这意味着后续任何 workflow 相关扩展都必须考虑：

是否继续走正式 durable mainline
是否继续沿用统一 capability 抽象
是否保持 definition / execution 的清晰边界
12.2 当前最大风险不是“功能不够”，而是“边界不清”

Workflow 很容易同时吸纳：

前端设计器逻辑
后端执行逻辑
tool 调用逻辑
agent 调用逻辑
governance 逻辑
long-running state 逻辑

如果不分层，很容易迅速变成平台中最复杂、最难维护的模块。

12.3 当前最需要避免的是“自研完整引擎冲动”

平台当然可以继续自研 workflow product layer 和 orchestration layer，
但不应贸然把底层 workflow engine 也纳入完全自研范围。

13. 后续演进重点
13.1 明确 workflow 元模型

需要进一步规范：

node type
edge type
input/output binding
policy binding
governance binding
error / retry behavior
trace / audit structure
13.2 明确 capability node 标准

workflow 中的节点能力应统一为：

Agent capability
Tool capability
Generation capability
Future human task / connector task / event task
13.3 明确 definition versioning 策略

需要进一步明确：

新版本发布规则
active version 切换规则
旧执行实例与新定义的关系
snapshot 的保留策略
13.4 明确 execution 状态机

需要进一步统一：

submitted
queued
running
waiting
failed
compensated
completed

等状态的语义和转换逻辑。

13.5 规划与成熟 workflow engine 的集成边界

应尽快明确未来接入工作流引擎时的边界，例如：

definition 存储边界
execution 真相源边界
runtime 与 engine 的职责划分
BPMN 映射边界
node capability 绑定方式
13.6 补齐 workflow 设计器与治理台

当前已有定义和执行 API，但产品层仍需建设：

workflow studio
workflow execution monitor
governance / audit / trace UI
version management UI
14. 模块总结

Workflow 模块是平台中最接近“业务编排核心”的层。

它之所以重要，不是因为“能画流程图”，而是因为它决定平台是否能够把：

Agent
Tool
Generation
Governance
Long-running execution
业务上下文

组织成一个可复用、可追踪、可交付、可治理的能力系统。

因此，Workflow 模块必须坚持以下方向：

作为业务编排层存在
复用正式 durable mainline
复用统一 runtime capability 体系
明确 versioning 和 execution model
底层复杂引擎优先复用成熟开源产品
平台自身重点建设 AI-native orchestration layer 与产品控制面

只有这样，Workflow 才不会演化成难以控制的大杂烩，而会成为 AI OS 平台的真正业务编排核心。