
这段内容你**原样复制**进 `.md` 文件就行，不要改成图片。

### 如果 VS Code 不显示图

有三种处理办法：

1. **先照常保存**
   - 即使 VS Code 当前不渲染，Markdown 内容本身也是正确的
   - GitHub、很多文档平台、部分 Markdown 预览插件都能识别 Mermaid

2. **在 VS Code 安装 Mermaid/Markdown 预览扩展**
   - 常见做法是装 Markdown 相关预览增强插件
   - 然后打开 Markdown Preview 查看

3. **如果你的环境始终不支持 Mermaid**
   - 先保留 Mermaid 源码块
   - 后面我可以再给你一版 **纯文本树状图 / ASCII 图** 作为降级版本

也就是说，**先粘贴 Mermaid 代码块完全没问题**，不要因为暂时看不到图就删掉。

---

那我们现在开始第 1 份文档。

---

# 文档 1：`docs/architecture/platform_overview.md`

```md
# AI OS / AI-PaaS 平台总体设计文档

## 1. 文档目的

本文档用于统一平台的终态目标、主线架构、产品边界、基础设施复用原则、模块分层、平台能力范围，以及后续模块设计文档的索引入口。

本文档不是单个迭代交接文档，而是平台级设计基线文档。

---

## 2. 平台定位

本平台的目标不是做一个单点 AI 应用，也不是简单复刻 Dify、Flowise 或 OpenClaw。

平台的目标是构建一个 **AI OS / AI-PaaS**：

- 面向 AI 应用开发与交付
- 面向企业业务流程的 AI 能力编排
- 面向 Agent / Skill / Tool / Workflow / Generation 的统一运行底座
- 面向多模型、多租户、多环境、多连接器的治理平台
- 面向后续商业化的权限、审计、计费、配额和运维控制平面

平台的终态不是“功能集合”，而是“统一主线上的可治理 AI 能力操作系统”。

---

## 3. 终态目标

### 3.1 产品终态

终态平台应具备以下能力：

1. **统一接入层**
   - 提供统一 Gateway API
   - 支持用户、系统、第三方服务调用
   - 支持 UI、API、后续 SDK 与 Connector 接入

2. **统一运行时**
   - 统一执行 Agent、Skill、Tool、Workflow、Generation
   - 统一处理 durable task、异步执行、重试、失败恢复、状态查询

3. **统一模型层**
   - 统一接入 OpenAI、Qwen、DeepSeek、Ollama 及其他模型供应方
   - 支持文本、多模态、图像、视频等生成能力

4. **统一 workflow 层**
   - 支持 workflow definition / execution
   - 支持 AI-native capability node
   - 后续对接成熟 BPMN/workflow engine，而不是完全从零自研底层引擎

5. **统一治理层**
   - 多租户
   - ABAC / OPA
   - 审计
   - 配额与计费
   - 策略治理
   - 追踪与监控

6. **统一产品层**
   - 对内是开发与交付底座
   - 对外是企业 AI 能力平台
   - 不让用户直接感知底层拼装复杂度

### 3.2 工程终态

工程上需要达到：

- 单一主线架构
- 单一 durable execution 主链路
- 单一任务状态真相源
- 单一 workflow 执行入口
- 模块边界清晰
- 测试与生产代码路径一致
- 避免历史实验层持续侵入主产品路径

---

## 4. 平台主线

当前平台必须坚持的正式主线为：

**Gateway → Durable Task Submission → Task Store / Outbox → Outbox Relay → Redis Queue → Worker Runtime → Capability Execution → Model / Tool / Workflow**

这条主线的意义：

- Gateway 负责标准接入和上下文注入
- Task Submission 负责 durable submit
- 数据库中的任务记录与 outbox 事件是正式真相源
- Redis 负责异步分发，不承担先写真相源的职责
- Worker Runtime 负责统一消费和调度
- 能力执行层负责执行 Agent / Generation / Workflow / Tool
- 模型层负责最终模型与生成调用

凡是不走这条主线的路径，都不应被视为正式主产品执行链路。

---

## 5. 平台分层

平台分为六层：

### 5.1 体验层
面向用户、运维、开发者的交互入口，包括 Web 控制台、后续控制台、应用台、运营台。

### 5.2 接入层
Gateway、API、认证授权、ABAC、OPA、外部代理等。

### 5.3 编排与执行层
Agent Runtime、Workflow Runtime、Tool Executor、Capability Guard、Policy Engine、State/Trace/Metrics。

### 5.4 Durable Task 层
Task Submission、Task Store、Outbox、Relay、Queue、Dispatcher、Worker Runner。

### 5.5 模型与生成层
Model Registry、Model Service、LLM Adapter、Generation Service、模型供应商适配。

### 5.6 治理与交付层
Bootstrap、Workers、Policies、Ops、Tests、Migrations、连接器与后续 Marketplace。

---

## 6. 产品形态

### 6.1 产品不是以下任意一个单品

平台不是：

- 纯 Dify 类 AI 应用搭建器
- 纯 Flowise 类节点编排器
- 纯 OpenClaw 类 agent 前台
- 纯 Workflow/BPM 引擎
- 纯模型网关

### 6.2 产品应该是什么

平台应该是：

**企业级 AI 能力编排、运行与治理底座**

它的用户价值不是“能搭几个节点”，而是：

- 让 AI 能力可以被开发、编排、运行、观察、治理、复用、交付
- 让企业可以把 Agent / Workflow / Generation 落在一个可治理的平台上
- 让平台承接真实业务流程，而不是只承接 Demo 场景

---

## 7. 产品边界

### 7.1 平台应该自己掌握的部分

必须自研并持续掌握：

- 统一运行时主线
- Agent / Skill / Tool / Workflow capability 协议
- Durable task 主链路
- 多租户、ABAC、审计、计费、配额
- 产品级控制台与运营界面
- 行业 know-how 抽象与可交付能力模型
- 平台级可观测性与故障追踪

### 7.2 平台不应从零重造的部分

优先复用成熟基础设施：

- Workflow / BPMN engine
- 通用数据库、消息队列、缓存
- 通用认证授权基础设施
- 通用可观测性组件
- 成熟连接器与外部系统 SDK

---

## 8. 基础设施复用原则

### 原则 1：高复杂度、低差异化、强成熟度依赖的基础设施优先复用
例如 workflow engine、BPMN engine、可观测性基础件、认证授权基础件。

### 原则 2：直接构成平台壁垒的能力坚持自研
例如 runtime 主线、能力协议、多租户治理、平台产品面、商业化控制面。

### 原则 3：避免“每层都想自己做”
平台复杂度是乘法，不是加法。低差异化底层设施的重复造轮子会显著放大失败概率。

### 原则 4：先统一主线，再扩展能力
没有进入主线的能力，不应被包装为正式产品能力。

---

## 9. 总体架构图

```mermaid
flowchart TB
    U[用户 / 外部系统] --> FE[WebApp / Console]
    U --> APIClient[API Client / SDK / Third-party]

    FE --> GW[Gateway]
    APIClient --> GW

    subgraph GatewayLayer[Gateway Layer]
        GW --> Health[/health/]
        GW --> UI[/ui/]
        GW --> AgentAPI[/agent runtime API/]
        GW --> GenAPI[/generation API/]
        GW --> TasksAPI[/tasks API/]
        GW --> WFDefAPI[/workflow definitions API/]
        GW --> WFExecAPI[/workflow executions API/]
        GW --> Authz[Auth / ABAC / OPA]
    end

    subgraph DurableMainline[Durable Mainline]
        TasksAPI --> Submit[TaskSubmissionService]
        Submit --> TaskDB[(runtime_tasks)]
        Submit --> OutboxDB[(runtime_outbox_events)]
        OutboxDB --> Relay[OutboxRelay]
        Relay --> Redis[(Redis Streams)]
        Redis --> Worker[Runtime Workers]
    end

    subgraph RuntimePlane[Runtime Plane]
        Worker --> AgentRuntime[Agent Runtime]
        Worker --> GenerationService[Generation Service]
        Worker --> WorkflowRuntime[Workflow Runtime]
        AgentRuntime --> SkillRegistry[Skill Registry / Resolver]
        AgentRuntime --> ToolExecutor[Tool Executor / Capability Guard]
    end

    subgraph ModelPlane[Model Plane]
        GenerationService --> ModelService[Model Service]
        AgentRuntime --> LLMAdapter[LLM Adapter]
        ModelService --> ModelRegistry[Model Registry]
        ModelRegistry --> Providers[Providers]
    end

    subgraph GovernancePlane[Governance Plane]
        Worker --> State[State Store]
        Worker --> Trace[Trace Store]
        Worker --> Metrics[Runtime Metrics]
        Authz --> Policies[Policies / OPA]
    end

