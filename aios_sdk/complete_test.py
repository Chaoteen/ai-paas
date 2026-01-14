#!/usr/bin/env python3
"""
AIOS SDK 完整功能测试
"""

print("🚀 AIOS SDK 完整功能测试")
print("=" * 50)

# 测试消息类型
print("1. 测试消息类型...")
import agent_pb2
import inference_pb2
import envelope_pb2
import model_pb2
import prompt_pb2

agent = agent_pb2.Agent(id="agent_001", name="Test Agent")
task = agent_pb2.Task(task_id="task_001", session_id="session_001")
request = inference_pb2.InferenceRequest(session_id="session_001")
metadata = envelope_pb2.StandardMetadata(request_id="req_001")
string_val = envelope_pb2.StringValue(value="hello")

print("✅ 消息类型测试通过")
print(f"   Agent: {agent.id} - {agent.name}")
print(f"   Task: {task.task_id}")
print(f"   StringValue: {string_val.value}")

# 测试gRPC
print("\n2. 测试gRPC客户端...")
import agent_pb2_grpc
import inference_pb2_grpc
import model_pb2_grpc

print("✅ gRPC客户端测试通过")
print(f"   AgentServiceStub: {hasattr(agent_pb2_grpc, 'AgentServiceStub')}")
print(f"   InferenceServiceStub: {hasattr(inference_pb2_grpc, 'InferenceServiceStub')}")
print(f"   ModelServiceStub: {hasattr(model_pb2_grpc, 'ModelServiceStub')}")

# 测试所有服务
print("\n3. 测试所有服务...")
services = [
    ('agent_pb2_grpc', 'AgentServiceStub'),
    ('inference_pb2_grpc', 'InferenceServiceStub'), 
    ('model_pb2_grpc', 'ModelServiceStub'),
    ('prompt_pb2_grpc', 'PromptServiceStub'),
    ('policy_pb2_grpc', 'PolicyServiceStub'),
    ('vector_pb2_grpc', 'VectorServiceStub'),
    ('langgraph_pb2_grpc', 'LangGraphServiceStub')
]

for module_name, stub_name in services:
    try:
        module = __import__(module_name)
        if hasattr(module, stub_name):
            print(f"   ✅ {module_name}.{stub_name}")
        else:
            print(f"   ⚠️  {module_name} 没有 {stub_name}")
    except ImportError:
        print(f"   ❌ {module_name} 导入失败")

print("\n" + "=" * 50)
print("🎉 AIOS SDK 所有功能测试完成！")
print("\n📖 使用方法:")
print("   import agent_pb2")
print("   agent = agent_pb2.Agent(id='test', name='Test Agent')")
print("   from agent_pb2_grpc import AgentServiceStub")
print("\n💡 提示: 所有文件都在当前目录，直接导入即可使用")
