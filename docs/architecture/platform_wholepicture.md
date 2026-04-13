一、你的反馈我先整理成正式决策
1. 录制层

你同意方案 3，但你补充了一个非常关键的产品点：

“录制”不一定等于开录屏。

它至少应包含两种入口：

A. 操作录制入口
录键盘鼠标 / GUI / 浏览器 / 软件操作
产出结构化 action sequence
B. 对话描述入口
用户通过对话讲述“我是怎么做这件事的”
平台理解意图
如果目标应用有 API 或已有 Skill，就直接组合调用
不一定要真的录屏

这个补充非常重要，因为它让你的“技能蒸馏”从纯 RPA 录制扩展成：

RPA 录制 + 知识抽取式技能生成

所以录制层以后应该定义成：

工作技能蒸馏层
而不是单纯的 recorder。

这对方案的影响

UI-TARS-desktop 更适合作为 GUI 执行层，而不是录制产品本体；它官方定位就是 GUI Agent / local and remote computer / browser operator，而不是 recorder。

所以录制层正式方案应变成：

自建“工作技能蒸馏层” + 集成 UI-TARS 作为 GUI 执行能力层。

2. 技能层

你希望评估 OpenClaw / IronClaw 有没有可直接 copy-paste 的代码块，降低周期。

我当前判断

OpenClaw 的 skill 更像：

兼容 AgentSkills 的 skill folder
SKILL.md + frontmatter + 指令包
运行时注入与筛选

也就是说，它非常适合参考：

Skill 元数据结构
Skill 包组织方式
Skill 加载与 allowlist 机制

但它不是你要的面向业务用户的“技能录制/编辑/测试/发布”产品。OpenClaw 官方自己也把 Skills 定义成一种目录与说明文档驱动的能力包。

所以技能层的策略应该是
参考 OpenClaw / IronClaw 的运行时和 skill 元数据结构
自建 Skill 资产层与前端技能管理页

也就是：

可复用 / 可参考的部分
Skill package metadata
Skill loading / filtering
Skill runtime binding
Plugin/skill allowlist 思路
必须自建的部分
Skill 资产模型
Skill 版本
Skill 测试运行
Skill 录制草稿
Skill 发布
Skill 库页面
3. 输入输出格式层

你同意方案 3C，并补充说：最初就是打算用 Flowise + PromptFlow；你不确定现在代码里还剩多少当初规划的能力。

我当前结论

这个方向没问题，而且是理性的。

Flowise 适合什么
表单输入
Variables
Structured Output
可视化配置体验。
PromptFlow 适合什么
DAG flow
输入输出 contract
YAML 化 flow 描述
工程化测试和评估。
你的最终产品不该怎么定义

不应该让用户说：

我在用 PromptFlow 定输入输出
我在用 Flowise 配格式

而应该让用户看到：

输入输出格式
变量映射
模板与结构
所以这个层的正式方案是

平台自建 IO 资产层；Flowise 做可视化承载补充；PromptFlow 做研发与评估补充。

研发计划上要补一个动作

你说得对，这块要做一次代码审计，确认当前 repo 里 promptflow/、flowise/ 相关集成还保留了哪些输入输出控制能力。仓库层面这两个目录当前仍在。

4. 流程层

你强调：

BPMN 引擎层应该用经过验证的开源产品。你要建设的能力不在 BPMN 标准引擎层，而是在它上面长能力。

这个判断非常关键，我基本同意。

这意味着

你不应该把大量时间花在“自研底层标准 BPMN engine”上。
你真正的价值层是：

技能节点
AI/Agent 节点
输入输出传播
执行观察
数字员工绑定
流程产品化
所以流程层的正式策略是

保留平台自有 workflow 主 schema / execution 主线；底层可集成成熟流程引擎；你在引擎之上建设技能编排和数字员工能力。

这和你原来 Phase 19 的定义也能对齐：
你当前还是必须先把 多 Step 顺序链 + 数据传播 + capability adapter 做实，因为这是你“在引擎上长能力”的前提。

5. 流程库

你说可以自研，我同意。

因为你已经有：

workflow definitions
workflow executions
execution query / timeline
product binding

