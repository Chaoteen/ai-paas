# 平台能力矩阵

## 1. 文档目的

本文档用于按 **平台域 / 模块 / 功能组 / 原子能力 / 当前状态** 的维度，系统梳理平台当前已经具备、已进入主线但待增强、规划中、以及不建议自研的能力。

本文档的作用不是重复架构总览，而是为以下工作提供统一能力视图：

- 平台能力盘点
- 研发优先级判断
- 产品边界判断
- 新模块是否进入主线的评估
- 后续 roadmap 制定
- 新研发接手时的能力理解

---

## 2. 状态说明

建议使用以下状态：

- `已实现`：代码主线中已具备明确实现与实际入口
- `已进入主线但待增强`：主线已有骨架，但能力尚未产品化或未完全固化
- `规划中`：方向明确，但当前尚未形成正式实现
- `复用优先`：应优先复用成熟基础设施，而非完全自研
- `不建议自研`：不应将其纳入完全从零开发范围

---

## 3. 平台能力矩阵

| 平台域 | 模块 | 功能组 | 原子能力 | 状态 | 说明 |
|---|---|---|---|---|---|
| 接入层 | Gateway | 基础 API | Health API | 已实现 | 平台基础健康检查 |
| 接入层 | Gateway | 基础 API | UI API | 已实现 | UI / bootstrap 入口 |
| 接入层 | Gateway | Runtime API | Agent Runtime API | 已实现 | 统一 agent 执行入口 |
| 接入层 | Gateway | Runtime API | Generation API | 已实现 | 图像 / 视频等生成入口 |
| 接入层 | Gateway | Durable API | Task submit API | 已实现 | 支持 durable submit |
| 接入层 | Gateway | Workflow API | Workflow Definitions API | 已实现 | definition 管理入口 |
| 接入层 | Gateway | Workflow API | Workflow Executions API | 已实现 | execution 查询入口 |
| 接入层 | Gateway | 外部集成 | Flowise Proxy | 已实现 | 外部代理入口 |
| 接入层 | Gateway Core | 安全治理 | Auth | 已实现 | 认证基础设施 |
| 接入层 | Gateway Core | 安全治理 | ABAC | 已实现 | 权限控制主线 |
| 接入层 | Gateway Core | 安全治理 | OPA Client | 已实现 | 策略引擎集成 |
| 接入层 | Gateway | 产品入口 | 平台统一 API 门户 | 已实现 | Gateway 已成为正式接入门面 |
| Durable Task | Tasks API | 提交 | Agent submit | 已实现 | durable submit |
| Durable Task | Tasks API | 提交 | Image generation submit | 已实现 | durable submit |
| Durable Task | Tasks API | 提交 | Video generation submit | 已实现 | durable submit |
| Durable Task | Tasks API | 提交 | Workflow submit | 已实现 | durable submit |
| Durable Task | Tasks API | 查询 | Task query | 已实现 | 查询任务状态 |
| Durable Task | Queue | 持久化 | runtime_tasks | 已实现 | 任务真相源 |
| Durable Task | Queue | 持久化 | runtime_outbox_events | 已实现 | outbox 真相源 |
| Durable Task | Queue | 一致性 | task + outbox 同事务写入 | 已实现 | durable mainline 核心 |
| Durable Task | Queue | 幂等 | idempotency check | 已实现 | tenant + idempotency 语义 |
| Durable Task | Queue | Relay | Outbox relay | 已实现 | 发布到 Redis |
| Durable Task | Queue | Relay | retry / backoff | 已实现 | 发布失败恢复 |
| Durable Task | Queue | Relay | dead-letter | 已实现 | 失败兜底 |
| Durable Task | Queue | 队列 | Redis Streams | 已实现 | 异步分发 |
| Durable Task | Queue | 调度 | TaskDispatcher | 已实现 | 队列到 runtime |
| Durable Task | Queue | 执行桥接 | Worker Runtime bridge | 已进入主线但待增强 | 已有正式桥接骨架 |
| Runtime | Agent Runtime | 执行 | AgentRuntime | 已实现 | Agent 主执行器 |
| Runtime | Skills | 注册 / 发现 | SkillRegistry | 已实现 | skill 注册 |
| Runtime | Skills | 解析 | SkillResolver | 已实现 | skill 解析 |
| Runtime | Tools | 执行 | ToolExecutor | 已实现 | tool 调用 |
| Runtime | Tools | 治理 | Capability Guard | 已实现 | capability 边界 |
| Runtime | Tools | 治理 | Tool Capability Guard | 已实现 | tool 调用边界 |
| Runtime | Workflow Runtime | 执行 | WorkflowRuntimeService | 已实现 | workflow 执行主服务 |
| Runtime | Workflow Runtime | 状态 | Workflow State | 已实现 | workflow state |
| Runtime | Workflow Runtime | capability | Capability Executor | 已实现 | node capability 执行 |
| Runtime | Model Plane | 注册 | Model Registry | 已实现 | 模型注册 |
| Runtime | Model Plane | 服务 | Model Service | 已实现 | 模型统一服务 |
| Runtime | Model Plane | 抽象 | LLM Adapter | 已实现 | LLM 统一抽象 |
| Runtime | Model Plane | 抽象 | Model-backed LLM Adapter | 已实现 | runtime 对接模型层 |
| Runtime | Generation | 服务 | GenerationService | 已实现 | 多模态生成服务 |
| Runtime | State / Trace | 状态 | State Store | 已实现 | 状态承载 |
| Runtime | State / Trace | 追踪 | Trace Store | 已实现 | 追踪承载 |
| Runtime | State / Trace | 指标 | Runtime Metrics | 已实现 | 指标承载 |
| Runtime | Policy | 执行治理 | Policy Engine | 已进入主线但待增强 | 基础件已存在 |
| Runtime | Context | 执行上下文 | Execution Context | 已进入主线但待增强 | 统一上下文骨架 |
| Runtime | Preflight | 执行前检查 | Preflight | 已进入主线但待增强 | 基础能力已存在 |
| Workflow | Workflow API | 定义 | workflow definition create | 已实现 | 创建 definition |
| Workflow | Workflow API | 定义 | active version query | 已实现 | 查询 active 版本 |
| Workflow | Workflow API | 定义 | specific version query | 已实现 | 查询指定版本 |
| Workflow | Workflow API | 元模型 | nodes | 已进入主线但待增强 | 已有定义字段 |
| Workflow | Workflow API | 元模型 | edges | 已进入主线但待增强 | 已有定义字段 |
| Workflow | Workflow API | 元模型 | policies | 已进入主线但待增强 | 已有定义字段 |
| Workflow | Workflow API | 元模型 | governance | 已进入主线但待增强 | 已有定义字段 |
| Workflow | Workflow API | 元模型 | input_schema | 已进入主线但待增强 | 已有定义字段 |
| Workflow | Workflow API | 元模型 | output_schema | 已进入主线但待增强 | 已有定义字段 |
| Workflow | Workflow Execution | 查询 | get by workflow_execution_id | 已实现 | 执行实例查询 |
| Workflow | Workflow Execution | 查询 | get by task_id | 已实现 | 通过任务查执行实例 |
| Workflow | Workflow Execution | 观测 | definition snapshot | 已进入主线但待增强 | 执行快照基础 |
| Workflow | Workflow Execution | 观测 | context | 已进入主线但待增强 | 执行上下文基础 |
| Workflow | Workflow Execution | 观测 | governance | 已进入主线但待增强 | 执行治理信息基础 |
| Workflow | Workflow Execution | 观测 | trace | 已进入主线但待增强 | 执行 trace 基础 |
| Workflow | Workflow Runtime | registry | workflow registry | 已实现 | runtime/workflows/registry.py |
| Workflow | Workflow Runtime | models | workflow models | 已实现 | runtime/workflows/models.py |
| Workflow | Workflow Runtime | orchestration | AI-native node execution | 已进入主线但待增强 | 已有骨架，待标准化 |
| Workflow | Product Layer | 设计器 | Workflow Studio | 规划中 | 尚未形成正式产品面 |
| Workflow | Product Layer | 治理 | Workflow Governance UI | 规划中 | 尚未形成正式产品面 |
| Workflow | Product Layer | 运维 | Workflow Execution Monitor UI | 规划中 | 尚未形成正式产品面 |
| Model / Generation | Model Plane | 配置 | provider config | 已进入主线但待增强 | 需进一步固化 |
| Model / Generation | Model Plane | 路由 | provider routing | 规划中 | 后续多模型治理能力 |
| Model / Generation | Model Plane | 回退 | fallback strategy | 规划中 | 后续高可用能力 |
| Model / Generation | Model Plane | 治理 | quota / cost control | 规划中 | 商业化需要 |
| Model / Generation | Generation | 图像 | image generation | 已实现 | 已有 generation API |
| Model / Generation | Generation | 视频 | video generation | 已实现 | 已有 generation API |
| Model / Generation | Generation | 音频 | audio generation | 规划中 | 后续扩展 |
| Model / Generation | Generation | 多模态 | multimodal generation | 规划中 | 后续扩展 |
| WebApp | Frontend | 控制台 | Phase 17 Console | 已实现 | 当前为验证控制台 |
| WebApp | Frontend | 主线验证 | Durable submit UI | 已实现 | 对接正式主线 |
| WebApp | Frontend | 主线验证 | Task query UI | 已实现 | 查询任务状态 |
| WebApp | Frontend | 主线验证 | Health UI | 已实现 | 健康检查 |
| WebApp | Frontend | Runtime | Agent Run / Submit UI | 已实现 | 主线验证入口 |
| WebApp | Frontend | Generation | Image Generation UI | 已实现 | 主线验证入口 |
| WebApp | Frontend | Generation | Video Generation UI | 已实现 | 主线验证入口 |
| WebApp | Product Layer | 应用台 | Applications Workspace | 规划中 | 尚未形成正式产品面 |
| WebApp | Product Layer | Workflow 台 | Workflow Studio | 规划中 | 尚未形成正式产品面 |
| WebApp | Product Layer | 治理台 | Tenant Governance UI | 规划中 | 尚未形成正式产品面 |
| WebApp | Product Layer | 审计台 | Audit UI | 规划中 | 尚未形成正式产品面 |
| WebApp | Product Layer | 计费台 | Billing / Quota UI | 规划中 | 尚未形成正式产品面 |
| WebApp | Product Layer | 能力台 | Skills / Connectors UI | 规划中 | 尚未形成正式产品面 |
| Governance | Gateway / Runtime | 权限 | ABAC | 已实现 | 权限治理主线 |
| Governance | Gateway / Runtime | 策略 | OPA integration | 已实现 | 策略引擎基础 |
| Governance | Runtime | 观测 | Trace | 已实现 | runtime trace 基础 |
| Governance | Runtime | 观测 | Metrics | 已实现 | runtime metrics 基础 |
| Governance | Runtime | 状态 | State Store | 已实现 | 状态承载基础 |
| Governance | Product Layer | 审计 | Audit trail UI / query | 规划中 | 商业化必需 |
| Governance | Product Layer | 配额 | Quota control | 规划中 | 商业化必需 |
| Governance | Product Layer | 计费 | Billing integration | 规划中 | 商业化必需 |
| Governance | Product Layer | 管理 | Tenant Admin Console | 规划中 | 平台治理必需 |
| 测试与质量 | Tests | 模块测试 | gateway tests | 已实现 | 模块测试基础 |
| 测试与质量 | Tests | 模块测试 | runtime tests | 已实现 | 模块测试基础 |
| 测试与质量 | Tests | 治理测试 | governance tests | 已实现 | 主线治理基础 |
| 测试与质量 | Tests | 集成测试 | integration tests | 已实现 | 主线集成验证 |
| 测试与质量 | Tests | 真实路径覆盖 | durable mainline coverage | 已进入主线但待增强 | 需持续强化 |
| 启动与交付 | Bootstrap | 组装 | runtime bootstrap | 已实现 | 运行时装配 |
| 启动与交付 | Bootstrap | 组装 | model bootstrap | 已实现 | 模型层装配 |
| 启动与交付 | Bootstrap | 组装 | generation bootstrap | 已实现 | 生成层装配 |
| 启动与交付 | Bootstrap | runner | runtime worker runner | 已实现 | worker 启动器 |
| 启动与交付 | Bootstrap | runner | outbox relay runner | 已实现 | relay 启动器 |
| 启动与交付 | Bootstrap | factory | event bus factory | 已实现 | 事件总线装配基础 |
| 基础设施复用 | Workflow Engine | 引擎 | 完整 BPMN / workflow engine | 不建议自研 | 应优先复用成熟产品 |
| 基础设施复用 | Observability | 引擎 | 完整通用观测栈 | 复用优先 | 优先集成成熟设施 |
| 基础设施复用 | Identity / Auth | 基础设施 | 全量 IAM 能力 | 复用优先 | 不建议全栈自研 |
| 基础设施复用 | Connectors | 连接器底座 | 通用外部系统连接器框架 | 复用优先 | 先集成成熟模式再产品化 |
| 基础设施复用 | Queue / Storage | 基础设施 | 通用 DB / MQ / Cache | 复用优先 | 不应重复造轮子 |

