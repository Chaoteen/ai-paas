# 平台全景图（Phase 18）
**日期**：2026-04-04  
**仓库**：`https://github.com/Chaoteen/ai-paas/tree/wip/integration-split-commits`  
**文档面向对象**：接手研发的 AI 工程师 / 平台研发团队 / 产品架构协同人员  

---

## 1. 平台目标

### 1.1 平台总体定位
本项目不是单一 Agent、单一 Workflow 工具、单一聊天应用，也不是只做一个模型调用中间层。  
平台目标是构建一个：

**AI OS for AI Applications**

它既要服务 **AI 程序员开发 AI 应用**，也要最终服务 **终端用户使用 Agent / Skill / Workflow 产品**。

### 1.2 平台必须同时满足的双重目标

#### 目标 A：作为 AI-PaaS 底座，支持 AI 程序员开发应用
平台应具备统一能力底座，支持开发者通过接口、配置、能力编排快速构建 AI 应用，至少包括：

- Agent Runtime
- Skill / Tool 调用
- Workflow 编排与执行
- 多模型统一接入
- 多模态 Generation
- 持久化任务与异步执行
- 权限控制与多租户治理
- 可观测性、追踪、审计

#### 目标 B：作为面向用户的 AI OS 产品层
平台最终不只是后端引擎集合，而要有完整产品控制面，支持：

- 定义 Agent
- 运行 Skill
- 用可视化界面搭建 Workflow
- 统一管理模型、工具、策略、权限
- 面向用户形成类似 Dify / OpenClaw 级别的一体化操作体验

### 1.3 平台设计原则
1. **平台主权优先**  
   第三方能力（LangGraph / PromptFlow / Flowise / OPA）可以集成，但不能取代平台自己的主 schema、主数据模型、主执行主线。

2. **统一执行模型优先**  
   Agent、Skill、Workflow、Tool、Generation、Long-running Task 必须进入统一任务主线，而不是彼此孤立。

3. **产品级完整功能优先，不做最小闭环**  
   用户要求每个模块都按完整产品能力开发，不接受“先糊一个能跑的最小版再说”。

4. **模块代码必须完整可直接粘贴使用**  
   用户本人主要负责复制粘贴代码，研发必须提供完整文件、完整函数、完整依赖关系、完整测试说明。

---

## 2. 当前阶段说明（截至 2026-04-04，Phase 18）

当前研发阶段为 **Phase 18**。  
结合当前分支结构与已讨论内容，平台已经进入：

**“后端主线开始成形，但前端产品控制面尚未闭环”的阶段。**

仓库当前已存在平台级目录分层，核心包括：

- `bootstrap/`
- `gateway/`
- `runtime/`
- `workers/`
- `persistence/`
- `migrations_runtime/`
- `webapp/`
- `langgraph/`
- `promptflow/`
- `flowise/`
- `policies/`
- `tests/`

这说明平台已超出单体 demo 范畴，已经具备平台化分层基础。

---

## 3. 当前已开发模块、实际能力范围、占位模块、不完善模块

### 3.1 Bootstrap / Runtime 装配层
#### 当前状态
已开发。

#### 已达到的能力范围
- 支持 runtime 启动装配
- 支持模型装配
- 支持 worker 启动装配
- 支持 outbox relay 启动
- 支持基于环境变量切换 persistence / event bus
- 支持 Postgres / Redis 路径切换思路

#### 解决的问题
- 平台从单进程 demo 走向真实部署结构
- 后端主线具备独立进程/组件化运行基础
- 后续支持 durable task / queue / relay / worker 分离

#### 当前不足
- 启动主线虽然存在，但面向研发的统一启动体验、环境检查、错误提示、运维脚本标准化仍需继续补强
- 缺少真正的“面向交付”的环境自检闭环

#### 结论
**半完成偏强**

### 3.2 Gateway API 层
#### 当前状态
已开发。

#### 已达到的能力范围
- 已有任务提交主线
- 已有 workflow definitions / executions / submit 类 API
- 已有健康检查与基础平台 API
- 已接入部分 UI / 管理入口