流程库相对容易，就是把 definition/product 资产层收口成一个正式产品页面和 API。这个是低风险高收益模块。

6. 数字员工层

你同意方案 6C：

自建数字员工对象模型，Dify 作为复杂 Agent / workflow 兼容层。

我认为这是现阶段最合理的。

Dify 为什么适合当兼容层

官方定位就是：

building agentic workflows
visual canvas
agent + tools + workflow + deployment。

它成熟、交付工程师熟悉、稳定性相对好，这是现实优势。

但它不该成为你的产品主语

因为你的数字员工定义比 Dify App 更重：

skill + agent + workflow
trigger
stop
evaluation
market-ready asset

所以正式策略应是：

数字员工对象模型、自身生命周期、绑定关系、触发/停止/评估都归你平台；Dify 只承接复杂 agent/workflow 执行能力。

二、基于你的反馈，正式研发计划我建议这样排

我按“现阶段最合理的搭建方案”来排，而不是按终态全量能力排。

阶段 0：架构收口与代码审计（1 周）
目标

在正式开干之前，把“哪些能力可以接、哪些必须自己做”核实清楚，避免重复返工。

要做的事
A. PromptFlow / Flowise 代码审计

确认当前 repo 里：

输入输出格式
变量映射
prompt / flow 配置
前后端接入点
还剩哪些能力没丢。
B. Dify / UI-TARS 技术接入验证

做两个最小技术 spike：

UI-TARS 作为 GUI 执行器接入
Dify 作为复杂 Agent / workflow 执行器接入
C. Skill 参考代码审计

评估 OpenClaw / IronClaw：

Skill metadata
Skill loading
Skill runtime binding
哪些代码可直接复用，哪些只能参考
交付物
选型审计报告
集成边界图
“直接复用 / 改造复用 / 自建”清单
阶段 1：工作技能蒸馏层 MVP（2–4 周）

这是第一优先级。

目标

打通：

用户描述工作 → 或录制操作 → 生成 Skill 草稿 → 保存到技能库

范围
1. 蒸馏入口双通道
对话描述入口
操作录制入口（先 MVP，不必一开始做到很复杂）
2. Skill 草稿模型
draft skill
action sequence
step metadata
parameter suggestions
3. 技能库基础
保存草稿
查看列表
查看详情
简单编辑
简单测试
后端需要开发
recording_sessions
recording_action_events
skill_drafts
skills
skill_versions
skill_test_runs
前端需要开发
录制工作台
对话蒸馏入口
技能库
技能详情/测试页
集成策略
UI-TARS：只作为 GUI 执行能力层
OpenClaw/IronClaw：只参考 skill metadata / runtime binding
这一阶段的价值

用户第一次能看到：
“我把一段工作方法变成技能了。”

阶段 2：输入输出格式层 + Skill 正式资产化（2–3 周）
目标

让 Skill 不只是“录出来的一段脚本”，而是可复用资产。

要做的事
IO format definition
variable mapping
template / schema 管理
Skill 版本与发布状态
Skill 测试与验证闭环
后端
io_format_definitions
io_format_versions
variable_mappings
template_assets
前端
输入输出格式页
Skill 发布状态页
Skill 版本页
集成策略
Flowise：短期承接部分可视化变量配置
PromptFlow：研发与评估层使用，不直接作为用户页面主语
价值

用户开始真正拥有：
可复用、可配置、可测试的 Skill 资产。

阶段 3：流程编排主线（3–5 周）

这是你原来定义的 Phase 19 核心，必须拉回主线。

目标

让 Workflow 从 foundation 真正变成：

多 Step 顺序链 + 数据传递 + capability adapter 的正式主线

必做后端
多 Step 顺序链
Step Output → Next Input
Capability Adapter Contract
Decision Node（至少设计完成，功能可后置）
Builder schema 与 runtime schema 对齐
Workflow lifecycle / version / publish 基础
前端
流程设计器第一版
流程库第一版
执行记录页继续增强
集成策略
流程引擎底层可接成熟产品
但 definition schema / execution 主线 / 观察台 / 产品化归你平台
价值

用户第一次能做到：
把多个 Skill 串成业务流程并稳定运行。

阶段 4：数字员工雏形（3–4 周）
目标

