# WebApp 模块设计文档

## 1. 文档目的

本文档用于定义平台 WebApp 模块的当前定位、代码结构、职责边界、与平台主线的关系、当前能力面，以及后续产品化演进方向。

当前 `webapp` 是平台前端入口，但从工程阶段判断，它更接近主线验证控制台，而不是终态产品前端。

---

## 2. 模块定位

当前 WebApp 的定位是：

- 平台前端入口
- Phase 17 主线验证控制台
- Runtime Mainline Console
- durable submit + task query + minimal ops UI

它的主要作用是：

- 验证平台正式主线是否可用
- 提供最小化的交互入口
- 作为开发和测试阶段的前端操作面
- 为后续平台级产品前端提供基础工程壳

当前 WebApp 不是完整的商业化产品界面。

---

## 3. 模块边界

### 3.1 WebApp 负责

当前 WebApp 负责：

- 提供最小前端交互入口
- 调用 Gateway 暴露的正式 API
- 承担主线验证、任务提交、任务查询、健康检查等能力
- 为后续平台控制台、应用台、治理台提供工程基础

### 3.2 WebApp 不负责

当前 WebApp 不应被视为已经完成以下职责：

- 完整的平台产品前端
- 完整的 workflow studio
- 完整的租户治理控制台
- 完整的审计、配额、计费控制平面
- 完整的 skill / connector marketplace
- 完整的用户交付产品面

换言之，当前 WebApp 是“控制台雏形”，不是“平台终态产品面”。

---

## 4. 当前代码结构

