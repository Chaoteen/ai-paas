# server/test_client.py
import time
from agent_core.redis_bus import create_message_bus

def on_result(data):
    print(f"🧠 [Agent] Received result for task {data['task_id']}:")
    print(data['result'])

if __name__ == "__main__":
    bus = create_message_bus(use_redis=True)
    bus.subscribe("agent.result", on_result)

    print("📨 Publishing test task...")
    bus.publish("agent.task", {"task_id": 1001, "content": "请帮我总结一下人工智能的主要研究方向。"})
    bus.run_forever()