让 Skill + 流程开始被包装成“数字员工”。

要做的事
后端对象
digital_workers
digital_worker_versions
digital_worker_bindings
digital_worker_run_sessions
前端页面
数字员工列表
数字员工配置
基础运行会话
能力范围

先不把 trigger/stop/evaluation 一次做满，先做：

绑定技能
绑定流程
绑定模型
发布/停用
手动运行
集成策略
Dify 作为复杂 Agent / workflow 兼容层
数字员工对象模型和生命周期归你平台
价值

用户第一次能看到：
“这不是一个 skill，也不是一个流程，而是一个数字员工。”

阶段 5：触发 / 停止 / 完成评估（3–4 周）
目标

让数字员工从“能跑”变成“能自动完成任务”。

要做的事
trigger definitions
stop conditions
completion criteria
evaluation rules
human review points
价值

数字员工开始真正具备：

何时开始
何时停止
如何判定完成
是否需要人工确认

这是你定义数字员工的核心分界线。

阶段 6：市场化准备（后置）

你自己已经把节奏讲清楚了：

先录制/蒸馏
再流程编排
再可迁移运行
最后才是市场

我认同这个顺序。

应用商店现在怎么处理

当前只做：

资产模型预留
发布接口预留
租户内/跨租户可见性模型预留

暂时不要把市场做成主菜单主能力。

三、每层采用的正式方案我再收口成一句话
1. 工作技能蒸馏层

自建产品层 + UI-TARS 执行层

2. Skill 资产层

自建，参考 OpenClaw / IronClaw 技术结构，但不直接把它们当产品

3. 输入输出格式层

自建资产层，Flowise 做可视化承载补充，PromptFlow 做研发/评估补充

4. 流程层

自建主 schema / runtime / 观察台，底层可接成熟流程引擎

5. 流程库

直接自研

6. 数字员工层

自建对象模型，Dify 做复杂 Agent / workflow 兼容层

四、对交付周期、研发投入和经费的现实建议

如果你现在要算“现阶段最合理的平台搭建方案”，我建议不要把预算平均撒开。

最应该优先投入的 3 层
1. 工作技能蒸馏层

因为这是你差异化最强的地方。

2. Skill 资产层

因为这是你后面一切可交易、可复用能力的基础。

3. Workflow 主线

因为 Skill 不进 Workflow，就无法形成业务闭环和数字员工。

暂时不该重投入的
1. 市场系统

后置。

2. 复杂计费和跨租户交易

后置。

3. 完整自研底层 BPMN engine

不值得现阶段重投入。

五、你现在这版研发计划，我建议的表述方式

我建议你内部直接把当前建设方案定义成：

第一阶段目标

建设“工作技能蒸馏 + Skill 资产化 + 流程编排”的平台基础闭环。

成功标志
用户能通过录制或对话蒸馏生成 Skill 草稿
Skill 能编辑、测试、发布
多个 Skill 能组成流程
流程能执行、能观察、能进入流程库
数字员工有最初的对象模型与绑定能力

这比“我要做一个 AI OS 平台”更适合当前立项、排期和预算。

一、1–6 阶段总控规划表
1. 平台总目标

平台总目标定义为：

建设一个“工作技能蒸馏 → Skill 资产化 → 流程编排 → 数字员工运行 → 治理与运维 → 应用商店预留”的 AI OS。

核心对象是 5 个：

技能
流程
数字员工
运行记录
治理策略

底层可集成：

UI-TARS-desktop：GUI 执行能力层
Flowise：可视化 AI / 变量 / 结构化输出辅助层
PromptFlow：研发型输入输出契约 / 评估辅助层
Dify：复杂 Agent / Workflow 兼容层
OpenClaw / IronClaw：Skill metadata / runtime binding 参考层

但平台主权必须掌握在你自己的：

数据模型
Runtime 主线
Workflow schema
Skill 资产层
数字员工对象层
市场对象层
2. 当前平台已具备的基础

按你当前仓库状态和我们前面已经确认过的内容，当前已具备：