---

## 4. 当前平台能力判断

### 4.1 已形成正式主线的能力

当前已经可以明确视为正式主线一部分的能力包括：

- Gateway API 门面
- Durable task mainline
- Task store / outbox / relay / Redis queue
- Runtime core
- Model / Generation plane
- Workflow definition / execution 基础主线
- Phase 17 Web 控制台
- ABAC / OPA 基础治理能力
- 基础 trace / metrics / state 能力

这说明平台已经不再是“纯概念架构”，而是具备主线工程骨架。

---

### 4.2 已进入主线但仍待增强的能力

以下能力已进入主线骨架，但仍需显著增强：

- Worker bridge 语义
- Policy / execution context / preflight 的统一契约
- Workflow 元模型标准化
- Workflow execution 观测结构
- AI-native node orchestration 标准
- Provider config / routing /治理
- Durable mainline 的状态机与失败语义
- 真实路径集成测试覆盖

这部分能力会直接决定平台能否从“能跑”走向“能商用”。

---

### 4.3 当前仍缺失正式产品面的能力

以下能力更接近产品控制面与商业化层，当前尚未形成正式产品实现：

- Workflow Studio
- Workflow Governance UI
- Applications Workspace
- Tenant Governance UI
- Audit UI
- Billing / Quota UI
- Skill / Connector Marketplace
- Tenant Admin Console
- Workflow Execution Monitor UI

