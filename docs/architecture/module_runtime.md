# Runtime 模块设计文档

## 1. 文档目的

本文档用于定义 Runtime 模块在平台中的职责、边界、内部结构、核心子模块、设计原则和后续演进重点。

Runtime 是平台的统一执行面，是 AI OS 的核心运行时，而不是简单的工具集合。

---

## 2. 模块定位

Runtime 是平台核心执行层，负责：

- Agent 执行
- Tool 执行
- Skill 注册与解析
- Workflow runtime
- Generation service
- State / Trace / Metrics
- Policy 与 capability 执行治理

Runtime 是平台真正的 AI 能力运行时，不是 Gateway 的附属，也不是单独的模型调用封装层。

---

## 3. 模块边界

### 3.1 Runtime 负责

Runtime 负责以下能力：

- 统一能力执行
- 统一上下文与状态处理
- 统一错误与追踪
- 将任务从 durable mainline 消费后执行
- 驱动 workflow / agent / generation 的实际业务逻辑
- 统一 skill / tool / capability / model 的执行协作
- 提供状态、追踪、指标等 runtime 级支撑能力

### 3.2 Runtime 不负责

Runtime 不应承担以下职责：

- 对外 API 门户
- durable submit 真相源落库入口
- 直接承载用户产品交互面
- 替代 Gateway 的接入职责
- 从零重造完整 workflow engine
- 在多个入口中重复实现相同执行逻辑

---

## 4. 当前代码目录结构