已完成或基本成立
Gateway / Tasks API / Task Store / Outbox / Relay / Worker / Runtime 主线
Workflow foundation：
definition
execution
step execution
execution events
success / failure / retry / retry exhausted
Workflow product submit / execution 主线
Execution Query / Timeline API
基础控制面前端骨架
OPA / ABAC 方向接入
多模型 / generation / tool / agent runtime 基础骨架
未完成但已明确要做
多 Step 顺序链
Step Output → Next Input
Capability Adapter Contract
Skill 资产层
Recording Session / Action Event
IO Format 资产层
数字员工对象模型
Trigger / Stop / Completion / Evaluation
市场层
3. 1–6 阶段总表
阶段	阶段主题	阶段目标	建议拆分子阶段	建议对话数	每轮对话控制目标
阶段1	工作技能蒸馏层	让用户通过对话描述或操作录制形成 Skill 草稿	1A 架构审计与接口边界；1B Recording Session；1C 对话蒸馏 → Skill Draft；1D Skill Draft API/UI 对接	4	每轮只解决一个对象层：模型/API/测试/前端骨架
阶段2	Skill 资产层	让 Skill 成为可编辑、可测试、可发布的正式资产	2A Skill 数据模型；2B Skill CRUD/API；2C Skill 测试运行；2D Skill 版本/发布	4	每轮聚焦一个模块族：表 + repo + API + 测试
阶段3	输入输出格式层	形成统一 IO 资产层，并和 Skill / Workflow 对齐	3A 代码审计 Flowise/PromptFlow；3B IO Format 模型；3C Variable Mapping；3D Template/Schema UI	4	每轮控制在一个资产对象和一组接口范围内
阶段4	流程编排主线	把 Workflow 从 foundation 升级为真正顺序运行时与流程产品	4A 多 Step 顺序链；4B 数据传播；4C Capability Adapter；4D 流程设计器/流程库；4E 执行观察增强	5	运行时主线每轮只改一个大逻辑，防止回归
阶段5	数字员工层	形成数字员工对象模型与基础运行能力	5A Digital Worker 模型；5B 绑定 Skill/Workflow/Model；5C 数字员工管理页；5D 运行会话	4	每轮只做一个资产面和对应 API
阶段6	治理与市场预留层	建立触发/停止/完成评估与市场化预留	6A Trigger/Stop/Completion；6B Evaluation/HITL；6C 市场对象模型预留；6D 治理页与分析预留	4	每轮先建对象和契约，不急着做复杂交易系统
合计建议对话数

25 轮左右

这是比较稳的拆法。
原因不是模型上下文不够，而是：

每一轮都应该控制在“一个模块族 + 一组接口 + 一组测试 + 一次回归验证”的粒度。

这样你不会在一轮对话里同时改：

数据模型
运行时
前端页面
集成工具
测试
文档

否则回归风险很高。

二、每个阶段建议怎么开对话
总原则

每个阶段开一个“阶段总控对话”，然后阶段内每个子阶段再开一个独立对话。

也就是：

阶段总控对话：负责对齐目标、确认边界、记录当前阶段完成情况
子阶段对话：负责产出完整代码、测试、迁移、接口、页面
为什么这么拆

因为你希望：

每个阶段都围绕一个大目标
但阶段内不同子项目可以独立推进
同时又不希望每个对话太长，影响工程准确性

这套拆法最适合你现在这种“AI 工程师逐轮接力开发”的模式。

三、6 个阶段的标准提示词

下面每个提示词，都已经包含你要求的 3 个部分：

全局目标、模块、逻辑关系
当前阶段开发目标、当前平台已有模块、对接要求、表结构/JSON/schema 对齐要求
阶段内子阶段拆分与对话方式

你开新对话时，直接复制对应阶段提示词即可。

阶段1提示词：工作技能蒸馏层
你现在接手的是 AI OS 第一阶段研发，主题是“工作技能蒸馏层”。

一、先理解平台全局目标
平台总目标不是单一 Agent 平台，也不是单一 Workflow 平台，而是一个 AI OS。它的目标是：
1. 让用户把自己的工作方法蒸馏成技能（Skill）
2. 把技能编排成流程（Workflow）
3. 把技能和流程进一步包装成数字员工（Digital Worker）
4. 后续进入租户内和跨租户的应用商店流通

