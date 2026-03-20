AI-PaaS Runtime 主线交接文档

项目名称：AI-PaaS
仓库地址：https://github.com/Chaoteen/ai-paas
当前主分支：wip/integration-split-commits

1. 文档目的

本文档不是历史清理总结，也不是旧架构回顾，而是给下一位接手开发的研发 / AI 程序员使用的主线交接文档。

目标只有三个：

让接手者快速理解平台当前正式主线是什么

明确哪些目录和模块可以继续开发，哪些只能参考不能继续堆代码

给出下一阶段的开发优先级、启动方法、验证方法和注意事项

2. 项目当前定位

本项目目标是构建一个 AI-PaaS（AI Platform-as-a-Service）平台，也可以理解为：

AI OS for AI Applications

平台的核心目标有四层：

2.1 面向 AI 开发者的统一应用底座

平台需要为 AI 程序员提供统一能力，让他们能够基于平台快速构建应用，而不是每做一个 AI 应用就从零搭建：

LLM 调用

Tool 调用

Skill 调用

Agent 运行

Generation 能力

Workflow 编排

Task 提交与查询

多模型路由

2.2 兼容多模型、多 Provider

平台底层必须支持：

OpenAI

Qwen

DeepSeek

Kimi

Minimax

Doubao

Ollama / 本地模型

目标不是绑死单一模型，而是形成统一 runtime 接口，支持：

本地模型

云模型

多 provider

路由策略切换

能力匹配选择

2.3 支持多模态生成能力

当前正式主线已经具备：

Text

Image

Video

后续保留扩展空间：

Audio

3D

更复杂的多模态 workflow

2.4 兼容更广泛的 Agent / Skill 生态

平台未来希望兼容：

OpenClaw

IronClaw

第三方 Skill

自定义 Agent/Skill 市场化生态

但这里要特别说明：

兼容外部生态 ≠ 延续仓库里的旧实现。

仓库中大量早期兼容实验和旧执行链路已经被归档到 archive/legacy/，后续兼容工作必须基于当前主线重新设计，而不是从 archive 里直接恢复旧代码。

3. 当前正式主线架构

当前仓库已经完成一次较大规模的治理收敛。
接手开发时，必须把下面这条链路当作唯一正式主线：

Gateway API -> Task Submission Service -> Task Store / Outbox -> Redis Queue -> Runtime Workers -> Runtime Services -> Model / Skill

同时保留同步执行路径：

Gateway API -> Runtime Services -> Model / Skill

也就是说，当前主线支持两类运行方式：

3.1 同步执行路径

适合即时请求：

POST /api/v1/agent/run

POST /api/v1/generation/image

POST /api/v1/generation/video

3.2 异步任务路径

适合队列任务：

POST /api/v1/agent/submit

POST /api/v1/generation/image/submit

POST /api/v1/generation/video/submit

GET /api/v1/tasks/{task_id}

4. 当前正式主线目录

后续开发时，优先使用、扩展、维护的目录如下。

4.1 gateway/

正式 HTTP/API 入口层。

职责：

对外暴露 FastAPI 接口

接收同步调用请求

接收异步任务提交请求

返回任务查询结果

提供 health 检查

这是当前对外主入口，不要再恢复旧 prompt_execution_gateway 体系。

4.2 runtime/

正式 runtime 运行层。

职责包括：

Task 模型定义

Queue 读写

Worker 消费循环

Runtime 执行服务

能力路由

模型适配

Generation 运行

这是当前平台最核心的主线目录。

4.3 control_plane/

当前仍在正式主线内的控制面模块。

主要承担：

Registry

Repository

Bus

控制面数据结构

注意：
control_plane/ 是保留且仍使用中的正式目录，不能因为历史清理就误判成全部废弃。

4.4 data_plane/

当前只保留仍被主线引用的基础设施部分。

结论很重要：

data_plane/ 不是完全删除

但旧的执行链路、旧 worker、旧 router 绝大多数已经归档

后续只能基于当前 surviving infra 使用，不能恢复早期 data-plane 执行架构

4.5 bootstrap/

正式运行时组装与启动装配层。

职责：

构建 runtime state

装配 registry / bus / queue / workers / repositories

提供 mainline bootstrap 逻辑

后续如果要做生产化装配、配置中心、环境差异注入，这里会是重点目录之一。

4.6 webapp/

当前正式前端目录。

这是这次治理里最关键的收敛结论之一：

正式前端 = webapp/ + Vite
不是 Flowise

Flowise 现在只能理解成：

历史集成组件

外部能力

可选工具

非正式主线前端

4.7 tests/

测试主线目录。

后续重点维护：

tests/gateway/

tests/runtime/

tests/governance/

其中：

tests/governance/

这是当前仓库治理的关键保障层，用于确保：

已归档的历史文件不回流

主线入口不再引用旧链路

启动脚本口径一致

前端口径一致

copilot/repo instructions 与正式主线一致

后续不要把 governance 当成“可有可无”的附属测试，它是仓库防止历史反弹的保护网。

5. 当前已经归档的区域

