import asyncio
import time
import logging
from typing import Dict, List, Optional, Any
import uuid

logger = logging.getLogger(__name__)

class AgentManager:
    """标准化Agent管理器 - 支持多Agent智能路由和负载均衡"""
    
    def __init__(self, registry, bus):
        self.registry = registry
        self.bus = bus
        self.routing_strategy = RoutingStrategy(registry)
        self._running = False
        
        # 🎯 Agent状态追踪
        self.agent_stats = {}
        self.session_agents = {}  # 会话到Agent的映射
        
        # 🎯 负载均衡配置
        self.load_balancing_config = {
            "max_tasks_per_agent": 100,
            "load_check_interval": 30,
            "sticky_session": True  # 会话粘性路由
        }
        
        logger.info("[AgentManager] ✅ 标准化Agent管理器初始化完成")
    
    def _ensure_event_loop(self):
        """确保当前线程有事件循环"""
        try:
            asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

    async def initialize(self):
        """异步初始化 - 标准化版本"""
        # 🎯 订阅标准化任务流
        await self.bus.subscribe("agent.tasks.stream", self.on_task)
        
        # 🎯 启动监控任务
        asyncio.create_task(self._load_monitor())
        
        self._running = True
        logger.info("[AgentManager] ✅ 订阅标准化任务流: agent.tasks.stream")

    async def on_task(self, processing_context: Dict[str, Any]):
        """处理新任务并路由到合适Agent - 标准化版本"""
        start_time = time.time()
        
        try:
            # 🎯 提取标准化字段
            envelope = processing_context["envelope"]
            session_id = processing_context["session_id"]
            task_id = processing_context["task_id"]
            message_seq = processing_context["message_seq"]
            metadata = processing_context["metadata"]
            raw_data = processing_context["raw_data"]
            
            logger.info(f"[AgentManager] 📨 收到标准化任务: session={session_id}, task={task_id}, seq={message_seq}")

            # 🎯 确定目标Agent
            target_agent = await self._select_target_agent(processing_context)
            
            if target_agent:
                # 🎯 更新Agent统计
                self._update_agent_stats(target_agent, "dispatched")
                
                # 🎯 创建标准化路由消息
                routed_message = self._create_routed_message(processing_context, target_agent)
                
                logger.info(f"[AgentManager] 📤 分发任务 {task_id} -> {target_agent}")
                
                # 🎯 发布到对应Agent的专属通道
                await self.bus.publish(f"agent.model.{target_agent}", routed_message)
                
            else:
                # 🎯 无可用Agent时的错误处理
                error_msg = "没有可用的Agent处理此任务"
                logger.error(f"[AgentManager] ❌ {error_msg}: {task_id}")
                
                await self._publish_error_result(processing_context, error_msg, start_time)
                
        except Exception as e:
            logger.error(f"[AgentManager] ❌ 处理任务时出错: {e}")
            await self._publish_error_result(processing_context, f"任务处理失败: {str(e)}", start_time)

    async def _select_target_agent(self, processing_context: Dict[str, Any]) -> Optional[str]:
        """智能Agent选择逻辑 - 标准化版本"""
        raw_data = processing_context["raw_data"]
        metadata = processing_context["metadata"]
        session_id = processing_context["session_id"]
        
        # 🎯 1. 检查会话粘性路由
        if self.load_balancing_config["sticky_session"] and session_id in self.session_agents:
            sticky_agent = self.session_agents[session_id]
            if self._is_agent_available(sticky_agent):
                logger.debug(f"[AgentManager] 🔄 使用粘性会话路由: {session_id} -> {sticky_agent}")
                return sticky_agent

        # 🎯 2. 优先使用用户指定的Agent
        agent_profile = metadata.get("agent_profile", {})
        subscribed_agents = agent_profile.get("subscribed_agents", [])
        
        if subscribed_agents:
            available_subscribed = [agent for agent in subscribed_agents 
                                  if self._is_agent_available(agent)]
            if available_subscribed:
                selected_agent = available_subscribed[0]
                self.session_agents[session_id] = selected_agent
                logger.debug(f"[AgentManager] 🎯 使用用户订阅Agent: {selected_agent}")
                return selected_agent

        # 🎯 3. 基于内容分析的智能路由
        content = raw_data.get("content", "")
        task_type = raw_data.get("task_type", "")
        user_profile = metadata.get("user_profile", {})
        
        target_agent = await self.routing_strategy.route_by_content(
            content, task_type, user_profile, agent_profile
        )
        
        if target_agent and self._is_agent_available(target_agent):
            self.session_agents[session_id] = target_agent
            logger.debug(f"[AgentManager] 🧠 基于内容分析路由: {target_agent}")
            return target_agent

        # 🎯 4. 负载均衡路由
        balanced_agent = self._select_balanced_agent()
        if balanced_agent:
            self.session_agents[session_id] = balanced_agent
            logger.debug(f"[AgentManager] ⚖️ 使用负载均衡路由: {balanced_agent}")
            return balanced_agent

        logger.warning(f"[AgentManager] ⚠️ 未找到可用Agent")
        return None

    def _is_agent_available(self, agent_id: str) -> bool:
        """检查Agent是否可用"""
        # 🎯 检查注册表中的Agent状态
        agent_spec = self.registry.get_model(agent_id)
        if not agent_spec or agent_spec.status != "online":
            return False
            
        # 🎯 检查负载情况
        agent_stat = self.agent_stats.get(agent_id, {})
        current_load = agent_stat.get("current_tasks", 0)
        max_load = self.load_balancing_config["max_tasks_per_agent"]
        
        return current_load < max_load

    def _select_balanced_agent(self) -> Optional[str]:
        """基于负载均衡选择Agent"""
        available_agents = self.get_available_agents()
        if not available_agents:
            return None
            
        # 🎯 选择负载最低的Agent
        return min(available_agents, 
                  key=lambda agent: self.agent_stats.get(agent, {}).get("current_tasks", 0))

    def _create_routed_message(self, processing_context: Dict[str, Any], target_agent: str) -> Dict[str, Any]:
        """创建标准化路由消息"""
        envelope = processing_context["envelope"]
        raw_data = processing_context["raw_data"]
        metadata = processing_context["metadata"]
        
        # 🎯 构建路由消息
        routed_data = raw_data.copy()
        routed_data["target_agent"] = target_agent
        routed_data["routed_by"] = "agent_manager"
        routed_data["routing_timestamp"] = time.time()
        
        # 🎯 创建完整的消息信封
        return {
            "envelope": envelope,
            "session_id": processing_context["session_id"],
            "task_id": processing_context["task_id"],
            "message_seq": processing_context["message_seq"],
            "metadata": metadata,
            "raw_data": routed_data
        }

    async def _publish_error_result(self, processing_context: Dict[str, Any], 
                                  error_message: str, start_time: float):
        """发布错误结果"""
        error_result = {
            "session_id": processing_context["session_id"],
            "task_id": processing_context["task_id"],
            "message_seq": processing_context["message_seq"],
            "status": "failed",
            "error": error_message,
            "processing_time": time.time() - start_time,
            "completion_time": time.time(),
            "routed_by": "agent_manager"
        }
        
        await self.bus.publish("agent.result.stream", error_result, processing_context["metadata"])

    def _update_agent_stats(self, agent_id: str, action: str):
        """更新Agent统计信息"""
        if agent_id not in self.agent_stats:
            self.agent_stats[agent_id] = {
                "total_tasks": 0,
                "completed_tasks": 0,
                "failed_tasks": 0,
                "current_tasks": 0,
                "last_activity": time.time()
            }
        
        stats = self.agent_stats[agent_id]
        stats["last_activity"] = time.time()
        
        if action == "dispatched":
            stats["total_tasks"] += 1
            stats["current_tasks"] += 1
        elif action == "completed":
            stats["completed_tasks"] += 1
            stats["current_tasks"] -= 1
        elif action == "failed":
            stats["failed_tasks"] += 1
            stats["current_tasks"] -= 1

    async def _load_monitor(self):
        """Agent负载监控"""
        while self._running:
            try:
                # 🎯 定期检查Agent状态
                available_count = len(self.get_available_agents())
                total_tasks = sum(stats.get("current_tasks", 0) for stats in self.agent_stats.values())
                
                logger.info(f"[AgentManager] 📊 负载监控 - 可用Agent: {available_count}, 运行中任务: {total_tasks}")
                
                # 🎯 清理过期的会话映射
                self._cleanup_expired_sessions()
                
                await asyncio.sleep(self.load_balancing_config["load_check_interval"])
                
            except Exception as e:
                logger.error(f"[AgentManager] ❌ 负载监控错误: {e}")
                await asyncio.sleep(60)

    def _cleanup_expired_sessions(self):
        """清理过期的会话映射"""
        current_time = time.time()
        expiration_time = 3600  # 1小时
        
        expired_sessions = [
            session_id for session_id, last_used in self.session_agents.items()
            if current_time - last_used > expiration_time
        ]
        
        for session_id in expired_sessions:
            del self.session_agents[session_id]
            logger.debug(f"[AgentManager] 🗑️ 清理过期会话: {session_id}")

    def get_available_agents(self) -> List[str]:
        """获取所有可用Agent列表"""
        return [agent_id for agent_id, spec in self.registry.model_registry.items()
                if spec.status == "online" and self._is_agent_available(agent_id)]

    def get_agent_stats(self) -> Dict[str, Any]:
        """获取Agent统计信息"""
        return {
            "total_agents": len(self.registry.model_registry),
            "available_agents": len(self.get_available_agents()),
            "agent_details": self.agent_stats,
            "session_mappings": len(self.session_agents),
            "load_balancing_config": self.load_balancing_config
        }

    def update_agent_status(self, agent_id: str, status: str):
        """更新Agent状态"""
        if agent_id in self.registry.model_registry:
            self.registry.model_registry[agent_id].status = status
            logger.info(f"[AgentManager] 🔄 更新Agent状态: {agent_id} -> {status}")

    async def stop(self):
        """停止Agent管理器"""
        self._running = False
        logger.info("[AgentManager] 🛑 Agent管理器已停止")


