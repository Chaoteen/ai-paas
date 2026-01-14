from agent_core.core import AgentCore
from myproject.bus import MessageBus  # 假设你的总线模块在这里
from myproject.models import QwenInterface  # 你封装的Qwen模型调用接口

bus = create_message_bus(use_redis=True)
qwen = QwenInterface()  # 你现有的模型接口
agent = AgentCore(bus, qwen, name="LocalAgent")

print("✅ AgentCore 启动完成，可通过 MessageBus 发送任务:")
print("   bus.publish('agent.task', {'task_id': 1, 'content': '帮我总结今天的对话'})")