这些能力不是“锦上添花”，而是平台从工程底座走向产品平台的关键步骤。

---

### 4.4 明确不建议从零自研的能力

基于平台边界与工程风险控制，以下能力明确不建议完全从零自研：

- 完整 BPMN / Workflow Engine
- 大而全 IAM 基础设施
- 完整通用 Observability 栈
- 通用 DB / MQ / Cache 基础设施
- 大而全连接器基础设施底座

平台应重点自研的是：

- AI-native orchestration layer
- Runtime 主线
- Durable execution 主线
- Capability protocol
- 多租户治理与商业化控制面
- 平台产品面与业务交付能力

---

## 5. 平台能力视图总结

从能力矩阵看，当前平台已经具备以下特征：

### 5.1 已具备“平台骨架”
平台已经拥有：
- 接入层
- 执行层
- durable task 主线
- workflow 基础骨架
- 模型平面
- 基础治理能力
- 基础前端控制台

### 5.2 尚未具备“完整产品面”
平台距离完整商业化产品，还缺：
- workflow studio
- 治理控制面
- 商业化控制面
- 连接器 / skills 产品面
- 应用级交付工作台

### 5.3 真正的关键不是继续横向堆模块
下一阶段最重要的不是盲目新增功能，而是：

- 固化主线
- 明确边界
- 统一能力抽象
- 补齐产品控制面
- 复用成熟基础设施
- 提升稳定性与可治理性