#### 解决的问题
- 为前端、外部系统、未来控制面提供统一访问入口
- 让 workflow、task、runtime 不再直接裸露内部实现

#### 当前不足
- API 已有骨架，但围绕 Agent、Skill、Workflow Builder 的产品级 API 仍未完整闭环
- 一些 API 是主线可用，但用户体验层仍未形成完整产品链路

#### 结论
**半完成偏强**

### 3.3 Runtime 核心执行层
#### 当前状态
已开发，是目前平台最接近“中枢”的部分。

#### 已达到的能力范围
- Agent Runtime 基础主线
- Generation / Models / Tools / Queue / Workflow 等子域
- 统一任务执行思路
- 为 durable runtime、worker 执行、异步执行提供骨架
- 已有 workflow 域模型，不是停留在纯第三方工具上

#### 解决的问题
- 把模型调用、工具能力、任务执行纳入统一运行时
- 为未来 Agent / Workflow / Skill / Tool / Generation 统一执行提供基础

#### 当前不足
- 各子域之间仍需进一步“产品化”与“主线统一”
- 目前仍偏向“后端能力底座”，距离“用户直接可操作产品”还有一层前端控制面缺口

#### 结论
**半完成偏强，是当前平台最核心已成形部分**

### 3.4 Workflow 域模型与执行骨架
#### 当前状态
已开发，且方向明确。

#### 已达到的能力范围
平台已不是“没有 workflow”，而是已经具备：
- Workflow Definition
- Workflow Execution
- Node / Edge 模型
- 节点类型抽象
- Workflow Submit 主线
- Durable Task 封装思路

节点能力方向已经覆盖：
- Start
- Capability
- Decision
- Parallel
- Join
- End
- Subworkflow
- Wait Event

#### 解决的问题
- 平台已经形成“自己的 workflow 语言层”
- 不再完全依赖外部 workflow 平台的内部格式

#### 当前不足
- 还没有自己的前端可视化 Builder
- 还没有成熟的执行可视化、步骤 trace、失败恢复展示
- 还没有完成“从 definition 到 execution 到 UI 可视化观察”的统一闭环

#### 结论
**后端主线已成形，产品层未完成**

### 3.5 Worker / Queue / Durable Task 主线
#### 当前状态
已开发基础骨架。

#### 已达到的能力范围
- 支持任务异步提交
- 支持持久化任务的主线方向
- 已有 queue / worker / relay 分层基础
- 已支持 workflow task 与普通 task 进入统一 envelope 思路

#### 解决的问题
- 平台开始具备可扩展的异步执行能力
- 为重试、补偿、长任务、恢复、失败处理提供基础

#### 当前不足
- 全链路生产级验证仍不足
- 跨模块场景下的 E2E 验证尚不系统
- 需要进一步补强 retry / backoff / DLQ / 可观测性展示

#### 结论
**半完成**

### 3.6 Models / Generation 多模型与多模态能力
#### 当前状态
已开发。

#### 已达到的能力范围
- 平台具备多模型适配思路
- 可接主流云模型与本地模型
- 已具备 generation 域
- 已能支撑后续多模态扩展方向

#### 解决的问题
- 平台不是单模型绑定
- 为用户在企业场景中根据成本 / 性能 / 推理能力做模型切换提供基础

#### 当前不足
- 模型选择、策略管理、前端控制面、运行日志等产品层能力仍不足
- 对终端用户而言还没有形成“模型运营控制台”

#### 结论
**后端能力已有，产品层不足**

### 3.7 OPA / ABAC / Policy 安全治理能力
#### 当前状态
已接入，已具备方向价值。

#### 已达到的能力范围
- 已具备 OPA 接入方向
- 已有策略相关管理入口
- 已有 ABAC / 权限治理的产品意图

#### 解决的问题
- 为平台商业化后的权限隔离、安全治理、多租户控制打基础

