AI-PaaS Runtime 主线交接文档
Phase 17 第一阶段完成说明 / 下一阶段开发指引

项目名称：AI-PaaS
仓库地址：https://github.com/Chaoteen/ai-paas

当前分支：wip/integration-split-commits
当前基线提交：123931c

1. 文档目的

本文档用于给下一位接手研发的 AI 程序员 / 工程师快速说明三件事：

我接手时的平台状态与已有交接结论是什么
本轮 Phase 17 第一阶段实际完成了哪些开发与验证
下一阶段应该优先做什么，不应该做什么

这份文档不是历史清理总结，也不是旧架构复盘，而是面向正式主线继续开发的工程交接说明。

2. 我接手时的上下文与前置交接结论

在进入本轮开发之前，平台已经经过两类前置交接：

2.1 Phase 16 研发交接结论

前序研发已经明确，平台当前正式主线应收敛为：

Gateway API
→ Task Submission Service
→ Task Store / Outbox
→ Redis Queue
→ Runtime Workers
→ Runtime Services
→ Model / Skill / Generation

这一结论意味着：

正式主线已经从早期 legacy bus / manager 路线中抽离
durable task persistence 与 outbox 已经进入正式主线
Phase 17 的第一优先级不是继续堆 connector，而是把 durable 主路径真正跑通并默认化
2.2 系统清理交接结论

系统清理后的正式结论包括：

正式前端只保留 webapp/
Flowise 不是正式前端主线
archive/legacy/ 只能参考，不能恢复旧实现
docs/ 重新作为正式主线文档区使用
tests/governance/ 作为主线治理保护网，必须持续通过

这意味着后续开发必须遵循：

只在正式主线目录继续开发
不再恢复旧执行链路
不再让双前端并行成为正式口径
所有新交接文档写入 docs/
3. 本轮开发目标

本轮进入 Phase 17 时，核心判断是：

平台已经有 durable task + outbox 基座，但还没有被真正收口为“正式默认主路径 + 可交付运行链”。

因此，本轮开发目标被定义为：

3.1 核心目标

把 Phase 16 的 durable task / outbox 基座，推进成一个：

可真实启动
可真实 submit/query
可通过 relay 发布
可由 worker 消费
可自动化验证
可文档化交接

的正式主线阶段节点。

3.2 这一轮不做的事

本轮明确不做：

大规模 legacy 删除
marketplace / registry UI 扩展
大量 connector 接入
workflow engine 开发
多租户计费与 billing hook

这些内容不是不重要，而是优先级低于“先把 durable 主链收口”。

4. 本轮实际完成的开发内容

本轮完成内容可分成五块。

4.1 Durable runtime 主链继续收口

本轮继续推进并稳定了以下正式链路：

POST /api/v1/agent/submit
→ TaskSubmissionService
→ runtime_tasks + runtime_outbox_events
→ OutboxRelay
→ Redis Streams
→ Runtime Worker
→ GET /api/v1/tasks/{task_id}

这意味着平台已经从“有 durable 基座”进入到“durable 主链已打通”的阶段。

本轮重点修复 / 收口点
修正 submit/task query 主路径
修复路由拼接问题（曾出现 /api/v1/api/v1/... 重复）
统一 task query 返回结构
明确 API、Relay、Worker 三进程协作模式
将一键启动从手工命令提升为正式脚本
4.2 新增 runtime stack 启动与运维脚本

本轮新增并落地了三类脚本：

1）启动整套 Phase 17 主线

scripts/run_phase17_runtime_stack.sh

作用：

启动 API
启动 Outbox Relay
启动 Agent Worker
启动 Generation Worker
生成 pid/log 目录
持续输出日志
2）查看运行状态

scripts/status_phase17_runtime_stack.sh

作用：

检查 API/Relay/Worker 进程是否仍在运行
打印最近日志
便于快速诊断主线状态
3）停止整套主线

scripts/stop_phase17_runtime_stack.sh

作用：

根据 .run/phase17/pids/ 中记录的 pid 停止整套进程

这意味着下一位研发不再需要靠多个终端手工起服务，已经有了最小可用的 runtime 运维脚手架。

4.3 文档补齐

本轮新增正式主线启动文档：

docs/runtime_startup_guide.md

文档覆盖内容包括：

所需基础设施
环境变量
migration 执行
API / relay / worker 启动方式
submit/query 示例
一键启动脚本
status/stop 脚本
测试与验证命令

这份文档现在已经成为下一位研发理解 Phase 17 主线运行方式的最直接入口。

4.4 测试补齐与修复

本轮做了大量“让主线可持续回归”的工作，重点不是单纯让代码能跑，而是让它能被测试稳定约束。

新增 / 修复的测试范围
tests/integration/test_phase17_durable_mainline.py
submit → outbox → relay → worker → succeeded 端到端验证
tests/runtime/test_outbox_relay_dlq.py
relay 失败重试 / dead-letter 第一版逻辑验证
修复若干旧测试与当前主线契约不一致的问题，包括：
test_tasks_api.py
test_tasks_api_queue_publish.py
test_task_store_backends.py
test_outbox_repository.py
test_task_submission_service.py
test_outbox_relay.py
当前测试结果

本轮稳定验证通过的关键测试包括：

pytest tests/governance -q
pytest tests/runtime tests/gateway -q
pytest tests/integration/test_phase17_durable_mainline.py -q

其中：

tests/governance -q：通过
tests/runtime tests/gateway -q：125 passed
integration durable mainline：通过

