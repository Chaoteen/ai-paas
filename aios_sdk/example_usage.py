#!/usr/bin/env python3
"""
AIOS SDK 使用示例 - 平面结构版本
"""

import sys
import os

# 添加SDK路径
sys.path.insert(0, os.path.dirname(__file__))

from aios_sdk import Agent, Task, InferenceRequest, StandardMetadata, StringValue
from aios_sdk.agent_pb2_grpc import AgentServiceStub
from aios_sdk.inference_pb2_grpc import InferenceServiceStub

def demo_sdk():
    print("🚀 AIOS SDK 使用演示 (平面结构)")
    print("=" * 50)
    
    # 创建消息实例
    agent = Agent(
        id="agent_001",
        name="Test Agent", 
        skill_manifest="测试技能清单"
    )
    
    task = Task(
        task_id="task_001",
        session_id="session_001", 
        agent_id="agent_001",
        goal="测试任务目标"
    )
    
    print("✅ 创建消息实例:")
    print(f"   Agent: {agent.id} - {agent.name}")
    print(f"   Task: {task.task_id} - {task.goal}")
    
    print("\n✅ 导入方式:")
    print("   from aios_sdk import Agent, Task, InferenceRequest")
    print("   from aios_sdk.agent_pb2_grpc import AgentServiceStub")
    print("   from aios_sdk.inference_pb2_grpc import InferenceServiceStub")
    
    print("\n🎉 SDK 准备就绪！")

if __name__ == "__main__":
    demo_sdk()
