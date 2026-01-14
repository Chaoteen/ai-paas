#!/usr/bin/env python3
"""
LangGraph gRPC 服务 - 标准化智能路由决策服务
"""

import sys
import os
# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import grpc
from concurrent import futures
import logging
from langgraph.graph import StateGraph, START, END
from typing import Dict, Any, TypedDict, List
import time
import json

# 生成的 gRPC 代码
from aios_sdk import langgraph_pb2 as langgraph_service_pb2
from aios_sdk import langgraph_pb2_grpc as langgraph_service_pb2_grpc

logger = logging.getLogger(__name__)

# 🎯 定义标准化状态结构
class RoutingState(TypedDict):
    # 🎯 任务标识
    task_id: str
    session_id: str
    message_seq: int
    
    # 🎯 输入内容
    content: str
    task_type: str
    model: str
    metadata: Dict[str, Any]
    timestamp: float
    
    # 🎯 分析结果
    intent: str
    content_length: int
    content_language: str
    complexity_level: str
    
    # 🎯 路由决策
    target_agent: str
    confidence: float
    reasoning: str
    fallback_agent: str
    
    # 🎯 上下文信息
    user_profile: Dict[str, Any]
    agent_profile: Dict[str, Any]
    session_context: Dict[str, Any]

class LangGraphRoutingService(langgraph_service_pb2_grpc.LangGraphRouterServicer):
    def __init__(self):
        self.graph = self._build_routing_workflow()
        self.routing_stats = {
            "total_requests": 0,
            "successful_routes": 0,
            "fallback_routes": 0,
            "average_confidence": 0.0
        }
        logger.info("✅ 标准化LangGraph路由服务初始化完成")

    def _build_routing_workflow(self) -> StateGraph:
        """构建标准化路由决策工作流"""
        workflow = StateGraph(RoutingState)

        # 🎯 添加处理节点
        workflow.add_node("extract_context", self._extract_context)
        workflow.add_node("analyze_intent", self._analyze_intent)
        workflow.add_node("evaluate_user_profile", self._evaluate_user_profile)
        workflow.add_node("select_agent", self._select_agent)
        workflow.add_node("validate_decision", self._validate_decision)

        # 🎯 定义工作流
        workflow.add_edge(START, "extract_context")
        workflow.add_edge("extract_context", "analyze_intent")
        workflow.add_edge("analyze_intent", "evaluate_user_profile")
        workflow.add_edge("evaluate_user_profile", "select_agent")
        workflow.add_edge("select_agent", "validate_decision")
        workflow.add_edge("validate_decision", END)

        return workflow.compile()

    async def _extract_context(self, state: RoutingState) -> RoutingState:
        """提取标准化上下文信息"""
        metadata = state.get("metadata", {})
        
        # 🎯 从metadata中提取标准化结构
        user_profile = metadata.get("user_profile", {})
        agent_profile = metadata.get("agent_profile", {})
        session_context = metadata.get("session_context", {})
        
        return {
            "user_profile": user_profile,
            "agent_profile": agent_profile,
            "session_context": session_context,
            "session_id": metadata.get("session_id", f"sess_{state['task_id']}"),
            "message_seq": metadata.get("message_seq", 0)
        }

    async def _analyze_intent(self, state: RoutingState) -> RoutingState:
        """分析任务意图 - 增强版本"""
        content = state.get("content", "").lower()
        task_type = state.get("task_type", "")
        user_profile = state.get("user_profile", {})
        
        # 🎯 基于内容的意图分析
        intent_keywords = {
            "summary": ["总结", "概括", "summary", "summarize", "要点"],
            "translation": ["翻译", "translate", "translation", "英文", "中文"],
            "programming": ["代码", "编程", "code", "programming", "函数", "算法"],
            "rewriting": ["改写", "重写", "rewrite", "rewriting", "润色"],
            "analysis": ["分析", "analyze", "analysis", "解析", "评估"],
            "qa": ["什么", "如何", "为什么", "怎么", "?", "？", "help", "帮助"]
        }
        
        # 🎯 计算意图匹配度
        intent_scores = {}
        for intent, keywords in intent_keywords.items():
            score = sum(1 for keyword in keywords if keyword in content)
            intent_scores[intent] = score
        
        # 🎯 选择最高分的意图
        primary_intent = max(intent_scores, key=intent_scores.get, default="general")
        
        # 🎯 内容复杂度分析
        content_length = len(content)
        if content_length > 500:
            complexity = "high"
        elif content_length > 100:
            complexity = "medium"
        else:
            complexity = "low"
            
        # 🎯 语言检测
        has_chinese = any('\u4e00' <= char <= '\u9fff' for char in content)
        language = "zh" if has_chinese else "en"

        return {
            "intent": primary_intent,
            "content_length": content_length,
            "content_language": language,
            "complexity_level": complexity
        }

    async def _evaluate_user_profile(self, state: RoutingState) -> RoutingState:
        """评估用户档案"""
        user_profile = state.get("user_profile", {})
        intent = state.get("intent", "general")
        complexity = state.get("complexity_level", "low")
        
        # 🎯 基于用户技术水平的路由调整
        technical_level = user_profile.get("technical_level", "beginner")
        department = user_profile.get("department", "")
        
        adjustment_factors = {
            "beginner": {"confidence_adjust": -0.1, "prefer_simple": True},
            "intermediate": {"confidence_adjust": 0.0, "prefer_simple": False},
            "expert": {"confidence_adjust": 0.1, "prefer_technical": True}
        }
        
        adjustment = adjustment_factors.get(technical_level, {})
        
        # 🎯 部门特定的路由偏好
        department_agents = {
            "engineering": ["agent.code", "agent.analyze"],
            "sales": ["agent.summary", "agent.rewrite"],
            "support": ["agent.qa", "agent.default"]
        }
        
        preferred_agents = department_agents.get(department, [])
        
        return {
            "user_profile": {
                **user_profile,
                "routing_adjustment": adjustment,
                "preferred_agents": preferred_agents
            }
        }

    async def _select_agent(self, state: RoutingState) -> RoutingState:
        """选择目标Agent - 标准化版本"""
        intent = state.get("intent")
        task_type = state.get("task_type", "")
        agent_profile = state.get("agent_profile", {})
        user_profile = state.get("user_profile", {})
        
        # 🎯 获取用户订阅的Agents
        subscribed_agents = agent_profile.get("subscribed_agents", ["agent.default"])
        user_preferred_agents = user_profile.get("preferred_agents", [])
        
        # 🎯 Agent能力映射
        agent_capabilities = {
            "agent.summary": ["summary", "general"],
            "agent.translate": ["translation"],
            "agent.code": ["programming", "analysis"],
            "agent.rewrite": ["rewriting", "general"],
            "agent.analyze": ["analysis", "qa"],
            "agent.qa": ["qa", "general"],
            "agent.default": ["general"]
        }
        
        # 🎯 路由决策逻辑
        candidate_agents = []
        
        # 1. 优先用户订阅的Agents
        for agent in subscribed_agents:
            if agent in agent_capabilities and intent in agent_capabilities[agent]:
                candidate_agents.append(agent)
        
        # 2. 考虑用户部门偏好
        for agent in user_preferred_agents:
            if agent in agent_capabilities and intent in agent_capabilities[agent]:
                if agent not in candidate_agents:
                    candidate_agents.append(agent)
        
        # 3. 基于意图的默认映射
        intent_agent_mapping = {
            "summary": "agent.summary",
            "translation": "agent.translate", 
            "programming": "agent.code",
            "rewriting": "agent.rewrite",
            "analysis": "agent.analyze",
            "qa": "agent.qa",
            "general": "agent.default"
        }
        
        if not candidate_agents:
            default_agent = intent_agent_mapping.get(intent, "agent.default")
            candidate_agents.append(default_agent)
        
        # 🎯 选择最佳Agent
        target_agent = candidate_agents[0] if candidate_agents else "agent.default"
        
        # 🎯 计算置信度
        base_confidence = 0.8
        if target_agent in subscribed_agents:
            base_confidence += 0.1
        if target_agent in user_preferred_agents:
            base_confidence += 0.05
            
        # 🎯 应用用户水平调整
        adjustment = user_profile.get("routing_adjustment", {})
        confidence_adjust = adjustment.get("confidence_adjust", 0.0)
        final_confidence = min(1.0, max(0.1, base_confidence + confidence_adjust))
        
        reasoning = f"基于意图'{intent}'选择Agent: {target_agent}"
        if user_preferred_agents:
            reasoning += f", 考虑用户部门偏好"
            
        return {
            "target_agent": target_agent,
            "confidence": final_confidence,
            "reasoning": reasoning,
            "fallback_agent": "agent.default"
        }

    async def _validate_decision(self, state: RoutingState) -> RoutingState:
        """验证路由决策"""
        target_agent = state.get("target_agent", "agent.default")
        
        # 🎯 验证Agent格式
        if not target_agent.startswith("agent."):
            target_agent = "agent.default"
            state["confidence"] *= 0.8
            state["reasoning"] += " (格式修正)"
        
        # 🎯 确保置信度在合理范围内
        state["confidence"] = max(0.1, min(1.0, state["confidence"]))
        
        return state

    async def GetRoutingDecision(self, request, context):
        """gRPC 方法实现 - 标准化路由决策"""
        start_time = time.time()
        
        try:
            # 🎯 更新统计
            self.routing_stats["total_requests"] += 1
            
            logger.info(f"📨 收到标准化路由请求: {request.task_id}, session: {request.metadata.get('session_id', 'unknown')}")

            # 🎯 解析标准化metadata
            metadata = {}
            for key, value in request.metadata.items():
                try:
                    # 尝试解析JSON格式的metadata
                    metadata[key] = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    metadata[key] = value

            # 🎯 准备标准化LangGraph状态
            initial_state = RoutingState(
                task_id=request.task_id,
                session_id=metadata.get("session_id", f"sess_{request.task_id}"),
                message_seq=metadata.get("message_seq", 0),
                content=request.content,
                task_type=request.task_type,
                model=request.model,
                metadata=metadata,
                timestamp=request.timestamp,
                intent="",
                content_length=0,
                content_language="",
                complexity_level="",
                target_agent="",
                confidence=0.0,
                reasoning="",
                fallback_agent="agent.default",
                user_profile={},
                agent_profile={},
                session_context={}
            )

            # 🎯 执行标准化路由工作流
            result = await self.graph.ainvoke(initial_state)

            # 🎯 构建标准化响应
            response = langgraph_service_pb2.RoutingResponse(
                target_agent=result["target_agent"],
                reasoning=result["reasoning"],
                confidence=result["confidence"],
                parameters={
                    "session_id": result["session_id"],
                    "intent": result["intent"],
                    "complexity_level": result["complexity_level"]
                },
                fallback_agent=result["fallback_agent"]
            )

            # 🎯 更新成功统计
            self.routing_stats["successful_routes"] += 1
            self.routing_stats["average_confidence"] = (
                (self.routing_stats["average_confidence"] * (self.routing_stats["successful_routes"] - 1) + 
                 result["confidence"]) / self.routing_stats["successful_routes"]
            )

            processing_time = time.time() - start_time
            logger.info(f"✅ 标准化路由决策完成: {request.task_id} → {result['target_agent']} "
                       f"(置信度: {result['confidence']:.2f}, 耗时: {processing_time:.2f}s)")
            
            return response

        except Exception as e:
            logger.error(f"❌ 标准化路由决策失败: {e}")
            self.routing_stats["fallback_routes"] += 1
            
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"路由决策失败: {str(e)}")

            # 🎯 返回标准化降级响应
            return langgraph_service_pb2.RoutingResponse(
                target_agent="agent.default",
                reasoning=f"路由失败，使用默认agent: {str(e)}",
                confidence=0.1,
                parameters={},
                fallback_agent="agent.default"
            )

    def GetRoutingStats(self, request, context):
        """获取路由统计信息"""
        stats_response = langgraph_service_pb2.RoutingStatsResponse(
            total_requests=self.routing_stats["total_requests"],
            successful_routes=self.routing_stats["successful_routes"],
            fallback_routes=self.routing_stats["fallback_routes"],
            average_confidence=self.routing_stats["average_confidence"],
            timestamp=time.time()
        )
        return stats_response

async def serve():
    """启动标准化gRPC服务器"""
    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=10))

    # 🎯 添加标准化服务
    service = LangGraphRoutingService()
    langgraph_service_pb2_grpc.add_LangGraphRouterServicer_to_server(service, server)

    # 🎯 启动服务
    server.add_insecure_port('[::]:50051')
    await server.start()
    logger.info("🚀 标准化LangGraph gRPC服务启动，端口 50051")

    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("🛑 收到停止信号，关闭服务...")
        await server.stop(0)

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    asyncio.run(serve())