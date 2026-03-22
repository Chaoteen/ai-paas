# AI-PaaS 平台服务分层与启动规范统一说明

**适用范围**：当前仓库开发阶段 + 后续服务收敛设计  
**目标**：让后续程序员无需重复排查“该启动哪个服务、测试对应哪套入口”的问题

---

## 1. 文档目的

本平台当前处于从“单体入口逐步演进为多服务平台”的阶段。代码仓库中已经同时存在：

- 控制平面入口
- 运行平面入口
- 前端控制台
- ABAC / OPA 策略服务
- 独立工具前端（如 Flowise）
- Runtime worker / relay / durable pipeline

由于历史迭代和不同 phase 的演进，当前仓库中存在多个启动入口、多个脚本、多个端口约定。  
如果没有统一说明，后续程序员很容易出现以下问题：

- 启动了 `gateway.main:app` 却去跑 `main.py` 对应的 live tests
- 启动了错误的 OPA 容器，导致 policy 未加载
- 把 Flowise 误当成平台正式前端
- 不清楚 8000 / 8181 / 5173 分别对应什么
- 不知道哪些测试依赖服务、哪些测试不依赖服务

本说明目标：

1. 讲清楚平台当前有哪些服务
2. 讲清楚每类服务负责什么职责
3. 讲清楚开发阶段如何启动
4. 讲清楚不同测试对应哪套服务
5. 讲清楚未来平台服务如何收敛成“内部多服务、对外一键启动”的正式方案

---

## 2. 当前平台服务分层

当前平台建议按下面 5 层理解。

### 2.1 Control Plane（控制平面）
**当前主要入口：**
- `gateway.main:app`

**职责：**
- API 统一接入
- JWT 鉴权
- ABAC / OPA 权限判定
- UI bootstrap
- 菜单与控制台数据下发
- 面向前端控制台的接口层
- 后续租户管理、管理员能力、平台配置、应用商店入口、监控/运维页面聚合入口

**当前典型接口：**
- `/api/health`
- `/api/ui/bootstrap`
- `/api/v1/...`

**定位：**
这是平台对“人类用户”和“平台管理界面”的主要门面层。

---

### 2.2 Runtime / Execution Plane（运行平面 / 执行平面）
**当前主要入口：**
- `main:app`
- Phase 17 runtime 相关 worker / relay / durable task chain

**职责：**
- Agent 注册
- Task 提交
- Runtime 任务链路执行
- Data events / control events
- durable task store
- outbox relay
- agent worker
- generation worker

**当前典型接口：**
- `/health`
- `/runtime/agents/register`
- `/runtime/tasks/submit`
- `/runtime/data-events`

**定位：**
这是平台面向 Agent 执行和任务运行的主链路。

---

### 2.3 Web UI（平台正式前端）
**当前主要入口：**
- `webapp/`
- `npm run dev`

**职责：**
- 平台控制台前端
- 面向管理员/开发者的 UI
- 菜单、权限、资源管理、监控视图、配置视图、应用入口

**当前后端依赖：**
- `gateway.main:app`

**定位：**
这是未来平台的正式前端壳。

---

### 2.4 Tooling / Embedded Apps（工具与嵌入式子应用）
**当前代表：**
- Flowise（容器中运行的前端/设计器）
- 后续可扩展 PromptFlow、LangGraph Studio、监控面板等

**职责：**
- 作为特定能力的设计器 / 工具前端
- 作为平台内被纳管的子系统
- 提供流程设计、Prompt 编排、Agent 设计等能力

**定位：**
不是平台正式外壳，不应与 `webapp` 混淆。  
应作为平台工具子模块被接入。

---

### 2.5 Infra / Policy / State Services（基础设施与策略服务）
**当前代表：**
- Postgres
- Redis
- OPA
- 后续 tracing / metrics / object storage 等

**职责：**
- 数据持久化
- 队列 / 缓存
- 策略判定
- 平台底层依赖

**定位：**
这些不是业务入口，但没有它们平台无法稳定运行。

---

## 3. 当前“两个主线”到底是什么

这里的“两条主线”不是两个产品，而是两个不同职责的服务入口。

