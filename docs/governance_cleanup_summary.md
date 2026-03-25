这次清理，本质上不是“删文件”，而是一次主线收敛 + 历史归档 + 治理规则固化的系统整理。

我给你按“目标—过程—结果—后续文档存放建议”完整总结。

一、这次系统清理的核心目标

这轮工作的核心目标很明确：

把正式主线从历史架构里剥离出来

把还留在正式路径里的旧模块、旧脚本、旧文档、旧说明材料迁入 archive

避免后续开发继续踩到历史兼容层

用治理测试把清理结果固化下来

统一正式启动口径、正式前端口径、正式运行口径

让后续 AI 程序员接手时，只会沿着 formal mainline 开发

也就是说，这轮不是一次普通重构，而是一次面向上线前准备的治理性架构收敛。

二、这次清理前存在的主要问题

清理前，仓库里存在几类典型问题。

1. 正式路径与历史路径混杂

仓库里虽然已经有新的主线：

gateway/

runtime/

control_plane/

bootstrap/

webapp/

但同时还残留了很多早期路径或兼容路径，例如：

agent_core/

services/server/

control_plane/prompt_execution_gateway.py

gateway/prompt_execution_gateway.py

data_plane/router.py

data_plane/router_worker.py

data_plane/agent_worker.py

data_plane/adapters/

data_plane/handlers/

历史运行脚本、历史 handoff 文档、历史 loose artifacts

这些内容即使不再被主线使用，只要还在正式目录里，就会持续制造认知噪音。

2. 启动口径不统一

之前前端和后端启动语义存在混乱：

start_frontend.sh 还在说“当前前端由 Flowise (Docker) 提供”

但实际 formal frontend 已经转向 webapp + Vite

基础设施检查脚本也逐渐转向检查 5173

文档里还有旧前端口径、旧启动口径

这会直接导致后续开发、测试、交接全都不稳定。

3. 历史文档还在 docs 正式目录中

很多 phase handoff 文档仍放在 docs/ 下，例如：

runtime_phase7_handover.md

runtime_phase8_checkpoint.md

runtime_phase10_handover.md

runtime_phase11_handover.md

runtime_phase12_handover.md

runtime_phase13_handover.md

runtime_phase1314_handover.md

runtime_phase15_handover.md

runtime_phase9_agent_worker.md

这些文档不是没价值，但它们已经属于历史阶段性材料，不适合继续占据 formal docs 主路径。

4. 仓库里还残留 loose artifacts

比如：

.bak

.txt

.docx

project_tree.txt

各类 PromptFlow / Proto 说明

日志快照

历史 requirements

各类 legacy script backup

这些内容不清理，后续每一轮开发都会继续被误判。

5. 缺少足够强的治理约束

之前虽然已经有部分治理测试，但还不足以覆盖：

第几批归档的对象是否已经从正式路径移除

formal frontend 是否已切到 webapp

Copilot instructions 是否还在把 legacy stack 写成 active path

启动脚本是否仍在沿用旧语义

所以这次清理的关键，不只是移动文件，而是补齐治理测试。

三、这次系统清理的完整过程

你这次是分批推进的，整体上已经做成了一个很清晰的 archive campaign。

第一阶段：确认 formal mainline

清理过程中逐步确认了正式主线应当只围绕这些路径展开：

gateway/

runtime/

control_plane/

data_plane/ 中仍被主线引用的 surviving infrastructure

bootstrap/

webapp/

root formal scripts（尤其 run_ai_platform_v4.sh、start_frontend.sh 等）

同时明确：

archive/legacy/ 是历史区

历史材料只能参考，不能继续扩展

这是整个治理的基线。

第二阶段：多批次归档历史模块和历史材料

你这轮实际上已经推进到十几批归档，核心动作包括：

已归档的典型内容

services/server/ 历史运行文件

agent_core/ 历史 bus/runtime/misc 内容

旧版 prompt_execution_gateway

data_plane 下旧执行路径与旧 worker/router 体系

历史 loose docs / txt / docx / logs / project tree

各阶段 runtime handoff 文档

agent_core/__init__.py 与 services/server/__init__.py 这类 package stub

gateway/requirements.txt

各类备份脚本与 freeze legacy 脚本

phase15 历史 handoff 文档也最终归档进了 archive

归档后的典型目录结构