平台全局模块包括：
- Gateway / Tasks API / Task Store / Outbox / Relay / Worker / Runtime 主线
- Workflow foundation（definition / execution / step / event / retry）
- Execution Query / Timeline API
- 多模型 / tool / generation / agent runtime 基础骨架
- OPA / ABAC 治理方向
- 前端控制面骨架

模块逻辑关系是：
- 技能是原子能力
- 流程是技能的编排
- 数字员工是技能和流程的岗位化运行体
- 治理和运维贯穿所有对象
- 市场层建立在技能、流程、数字员工资产化之后

二、本阶段目标
本阶段不是做完整数字员工，也不是做市场，而是做“工作技能蒸馏层”。
本阶段要完成两类技能蒸馏入口：
1. 操作录制入口：用户通过录制桌面/网页/应用操作形成 Skill Draft
2. 对话描述入口：用户通过对话描述自己的操作过程，平台理解后生成 Skill Draft；如果目标系统已有 API 或已有 Skill，则优先调用接口或既有 Skill，而不是强制录制

本阶段要交付的核心对象和能力：
- recording_sessions
- recording_action_events
- skill_drafts
- draft → skill 基础映射
- 技能蒸馏入口 API
- 最基础的前端“录制工作台 / 技能草稿页”

三、你必须先检查当前平台已开发内容
你必须先阅读当前仓库代码，而不是假设：
- gateway/
- runtime/
- persistence/
- migrations_runtime/
- webapp/
- flowise/
- promptflow/
- langgraph/
- docs/ 当前阶段交接文档

你必须明确：
1. 当前 workflow 和 task 主线接口怎么写
2. 当前 Database 和 repository 风格
3. 当前 migrations_runtime 中已有哪些表
4. 当前 JSON contract、Pydantic model、schema 风格是什么
5. 当前前端菜单和页面骨架如何组织

四、本阶段开发要求
1. 所有新增表结构必须和当前 persistence / migrations_runtime 风格一致
2. 所有 API JSON 结构必须和当前 gateway / runtime contract 风格一致
3. 所有对象命名必须对齐现有 workflow / runtime 对象命名习惯
4. 不允许做演示级假模型，必须是后续可演进的正式对象
5. 不允许只给片段代码，必须给完整文件
6. 所有新增能力都要说明与 UI-TARS 执行层的接口边界
7. 操作录制与对话蒸馏两个入口都要考虑，但当前可以先把“对象模型 + 后端接口 + 最小前端骨架”做扎实

五、本阶段建议拆分成 4 个子阶段，分 4 个开发对话推进
子阶段1A：审计当前仓库中与录制、promptflow、flowise、skill、runtime 执行相关的代码，明确可复用点和接口边界
子阶段1B：设计 recording_sessions / recording_action_events / skill_drafts 的数据库表、repository、API
子阶段1C：实现对话蒸馏入口，把用户描述转成 Skill Draft 的最小后端闭环
子阶段1D：实现录制工作台 / Skill Draft 页面骨架，并打通保存、查看、测试草稿的最小前端闭环

六、本轮对话你的任务
先完成本阶段的技术评估和子阶段1A：
- 扫描当前仓库中可复用的录制、skill、promptflow、flowise 相关代码
- 明确阶段1要新增哪些表、API、页面
- 输出一个严格对齐当前仓库结构的开发清单
- 如果发现已有代码可直接复用，要指出具体文件和原因
- 不要跳到市场或数字员工层
阶段2提示词：Skill 资产层
你现在接手的是 AI OS 第二阶段研发，主题是“Skill 资产层”。

一、全局目标
平台总目标是“技能蒸馏 → Skill 资产化 → 流程编排 → 数字员工运行 → 治理 → 市场化”。
本阶段聚焦的是把 Skill 从草稿和概念，推进成正式的一等资产对象。

技能在全局中的逻辑关系：
- 技能是最小可复用能力单元
- 技能可来源于录制、对话蒸馏、API 封装、已有工具封装
- 流程编排的是技能
- 数字员工绑定技能和流程
- 市场未来可售卖技能、流程、数字员工