### 主线 A：Gateway / Control Plane 主线
**启动方式：**
```bash
cd ~/work/ai-paas
uvicorn gateway.main:app --host 0.0.0.0 --port 8000 --reload

适用场景：

跑 gateway tests
跑 UI bootstrap / ABAC 测试
跑平台控制台相关接口
对接 webapp
主线 B：Runtime / Execution 主线

启动方式：

cd ~/work/ai-paas
uvicorn main:app --host 0.0.0.0 --port 8000

适用场景：

跑 test_runtime_phase10_live.py
跑 test_runtime_phase11_*_live.py
跑 test_runtime_phase13_*_live.py
验证 /health 与 /runtime/... 旧 live contract
关键结论

后续程序员必须知道：

gateway.main:app 和 main:app 不是一回事
它们当前服务的测试对象也不同
如果服务起错，会表现为：
端口正常
但 health 路径 404
或 live test 一直等不到 ready
4. 当前端口约定
4.1 8000

当前用于：

gateway.main:app 或
main:app

注意：
这两个入口当前都可能占用 8000，不能同时启动在同一个端口。

4.2 5173

当前用于：

webapp Vite 开发前端
4.3 8181

当前用于：

正式 OPA 容器
正式 ABAC 策略入口
4.4 8182

当前用于：

临时隔离验证用 OPA 容器（opa_ui_test）

说明：
8182 只是本轮排障中的隔离验证口。
未来应收口回 8181，不应长期依赖 8182 作为正式配置。

5. 当前服务启动规范
5.1 Gateway / Control Plane 启动

用途：

UI bootstrap
ABAC
webapp 对接
平台控制台 API

命令：

cd ~/work/ai-paas
uvicorn gateway.main:app --host 0.0.0.0 --port 8000 --reload

前置条件：

OPA 需在线
Postgres / Redis 视具体接口需求决定是否需要在线

探活：

curl -i http://127.0.0.1:8000/api/ui/bootstrap

预期：

未带 Bearer token 时返回 401 Missing Bearer token
说明服务在线、路由存在、鉴权正常
5.2 Runtime / Execution Plane 启动

用途：

runtime live tests
phase10 / 11 / 13 旧 live contract
/health、/runtime/... 接口验证

命令：

cd ~/work/ai-paas
uvicorn main:app --host 0.0.0.0 --port 8000

探活：

curl -i http://127.0.0.1:8000/health

预期：

HTTP 200
返回 runtime 状态信息
5.3 Web UI 启动

用途：

平台正式前端开发态

命令：

cd ~/work/ai-paas/webapp
npm install
npm run dev

访问地址：

http://localhost:5173

后端依赖：

gateway.main:app
5.4 OPA 启动

正式目标：
OPA 应始终通过仓库配置启动，并加载：

ops/opa/policy -> /policy

当前正式口：

http://127.0.0.1:8181

运行检查：

curl -s http://127.0.0.1:8181/v1/policies
curl -s http://127.0.0.1:8181/v1/data/ui/allow

预期：

/v1/policies 非空
/v1/data/ui/allow 不应返回 {}
风险判断

如果出现：

/v1/policies 空
/v1/data/ui/allow 返回 {}

说明：

OPA 虽然在线
但 policy 没有加载成功
会导致 gateway bootstrap 菜单全空或 ABAC 逻辑失效
6. 测试与服务的映射关系
6.1 不依赖外部服务的测试

通常可直接运行：

tests/governance/...
大部分 tests/runtime/...
大部分 tests/gateway/...

但仍需注意：少数 gateway/runtime 集成测试可能需要数据库或 mock 以外资源。

6.2 依赖 Gateway / Control Plane 的测试

需要先启动：

gateway.main:app
OPA（至少 bootstrap/ABAC 相关测试需要）

典型：

tests/integration/test_gateway_ui_bootstrap_abac.py
/api/... 体系相关测试
6.3 依赖 Runtime 主线的 live tests

需要先启动：

main:app

典型：

tests/integration/test_runtime_phase10_live.py
tests/integration/test_runtime_phase11_*_live.py
tests/integration/test_runtime_phase13_*_live.py

这些测试不能拿 gateway.main:app 去跑。

6.4 依赖 OPA 的测试

需要先确认：

8181 上 OPA 可达
policy 已加载成功

典型：

tests/integration/test_opa_ui_policy.py
tests/integration/test_gateway_ui_bootstrap_abac.py
6.5 依赖 durable runtime 的测试

需要关注：

Postgres
Redis
outbox relay
worker
task store

典型：

tests/integration/test_phase17_durable_mainline.py

说明：
这组测试目前存在“单跑通过、全量 integration 套跑时可能受 async 资源生命周期影响”的现象，需要后续单独治理测试隔离。

7. 本轮已确认的关键问题与结论
7.1 ui.rego 是什么

ops/opa/policy/ui.rego 是 OPA Rego 策略文件。
它不是普通静态配置，而是：

菜单授权规则
admin/user 菜单可见性规则
ABAC 决策规则代码
7.2 为什么之前 ui.rego 有内容却不生效

根因有两个：

OPA 容器曾经未正确加载 policy
policy 输入契约与调用方字段不完全对齐
（subject/type vs user/kind）

当前已修复：

policy 已加载
规则已兼容标准契约与旧契约
对应测试已通过
7.3 8182 的意义

8182 是本轮用于隔离验证的临时 OPA 端口。
它帮助确认：

policy 文件是正确的
gateway 代码链路是正确的
真正的问题在 8181 的容器运行态 / 编排

最终目标不是保留 8182，而是回归 8181。

7.4 当前正式状态

当前 ABAC 正式链路已回归：

Gateway → 8000
OPA → 8181
8. 平台未来服务收敛方案（建议）
8.1 未来不应再对外暴露“两条主线”概念

“两条主线”只是当前代码演进阶段的技术现象。
未来产品形态对用户应是：

一个平台
一套启动入口
一套控制台
一套运行系统

用户不应该知道：

哪个是 gateway
哪个是 runtime
哪个是 OPA
哪个是 Flowise
8.2 未来应收敛为“多服务架构 + 单一启动入口”

推荐收敛成以下服务包：

A. platform-control

控制平面服务：

gateway
auth
ABAC
UI bootstrap
admin APIs
tenant/config/catalog
B. platform-runtime

运行平面服务：

runtime API
durable task pipeline
outbox relay
agent worker
generation worker
runtime event services
C. platform-ui

平台正式前端：

webapp
console
运维视图
监控视图
管理视图
D. platform-tools

子工具系统：

Flowise
PromptFlow
LangGraph Studio
后续 Prompt / Workflow / Skill 设计器
E. platform-infra

基础设施：

Postgres
Redis
OPA
tracing / metrics backends
object storage
8.3 对研发的启动方式

研发应支持模块化启动：

start_infra.sh
start_control.sh
start_runtime.sh
start_ui.sh
start_tools.sh

好处：

调试单一服务
缩短本地启动时间
隔离排障
8.4 对用户 / 运维的启动方式

对用户和部署环境，不应要求理解内部模块。
应统一为一键入口，例如：

run_platform_dev.sh
platform up
docker compose up -d
Helm / K8s 一键拉起

也就是说：

内部拆服务，外部统一编排。

8.5 前端收敛建议
正式前端
以 webapp 为正式平台前端
Flowise 定位
作为平台子工具 / 嵌入式工具
由控制台纳管
不再作为平台整体壳的替代品
后续监控 / 运维 / UI 归属

建议：

监控
运维
审计
配置
应用商店

统一收敛到 webapp + gateway 这条控制平面 UI 主线中。

8.6 Runtime 入口收敛建议

当前 main.py 和 gateway.main:app 并存。
未来建议逐步演化为：

gateway 负责外部入口、用户访问、控制平面
runtime 作为内部服务或独立 API 服务
对外由 gateway 统一编排和转发
测试逐步按服务边界重构，而不是共享同一 8000 端口入口

最终目标不是把所有东西塞回一个 app，而是：

控制平面统一对外，运行平面独立对内。

9. 当前推荐的开发态启动组合
9.1 做控制台 / ABAC / UI bootstrap 开发

启动：

cd ~/work/ai-paas
uvicorn gateway.main:app --host 0.0.0.0 --port 8000 --reload

同时保证：

OPA 8181 可用

前端如需联调：

cd ~/work/ai-paas/webapp
npm run dev
9.2 做 runtime live tests 开发

启动：

cd ~/work/ai-paas
uvicorn main:app --host 0.0.0.0 --port 8000

说明：

这时不要同时跑 gateway 8000
否则 live tests 会打错入口
9.3 做 durable runtime / outbox / worker 开发

应按 Phase 17 的 runtime 组件组合启动，或使用对应脚本 / 服务方式启动：

Postgres
Redis
relay
worker
runtime durable pipeline

说明：

这类测试不要和 gateway-only 测试混用启动方式
10. 对后续程序员的操作建议
10.1 启动前先判断测试对象

先问自己：

我跑的是 /api/... 还是 /runtime/...？
我测的是控制平面还是运行平面？
我需要 OPA 吗？
我需要 Redis / Postgres / worker 吗？
10.2 不要看到 8000 有服务就以为服务起对了

要看：

路由是不是对的
health 路径是不是对的
OPA 是否在线
policy 是否真的加载了
10.3 OPA 的健康判断不能只看容器是否 Up

必须同时看：

curl -s http://127.0.0.1:8181/v1/policies
curl -s http://127.0.0.1:8181/v1/data/ui/allow
10.4 不要把 Flowise 当成平台正式前端

它只是工具模块。

11. 当前建议保留的关键测试守门线
ABAC / OPA
pytest tests/integration/test_opa_ui_policy.py -q
pytest tests/integration/test_gateway_ui_bootstrap_abac.py -q
Durable mainline
pytest tests/integration/test_phase17_durable_mainline.py -q
Outbox / dead_letter
pytest tests/runtime/test_outbox_repository.py -q
pytest tests/runtime/test_outbox_relay_dlq.py -q
pytest tests/integration/test_outbox_dead_letter_postgres.py -q
数据模型一致性
pytest tests/integration/test_database.py -q
12. 总结

当前平台已经自然演进出：

控制平面
运行平面
UI
工具前端
策略服务
基础设施

这说明平台架构方向是对的。
当前的主要问题不是“是不是该分服务”，而是：

服务已分化，但启动规范、测试映射关系、对外统一编排方式还没有文档化和产品化。

后续收敛原则应为：

架构上分服务
研发上可分模块启动
用户上统一一键启动
正式前端用 webapp
Flowise 作为子工具
Gateway 负责控制平面
Runtime 负责运行平面
OPA / Redis / Postgres 作为基础设施独立服务
最终由统一 launcher / compose / k8s 编排收口