# Durable Task / Queue 模块设计文档

## 1. 文档目的

本文档用于定义平台 Durable Task / Queue 模块的职责、边界、主线链路、内部结构、设计原则和后续演进重点。

Queue 模块不是普通消息队列封装，而是平台 durable execution 主链路的核心组成部分。

---

## 2. 模块定位

Durable Task / Queue 模块负责：

- durable submit
- task 持久化
- outbox 事件持久化
- relay 发布
- Redis 队列分发
- worker 消费桥接
- 状态查询基础支撑
- 幂等、一致性、失败恢复相关语义

这一模块的核心价值不是“发消息”，而是承载平台正式任务主线的一致性和可靠性。

---

## 3. 模块边界

### 3.1 Queue 模块负责

Queue 模块负责以下能力：

- 接收来自接入层的 durable task submit 请求
- 将任务与 outbox 事件作为正式真相源先落库
- 为后续异步分发提供可恢复、可重试的 outbox 机制
- 将 publishable event relay 到 Redis
- 连接 worker runtime 的消费链路
- 提供任务状态查询所依赖的任务存储基础
- 提供 idempotency、retry、backoff、dead-letter 等关键语义

### 3.2 Queue 模块不负责

Queue 模块不应承担以下职责：

- 对外完整产品 UI
- 业务能力执行
- 模型推理
- workflow 业务编排
- 替代 runtime 执行层
- 让 Redis 直接成为提交时的第一真相源

---

## 4. 当前主线定位

Durable Task / Queue 模块位于平台主线的中段：

**Gateway → Durable Task Submission → Task Store / Outbox → Outbox Relay → Redis Queue → Worker Runtime → Capability Execution**

其职责是：

- 把提交请求转换成 durable source of truth
- 把 durable source of truth 转换成异步消费事件
- 确保任务执行链路在发布失败、消费失败、重试、恢复场景中仍然具备稳定语义

---

## 5. 当前代码目录结构