#### 当前不足
- 还未全面打通到 Agent、Workflow、Skill、Execution 产品主线
- 权限控制更多还是“基础设施方向”，还不是“完整产品闭环”

#### 结论
**基础已接入，尚未系统完工**

### 3.8 WebApp 前端壳层
#### 当前状态
已开发基础前端骨架。

#### 已达到的能力范围
- 已有统一导航壳
- 已有 chat 页面
- 已有菜单体系
- 已有若干管理入口

#### 解决的问题
- 平台开始具备统一前端入口
- 不再只是纯 API 系统

#### 当前不足
- 当前更多是“平台外壳”，不是“完整产品控制面”
- 核心产品页面仍未闭环

#### 结论
**基础壳层已存在，但远未完成**

### 3.9 Agent 管理中心
#### 当前状态
**占位**

#### 已达到的能力范围
- 仅说明产品方向存在

#### 当前问题
- 没有 agent CRUD
- 没有 agent version
- 没有 capability binding
- 没有运行记录与管理控制面

#### 结论
**占位模块，未完成**

### 3.10 Chat / Assistant 前端
#### 当前状态
已开发轻量页面。

#### 已达到的能力范围
- 基本消息输入输出
- 可作为 UI 骨架存在

#### 当前不足
- 不是完整 Agent 操作台
- 没有 skill 调用观察
- 没有 workflow/task trace 可视化
- 没有 agent 选择、会话治理、运行状态控制

#### 结论
**初始可见页面，产品能力不足**

### 3.11 Flowise / PromptFlow / LangGraph 集成入口
#### 当前状态
已集成入口，但主要是外挂方式。

#### 已达到的能力范围
- 平台可以把这些外部系统接进统一壳层
- 可作为验证和兼容性接入

#### 当前不足
- 当前主要是 iframe / 外挂入口思路
- 这些还不是平台内部 canonical workflow / agent 控制面
- 用户如果主要靠这些入口操作，平台主权会被削弱

#### 结论
**集成存在，但不是最终形态**

---

## 4. 当前平台能力的总体判断

截至 2026-04-04，平台已经具备：

### 已经明确形成的部分
- 后端平台分层
- runtime 主线骨架
- workflow 领域模型与 definition / execution / submit 主线
- 异步任务 / durable task 方向
- 多模型接入与 generation 基础
- OPA / ABAC 安全治理方向
- 前端统一入口壳层

### 尚未形成完整产品闭环的部分
- Agent Builder / Agent 管理中心
- Skill 注册与执行管理控制面
- 平台自有 Workflow Builder
- Workflow Execution 可视化
- 面向用户的一体化控制面
- 全链路系统级 E2E 验证

---

## 5. 八个平台完善标准

### 标准 1：统一运行时主线成立
要求：
- Agent / Skill / Workflow / Tool / Generation / Long-running Task 进入统一任务执行模型
- 支持异步执行、持久化、状态追踪、错误处理

验收标准：
- 任意一种任务都能进入统一 runtime envelope
- 可统一查询执行状态
- 有统一错误模型与恢复模型

### 标准 2：平台自有 Workflow 主线成立
要求：
- 平台拥有自己的 workflow schema、definition、execution、versioning
- 第三方 workflow 只是 adapter

验收标准：
- Workflow Builder 保存的是平台自己的 schema
- Workflow 执行查询、版本管理走平台 API
- LangGraph / Flowise / PromptFlow 不再是用户主操作面

### 标准 3：Agent Builder 成立
要求：
- 用户可在前端定义 agent
- 可绑定模型、skill、workflow、tool、策略

验收标准：
- Agent CRUD 完整可用
- Agent version 可管理
- 可发布 / 停用 / 运行
- 运行记录可查询

### 标准 4：Skill 平台化成立
要求：
- Skill 有注册、元数据、输入输出 schema、执行管理、日志与绑定能力

验收标准：
- 可在 UI 查看 skill 列表
- 可配置 skill
- 可被 agent / workflow 节点引用
- 运行日志与错误信息可查看

