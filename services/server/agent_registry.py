# server/agent_registry.py
from collections import defaultdict
from typing import Dict, List, Optional, Set, Any
import time
import logging
import threading
from dataclasses import dataclass, field
from enum import Enum
import uuid

logger = logging.getLogger(__name__)

class AgentStatus(Enum):
    """Agent状态枚举"""
    ONLINE = "online"
    OFFLINE = "offline" 
    BUSY = "busy"
    MAINTENANCE = "maintenance"
    ERROR = "error"

class LoadLevel(Enum):
    """负载级别"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class ResourceRequirements:
    """资源需求"""
    cpu_request: str = "100m"
    cpu_limit: str = "500m"
    memory_request: str = "512Mi"
    memory_limit: str = "2Gi"
    gpu_type: str = ""
    gpu_count: int = 0
    custom_resources: Dict[str, str] = field(default_factory=dict)

@dataclass
class AgentCapabilities:
    """Agent能力定义"""
    task_types: List[str] = field(default_factory=list)
    languages: List[str] = field(default_factory=list)
    context_window: int = 4096
    supports_streaming: bool = False
    supports_tools: bool = False
    supports_vision: bool = False
    supports_audio: bool = False
    specializations: List[str] = field(default_factory=list)
    custom_capabilities: Dict[str, str] = field(default_factory=dict)

@dataclass
class PerformanceMetrics:
    """性能指标"""
    p50_latency: float = 0.0
    p95_latency: float = 0.0
    p99_latency: float = 0.0
    throughput: float = 0.0  # 请求/秒
    error_rate: float = 0.0
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    custom_metrics: Dict[str, str] = field(default_factory=dict)

@dataclass
class ResourceUsage:
    """资源使用情况"""
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    gpu_usage: float = 0.0
    active_connections: int = 0
    current_tasks: int = 0
    custom_metrics: Dict[str, str] = field(default_factory=dict)

@dataclass
class AgentSpec:
    """标准化Agent规格定义"""
    agent_id: str
    name: str
    version: str = "1.0.0"
    endpoint: str = ""
    capabilities: AgentCapabilities = field(default_factory=AgentCapabilities)
    priority: int = 1
    status: AgentStatus = AgentStatus.ONLINE
    tenant_id: str = "default"
    
    # 🎯 新增企业级字段
    resource_requirements: ResourceRequirements = field(default_factory=ResourceRequirements)
    performance_metrics: PerformanceMetrics = field(default_factory=PerformanceMetrics)
    resource_usage: ResourceUsage = field(default_factory=ResourceUsage)
    
    # 🎯 部署配置
    deployment_type: str = "realtime"  # realtime, batch, on-demand
    min_replicas: int = 1
    max_replicas: int = 3
    scaling_policy: Dict[str, Any] = field(default_factory=dict)
    
    # 🎯 元数据
    metadata: Dict[str, str] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_heartbeat: float = field(default_factory=time.time)
    
    def get_load_level(self) -> LoadLevel:
        """获取当前负载级别"""
        load_factor = self.resource_usage.current_tasks / self.max_replicas if self.max_replicas > 0 else 0
        
        if load_factor >= 0.8:
            return LoadLevel.CRITICAL
        elif load_factor >= 0.6:
            return LoadLevel.HIGH
        elif load_factor >= 0.4:
            return LoadLevel.MEDIUM
        else:
            return LoadLevel.LOW
    
    def is_available(self) -> bool:
        """检查Agent是否可用"""
        return (self.status == AgentStatus.ONLINE and 
                self.get_load_level() != LoadLevel.CRITICAL and
                time.time() - self.last_heartbeat < 300)  # 5分钟超时
    
    def update_heartbeat(self):
        """更新心跳"""
        self.last_heartbeat = time.time()
    
    def update_metrics(self, processing_time: float, success: bool = True):
        """更新性能指标"""
        self.performance_metrics.total_requests += 1
        if success:
            self.performance_metrics.successful_requests += 1
        else:
            self.performance_metrics.failed_requests += 1
        
        # 更新错误率
        total = self.performance_metrics.total_requests
        failed = self.performance_metrics.failed_requests
        self.performance_metrics.error_rate = failed / total if total > 0 else 0.0
        
        # 更新吞吐量（简化计算）
        self.performance_metrics.throughput = total / (time.time() - self.created_at) if time.time() > self.created_at else 0.0

class AgentRegistry:
    """标准化Agent注册表 - 支持多租户和企业级功能"""
    
    def __init__(self):
        self.agent_registry: Dict[str, AgentSpec] = {}
        self.capability_index: Dict[str, List[str]] = defaultdict(list)
        self.tenant_index: Dict[str, Set[str]] = defaultdict(set)
        self.task_type_index: Dict[str, List[str]] = defaultdict(list)
        
        # 🎯 新增索引
        self.specialization_index: Dict[str, List[str]] = defaultdict(list)
        self.language_index: Dict[str, List[str]] = defaultdict(list)
        
        # 🎯 线程安全
        self._lock = threading.RLock()
        
        # 🎯 统计信息
        self.registry_stats = {
            "total_agents": 0,
            "online_agents": 0,
            "total_tenants": 0,
            "last_updated": time.time()
        }
        
        logger.info("✅ 标准化Agent注册表初始化完成")

    def register_agent(self, agent_spec: AgentSpec) -> bool:
        """注册标准化Agent"""
        with self._lock:
            try:
                # 🎯 验证Agent规格
                if not self._validate_agent_spec(agent_spec):
                    logger.error(f"❌ Agent规格验证失败: {agent_spec.agent_id}")
                    return False
                
                # 🎯 检查是否已存在
                if agent_spec.agent_id in self.agent_registry:
                    logger.warning(f"🔄 更新已存在的Agent: {agent_spec.agent_id}")
                
                # 🎯 注册Agent
                self.agent_registry[agent_spec.agent_id] = agent_spec
                
                # 🎯 更新索引
                self._update_indexes(agent_spec)
                
                # 🎯 更新统计
                self._update_stats()
                
                logger.info(f"✅ 注册标准化Agent: {agent_spec.agent_id} "
                          f"(租户: {agent_spec.tenant_id}, 能力: {len(agent_spec.capabilities.task_types)})")
                return True
                
            except Exception as e:
                logger.error(f"❌ 注册Agent失败 {agent_spec.agent_id}: {e}")
                return False

    def _validate_agent_spec(self, agent_spec: AgentSpec) -> bool:
        """验证Agent规格"""
        if not agent_spec.agent_id or not agent_spec.agent_id.startswith("agent."):
            logger.error(f"❌ Agent ID格式无效: {agent_spec.agent_id}")
            return False
            
        if not agent_spec.tenant_id:
            logger.error(f"❌ 租户ID不能为空: {agent_spec.agent_id}")
            return False
            
        if not agent_spec.capabilities.task_types:
            logger.warning(f"⚠️ Agent没有定义任务类型: {agent_spec.agent_id}")
            
        return True

    def _update_indexes(self, agent_spec: AgentSpec):
        """更新所有索引"""
        agent_id = agent_spec.agent_id
        
        # 🎯 能力索引
        for capability in agent_spec.capabilities.task_types:
            if agent_id not in self.capability_index[capability]:
                self.capability_index[capability].append(agent_id)
        
        # 🎯 租户索引
        self.tenant_index[agent_spec.tenant_id].add(agent_id)
        
        # 🎯 任务类型索引
        for task_type in agent_spec.capabilities.task_types:
            if agent_id not in self.task_type_index[task_type]:
                self.task_type_index[task_type].append(agent_id)
        
        # 🎯 专业领域索引
        for specialization in agent_spec.capabilities.specializations:
            if agent_id not in self.specialization_index[specialization]:
                self.specialization_index[specialization].append(agent_id)
        
        # 🎯 语言索引
        for language in agent_spec.capabilities.languages:
            if agent_id not in self.language_index[language]:
                self.language_index[language].append(agent_id)

    def get_agent(self, agent_id: str) -> Optional[AgentSpec]:
        """获取Agent规格"""
        with self._lock:
            agent = self.agent_registry.get(agent_id)
            if agent and agent.is_available():
                return agent
            return None

    def get_agents_by_capability(self, capability: str, tenant_id: str = None) -> List[AgentSpec]:
        """根据能力获取可用Agent列表"""
        with self._lock:
            agent_ids = self.capability_index.get(capability, [])
            agents = []
            
            for agent_id in agent_ids:
                agent = self.agent_registry.get(agent_id)
                if (agent and 
                    agent.is_available() and 
                    (tenant_id is None or agent.tenant_id == tenant_id)):
                    agents.append(agent)
            
            # 🎯 按优先级和负载排序
            agents.sort(key=lambda x: (x.priority, -x.get_load_level().value))
            return agents

    def get_agents_by_task_type(self, task_type: str, tenant_id: str = None) -> List[AgentSpec]:
        """根据任务类型获取Agent"""
        return self.get_agents_by_capability(task_type, tenant_id)

    def query_agents(self, 
                    capabilities: List[str] = None,
                    task_type: str = None,
                    tenant_id: str = None,
                    specialization: str = None,
                    language: str = None,
                    max_load: LoadLevel = LoadLevel.HIGH) -> List[AgentSpec]:
        """高级查询Agent"""
        with self._lock:
            candidate_agents = set()
            
            # 🎯 基于能力查询
            if capabilities:
                for capability in capabilities:
                    agents = self.get_agents_by_capability(capability, tenant_id)
                    candidate_agents.update(agents)
            
            # 🎯 基于任务类型查询
            if task_type:
                agents = self.get_agents_by_task_type(task_type, tenant_id)
                candidate_agents.update(agents)
            
            # 🎯 基于专业领域查询
            if specialization:
                agent_ids = self.specialization_index.get(specialization, [])
                for agent_id in agent_ids:
                    agent = self.get_agent(agent_id)
                    if agent and (tenant_id is None or agent.tenant_id == tenant_id):
                        candidate_agents.add(agent)
            
            # 🎯 基于语言查询
            if language:
                agent_ids = self.language_index.get(language, [])
                for agent_id in agent_ids:
                    agent = self.get_agent(agent_id)
                    if agent and (tenant_id is None or agent.tenant_id == tenant_id):
                        candidate_agents.add(agent)
            
            # 🎯 如果没有查询条件，返回所有可用Agent
            if not any([capabilities, task_type, specialization, language]):
                candidate_agents = {agent for agent in self.agent_registry.values() 
                                  if agent.is_available() and
                                  (tenant_id is None or agent.tenant_id == tenant_id)}
            
            # 🎯 过滤负载
            filtered_agents = [agent for agent in candidate_agents 
                             if agent.get_load_level().value <= max_load.value]
            
            # 🎯 排序：优先级 > 负载 > 响应时间
            filtered_agents.sort(key=lambda x: (
                x.priority, 
                -x.get_load_level().value,
                x.performance_metrics.p50_latency
            ))
            
            return filtered_agents

    def update_agent_status(self, agent_id: str, status: AgentStatus, reason: str = "") -> bool:
        """更新Agent状态"""
        with self._lock:
            agent = self.agent_registry.get(agent_id)
            if not agent:
                logger.error(f"❌ 更新状态失败，Agent不存在: {agent_id}")
                return False
            
            old_status = agent.status
            agent.status = status
            logger.info(f"🔄 更新Agent状态: {agent_id} {old_status.value} -> {status.value} ({reason})")
            
            self._update_stats()
            return True

    def update_agent_heartbeat(self, agent_id: str) -> bool:
        """更新Agent心跳"""
        with self._lock:
            agent = self.agent_registry.get(agent_id)
            if not agent:
                return False
            
            agent.update_heartbeat()
            return True

    def record_agent_metrics(self, agent_id: str, processing_time: float, success: bool = True) -> bool:
        """记录Agent性能指标"""
        with self._lock:
            agent = self.agent_registry.get(agent_id)
            if not agent:
                return False
            
            agent.update_metrics(processing_time, success)
            
            # 🎯 更新延迟指标（简化版）
            if success:
                # 这里可以实现更复杂的延迟统计
                agent.performance_metrics.p50_latency = processing_time
            
            return True

    def increment_agent_tasks(self, agent_id: str) -> bool:
        """增加Agent任务计数"""
        with self._lock:
            agent = self.agent_registry.get(agent_id)
            if not agent:
                return False
            
            agent.resource_usage.current_tasks += 1
            return True

    def decrement_agent_tasks(self, agent_id: str) -> bool:
        """减少Agent任务计数"""
        with self._lock:
            agent = self.agent_registry.get(agent_id)
            if not agent:
                return False
            
            if agent.resource_usage.current_tasks > 0:
                agent.resource_usage.current_tasks -= 1
            return True

    def list_agents(self, tenant_id: str = None, include_offline: bool = False) -> List[str]:
        """列出Agent ID列表"""
        with self._lock:
            if tenant_id:
                agents = list(self.tenant_index.get(tenant_id, set()))
            else:
                agents = list(self.agent_registry.keys())
            
            if not include_offline:
                agents = [agent_id for agent_id in agents 
                         if self.agent_registry[agent_id].is_available()]
            
            return agents

    def get_tenant_agents(self, tenant_id: str) -> List[AgentSpec]:
        """获取租户的所有Agent"""
        with self._lock:
            agent_ids = self.tenant_index.get(tenant_id, set())
            agents = [self.agent_registry[agent_id] for agent_id in agent_ids 
                     if agent_id in self.agent_registry]
            return agents

    def _update_stats(self):
        """更新注册表统计信息"""
        total_agents = len(self.agent_registry)
        online_agents = sum(1 for agent in self.agent_registry.values() 
                           if agent.status == AgentStatus.ONLINE and agent.is_available())
        total_tenants = len(self.tenant_index)
        
        self.registry_stats.update({
            "total_agents": total_agents,
            "online_agents": online_agents,
            "total_tenants": total_tenants,
            "last_updated": time.time()
        })

    def get_registry_stats(self) -> Dict[str, Any]:
        """获取注册表统计信息"""
        with self._lock:
            return self.registry_stats.copy()

    def get_agent_stats(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """获取Agent详细统计信息"""
        with self._lock:
            agent = self.agent_registry.get(agent_id)
            if not agent:
                return None
            
            return {
                "agent_id": agent.agent_id,
                "status": agent.status.value,
                "load_level": agent.get_load_level().value,
                "tenant_id": agent.tenant_id,
                "performance_metrics": {
                    "total_requests": agent.performance_metrics.total_requests,
                    "successful_requests": agent.performance_metrics.successful_requests,
                    "failed_requests": agent.performance_metrics.failed_requests,
                    "error_rate": agent.performance_metrics.error_rate,
                    "throughput": agent.performance_metrics.throughput,
                    "p50_latency": agent.performance_metrics.p50_latency
                },
                "resource_usage": {
                    "current_tasks": agent.resource_usage.current_tasks,
                    "active_connections": agent.resource_usage.active_connections,
                    "cpu_usage": agent.resource_usage.cpu_usage,
                    "memory_usage": agent.resource_usage.memory_usage
                },
                "last_heartbeat": agent.last_heartbeat,
                "availability": agent.is_available()
            }

    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        with self._lock:
            now = time.time()
            stale_agents = []
            
            for agent_id, agent in self.agent_registry.items():
                if now - agent.last_heartbeat > 300:  # 5分钟无心跳
                    stale_agents.append(agent_id)
                    if agent.status == AgentStatus.ONLINE:
                        agent.status = AgentStatus.OFFLINE
            
            return {
                "healthy": len(stale_agents) == 0,
                "total_agents": self.registry_stats["total_agents"],
                "online_agents": self.registry_stats["online_agents"],
                "stale_agents": stale_agents,
                "total_tenants": self.registry_stats["total_tenants"]
            }

# 🎯 向后兼容的包装器
class ModelSpec:
    """向后兼容的ModelSpec类"""
    def __init__(self, model_id, model_type, endpoint, capabilities, priority=1, status="online"):
        self.model_id = model_id
        self.model_type = model_type
        self.endpoint = endpoint  
        self.capabilities = capabilities
        self.priority = priority
        self.status = status

# 🎯 全局注册表实例
global_registry = AgentRegistry()