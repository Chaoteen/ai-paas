# ai-os/data_plane/legacy/__init__.py

"""
Data Plane Legacy Adapters

用于兼容旧系统的本地总线 / 旧消息格式，并适配到新的 Redis Streams 或冻结信封结构。
"""

from .router_bridge_adapter import RouterBridgeAdapter  # noqa: F401
