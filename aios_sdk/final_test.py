#!/usr/bin/env python3
"""
AIOS SDK 最终测试 - 直接使用方式
"""

import sys
import os

# 确保在当前目录
print("工作目录:", os.getcwd())

# 方法1：直接导入文件（最可靠）
print("方法1: 直接导入文件")
import agent_pb2
import inference_pb2
import envelope_pb2
import agent_pb2_grpc
import inference_pb2_grpc

# 使用消息类型
agent = agent_pb2.Agent(id="agent_001", name="Test Agent")
task = agent_pb2.Task(task_id="task_001", session_id="session_001")
request = inference_pb2.InferenceRequest(session_id="session_001")
metadata = envelope_pb2.StandardMetadata(request_id="req_001")
string_val = envelope_pb2.StringValue(value="hello")

print("✅ 直接导入成功！")
print(f"   Agent: {agent.id} - {agent.name}")
print(f"   Task: {task.task_id}")
print(f"   StringValue: {string_val.value}")

# 使用gRPC Stub
print("✅ gRPC Stub:")
print(f"   AgentServiceStub: {hasattr(agent_pb2_grpc, 'AgentServiceStub')}")
print(f"   InferenceServiceStub: {hasattr(inference_pb2_grpc, 'InferenceServiceStub')}")

print("\n" + "="*50)
print("方法2: 通过包导入（需要正确设置Python路径）")

# 方法2：通过包导入
try:
    # 添加父目录到路径
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    
    from aios_sdk import Agent, Task, InferenceRequest, StandardMetadata
    from aios_sdk.agent_pb2_grpc import AgentServiceStub
    
    agent2 = Agent(id="agent_002", name="Test Agent 2")
    task2 = Task(task_id="task_002", session_id="session_002")
    
    print("✅ 包导入成功！")
    print(f"   Agent: {agent2.id} - {agent2.name}")
    
except ImportError as e:
    print("⚠️  包导入失败（这很正常，需要安装或设置路径）")
    print(f"   错误: {e}")

print("\n" + "="*50)
print("🎉 AIOS SDK 生成完成！")
print("📖 推荐使用方法1（直接导入文件）")
print("💡 使用方法:")
print("   import agent_pb2")
print("   agent = agent_pb2.Agent(id='test', name='Test Agent')")
print("   from agent_pb2_grpc import AgentServiceStub")