class RoutingStrategy:
    """标准化路由策略"""
    
    def __init__(self, registry):
        self.registry = registry
        
    async def route_by_content(self, content: str, task_type: str, 
                             user_profile: Dict[str, Any], 
                             agent_profile: Dict[str, Any]) -> Optional[str]:
        """基于内容分析的智能路由 - 标准化版本"""
        content_lower = content.lower()

        # 🎯 Agent能力映射
        agent_capabilities = {
            "agent.code": ["programming", "technical"],
            "agent.analyze": ["analysis", "reasoning"], 
            "agent.summary": ["summary", "general"],
            "agent.translate": ["translation"],
            "agent.rewrite": ["rewriting", "creative"],
            "agent.qa": ["qa", "general"],
            "agent.default": ["general"]
        }

        # 🎯 基于任务类型的路由
        task_type_mapping = {
            "code": "agent.code",
            "programming": "agent.code",
            "analysis": "agent.analyze", 
            "summary": "agent.summary",
            "translation": "agent.translate",
            "rewriting": "agent.rewrite",
            "qa": "agent.qa"
        }

        if task_type and task_type in task_type_mapping:
            return task_type_mapping[task_type]

        # 🎯 基于内容关键词的路由
        routing_rules = [
            # 代码相关任务
            {
                "keywords": ["代码", "编程", "function", "class", "def", "python", "java", "javascript"],
                "agent": "agent.code"
            },
            # 推理分析任务  
            {
                "keywords": ["推理", "分析", "思考", "为什么", "how", "why", "原因", "解析"],
                "agent": "agent.analyze"
            },
            # 总结任务
            {
                "keywords": ["总结", "概括", "要点", "summary", "summarize"],
                "agent": "agent.summary"
            },
            # 翻译任务
            {
                "keywords": ["翻译", "translate", "英文", "中文", "language"],
                "agent": "agent.translate"
            },
            # 改写任务
            {
                "keywords": ["改写", "重写", "润色", "rewrite", "paraphrase"],
                "agent": "agent.rewrite"
            },
            # 问答任务
            {
                "keywords": ["什么", "如何", "怎么", "?", "？", "help", "帮助", "question"],
                "agent": "agent.qa"
            }
        ]

        for rule in routing_rules:
            if any(keyword in content_lower for keyword in rule["keywords"]):
                return rule["agent"]

        # 🎯 基于用户技术水平的路由
        technical_level = user_profile.get("technical_level")
        if technical_level == "expert":
            return "agent.analyze"
        elif technical_level == "beginner":
            return "agent.qa"

        # 🎯 默认路由
        return "agent.default"

    def _select_best_model(self, capabilities: List[str]) -> Optional[str]:
        """从具备指定能力的模型中选择最优的 - 向后兼容"""
        available_models = []
        for capability in capabilities:
            models = self.registry.get_models_by_capability(capability)
            available_models.extend(models)

        if available_models:
            return sorted(available_models, key=lambda x: x.priority, reverse=True)[0].model_id
        return None