---

## 6. 使用建议

本能力矩阵建议作为以下工作的基础文档：

1. **研发优先级梳理**
   - 判断哪些是主线必须做
   - 判断哪些属于产品化补齐
   - 判断哪些应复用而非自研

2. **新研发接手**
   - 快速理解当前平台到底已有何能力
   - 避免重复造轮子
   - 避免误判平台完成度

3. **产品路线梳理**
   - 区分工程底座能力与产品面能力
   - 区分主线能力与未来增强能力
   - 区分必须自研与应复用能力

4. **架构治理**
   - 新功能进入主线前，对照本矩阵判断其所属域
   - 判断其是否破坏边界
   - 判断其是否需要形成正式模块文档

---

## 7. 结论

当前平台已经不是“点状功能集合”，而是一个具有明确骨架的 AI OS / AI-PaaS 平台雏形。

但平台是否会成功，不取决于它还能再堆多少模块，而取决于：

- 是否坚持唯一主线
- 是否坚持基础设施复用原则
- 是否把 workflow、runtime、governance、frontend 逐步产品化
- 是否避免平台演化为大杂烩
- 是否真正把能力矩阵中的“已实现骨架”升级为“可治理、可交付、可商用的平台能力”

本矩阵的目标，就是为这个过程提供一张清晰的全局能力地图。