### 标准 5：Workflow Builder 成立
要求：
- 平台有自己的可视化流程搭建界面
- 支持节点配置、边配置、参数配置、版本管理、发布

验收标准：
- 用户不依赖外部 iframe 即可搭建流程
- Builder 保存、发布、运行、查询全闭环可用
- 至少支持 Start / Capability / Decision / Parallel / Join / End

### 标准 6：统一产品控制面成立
要求：
- Agent / Skill / Workflow / Chat / Policy / Model / Execution 在统一前端体验内操作
- 前端不只是导航壳

验收标准：
- 核心页面全部是真实产品页面，不是占位
- 外部系统仅作为兼容入口，而非主入口

### 标准 7：安全治理与多租户闭环成立
要求：
- OPA / ABAC / 多租户 / 审计打通到平台核心能力

验收标准：
- 不同租户的 agent / workflow / execution 可隔离
- 权限控制落实到具体资源与操作
- 审计日志可追踪

### 标准 8：全链路验证体系成立
要求：
- 有完整 E2E 测试与交付级验证
- 平台不是“模块都在，但主线没验证”

验收标准：
至少跑通以下链路：
1. UI 创建 workflow → 保存 → 提交 → 执行 → 状态回写  
2. UI 创建 agent → 绑定 skill → 运行 → 返回结果  
3. workflow capability 节点失败 → retry/backoff → trace 可见  
4. 多租户访问控制验证  
5. 外部 adapter 由平台统一调度验证  

---

## 6. 总体 roadmap 与优先级

### P0：平台主权确立与产品控制面补齐（最高优先级）
**为什么优先**  
当前最大问题不是“没接够引擎”，而是平台后端已成形，但产品层没闭环。继续接新模块只会让系统更碎。

#### 开发模块
1. Agent 管理中心  
2. 平台自有 Workflow Builder  
3. Workflow Execution 观察页  
4. Skill Registry / Skill 管理页  
5. Chat 升级为 Agent 操作台  

#### 解决的问题
- 当前 AgentHub 是占位
- 当前 workflow 主要靠外部入口
- 当前 skill 没有统一控制面
- 当前 chat 不是完整的产品台

#### 开发功能
- Agent CRUD / version / binding / publish
- Workflow 可视化搭建、保存、发布、运行
- Execution 查询、step trace、状态流展示
- Skill 列表、元数据、调试、绑定
- Chat 页面支持 agent 选择、任务观察、调用过程查看

#### 验收标准
- 用户在前端可独立完成 agent 定义、workflow 搭建、skill 绑定与运行
- 不依赖外部 iframe 作为主操作面
- 前端控制面第一次闭环

### P1：统一执行主线增强与 workflow 产品化
#### 开发模块
1. Workflow Runtime Executor 补强  
2. Retry / Backoff / DLQ / Resume  
3. Workflow Product Binding  
4. Agent / Workflow / Skill 的统一执行记录中心  

#### 解决的问题
- 后端主线有骨架，但还需补强生产级执行特性
- 没有完整恢复和失败处理产品能力

#### 开发功能
- workflow 节点执行策略
- 失败恢复与重试机制
- 执行快照与上下文持久化
- 统一 execution store 与查询接口
- product schema / public API schema / ui schema

#### 验收标准
- workflow 支持稳定执行、失败处理、恢复
- 能把 workflow 包装为面向用户的产品能力
- execution 主线清晰可追踪

### P2：安全治理、多租户、审计闭环
#### 开发模块
1. OPA / ABAC 深度接入资源层  
2. 多租户资源隔离强化  
3. 审计日志与操作审计 UI  
4. 安全策略与发布策略体系  

#### 解决的问题
- 当前安全治理还没全面进入产品主线
- 商业化前必须补足治理能力

#### 开发功能
- 资源级授权控制
- 执行权限控制
- agent/workflow 发布审批 / 审计
- 审计日志查询与导出

#### 验收标准
- 核心资源操作可授权、可隔离、可审计
- 多租户主线可验证