二、本阶段目标
本阶段要把 Skill 做成正式资产层，至少具备：
- Skill 主对象
- Skill Version
- Skill 输入输出绑定
- Skill 测试运行
- Skill 发布 / 停用
- Skill 库查询与管理 API
- 前端技能库和技能详情页

三、必须检查当前平台已有模块
你必须先确认：
- 阶段1产出的 skill_drafts、recording_sessions 等对象状态
- 当前 workflow product / execution / repository / API 风格
- 当前前端菜单和路由结构
- OpenClaw / IronClaw 可参考的 skill 元数据或运行时绑定代码，若有可复用点要指出具体文件

四、本阶段对接要求
1. Skill 表结构必须与当前 workflow / runtime 风格一致
2. JSON schema、Pydantic model、repository 风格必须与现有项目对齐
3. Skill 必须考虑未来绑定：
   - IO Format
   - Workflow Node Capability
   - Digital Worker
   - 市场商品对象
4. 不允许把 Skill 实现成临时 JSON blob，无版本状态机
5. 所有新增 API 必须说明和当前 Gateway / Runtime 主线的关系

五、本阶段建议拆成 4 个开发对话
子阶段2A：Skill 数据模型与 migration
子阶段2B：Skill CRUD / Query / Repository / API
子阶段2C：Skill Test Run / Skill Publish / Skill Version
子阶段2D：前端技能库 / 技能详情 / 测试与发布页面

六、本轮对话任务
先完成子阶段2A：
- 设计 skills、skill_versions、skill_test_runs、skill_publish_records 等对象
- 输出完整 migration、repository、model 设计
- 明确和 skill_drafts 的对接方式
- 明确和后续 workflow / digital worker 的引用关系
阶段3提示词：输入输出格式层
你现在接手的是 AI OS 第三阶段研发，主题是“输入输出格式层”。

一、全局目标
平台不是单纯的 Prompt 工具，而是要把技能、流程、数字员工统一建立在一套可复用的输入输出格式资产之上。
这一层的逻辑关系是：
- Skill 依赖 IO Format
- Workflow 节点传递依赖 IO Format
- Digital Worker 对外接任务也依赖 IO Format
- 提示词工程、模板、变量映射都属于这一层的资产

二、本阶段目标
本阶段要建立平台自有 IO 资产层，同时审计和合理利用：
- Flowise 的变量、结构化输出能力
- PromptFlow 的 DAG 输入输出 contract 和研发评估能力

本阶段最终要交付：
- io_format_definitions
- io_format_versions
- variable_mappings
- template_assets
- 与 Skill / Workflow 的绑定接口
- 前端“输入输出格式”页面

三、必须检查当前平台已有能力
你必须先扫描：
- promptflow/ 相关代码
- flowise/ 相关代码
- 当前 workflow product schema / public_api_schema / ui_schema
- 当前 Skill 层对象和表结构
- 当前前端页面框架

四、本阶段开发要求
1. 不能让 Flowise 或 PromptFlow 成为平台唯一真相
2. 平台必须有自己的 IO 资产对象
3. Flowise 只作为可视化配置承载补充
4. PromptFlow 只作为研发与评估辅助
5. 所有 IO schema 必须可被 Skill / Workflow / Digital Worker 共同引用
6. JSON schema / template / variable mapping 需要有版本和引用关系

五、本阶段建议拆成 4 个开发对话
子阶段3A：代码审计当前 promptflow / flowise / io schema 相关代码
子阶段3B：IO Format 数据模型与 migration
子阶段3C：Variable Mapping / Template Asset / Binding API
子阶段3D：前端输入输出格式页与 Skill / Workflow 绑定页

六、本轮对话任务
先完成子阶段3A：
- 审计当前仓库中 promptflow / flowise 相关代码是否还保留输入输出控制能力
- 明确哪些可复用，哪些只能参考
- 输出本阶段的数据模型与接口设计清单
阶段4提示词：流程编排主线
你现在接手的是 AI OS 第四阶段研发，主题是“流程编排主线”。

一、全局目标
平台的流程层不是为了复刻一个底层 BPMN 引擎，而是要在成熟引擎或现有 runtime 之上，形成：
- 技能编排
- AI/Agent 节点编排
- 输入输出传播
- 执行观察
- 流程产品化
- 数字员工绑定

