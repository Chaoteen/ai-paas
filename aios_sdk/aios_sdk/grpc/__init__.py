"""
gRPC client stubs for AIOS services.
"""

from . import agent_pb2_grpc
from . import inference_pb2_grpc
from . import prompt_pb2_grpc
from . import policy_pb2_grpc
from . import vector_pb2_grpc
from . import langgraph_pb2_grpc

# 只导出实际存在的Stub类
__all__ = [
    'agent_pb2_grpc', 'inference_pb2_grpc', 'prompt_pb2_grpc',
    'policy_pb2_grpc', 'vector_pb2_grpc', 'langgraph_pb2_grpc'
]

# 动态导出可用的Stub类
try:
    from .agent_pb2_grpc import AgentServiceStub
    __all__.append('AgentServiceStub')
except ImportError:
    pass

try:
    from .inference_pb2_grpc import InferenceServiceStub
    __all__.append('InferenceServiceStub')
except ImportError:
    pass

try:
    from .prompt_pb2_grpc import PromptServiceStub
    __all__.append('PromptServiceStub')
except ImportError:
    pass

try:
    from .model_pb2_grpc import ModelServiceStub
    __all__.append('ModelServiceStub')
except ImportError:
    pass