```text
runtime/queue/
├─ outbox_relay.py
├─ postgres_task_store.py
├─ redis_queue.py
├─ task_dispatcher.py
├─ task_submission_service.py
└─ ...
6. 核心模块拆分
6.1 task_submission_service.py

职责：

在同一数据库事务中创建 runtime_tasks
在同一数据库事务中创建 runtime_outbox_events
保证 durable source of truth 先于队列发布
处理 idempotency 检查
明确 submit 阶段不直接 publish 到 Redis

这是整个 durable mainline 最关键的组件之一。

6.2 postgres_task_store.py

职责：

提供任务持久化读写能力
支持任务状态读取
支持任务查询与任务生命周期记录

该模块是任务状态真相源的重要组成部分。

6.3 outbox_relay.py

职责：

从 outbox 中读取 publishable event
将事件发布到 Redis
在发布失败时进行 retry
控制 retry backoff
超过阈值后转入 dead-letter

Relay 的存在让“提交”和“发布”解耦，这是平台稳定性的重要基础。

6.4 redis_queue.py

职责：

提供 Redis Streams 队列客户端能力
承担 worker runtime 的异步消费媒介
作为 relay 和 worker 之间的桥梁

Redis 在这里是异步分发层，不是 durable submit 的第一真相源。

6.5 task_dispatcher.py

职责：

将队列消息转交 worker runtime
作为 queue → runtime 的桥梁
保持任务分发与执行层的解耦
7. Queue 模块工程图
flowchart LR
    API[Gateway Tasks API] --> SUBMIT[TaskSubmissionService]
    SUBMIT --> TASKDB[(runtime_tasks)]
    SUBMIT --> OUTBOX[(runtime_outbox_events)]
    OUTBOX --> RELAY[OutboxRelay]
    RELAY --> REDIS[(Redis Streams)]
    REDIS --> DISPATCH[TaskDispatcher]
    DISPATCH --> WORKER[Worker Runtime]
8. 数据与状态主线
8.1 正式真相源

任务正式真相源是数据库中的：

runtime_tasks
runtime_outbox_events
8.2 Redis 的角色

Redis 的角色是：

异步分发媒介
worker 消费来源

Redis 不应被视为 durable submit 的唯一真相源。

8.3 状态语义的重要性

Queue 模块必须保证：

提交成功与否有清晰语义
发布成功与否有清晰语义
重试逻辑可控
死信逻辑可控
worker 消费与任务状态流转之间关系明确
9. 设计原则
原则 1：先落真相源，再异步分发

数据库中的 task 和 outbox 必须先写入，再进入后续 relay 与队列流程。

原则 2：提交与发布分离

TaskSubmissionService 只负责 durable submit；
publish 的职责属于 OutboxRelay，两者不能混在一起。

原则 3：Redis 不是第一真相源

不能把“能发到 Redis”当成“任务已可靠提交”。

原则 4：必须具备幂等与失败恢复语义

没有 idempotency、retry、backoff、dead-letter 的任务主线，不足以支撑商用平台。

原则 5：队列模块承载一致性语义，不只是消息投递

这一层是平台主线的可靠性基础，而不是简单 MQ wrapper。

原则 6：Queue 模块必须服务正式主线

任何新增异步执行能力，都必须回答：

是否复用正式 outbox 链路
是否进入正式任务状态机
是否具备统一查询与恢复能力
10. 当前已实现能力

当前 Queue 模块已具备以下能力：

Agent submit
Image generation submit
Video generation submit
Workflow submit
Task 查询
Task + Outbox 同事务落库
Idempotency-aware submit
Outbox relay
Retry / backoff / dead-letter 基础语义
Redis queue 基础能力
Queue → worker dispatch 桥接能力

这说明平台 durable mainline 已经从“概念方案”进入“实际工程实现”。

11. 当前工程判断
11.1 Queue 模块已经是平台主线骨架的一部分

它不再是某个临时队列工具，而是平台可靠性与执行主线的基础设施层。

11.2 当前最重要的是保持语义统一，而不是继续分叉路径

如果后续又出现新的“绕过 task store / outbox 直接 publish”的路径，会破坏主线一致性。

11.3 Queue 模块的失败风险主要在于语义失控

真正危险的不是“某次 Redis 不可用”，而是：

提交成功但状态不一致
发布失败后恢复逻辑不清楚
重试行为与状态更新脱节
死信逻辑没有运维闭环
worker 消费语义与任务状态机不一致
12. 后续演进重点
12.1 固化任务状态机

应进一步明确：

submitted
published
queued
processing
succeeded
failed
dead-lettered
retrying

等状态语义及转移规则。

12.2 固化 worker 失败恢复语义

需要明确：

任务执行失败后的状态更新规则
可重试失败与不可重试失败的分类
worker 崩溃场景下的恢复语义
12.3 完整建立 DLQ 运维处理机制

Dead-letter 不能只停留在字段或表结构上，还应配套：

查询能力
重放能力
运维处理策略
可观测性与告警机制
12.4 强化 integration tests 对真实主线的覆盖

必须确保测试覆盖的是：

正式 durable submit 路径
正式 relay 路径
正式 queue → worker 路径
状态机真实流转
12.5 为 workflow execution 扩展提供统一主线

workflow submit、workflow execution 查询和 workflow runtime 执行，应继续统一落在正式 durable mainline 上。

13. 模块总结

Durable Task / Queue 模块是平台“可靠执行主线”的基础设施核心。

它的价值不在于：

发消息更快
工具更多
实现更炫

而在于它决定平台是否真正具备：

可恢复
可重试
可追踪
可查询
可治理
可商用

因此，Queue 模块必须始终坚持：

数据库真相源优先
submit / publish 分离
Redis 作为分发媒介
统一状态机
统一失败语义
统一主线入口

这也是平台后续所有异步能力的共同基础。