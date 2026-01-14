"""
AIOS SDK - AI PaaS Platform Client Library
Automatically generated from proto files.
Version: 1.0.0
"""

# 直接导入当前目录的文件
from .agent_pb2 import Agent, Task
from .inference_pb2 import InferenceRequest
from .envelope_pb2 import StandardMetadata, StringValue

# 重新导出
__all__ = [
    'Agent', 'Task', 'InferenceRequest', 'StandardMetadata', 'StringValue'
]

__version__ = "1.0.0"