二、本阶段目标
把当前 Phase 18 已经跑通的 durable workflow foundation，推进成：
- 多 Step 顺序链
- Step Output → Next Input 数据传递
- 正式 Capability Adapter Contract
- 流程设计器第一版
- 流程库第一版
- Execution 观察继续增强

三、必须检查当前平台已有内容
你必须先阅读：
- runtime/workflow_runtime_service.py
- runtime/workflows/capability_executor.py
- persistence/repositories/workflow_* 
- gateway/api/workflow_*.py
- 已有 workflow integration tests
- 当前前端 execution 页面和 router

四、本阶段开发要求
1. 必须保证 success / failure / retry / exhausted 基线不被破坏
2. 新增多 Step 顺序链必须和现有 task/outbox/relay/worker/runtime 主线对齐
3. Step Output → Next Input 的 JSON 传播格式必须明确
4. Capability Adapter 必须是正式 contract，不能堆大量兼容层
5. 流程设计器保存出来的 schema 必须和 runtime definition schema 对齐
6. 流程库、流程产品、执行观察要围绕平台自有 workflow schema 展开，不以 Dify/Flowise 为主 schema

五、本阶段建议拆成 5 个开发对话
子阶段4A：多 Step 顺序链 runtime
子阶段4B：Step Output → Next Input 数据传播
子阶段4C：Capability Adapter Contract 与真实能力适配接口
子阶段4D：流程设计器 / 流程库 API 与前端骨架
子阶段4E：Execution 观察增强与流程产品接口收口

六、本轮对话任务
先完成子阶段4A：
- 在不破坏现有 workflow retry foundation 的前提下，设计多 Step 顺序链正式主线
- 输出需要改哪些文件、哪些测试、哪些 JSON contract
- 不能走最小 demo 路线，必须考虑后续流程设计器和数字员工绑定
阶段5提示词：数字员工层
你现在接手的是 AI OS 第五阶段研发，主题是“数字员工层”。

一、全局目标
数字员工不是一个简单的 Agent App，而是：
- 绑定 Skill
- 绑定 Workflow
- 绑定模型和策略
- 能手动或自动执行任务
- 后续可配置触发、停止、完成评估
- 最终可进入市场作为商品对象

二、本阶段目标
本阶段先建立数字员工对象层雏形，而不是一次性做完整市场化系统。
要做的是：
- digital_workers
- digital_worker_versions
- digital_worker_bindings
- digital_worker_run_sessions
- 数字员工列表 / 基础配置 / 基础运行会话

Dify 可作为复杂 Agent / Workflow 兼容层，但数字员工对象模型和生命周期必须归平台自身。

三、必须检查当前已有内容
你必须先确认：
- Skill 资产层当前状态
- Workflow 主线当前状态
- 当前 agent runtime / tool / generation 基础
- Dify 集成边界和接口方式
- 当前前端菜单和页面骨架

四、本阶段开发要求
1. 数字员工必须作为正式平台对象，而不是 Dify App 的别名
2. 必须能绑定 Skill、Workflow、Model、Policy
3. 必须考虑未来：
   - Trigger
   - Stop
   - Completion / Evaluation
   - Marketplace
4. 当前阶段先不做完整市场与复杂计费
5. 当前阶段先做：
   - 列表
   - 配置
   - 手动运行
   - 基础运行会话

五、本阶段建议拆成 4 个开发对话
子阶段5A：Digital Worker 数据模型与 migration
子阶段5B：Binding Skill / Workflow / Model / Policy 的后端接口
子阶段5C：数字员工列表与配置页面
子阶段5D：基础运行会话与手动运行

六、本轮对话任务
先完成子阶段5A：
- 设计 digital_workers、versions、bindings、run_sessions
- 明确与 Skill / Workflow / Model / Policy 的引用关系
- 输出完整 migration、repository、API 设计清单
阶段6提示词：治理与市场预留层
你现在接手的是 AI OS 第六阶段研发，主题是“治理与市场预留层”。

一、全局目标
平台最终不只是“能运行”，而是要做到：
- 可触发
- 可停止
- 可判断完成
- 可治理
- 可发布到市场
- 可租户内或跨租户分发