```text id="ehgse3"
webapp/
├─ package.json
└─ src/
   ├─ api/
   ├─ app/
   ├─ components/
   ├─ pages/
   ├─ plugins/
   ├─ styles/
   ├─ App.tsx
   └─ main.tsx
5. 工程结构说明
5.1 package.json

表明当前 WebApp 是基于以下技术栈构建：

Vite
React
TypeScript
axios
react-router-dom

这说明前端工程已经是标准现代前端工程，而不是简单静态页面。

5.2 src/api/

职责：

封装前端对 Gateway API 的访问
提供后续 API 调用抽象基础
5.3 src/app/

职责：

前端应用层组织
应用级初始化与结构组织
5.4 src/components/

职责：

页面与功能组件复用
为后续产品级前端演进提供基础组件层
5.5 src/pages/

职责：

页面级结构承载
后续平台前端能力域的页面拆分基础
5.6 src/plugins/

职责：

插件化前端扩展支持
未来可用于前端侧能力扩展或接入
5.7 src/styles/

职责：

平台控制台风格基础
后续统一设计系统的落点之一
5.8 App.tsx

当前 App.tsx 的角色更接近：

主线验证入口
统一控制台页
API 手动测试与最小操作面
6. 当前能力面

从当前前端控制台能力看，WebApp 已支持以下能力：

6.1 共享请求输入能力

已具备以下基础输入项：

Tenant ID
Model
Prompt
System Prompt
Temperature
Max Tokens
Image Size
Video Duration

这些字段说明当前前端主要围绕运行时和生成能力做统一表单化验证。

6.2 当前功能面

当前控制台已具备以下功能入口：

Dashboard
Agent Run / Submit
Image Generation
Video Generation
Task Query
Health

这说明 WebApp 当前主要服务于：

主线验证
runtime/generation submit
durable task 查询
最小化运维检查
7. WebApp 模块工程图
flowchart TB
    WebApp[WebApp / Console]
    WebApp --> API[api]
    WebApp --> APP[app]
    WebApp --> COMP[components]
    WebApp --> PAGES[pages]
    WebApp --> PLUGINS[plugins]
    WebApp --> STYLES[styles]
    WebApp --> AppTsx[App.tsx]

    AppTsx --> Dashboard[Dashboard]
    AppTsx --> Agent[Agent Run / Submit]
    AppTsx --> Image[Image Generation]
    AppTsx --> Video[Video Generation]
    AppTsx --> Task[Task Query]
    AppTsx --> Health[Health]

8. 与平台主线的关系

WebApp 当前主要服务于平台主线的前端验证与可视化调用：

WebApp → Gateway → Durable Task / Runtime Mainline → Task Query / Health / Minimal Ops

因此，当前 WebApp 的核心任务不是展示复杂产品包装，而是保证：

正式 API 可调用
正式 durable submit 可操作
正式任务查询可验证
主线行为可被前端观察

这对于当前阶段是合理的，但不等于最终产品形态。

9. 与其他模块的关系
9.1 与 Gateway 的关系

WebApp 的正式后端入口应统一走 Gateway。
前端不应绕过 Gateway 直接访问 runtime、queue 或内部基础设施。

9.2 与 Runtime 的关系

WebApp 并不直接承担执行逻辑，它只是通过 Gateway 间接触发 Runtime 主线能力。

9.3 与 Workflow 的关系

当前前端尚未形成完整 workflow studio，但未来 workflow product layer 必须落在前端产品面中，而不是仅停留在 API 层。

9.4 与治理层的关系

未来的租户治理、配额、审计、计费、策略配置，都需要最终在 WebApp 中形成正式控制面。

10. 设计原则
原则 1：当前 WebApp 不是终态产品面

不能把当前 console 误认为已经是完整平台前端，否则会高估产品完成度、低估后续产品化工作量。

原则 2：当前 WebApp 首要任务是服务主线验证

在当前阶段，前端最重要的是覆盖正式主线，而不是优先追求复杂 UI 包装。

原则 3：后续必须从“验证控制台”升级为“平台控制台”

WebApp 后续必须逐步承接：

应用台
workflow 设计台
运行监控台
租户治理台
skill / connector 管理台
审计与计费台
原则 4：前端产品面必须围绕统一主线设计

不能分别围绕：

flowise
promptflow
langgraph
临时验证页

去形成多个并行产品入口。

原则 5：前端叙事必须服务平台一级产品定位

WebApp 的信息架构和导航体系，最终要回答的是：

这个平台是什么
用户如何创建能力
用户如何运行能力
用户如何观察能力
用户如何治理能力

而不是把平台底层模块直接暴露给用户。

11. 当前已实现能力

当前 WebApp 已实现以下基础能力：

Vite + React + TypeScript 工程
基础 API 调用能力
Dashboard
Agent Run / Submit
Image Generation
Video Generation
Task Query
Health
统一输入表单基础结构
最小化主线验证 UI
12. 当前工程判断
12.1 当前 WebApp 是“平台前端雏形”，不是“终态前端产品”

这意味着它的工程价值主要体现在：

主线验证
API 联调
最小操作入口
前端工程壳
12.2 当前前端尚未承接完整产品控制面

还缺少至少以下产品域：

Workflow Studio
Tenant Governance
Audit / Billing / Quota
Skill / Connector Marketplace
Platform Operations Console
User-facing Application Workspace
12.3 当前最大的风险是前端被历史路径碎片化

如果后续继续同时围绕：

Flowise
PromptFlow
LangGraph
临时测试页
主线控制台

各自发展前端入口，平台很容易在前端层面先变成大杂烩。

13. 后续演进重点
13.1 从验证控制台升级为平台控制台

形成真正的产品信息架构与导航体系。

13.2 建立前端产品域分层

建议未来按以下域拆分：

Applications
Workflows
Executions
Skills / Connectors
Governance
Billing / Quotas / Audit
Admin / Ops
13.3 Workflow Studio 纳入正式产品面

workflow 不能只停留在后端 API，必须有正式的设计、版本、执行、治理前端。

13.4 建立租户与治理控制平面

后续前端必须承接：

tenant settings
policy settings
quota controls
audit views
admin operations
13.5 统一设计系统与组件体系

随着前端产品面扩张，必须避免继续依赖“单页拼装式”控制台增长方式。

13.6 明确前端对历史实验层的态度

需要明确哪些集成层：

继续保留
作为桥接层
作为参考对象
不进入正式产品导航
14. 模块总结

WebApp 模块当前的正确理解方式是：

它已经是平台前端入口，但仍处于控制台与验证面阶段。

它当前最重要的贡献不是“产品已经完成”，而是：

为正式主线提供可操作的前端入口
为 API 和 runtime 主线提供验证面
为未来产品控制台提供前端工程基础

因此，WebApp 后续的核心目标不是继续叠加零散页面，而是逐步演进成：

面向平台用户的统一控制台
面向业务交付的操作平台
面向治理与运维的控制平面
面向 AI OS 产品叙事的正式前端产品面

只有这样，前端才不会沦为临时控制页集合，而会真正成为平台产品的一部分。