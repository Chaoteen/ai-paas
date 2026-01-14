# ==============================
# File: /agent_core/core.py
# ==============================
import asyncio
from agent_core.memory import MemoryManager
from agent_core.reasoning import ReasoningUnit
from agent_core.skills import SkillRegistry


class AgentCore:
    """
    核心智能体模块：
    - 接收来自MessageBus的任务消息
    - 使用ReasoningUnit推理任务目标
    - 通过SkillRegistry调用技能执行任务
    """

    def __init__(self, bus, model_interface=None, name="AgentCore"):
        self.bus = bus
        self.name = name
        self.memory = MemoryManager()
        self.skills = SkillRegistry()
        self.reasoner = ReasoningUnit(model_interface)
        self._register_bus_events()

    # =========================
    # MessageBus集成
    # =========================
    def _register_bus_events(self):
        """注册到MessageBus，不会引起冲突"""
        @self.bus.subscribe("agent.task")
        async def handle_agent_task(event):
            task_id = event.get("task_id")
            content = event.get("content", "")
            print(f"[{self.name}] 收到任务 {task_id}: {content}")
            await self.handle_task(task_id, content)

        print(f"[{self.name}] 已注册到MessageBus (topic='agent.task')")

    # =========================
    # 核心逻辑
    # =========================
    async def handle_task(self, task_id, content):
        """处理来自总线的任务"""
        self.memory.add("history", f"收到任务: {content}")
        plan = await self.reasoner.think(content)
        print(f"[{self.name}] 推理结果: {plan}")

        # 执行技能
        result = await self.skills.execute(plan)
        self.memory.add("history", f"执行结果: {result}")

        # 将结果广播回总线
        await self.bus.publish("agent.result", {
            "task_id": task_id,
            "result": result,
            "agent": self.name
        })
        print(f"[{self.name}] 已完成任务并返回结果。")