### P3：外部引擎适配器体系标准化
#### 开发模块
1. LangGraph Adapter  
2. Flowise Adapter  
3. PromptFlow Adapter  
4. 外部 workflow / agent 接口规范  

#### 解决的问题
- 当前外部系统接入方式偏入口化、碎片化
- 需要降级为平台适配器，而不是主产品层

#### 开发功能
- adapter contract
- external execution mapping
- external trace/result mapping
- UI 中作为兼容入口，而不是主入口

#### 验收标准
- 用户主要使用平台控制面
- 外部系统通过 adapter 纳入平台治理

### P4：运维、监控、交付与商业化补全
#### 开发模块
1. 环境自检与启动管理  
2. 运维看板  
3. 资源配额与成本管理  
4. 租户运营后台  
5. 商店 / 产品发布体系  

#### 解决的问题
- 平台可研发不等于平台可交付
- 商业化需要运营与运维能力

#### 开发功能
- runtime health dashboard
- queue / worker / task 状态监控
- token / cost / usage 统计
- 应用 / agent / workflow 产品发布

#### 验收标准
- 平台具备交付和运营基本能力
- 可面向真实客户运行与治理

---

## 7. 当前阶段的核心架构判断

### 7.1 关于 Workflow 路线
**结论：不要把 LangGraph 直接当成平台唯一 workflow。**

正确路线是：

- 平台保留自己的 workflow schema、definition、execution 主线
- LangGraph 作为某类 agentic workflow 的执行适配器
- Flowise / PromptFlow 作为兼容接入，不作为平台主 schema

### 7.2 为什么不是继续新增独立 workflow 平台
因为当前缺口不是“又少了一个 workflow 引擎”，而是：
- 缺自己的 Builder
- 缺自己的控制面
- 缺 execution 可视化
- 缺统一产品闭环

新增外部 workflow 只会让主线更分散。

---

## 8. 下一迭代的需求文档（交给下一个接手程序员）

# Phase 19 需求文档
**主题**：补齐平台产品控制面第一阶段闭环  
**目标**：让平台第一次具备“用户可见、可操作、可运行”的 AI OS 基础产品形态

## 8.1 本迭代必须完成的模块

### 模块 A：Agent 管理中心（正式版，替换占位页）
#### 要做什么
开发完整 Agent 管理中心页面和后端接口，不能只做列表页或占位页。

#### 必须具备的功能
- Agent 列表
- Agent 创建
- Agent 编辑
- Agent 删除
- Agent 版本管理
- 模型绑定
- Skill / Tool / Workflow 绑定
- 发布 / 停用
- 运行记录查看

#### 验收标准
- 用户可在 UI 完整定义和管理 agent
- 不是演示页，不是占位页
- 页面、接口、数据模型、状态流完整闭环

### 模块 B：平台自有 Workflow Builder（第一正式版）
#### 要做什么
开发平台自己的可视化 Builder，不能继续依赖外部 iframe 作为主工作流搭建方式。

#### 必须具备的功能
- 节点面板
- 边连接
- 节点配置
- 工作流保存
- 工作流发布
- 工作流运行
- 工作流版本管理
- workflow definition 与 execution 查询

#### 节点范围（首批必须支持）
- Start
- Capability
- Decision
- Parallel
- Join
- End

#### 验收标准
- Builder 产物必须保存为平台自己的 workflow schema
- 前端可直接调用平台 API 保存与运行
- 用户不需要进入 Flowise / PromptFlow / LangGraph 页面来完成主流程搭建

### 模块 C：Workflow Execution 观察台
#### 要做什么
开发 workflow execution 状态与步骤观察页面。

#### 必须具备的功能
- execution 列表
- execution 详情
- step timeline
- 当前状态
- 输入输出信息
- 错误信息
- retry/backoff 展示

#### 验收标准
- workflow 运行结果不是黑盒
- 用户可看到流程实际执行情况

### 模块 D：Skill Registry / Skill 管理页（第一版）
#### 要做什么
把 Skill 从“代码中存在”升级为“产品中可见”。

