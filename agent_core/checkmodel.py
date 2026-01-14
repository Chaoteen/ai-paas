async def send_task(self, task_id, content):
    # 强制使用 deepseek 模型
    model = "deepseek"  # 直接指定，不通过 reasoning
    self.memory.add(task_id, content)
    msg = {"task_id": task_id, "content": content, "model": model}
    print(f"[AgentController] 📤 {task_id} routed to {model}")
    await self.bus.publish("agent.task", msg)