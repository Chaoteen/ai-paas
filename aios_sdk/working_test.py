#!/usr/bin/env python3
"""
AIOS SDK 工作测试 - 修复版本
"""

print("🚀 AIOS SDK 测试")

try:
    # 导入所有消息文件
    import agent_pb2
    import inference_pb2
    import envelope_pb2
    import model_pb2
    import prompt_pb2
    import policy_pb2
    import vector_pb2
    import langgraph_pb2
    
    print("✅ 所有消息文件导入成功")
    
    # 测试创建实例
    agent = agent_pb2.Agent(id="agent_001", name="Test Agent")
    task = agent_pb2.Task(task_id="task_001", session_id="session_001")
    request = inference_pb2.InferenceRequest(session_id="session_001")
    metadata = envelope_pb2.StandardMetadata(request_id="req_001")
    string_val = envelope_pb2.StringValue(value="hello world")
    
    print("✅ 消息实例创建成功:")
    print(f"   Agent: {agent.id} - {agent.name}")
    print(f"   Task: {task.task_id}")
    print(f"   InferenceRequest: {request.session_id}")
    print(f"   StringValue: {string_val.value}")
    
    # 测试gRPC文件
    import agent_pb2_grpc
    import inference_pb2_grpc
    
    print("✅ gRPC文件导入成功:")
    print(f"   AgentServiceStub: {hasattr(agent_pb2_grpc, 'AgentServiceStub')}")
    print(f"   InferenceServiceStub: {hasattr(inference_pb2_grpc, 'InferenceServiceStub')}")
    
    print("\n🎉 AIOS SDK 完全可用！")
    print("\n📖 使用方法:")
    print("   import agent_pb2")
    print("   agent = agent_pb2.Agent(id='test', name='Test Agent')")
    print("   from agent_pb2_grpc import AgentServiceStub")
    
except Exception as e:
    print(f"❌ 导入失败: {e}")
    import traceback
    traceback.print_exc()