#### 必须具备的功能
- Skill 列表
- Skill 元数据展示
- 输入输出 schema 展示
- Skill 绑定到 Agent / Workflow
- 基本运行调试入口

#### 验收标准
- Skill 在平台前端可见、可选、可绑定
- 不再只是隐藏在代码目录中的能力

### 模块 E：Chat 升级为 Agent 操作台
#### 要做什么
把当前轻量 chat 页升级为真正的 agent 操作页。

#### 必须具备的功能
- 选择 agent
- 查看 agent 运行过程
- 展示工具/skill/workflow 调用状态
- 显示任务状态与返回结果

#### 验收标准
- chat 不只是聊天框
- 可以承载 AI OS 的用户操作入口

## 8.2 本迭代禁止事项
1. **禁止继续新增新的外部 workflow 平台作为主线**
2. **禁止只做最小闭环**
3. **禁止只写 demo 代码**
4. **禁止只补页面壳子不补真实业务接口**
5. **禁止交付代码片段而不是完整文件**

## 8.3 本迭代的架构原则
1. 前端 Builder / Agent / Skill 页面必须直接绑定平台自己的 schema 与 API  
2. LangGraph / Flowise / PromptFlow 继续保留，但只能作为 adapter 或兼容入口  
3. 所有新增模块都必须进入平台统一任务主线  
4. 所有模块必须考虑后续多租户、权限、审计扩展  
5. 所有代码必须是“可直接复制粘贴执行的完整代码”，不能给不完整片段  

## 8.4 交付要求（给下一个程序员）
用户的工作方式明确如下：

- 用户主要负责复制粘贴代码，不负责替你补代码结构
- 你必须提供完整代码，不要只给思路
- 每一个模块都要按完整产品功能开发，不做 MVP 式最小闭环
- 写清楚新增文件、替换文件、修改文件路径
- 写清楚依赖安装方式、启动方式、测试方式
- 如果需要数据库迁移，要提供完整 migration
- 如果需要 API 变更，要提供前后端联动代码
- 如果需要页面联动，要提供完整页面代码、接口调用代码、状态管理代码
- 不能让用户自己“拼一拼”完成模块

---

## 9. 对下一个接手程序员的明确指令

你接手后，不要从“再接哪个外部框架”开始。  
你要从 **平台控制面闭环** 开始。

### 你的第一工作顺序
1. 先阅读仓库中 runtime / gateway / webapp / workflows 相关主线代码  
2. 明确平台自己的 workflow schema 与任务主线  
3. 开始补 Agent 管理中心  
4. 开始补平台自己的 Workflow Builder  
5. 做 Workflow Execution 观察台  
6. 做 Skill Registry 页面  
7. 把 Chat 升级为 Agent 操作台  
8. 最后再考虑把 LangGraph 等接成标准 adapter

### 你的交付要求
- 交付完整模块代码
- 交付完整接口
- 交付完整页面
- 交付完整测试方法
- 交付完整启动方法
- 不能只做“先跑起来再说”的最小闭环

---

## 10. 最终结论

截至 Phase 18（2026-04-04），平台已经完成了后端主线的重要骨架，包括：

- runtime 分层
- workflow 域模型
- workflow definition / execution / submit 主线
- durable task 与 worker 方向
- 多模型与 generation 基础
- OPA / ABAC 治理方向
- 前端统一入口壳层

但平台仍未达到“AI OS 初版成立”的标准，主要缺口集中在：

- Agent 控制面
- 平台自有 Workflow Builder
- Skill 平台化管理
- Workflow Execution 可视化
- Chat 产品化操作台
- 全链路 E2E 闭环验证

因此，下一阶段的核心任务不是再扩更多外部模块，而是：

**把已经存在的后端平台骨架，真正翻译成前端产品控制面。**

当平台完成 Agent Builder、Workflow Builder、Skill Registry、Execution 观察台、统一 Chat 操作台并跑通全链路后，平台才会第一次真正具备“AI OS”的雏形。