本阶段不做完整交易系统，但要把市场和治理的对象层预留出来。

二、本阶段目标
本阶段要优先完成：
- trigger_definitions
- stop_conditions
- completion_criteria
- evaluation_rules
- human review / HITL 基础对象
- 市场对象模型预留（商品对象、可见性、版本引用）
- 治理页和管理员分析页的数据接口预留

三、必须检查当前平台已有内容
你必须先确认：
- 数字员工对象模型当前状态
- Skill / Workflow / IO Format 的资产状态
- 当前 OPA / ABAC / governance 基础
- 当前 analytics / 埋点设计状态（如有）
- 当前前端治理菜单与页面骨架

四、本阶段开发要求
1. Trigger / Stop / Completion 必须是正式对象模型，不是散落在 payload_json 里的临时字段
2. Evaluation 与 HITL 必须能和 Workflow / Digital Worker 执行状态关联
3. 市场层当前只做对象模型和接口预留，不做完整买卖/计费
4. 权限和可见性必须和租户模型对齐
5. 要为未来管理员分析页预留查询接口和聚合对象，但不抢在前面做复杂 BI 系统

五、本阶段建议拆成 4 个开发对话
子阶段6A：Trigger / Stop / Completion 模型
子阶段6B：Evaluation / HITL 模型
子阶段6C：Marketplace 对象模型预留
子阶段6D：治理页 / 管理员分析页接口预留

六、本轮对话任务
先完成子阶段6A：
- 设计 trigger_definitions、stop_conditions、completion_criteria
- 明确与 digital_workers、workflows、skills 的绑定方式
- 输出 migration、repository、API 设计方案
- 不要直接展开完整市场交易系统
四、建议你怎么实际使用这 6 个阶段提示词
用法
每个阶段开一个“阶段总控对话”

先贴对应阶段提示词，拿到：

当前阶段目标
子阶段拆分
本阶段设计边界
需要审计的当前代码范围
然后每个子阶段再开一个单独对话

例如阶段4有 5 个子阶段，你就可以开 5 个子对话：

4A：多 Step 顺序链
4B：数据传播
4C：Capability Adapter
4D：流程设计器 / 流程库
4E：Execution 观察增强

这样每一轮对话都能控制在：

一个模块族
一组接口
一组表
一组测试
一次回归

这是最稳的。

五、我建议的总控表（适合你自己拿着排研发）
阶段	子阶段	对话数	开发目标
阶段1	1A	1	审计录制 / skill / flowise / promptflow 相关代码与边界
阶段1	1B	1	recording_sessions / action_events / skill_drafts 模型与 API
阶段1	1C	1	对话蒸馏 → Skill Draft 最小闭环
阶段1	1D	1	录制工作台 / Skill Draft 页面骨架
阶段2	2A	1	Skill 数据模型与 migration
阶段2	2B	1	Skill CRUD / Query / API
阶段2	2C	1	Skill Test Run / Version / Publish
阶段2	2D	1	技能库 / 技能详情 / 测试发布页
阶段3	3A	1	审计 Flowise / PromptFlow 输入输出能力
阶段3	3B	1	IO Format 模型与 migration
阶段3	3C	1	Variable Mapping / Template Asset / Binding API
阶段3	3D	1	输入输出格式页与绑定页面
阶段4	4A	1	多 Step 顺序链 runtime
阶段4	4B	1	Step Output → Next Input
阶段4	4C	1	Capability Adapter Contract
阶段4	4D	1	流程设计器 / 流程库第一版
阶段4	4E	1	Execution 观察增强 / 流程产品接口
阶段5	5A	1	Digital Worker 模型与 migration
阶段5	5B	1	Skill / Workflow / Model / Policy 绑定
阶段5	5C	1	数字员工列表与配置页
阶段5	5D	1	基础运行会话与手动运行
阶段6	6A	1	Trigger / Stop / Completion 模型
阶段6	6B	1	Evaluation / HITL 模型
阶段6	6C	1	Marketplace 对象模型预留
阶段6	6D	1	治理页 / 分析页接口预留
总计

25 个开发对话

这是比较理性的拆法。