你现在 archive/legacy/ 已经形成了比较系统的历史区，例如：

archive/legacy/agent_core_bus

archive/legacy/agent_core_misc

archive/legacy/agent_core_runtime

archive/legacy/control_plane_gateway

archive/legacy/data_plane_execution

archive/legacy/gateway_compat

archive/legacy/historical_runtime_docs

archive/legacy/log_snapshots

archive/legacy/package_stubs

archive/legacy/promptflow_docs

archive/legacy/proto_docs

archive/legacy/scripts

archive/legacy/services_server

archive/legacy/services_server_runtime

这意味着历史资产已经不再散落，而是基本进入了结构化归档状态。

第三阶段：从正式路径真正删除原始位置

这一步很关键。你不是只“复制到 archive”，而是继续做了第二步：

从原路径删除旧文件

提交专门的 remove-original-path commits

确保正式目录不再同时保留旧版本

这是对的。
因为如果只是 copy，不 remove，formal path 仍会继续污染主线。

第四阶段：为每一批归档补治理测试

这是这次清理最有价值的部分之一。

你为很多批次都建立了治理测试，例如：

test_first_archive_batch_moved.py

test_second_archive_batch_moved.py

test_third_archive_batch_moved.py

test_fourth_archive_batch_moved.py

test_fifth_archive_batch_moved.py

test_sixth_archive_batch_moved.py

test_seventh_archive_batch_moved.py

test_eighth_archive_batch_moved.py

test_ninth_archive_batch_moved.py

test_tenth_archive_batch_moved.py

test_eleventh_archive_batch_moved.py

test_twelfth_archive_batch_moved.py

test_fourteenth_archive_batch_moved.py

这些测试的作用非常大：

证明原路径已移除

证明归档路径存在

防止历史文件回流到 formal path

给后续 AI 程序员一个明确边界

这相当于把“架构治理”写进测试体系。

第五阶段：统一 startup 和 frontend 口径

这部分也是重点。

你实际完成了两件事
1. formal backend 运行口径确认

你现在已经稳定验证了：

Redis 正常

OPA 正常

Gateway 正常

main app 进程正常

2. formal frontend 口径收敛到 webapp + Vite

你已经把实际运行状态跑通：

webapp 下 npm run dev -- --host 0.0.0.0 --port 5173

verify_infrastructure.py 能检测到 5173

start_frontend.sh 的口径也被修正为 formal frontend 指向 Vite webapp

Flowise 不再作为正式前端口径

这是一次很重要的产品方向收敛。

第六阶段：修正 .github/copilot-instructions.md

你这轮遇到的一个典型问题就是：

copilot instructions 一边要避免把 legacy path 写成 active

一边又必须保留 formal mainline 的关键 marker

一边还要满足治理测试要求，比如：

formal runtime chain

governance test command

runtime/gateway validation command

frontend 主线说明

archive 只作参考

中间你经历了几次失败：

缺少 data_plane/handlers/ 相关约束

缺少 formal runtime chain marker

缺少 pytest tests/governance -q

缺少 pytest tests/runtime tests/gateway -q

最后你把这些 marker 恢复到了合格状态，并通过了：

test_copilot_instructions_aligned.py

test_fifteenth_copilot_wording_convergence.py

这说明仓库级“开发说明书”已经和当前主线相对一致。

第七阶段：基础设施验证闭环

最终你做到了三个层面的闭环验证：

1. Governance tests

全部通过。

2. Runtime + Gateway tests

121 项通过。

3. 基础设施检查脚本

最终是 8/8 通过，包括：

Redis

OPA

OPA Policy

formal scripts

Gateway

Frontend Vite

main.py process

vite process

这说明这轮清理不是“文档治理”，而是真正影响到运行口径，并且已经被实测验证。

四、这次清理的最终成果

这次清理完成后，可以把成果总结为 8 条。

1. 正式主线已经基本收敛

正式开发路径现在已经明显集中到：

gateway/

runtime/

control_plane/

bootstrap/

webapp/

formal root scripts

2. 历史架构基本退出正式目录

早期遗留内容已大规模迁入 archive/legacy/，不再继续占据 formal path。

3. docs 正式目录被瘦身

现在根目录 docs/ 基本只剩：

docs/CONTEXT_SUMMARY_FOR_NEW_CHAT.md

