AI-PaaS Runtime Phase 9

Agent Worker Execution Pipeline

1 Phase 9 目标

Phase 9 的目标是引入：

AgentWorker

使 Runtime 具备 任务执行能力。

Phase 8 只有：

task.submitted
→ router.success

Phase 9 实现：

task.submitted
→ router.success
→ task.executing
→ task.completed
2 Runtime 执行架构
Runtime API
      │
      ▼
task.submitted
      │
      ▼
RouterWorker
      │
      ▼
router.success
      │
      ▼
AgentWorker
      │
      ▼
task.executing
      │
      ▼
task.completed
3 AgentWorker 模块

路径：

data_plane/agent_worker.py

职责：

消费 router.success
执行任务
发布任务状态
4 AgentWorker 输入事件

来自：

router.success

示例：

{
 "event_type":"router.success",
 "task_id":"task_004",
 "payload":{
   "route_to":"agent_translation_001",
   "extra":{
     "selected_agent_id":"agent_translation_001",
     "required_capability":"translation",
     "input":{"text":"phase9 test"}
   }
 }
}
5 AgentWorker 执行流程

执行步骤：

1 接收 router.success
2 发布 task.executing
3 调用 agent
4 发布 task.completed
6 当前执行模式

当前 Phase 9 为：

模拟执行

返回结果：

{
 "execution_mode":"simulated"
}
7 输出事件

执行开始：

task.executing

示例：

{
 "event_type":"task.executing",
 "task_id":"task_004",
 "payload":{
   "route_to":"agent_translation_001"
 }
}

执行完成：

task.completed

示例：

{
 "event_type":"task.completed",
 "payload":{
   "result":{
      "execution_mode":"simulated",
      "agent_id":"agent_translation_001"
   }
 }
}
8 Redis Consumer Group

新增：

agent-workers

Consumer：

agent-1
9 Phase 9 事件链

成功路径：

task.submitted
→ router.success
→ task.executing
→ task.completed

失败路径：

task.submitted
→ router.success
→ task.failed
10 测试

新增测试：

tests/test_agent_worker.py

测试：

test_agent_worker_completed
test_agent_worker_failed_when_agent_not_found
11 Phase 9 完成状态

系统首次具备：

任务执行能力

Runtime 从：

Routing System

升级为：

Execution Runtime
12 当前限制

当前执行仍然是：

模拟 Agent

尚未接入：

LLM
Tool
Skill
Plugin
13 下一阶段

Phase 10：

Agent Runtime

新增能力：

LLM Invocation
Tool Invocation
Skill Framework

事件链：

task.submitted
→ router.success
→ task.executing
→ agent.invoke
→ tool.invoke
→ task.completed
Phase 9 完成标志

Runtime 现在具备：

任务提交
能力路由
任务执行
事件持久化
Redis EventBus
Postgres EventStore

系统已形成 完整 Runtime Core。