所有历史代码、旧说明、旧文档、旧脚本、旧兼容层，现在统一存放在：

archive/legacy/

这个目录存在的意义是：

保留历史上下文

保留治理审计证据

允许研发查看旧实现思路

避免正式主线再次掺入历史包袱

但原则非常明确：

5.1 archive/legacy/ 只能参考

不能直接作为正式实现恢复到主线。

5.2 如需复用历史思路

必须：

先阅读 archive

再在正式主线目录中重新实现

不允许把旧文件原地搬回正式路径继续堆功能

5.3 历史文档也已归档

包括 phase7 到 phase15 的大量旧交接文档、运行说明、gateway requirements、package stub、旧脚本、旧日志快照等。

6. 当前前端结论：Flowise 与 webapp 的关系

这是接手开发时最容易误判的地方，必须单独写清楚。

6.1 当前正式前端

正式前端是 webapp/，启动方式是 Vite。

默认访问地址：

http://localhost:5173

6.2 Flowise 的当前定位

Flowise 当前不是正式前端主线，只能算：

历史集成入口

外部工具

可选能力面板

非正式 UI

6.3 为什么要这样收敛

因为如果继续让 Flowise 和 webapp 同时作为“正式前端”，后果会非常糟：

前端维护口径混乱

文档无法统一

启动脚本无法统一

测试环境无法统一

后续 UI 功能开发不知道该落到哪里

最终导致“名义上两个前端，实际上两个都不完整”

所以本轮治理已经把口径统一为：

正式前端：webapp/Vite

Flowise：历史或外部集成，不作为正式主线

7. 当前启动方式

下面是当前正式主线的基础启动口径。

7.1 基础设施
Redis

用于 queue / stream。

OPA

用于策略能力。

7.2 后端主线

正式后端当前验证方式：

uvicorn gateway.main:app --host 0.0.0.0 --port 8000

访问地址：

http://localhost:8000

7.3 前端主线

正式前端当前验证方式：

cd webapp
npm install
npm run dev -- --host 0.0.0.0 --port 5173

访问地址：

http://localhost:5173

7.4 基础检查脚本

当前基础设施验证脚本：

python tests/scripts/verify_infrastructure.py

在你当前环境里，这个脚本已经验证通过，能检查：

Redis

OPA

OPA Policy

Formal scripts

Gateway

Frontend Vite

Main App process

Frontend Vite process

8. 当前标准验证命令

这是当前主线最重要的标准验证命令，接手后每轮修改都建议至少跑一遍。

8.1 Governance
pytest tests/governance -q
8.2 Runtime + Gateway
pytest tests/runtime tests/gateway -q
8.3 Infra verify
python tests/scripts/verify_infrastructure.py

当前你给出的结果是：

governance：通过

runtime + gateway：通过

infra verify：8/8 通过

这说明当前主线在“治理、主功能、基础设施口径”三条线上是收敛的。

9. 当前阶段已经完成的事

从这次连续治理动作来看，已经完成了几类关键收敛：

9.1 历史代码归档

多批次旧模块、旧脚本、旧文档、旧说明、旧 package stub、旧 gateway 兼容入口，已经迁移到 archive/legacy/。

9.2 正式主线口径统一

已经明确：

正式 gateway

正式 runtime

正式 bootstrap

正式 webapp frontend

正式启动脚本

正式治理测试

9.3 前端口径统一

已经从“Flowise 可能也是前端”收敛为：

webapp 是正式前端

start_frontend.sh 要服务于 webapp/Vite 语义

9.4 文档口径初步统一

历史 phase 文档已经归档，根目录 docs/ 已基本清空，只剩：

docs/CONTEXT_SUMMARY_FOR_NEW_CHAT.md

这意味着后续 docs/ 可以重新作为正式主线文档目录使用。

9.5 Governance 保护网形成

现在 governance 测试已经不仅检查“文件有没有移动”，还检查：

文案口径

启动脚本口径

frontend convergence

copilot instructions 与主线描述一致性

这对后续持续迭代很关键。

10. 当前还没有完成的事

虽然已经治理了很多历史问题，但这并不等于平台已经完整。

当前仍然缺失或尚未完善的部分包括：

10.1 正式完整前端还没有真正做完

目前 webapp 已经是正式前端主线，但它还不是完整产品前端。

也就是说，当前解决的是“前端主线归属问题”，不是“前端产品已完成”。

10.2 Worker 生产化运行方式还不完整

当前队列与 worker 逻辑已经进入主线，但生产化入口、守护、部署编排还需要继续做。

10.3 任务持久化、结果持久化、运行审计还需要加强

已有部分 task store / outbox / postgres 能力，但距离完整生产级仍有空间。

10.4 前端与后端的正式联调面还不完整

虽然 gateway/runtime 已经形成主线，但面向用户的完整前端交互还未形成稳定产品层。

10.5 外部连接器与生态兼容还处于后续阶段

例如：

第三方 skill 接入

外部 connector

更完善的 agent 市场化能力

更成熟的 UI/console

这些都还在后续路线里。

11. 后续前端应该怎么做