```text
runtime/
├─ generation/
├─ models/
├─ queue/
├─ tools/
├─ workers/
├─ workflows/
├─ agent_runtime.py
├─ capability_guard.py
├─ execution_context.py
├─ generation_service.py
├─ llm_adapter.py
├─ model_backed_llm_adapter.py
├─ model_service.py
├─ policy_engine.py
├─ preflight.py
├─ runtime_metrics.py
├─ skill_registry.py
├─ skill_resolver.py
├─ state_store.py
├─ tool_capability_guard.py
├─ tool_executor.py
├─ trace_store.py
├─ workflow_runtime_service.py
└─ workflow_state.py
5. Runtime 的角色定义

Runtime 在平台主线中的位置是：

Gateway → Durable Task Submission → Task Store / Outbox → Outbox Relay → Redis Queue → Worker Runtime → Capability Execution → Model / Tool / Workflow

其中 Runtime 负责主线中的：

Worker 后的统一执行面
Capability execution
Agent / Tool / Workflow / Generation 的实际承接
State / Trace / Metrics 的统一记录

也就是说，Runtime 是“能力执行主机”，不是“接入门面”，也不是“持久化队列”。

6. 内部模块拆分
6.1 Agent Runtime

对应：

agent_runtime.py

职责：

承接 Agent 执行请求
组织 prompt / model / skill / tool 协作
为上层提供统一 Agent 执行能力

Agent Runtime 不应演化为所有能力的总入口控制器，而应作为 capability execution 中的一个正式执行器。

6.2 Skill 层

对应：

skill_registry.py
skill_resolver.py

职责：

注册 skill
解析 skill
为 runtime 提供能力发现与绑定机制
为后续 skill marketplace / registry 提供底层抽象

Skill 层的价值在于平台化能力抽象，而不只是“函数表”。

6.3 Tool 层

对应：

tool_executor.py
capability_guard.py
tool_capability_guard.py

职责：

执行 tool
做 capability 权限检查
保障工具调用边界
为 workflow、agent、future connector 调用提供统一执行面

Tool 层不应分裂成多个彼此不兼容的工具调用系统。

6.4 Model / Generation 层

对应：

model_service.py
generation_service.py
llm_adapter.py
model_backed_llm_adapter.py

职责：

提供统一模型服务
为 runtime 提供模型推理抽象
为 generation API 提供执行承接
避免各个执行器直接耦合具体 provider

这一层是 runtime 中的基础设施抽象层，而不是独立产品面。

6.5 Workflow Runtime 层

对应：

workflow_runtime_service.py
workflow_state.py
runtime/workflows/*

职责：

承接 workflow 实际执行逻辑
管理 workflow execution state
调用 capability executor
承接 workflow node 到 agent/tool/generation 的映射

这一层不是完整 BPMN engine，而是当前 AI OS 的 workflow runtime 层。

6.6 可观测与状态层

对应：

state_store.py
trace_store.py
runtime_metrics.py

职责：

状态承接
执行追踪
指标记录
为排障、治理、审计和后续平台控制面提供数据基础

这层能力不是附属功能，而是 runtime 成为商用平台的必要组成部分。

6.7 其他支撑层

对应：

execution_context.py
policy_engine.py
preflight.py

职责：

承接统一执行上下文
提供策略判断基础
提供执行前检查能力

这些文件虽然不是独立产品模块，但构成 runtime 稳定性的关键基础件。

7. Runtime 模块工程图
flowchart TB
    RT[Runtime]
    RT --> AR[Agent Runtime]
    RT --> SK[Skill Registry / Resolver]
    RT --> TL[Tool Executor]
    RT --> CG[Capability Guard]
    RT --> GS[Generation Service]
    RT --> MS[Model Service]
    RT --> LLM[LLM Adapter]
    RT --> WFR[Workflow Runtime Service]
    RT --> WS[Workflow State]
    RT --> ST[State Store]
    RT --> TR[Trace Store]
    RT --> RM[Runtime Metrics]
    RT --> PE[Policy Engine]
    RT --> EC[Execution Context]

8. Runtime 与其他层的关系
8.1 与 Gateway 的关系

Gateway 负责接入，Runtime 负责执行。
两者必须清晰分层。

8.2 与 Queue 的关系

Queue 负责 durable submit、持久化、relay、分发；Runtime 负责真正消费任务并执行。
Queue 不是 Runtime，Runtime 也不是 Queue。

8.3 与 Workflow 的关系

Workflow Runtime 是 Runtime 的一部分，但完整 workflow 平台产品能力不等于 Runtime 本身。
Workflow 需要 runtime 支撑，但产品层还包括 definitions、executions、设计器、治理台等。

8.4 与 Model Plane 的关系

模型层是 Runtime 的能力基础设施之一，但 Runtime 价值不应等同于“多模型接入层”。

9. 设计原则
原则 1：Runtime 是统一执行面

所有正式能力执行都应进入 Runtime，不应在多个地方各自实现执行逻辑。

原则 2：Runtime 内部必须分层

Agent、Workflow、Tool、Model、State、Trace 不能互相缠绕成单体控制器。

原则 3：Runtime 应围绕 capability 统一抽象

最终平台能力应统一表达为 capability / skill / tool / workflow node 的执行模型，而不是彼此独立的一堆调用路径。

原则 4：Runtime 不应演变为接入层

对外 API 仍由 Gateway 承担，Runtime 不应直接暴露成产品接入层。

原则 5：Runtime 不是“任何东西都能放进去”的杂项目录

新增能力必须回答：

是否是执行层能力
是否应该进入 Runtime
是否更适合在 Gateway、Queue、Workflow、Model Plane 或 Governance Plane
原则 6：Runtime 的稳定性优先于功能堆叠

Runtime 是平台运行时内核。
对于 Runtime 而言，错误语义、状态语义、一致性语义、可观测性，优先级高于盲目增加新功能点。

10. 当前已实现能力

当前 Runtime 已具备以下核心能力：

Agent Runtime
Skill Registry / Resolver
Tool Executor
Capability Guard
Tool Capability Guard
Model Service
Generation Service
LLM Adapter
Model-backed LLM Adapter
Workflow Runtime Service
Workflow State
State Store
Trace Store
Runtime Metrics
Policy Engine / Preflight / Execution Context 等基础件

这表明 Runtime 已经形成平台核心执行面的骨架，而不是零散功能拼装。

11. 当前工程判断
11.1 Runtime 已经具备平台内核雏形

从目录结构看，Runtime 不再只是“几个执行脚本”，而是平台正式执行层。

11.2 Runtime 未来最怕边界失控

随着 workflow、connector、marketplace、governance、tooling 扩张，Runtime 很容易被滥用为“什么执行相关都塞进去”的超级目录。
这会导致：

模块缠绕
状态语义混乱
测试路径发散
新人接手困难
11.3 Runtime 的真正风险不是代码量，而是执行语义失控

商用平台失败，很多时候不是 runtime 功能不够，而是：

错误语义不一致
状态变化没有统一规范
不同执行器行为不一致
追踪和排障困难
边界问题导致维护成本失控
12. 后续演进重点
12.1 统一 capability 协议

将 Agent / Tool / Workflow Node / Generation 的能力表达进一步统一。

12.2 明确通用执行契约

包括：

输入契约
输出契约
错误契约
trace 契约
state 契约
policy 契约
12.3 补齐错误分类与恢复语义

Runtime 不只要“能执行”，还要“失败时行为一致”。

12.4 强化状态与观测

后续必须让 Runtime 为：

审计
排障
回放
运维
商业化控制面
提供足够稳定的数据面。
12.5 防止历史实验框架侵入主线

任何实验层、兼容层、桥接层，不应持续侵入 Runtime 正式链路。

12.6 为未来 workflow engine 集成预留边界

Runtime 可以承接 AI-native capability execution，但不应承诺自己就是完整 BPM 引擎。

13. 模块总结

Runtime 是平台真正的“AI 能力执行内核”。

平台最终是否能做到：

稳定运行
可治理
可追踪
可扩展
可商业化

很大程度取决于 Runtime 是否做到：

单一执行主线
清晰的 capability 抽象
严格的边界控制
一致的状态与错误语义
充分的可观测性

因此，Runtime 的核心任务不是“持续堆功能”，而是“成为可长期演进的统一执行内核”。