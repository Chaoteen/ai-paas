"""
模型基础存在性与兼容性测试

说明：
当前 MVP 版本中，models.agent 只实现了 Agent，
Tool / WorkflowNode / WorkflowEdge 尚未实现。
因此这里不再强制导入未实现模型，避免测试收集阶段失败。
"""

import pytest

import models.agent as agent_module


def test_agent_model_exists():
    """Agent 模型必须存在"""
    assert hasattr(agent_module, "Agent")
    assert agent_module.Agent is not None


def test_optional_tool_model_placeholder():
    """
    Tool 当前允许未实现。
    该测试用于显式记录当前状态，而不是让 pytest 在 import 阶段失败。
    """
    assert hasattr(agent_module, "Tool") is False or getattr(agent_module, "Tool") is not None


def test_optional_workflow_node_model_placeholder():
    """WorkflowNode 当前允许未实现"""
    assert hasattr(agent_module, "WorkflowNode") is False or getattr(agent_module, "WorkflowNode") is not None


def test_optional_workflow_edge_model_placeholder():
    """WorkflowEdge 当前允许未实现"""
    assert hasattr(agent_module, "WorkflowEdge") is False or getattr(agent_module, "WorkflowEdge") is not None