你问到一个非常关键的问题：
现在既然曾经出现过 Flowise 和 Node/Vite 两套前端口径，后面到底该怎么做？

结论很明确：

后续前端开发必须以 webapp/ 为唯一正式产品前端继续推进。
原则如下：
11.1 Flowise 不再承担正式产品前端职责

它可以保留为：

外部集成能力

Prompt/Flow 可视化工具

实验性辅助组件

但不能再承担“平台正式 UI 主线”的角色。

11.2 所有新前端功能应进入 webapp/

后续新增页面、主控台、任务列表、模型管理、agent/skill 市场、运行监控等，都应优先落在：

webapp/

11.3 后续前端开发建议分阶段推进
第一阶段：主线控制台框架

先补齐平台正式前端的最小骨架：

登录后主框架

左侧导航

顶部状态栏

health / runtime / tasks 基础页面

API 调试/任务查看页

第二阶段：Runtime Console

围绕当前已经完成的 backend mainline 做 UI：

Agent Run

Agent Submit

Generation Image

Generation Video

Task Query

Task Status

Task Trace / Result

第三阶段：平台管理页

再做控制台型页面：

Model registry view

Provider config

Skill registry

Agent registry

Runtime metrics

Queue / worker status

第四阶段：生态层页面

最后再扩展：

Skill marketplace

Agent marketplace

Workflow builder

External connectors

租户与权限管理页

11.4 前端文档也应主线化

后续前端相关交接、设计说明、页面规划，都不要再散落在 archive 或历史 phase 文档里，而应该放进 docs/ 里的正式文档。

12. 后续建议的文档存放规则

因为当前 docs/ 已经基本清空，所以现在正是重新建立正式文档体系的最好时机。

建议从现在开始按下面规则存放。

12.1 docs/ 只放正式主线文档

例如：

docs/runtime_mainline_handover.md

docs/frontend_mainline_plan.md

docs/runtime_startup_guide.md

docs/testing_and_validation.md

docs/phase17_plan.md

12.2 历史文档一律不回到 docs/

历史 phase 文档、旧手册、旧兼容说明，都已经归档到：

archive/legacy/

后续不要再把历史文件拷回 docs/。

12.3 archive/legacy/ 继续作为历史区

任何发现的旧说明、旧脚本、旧快照、旧文档，都应进入 archive，而不是继续污染主线。

13. 建议下一阶段研发优先级

对下一位接手者，我建议优先级如下。

P0：保持主线收敛，不回退

先保证：

不从 archive 恢复旧执行链路

不重新引入旧 gateway 兼容实现

不让 Flowise 再次成为“正式前端”

governance 测试持续通过

P1：完成正式前端第一轮主线化

重点落在 webapp/：

建立平台控制台框架

对接当前 gateway API

实现任务提交与查询页

明确正式路由结构

P2：补齐 runtime 观测与管理界面

基于已有后端能力，增加：

task list

task detail

queue state

worker status

runtime metrics / traces

P3：强化 worker / persistence / ops

包括：

worker 启动入口规范化

supervisor/systemd/docker 编排

task/result/traces 持久化增强

失败重试 / DLQ 策略

P4：再考虑生态兼容层

比如：

第三方 skill 接入规范

OpenClaw / IronClaw 兼容方案

marketplace / plugin 机制

注意顺序不能反。
先把主线产品做稳，再谈兼容生态。

14. 接手开发的禁止事项

接手者必须避免以下行为：

14.1 不要把 archive/legacy/ 当作正式代码区

它不是待恢复区，是历史参考区。

14.2 不要继续做“兼容层叠兼容层”

这正是之前仓库变臃肿的核心原因之一。

14.3 不要再让双前端并存为正式口径

后续正式前端只能是 webapp/。

14.4 不要绕开 governance 测试

任何修改都应该以 governance 继续通过为前提。

14.5 不要把 phase 文档重新堆回 docs/

docs/ 现在应该只服务正式主线。

15. 当前仓库状态结论

截至当前阶段，可以把仓库状态总结为：

已完成

正式主线收敛

大量历史遗留归档

governance 保护建立

前端主线口径统一到 webapp

runtime/gateway 主线测试稳定通过

基础设施检查通过

当前正式运行口径

后端：gateway.main:app on 8000

前端：webapp Vite on 5173

基础设施：Redis + OPA

测试基线：

pytest tests/governance -q

pytest tests/runtime tests/gateway -q

python tests/scripts/verify_infrastructure.py

当前正式文档区

docs/：后续主线文档区

archive/legacy/：历史参考区

16. 给下一位研发的直接工作指令

如果你是下一位接手开发的研发，请按这个顺序开始：

先阅读本文件

运行：

pytest tests/governance -q

pytest tests/runtime tests/gateway -q

python tests/scripts/verify_infrastructure.py

确认主线环境无误后，只在以下区域继续开发：

gateway/

runtime/

control_plane/

bootstrap/

webapp/

tests/

docs/

不要从 archive/legacy/ 恢复旧实现

前端新开发统一进入 webapp/

后续所有正式交接文档与主线设计文档写入 docs/