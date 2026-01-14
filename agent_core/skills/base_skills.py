# ==============================
# File: /agent_core/skills/base_skills.py
# ==============================
import asyncio

class SkillRegistry:
    """注册并执行可调用技能"""

    def __init__(self):
        self.skills = {}
        self.register("echo", self.skill_echo)

    def register(self, name, func):
        self.skills[name] = func

    async def execute(self, instruction: str):
        """根据模型推理输出，找到合适的技能执行"""
        for name, func in self.skills.items():
            if name in instruction.lower():
                return await asyncio.to_thread(func, instruction)
        return f"未找到可执行技能：{instruction}"

    # ========== 示例技能 ==========
    def skill_echo(self, text):
        """简单回显任务"""
        return f"Echo: {text}"