这意味着 docs/ 不再承载大量历史阶段性 handoff 文档。

4. 历史 handoff 文档有了统一归档区

这些历史交接文档已经被收拢进：

archive/legacy/historical_runtime_docs/

这是对的。

5. 前端正式主线已经明确

正式前端已经不再是 Flowise，而是：

webapp

Vite

5173

Flowise 未来只能作为外部工具或辅助集成，不应继续作为 formal frontend。

6. 治理测试体系更完整

你已经把 archive campaign、frontend convergence、copilot wording convergence 都纳入治理测试。

7. 运行验证口径稳定

不仅代码测试通过，而且主线运行链路也通过了脚本检查。

8. 接手门槛显著下降

后续 AI 程序员不用再猜：

哪条是正式前端

哪条是历史兼容

哪些文档是主线

哪些路径可以继续扩展

五、这次清理里还需要注意的一点

有一个小风险你已经暴露出来了：

历史归档文件不应该被意外清空

你后来发现：

archive/legacy/historical_runtime_docs/runtime_phase15_handover.md
被错误清空了

然后你又通过：

git checkout 6cee3ab -- archive/legacy/historical_runtime_docs/runtime_phase15_handover.md

把内容恢复回来，这一步是非常必要的。

这说明以后在 archive 区也要遵循一个原则：

archive 是“冻结保存”，不是“继续编辑”

除非是补充 very small metadata，不然不要动 archive 正文内容。

六、你问的关键问题：后面的交接文档应该存在哪个目录？

现在 docs/ 已经基本空了，这反而是个好时机，可以把文档体系重新定义清楚。

我的建议是：

建议采用“双层文档目录”
1. docs/ 只存正式主线文档

也就是“当前有效、指导后续开发”的文档。

建议放这些类型：

当前总交接文档

当前架构白皮书

当前启动说明

当前 roadmap

当前模块说明

当前前后端主线说明

当前测试与治理说明

这些文档必须服务于现在和未来的主线开发。

2. archive/legacy/historical_runtime_docs/ 继续存历史阶段性交接文档

比如：

phase7

phase8

phase10

phase11

phase12

phase13/14

phase15

这些都应该留在 archive，不应该再放回 docs/。

七、具体建议：后续交接文档怎么放
现在开始，建议这样分：
放在 docs/ 的内容

这些是“唯一应继续维护的正式文档”：

1. 总交接文档

例如：

docs/runtime_mainline_handover.md

内容应包括：

项目目标

formal mainline

当前 repo 结构

当前运行口径

当前已完成能力

当前未完成能力

后续 roadmap

开发优先级

启动与测试方法

这是给下一个 AI 程序员看的主文档。

2. 当前架构总览

例如：

docs/runtime_mainline_architecture.md

写清：

Gateway

Runtime

Queue/Workers

Control plane

Frontend

任务链路

同步/异步执行链路

3. 当前启动说明

例如：

docs/mainline_runbook.md

写清：

Redis / OPA / DB

后端怎么启动

前端怎么启动

验证命令

常见故障

4. 当前前端 roadmap

例如：

docs/frontend_mainline_roadmap.md

这个对你接下来尤其重要。

5. 当前治理规则

例如：

docs/governance_mainline_rules.md

写清：

archive 原则

formal path 原则

启动口径

前端口径

新增模块规则

不允许再向 legacy path 写新代码

放在 archive/legacy/... 的内容

只放：

历史 phase handoff

历史 checkpoint

历史 loose docs

历史说明材料

历史脚本

历史兼容层

八、最推荐的目录方案

我建议你后面把正式文档体系固定成下面这样：

docs/
  CONTEXT_SUMMARY_FOR_NEW_CHAT.md
  runtime_mainline_handover.md
  runtime_mainline_architecture.md
  mainline_runbook.md
  frontend_mainline_roadmap.md
  governance_mainline_rules.md

而历史文档继续保留在：

archive/legacy/historical_runtime_docs/

这样层次最清楚。

九、给你的结论
这次系统清理的本质成果

不是单纯“归档了很多文件”，而是：

把正式主线从历史遗留里剥离出来

把历史资产系统化迁入 archive/legacy/

用治理测试把收敛结果固化

把正式前端收敛到 webapp + Vite

把正式运行口径稳定下来

给后续 phase 开发建立了干净基线