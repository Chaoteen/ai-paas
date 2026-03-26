# Gateway 模块设计文档

## 1. 文档目的

本文档用于定义 Gateway 模块在平台中的职责、边界、目录结构、核心 API 类型、设计原则和后续演进方向。

Gateway 是平台统一接入层，不是平台业务执行核心。

---

## 2. 模块定位

Gateway 是平台统一接入层，负责：

- 标准 API 暴露
- 路由组织
- 认证与授权接入
- ABAC / OPA 治理入口
- UI / bootstrap 接口
- Agent / Generation / Task / Workflow 的统一 API 门户
- 外部系统桥接与代理入口

Gateway 不负责真实业务执行，不负责 durable publish 的最终落队逻辑，也不负责模型实际推理执行。

---

## 3. 模块边界

### 3.1 Gateway 负责

Gateway 负责以下能力：

- 接收外部请求
- 进行参数校验与 schema 映射
- 提供统一 HTTP API 入口
- 统一响应结构
- 调用 runtime / queue / workflow 相关服务
- 注入租户、用户、上下文
- 承担 API 契约稳定性
- 作为安全与治理入口接入 auth / ABAC / OPA
- 暴露平台 UI/bootstrap 能力信息

### 3.2 Gateway 不负责

Gateway 不应承担以下职责：

- 直接承担业务长流程状态机
- 直接执行模型推理
- 直接替代 worker runtime
- 直接替代 outbox relay
- 直接承担 durable queue publish 的真相源职责
- 直接承载复杂编排逻辑
- 直接替代 workflow runtime

---

## 4. 当前代码目录结构

```text
gateway/
├─ api/
├─ app/
├─ core/
├─ ui_def/
├─ main.py
├─ prompt_execution_gateway.py
└─ ui_bootstrap.py
4.1 目录职责说明
gateway/api/

负责对外 API 定义，包括：

health
ui
agent runtime
generation
tasks
workflow definitions
workflow executions
gateway/core/

负责接入层公共能力，包括：

auth.py：认证
abac.py：鉴权
config.py：配置
opa_client.py：OPA 调用
gateway/app/

负责应用层组织与公共装配。

gateway/ui_def/

负责 UI 定义、菜单能力与产品面能力配置。

gateway/main.py

负责 FastAPI 应用入口、路由挂载、中间件接入与网关整体装配。

5. 当前已挂载的 API 结构

当前 Gateway 已挂载以下 API 类型：

Health API
UI API
Agent Runtime API
Generation API
Tasks API
Workflow Definitions API
Workflow Executions API

这说明 Gateway 已经成为平台正式主线的统一 API 门户。

6. 主要职责拆分
6.1 main.py

职责包括：

FastAPI 应用初始化
挂载各类 router
注册中间件
统一上下文装配
外部代理入口挂载
将平台正式主线暴露为标准 API
6.2 gateway/api/*

职责包括：

request / response schema 定义
HTTP API 路由定义
调用 runtime、queue、workflow 相关服务
将后端执行链路封装为可调用接口
6.3 gateway/core/*

职责包括：

认证能力承接
ABAC 权限控制
OPA 策略调用
配置装载
6.4 gateway/ui_def/*

职责包括：

菜单与界面能力定义
平台前端 bootstrap 数据的结构来源
后续产品级前端的能力面映射基础
7. Gateway 工程图
    flowchart TB
    GW[Gateway]
    GW --> API[gateway/api]
    GW --> CORE[gateway/core]
    GW --> APP[gateway/app]
    GW --> UIDEF[gateway/ui_def]
    GW --> MAIN[main.py]

    API --> A1[health]
    API --> A2[ui]
    API --> A3[agent runtime]
    API --> A4[generation]
    API --> A5[tasks]
    API --> A6[workflow definitions]
    API --> A7[workflow executions]

    CORE --> C1[auth]
    CORE --> C2[abac]
    CORE --> C3[opa_client]
    CORE --> C4[config]

8. Gateway 与平台主线的关系

Gateway 在平台主线中的位置是：

Gateway → Durable Task Submission → Task Store / Outbox → Outbox Relay → Redis Queue → Worker Runtime → Capability Execution

Gateway 是主线入口，但不是主线执行中心。

其关键职责是：

把平台能力暴露给外部
保持契约稳定
保持上下文一致
不侵入 runtime 内部执行职责
9. 设计原则
原则 1：Gateway 是统一门面，不是业务执行中心

业务执行必须继续落在 runtime / worker / workflow runtime，而不是迁移到 gateway 中。

原则 2：Gateway 承担 API 契约稳定性

后端主线可以持续演进，但 Gateway 对前端、SDK、第三方系统的 API 契约不应随意震荡。

原则 3：Gateway 承担安全与治理入口

ABAC、OPA、租户上下文、用户上下文应从接入层统一进入，而不是在 runtime 各处零散处理。

原则 4：Gateway 只做必要的 orchestration，不做深层编排

避免 Gateway 逐步演化成第二个 runtime 或第二个 workflow engine。

原则 5：Gateway 要服务平台统一主线

任何 API 的新增，都必须回答：

是否进入正式主线
是否只是实验层
是否只是历史兼容入口
是否需要被产品化保留
10. 当前已实现能力

当前 Gateway 已具备以下能力：

统一 FastAPI 应用入口
统一路由挂载
Health API
UI API
Agent Runtime API
Generation API
Tasks API
Workflow Definitions API
Workflow Executions API
Flowise 外部代理入口
Auth / ABAC / OPA 基础接入目录
平台 UI 定义目录基础
11. 当前存在的工程判断
11.1 Gateway 已进入平台正式主线

Gateway 不再是简单的 demo server，而是正式的接入层。

11.2 Gateway 当前仍偏“平台工程入口”，不是完整产品控制平面

虽然已具备主线 API，但产品级 UI / 控制平面仍需后续完善。

11.3 Gateway 必须持续防止职责膨胀

随着 workflow、connector、governance、marketplace 等能力增加，Gateway 很容易变成“什么都放一点”的膨胀层，需要持续做职责边界治理。

12. 后续演进重点
12.1 安全上下文进一步统一

补齐更完整的：

user context
tenant context
request tracing context
policy evaluation context
12.2 UI bootstrap 与产品能力面继续固化

让 Gateway 成为正式产品控制台的稳定数据入口。

12.3 workflow / runtime 契约进一步固化

避免 Gateway 对 workflow、runtime 做过深耦合。

12.4 历史层和正式层进一步隔离

对实验性入口、兼容性入口、正式入口做清晰区分。

12.5 API 生命周期治理

后续应建立：

API 版本策略
废弃策略
向后兼容策略
文档同步策略
13. 模块总结

Gateway 模块不是平台的“业务核心”，但它是平台的“产品接口核心”。

平台对外是否清晰、稳定、可接入、可治理，首先取决于 Gateway 是否：

边界清晰
契约稳定
安全入口统一
不过度膨胀
严格服务于平台主线

因此，Gateway 必须保持“接入层门面”的角色纯度，而不是变成混杂执行逻辑的大型控制器。