这说明当前远端基线已经具备较强的主线回归保护。

4.5 Outbox relay retry / backoff / dead-letter 第一版

本轮没有只停留在“relay 能发”，还往前推进了一步：

已完成
relay 失败后回写 failed 状态
backoff/retry 的基础结构
dead-letter 第一版代码逻辑
对旧测试替身和 fake repo/fake result 的兼容修复
当前阶段判断

这一部分目前已经具备：

代码能力
单元测试能力
与主线结构兼容的实现

但是还没有完成：

真实数据库 schema 上的 dead_letter 状态扩容
基于真实 Postgres 的 dead_letter integration 验证

也就是说：

DLQ 第一版已经进入代码主线，但还没有完成真实 DB 层的正式化。

5. 本轮实际验证过的运行事实

这一轮不是只看单测通过，而是做了真实运行验证。

已经实际验证通过的运行链包括：

启动 API
启动 relay
启动 worker
POST /api/v1/agent/submit 返回 queued
outbox 事件进入 runtime_outbox_events
relay 发布到 Redis Streams
worker 消费消息
task 状态由 queued 推进到 succeeded
GET /api/v1/tasks/{task_id} 能返回最终结果

也验证了：

一键启动脚本可用
运行日志目录可用
status/stop 脚本可用
6. 本轮提交到 GitHub 的结果

本轮最终已推送到远端分支：

wip/integration-split-commits

关键收口提交包括：

123931c
feat(runtime): harden phase17 durable runtime mainline

这说明本轮不是本地实验，而是已经形成远端正式阶段节点。

7. 当前主线状态结论

截至当前阶段，可以把平台状态总结为：

已完成
Phase 17 durable runtime mainline 已打通
API / relay / worker 运行链实测成功
runtime startup guide 已落库
run/status/stop 脚本已落库
integration test 已落库
runtime/gateway/governance 测试稳定通过
outbox relay retry/backoff/DLQ 第一版已进入代码主线
当前仍未完成
dead_letter 的真实 DB migration
基于真实 Postgres 的 dead_letter integration 验证
webapp 真正的联调验证与任务控制台增强
relay / worker 更生产化的 supervisor/systemd/docker 编排
更完善的 observability / metrics / traces 展示
8. 下一位研发应优先做什么

下面是明确优先级，不建议打乱顺序。

P0：完成 dead_letter 的真实数据库正式化

这是最优先的下一步。

原因：

代码层已经有 DLQ 第一版
单元测试已经有
当前只差真实 DB schema 与真实 integration 收口
这是把 Phase 17 从“能跑”推进到“更生产化”的最短路径

建议工作项：

新增 migrations_runtime/005_outbox_dead_letter.sql
更新 runtime_outbox_events 的状态约束
允许 dead_letter 成为正式状态
真实 Postgres 下验证 relay 达到最大重试后能写入 dead_letter
新增对应 integration test
P1：补强 relay / worker 生产化行为

下一阶段应继续强化：

更明确的 retry policy
最大重试次数配置化
backoff 策略配置化
worker 运行日志改善
relay / worker 健康状态探针
更清晰的错误分类
P2：开始 webapp 的真实联调

当前 webapp/ 已是正式前端目录，但还没有真正完成产品层联调。

建议下一位研发围绕已经稳定的后端主链，继续做：

task submit 页面
task query 页面
task status 自动轮询
runtime console 基础页
health / queue / worker 状态页

注意：

这一步应该建立在后端主线已稳定的前提上，而不是重新分散到 Flowise 或历史 UI 口径。

P3：再进入 connector foundation

只有在 P0/P1 收口后，才建议进入：

Webhook connector
Feishu connector
Slack / Email connector

顺序仍然建议：

Webhook → Feishu → Slack/Email

原因：

connector 开发必须建立在 durable task / outbox / retry / dead-letter 主线更稳定之后，否则后面返工概率很高。

9. 下一位研发不应该做什么

为了避免主线再次发散，以下事项应明确禁止：

9.1 不要恢复 legacy 路线

不要从：

archive/legacy/
旧 gateway 兼容路径
旧 bus / manager / router 路线

恢复代码回主线。

9.2 不要同时扩三条线

不要在下一阶段同时做：

dead_letter migration
webapp 大改版
connector 批量接入

这会导致主线再次发散。

9.3 不要重新引入双前端口径

正式前端仍然只能是：

webapp/

不要重新让 Flowise 成为正式前端。

9.4 不要跳过治理测试

每轮修改后，至少应继续验证：

pytest tests/governance -q
pytest tests/runtime tests/gateway -q
10. 当前建议的正式验证命令

下一位研发接手后，建议先跑下面这些命令确认基线正常：

pytest tests/governance -q
pytest tests/runtime tests/gateway -q
pytest tests/integration/test_phase17_durable_mainline.py -q

本地主线启动可直接使用：

bash scripts/run_phase17_runtime_stack.sh

查看状态：

bash scripts/status_phase17_runtime_stack.sh

停止主线：

bash scripts/stop_phase17_runtime_stack.sh
11. 一句话交接结论

这轮 Phase 17 第一阶段已经完成的本质不是“又加了几个脚本”，而是：

把 Phase 16 的 durable task / outbox 基座，推进成了一个真实可启动、可提交、可查询、可测试、可交接的正式 runtime 主链阶段节点。

下一位研发最应该做的，不是再扩功能面，而是：

把 dead_letter 从代码级能力正式推进到真实数据库和真实运行链。