# Simplified gRPC client stub for AgentService
import grpc
from . import agent_pb2 as agent__pb2

class AgentServiceStub:
    def __init__(self, channel):
        self.RegisterAgent = channel.unary_unary(
            '/ai.os.agent.AgentService/RegisterAgent',
            request_serializer=agent__pb2.Agent.SerializeToString,
            response_deserializer=agent__pb2.Agent.FromString,
        )
        self.ExecuteTask = channel.unary_unary(
            '/ai.os.agent.AgentService/ExecuteTask',
            request_serializer=agent__pb2.Task.SerializeToString,
            response_deserializer=agent__pb2.TaskStatus.FromString,
        )
        # 添加其他方法...

class AgentServiceServicer:
    """Missing associated documentation comment in .proto file."""
    pass

def add_AgentServiceServicer_to_server(servicer, server):
    pass