10. 当前代码映射
10.1 顶层目录映射
gateway/：接入层
runtime/：运行时层
bootstrap/：组装与启动层
webapp/：前端控制台
tests/：测试与治理
ops/：运维与基础设施
policies/：策略
migrations_runtime/：runtime 数据表迁移
flowise/、promptflow/、langgraph/：历史/集成/实验层
10.2 当前主产品链路映射
Gateway 已挂载 health、ui、agent runtime、generation、tasks、workflow definitions、workflow executions
Durable submit 已支持 agent、image generation、video generation、workflow submit
runtime 已形成 task store + outbox + relay + queue + worker 的 durable mainline
webapp 当前是 Phase 17 console，主要用于 durable submit、task query、minimal ops UI
11. 当前阶段的关键判断
11.1 这不是单点产品，而是平台型仓库

平台已经形成多层结构，不再适合以“单模块文档”理解全局。

11.2 当前真正需要收敛的是主线，不是继续无边界扩张模块

未来一切新增能力，都应明确：

是否进入正式主线
是否只是实验层
是否只是桥接层
是否值得纳入产品化范围
11.3 workflow 不应从零自研底层引擎

workflow 是业务核心，但底层 workflow engine 本身属于高复杂度基础设施，优先采用成熟开源产品，再在其上构建 AI-native orchestration layer。

12. 配套文档索引
module_gateway.md
module_runtime.md
module_queue.md
module_workflow.md
module_model_generation.md
module_webapp.md
platform_capability_matrix.md