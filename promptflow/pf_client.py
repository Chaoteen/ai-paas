# /mnt/d/RD/ai-os/promptflow/pf_client.py
import aiohttp
import json
import logging
import asyncio
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import uuid

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class UserProfile:
    """标准化用户档案"""
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None
    department: Optional[str] = None
    role: Optional[str] = None
    permissions: List[str] = None
    technical_level: Optional[str] = None
    preferred_language: Optional[str] = "zh-CN"
    
    def __post_init__(self):
        if self.permissions is None:
            self.permissions = ["default_access"]

@dataclass
class AgentProfile:
    """标准化Agent档案"""
    agent_id: Optional[str] = None
    subscribed_agents: List[str] = None
    routing_policy: str = "langgraph_priority"
    model_policy: Dict[str, Any] = None
    specialization: Optional[str] = None
    style: str = "professional"
    
    def __post_init__(self):
        if self.subscribed_agents is None:
            self.subscribed_agents = ["agent.default"]
        if self.model_policy is None:
            self.model_policy = {
                "default_model": "qwen-8b",
                "temperature": 0.2,
                "max_tokens": 2048
            }

@dataclass
class MemoryItem:
    """记忆项"""
    role: str  # user, assistant, system
    content: str
    timestamp: float
    type: str = "hot"  # hot, cold, event
    
    def to_dict(self):
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "type": self.type
        }

@dataclass
class RetrievedDocument:
    """检索文档"""
    id: str
    content: str
    source: str
    score: float
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self):
        return {
            "id": self.id,
            "content": self.content,
            "source": self.source,
            "score": self.score,
            "metadata": self.metadata
        }

@dataclass
class PromptFlowInput:
    """标准化PromptFlow输入结构"""
    user_message: str
    user_profile: UserProfile
    agent_profile: AgentProfile
    memory_hot: List[MemoryItem]
    memory_cold: List[MemoryItem]
    retrieved_docs: List[RetrievedDocument]
    system_context: Dict[str, Any] = None
    task_id: Optional[str] = None
    session_id: Optional[str] = None
    
    def __post_init__(self):
        if self.system_context is None:
            self.system_context = {
                "current_time": time.time(),
                "api_version": "1.0",
                "deployment_env": "production"
            }
    
    def to_api_input(self) -> Dict[str, Any]:
        """转换为API请求格式"""
        return {
            "user_message": self.user_message,
            "user_profile": {
                "user_id": self.user_profile.user_id,
                "tenant_id": self.user_profile.tenant_id,
                "department": self.user_profile.department,
                "role": self.user_profile.role,
                "permissions": self.user_profile.permissions,
                "technical_level": self.user_profile.technical_level,
                "preferred_language": self.user_profile.preferred_language
            },
            "agent_profile": {
                "agent_id": self.agent_profile.agent_id,
                "subscribed_agents": self.agent_profile.subscribed_agents,
                "routing_policy": self.agent_profile.routing_policy,
                "model_policy": self.agent_profile.model_policy,
                "specialization": self.agent_profile.specialization,
                "style": self.agent_profile.style
            },
            "memory_hot": [item.to_dict() for item in self.memory_hot],
            "memory_cold": [item.to_dict() for item in self.memory_cold],
            "retrieved_docs": [doc.to_dict() for doc in self.retrieved_docs],
            "system_context": self.system_context,
            "task_id": self.task_id,
            "session_id": self.session_id
        }

@dataclass
class PromptFlowOutput:
    """标准化PromptFlow输出结构"""
    final_prompt: str
    enhanced_message: str
    metadata: Dict[str, Any]
    processing_time: float
    trace_id: str
    
    @classmethod
    def from_api_response(cls, response_data: Dict[str, Any]) -> 'PromptFlowOutput':
        """从API响应创建输出对象"""
        return cls(
            final_prompt=response_data.get("final_prompt", ""),
            enhanced_message=response_data.get("enhanced_message", ""),
            metadata=response_data.get("metadata", {}),
            processing_time=response_data.get("processing_time", 0.0),
            trace_id=response_data.get("trace_id", str(uuid.uuid4()))
        )

class PromptFlowClient:
    """标准化PromptFlow客户端"""
    
    def __init__(self, base_url: str = "http://localhost:8081", timeout: int = 30):
        self.base_url = base_url
        self.score_url = f"{base_url}/score"
        self.health_url = f"{base_url}/health"
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        await self.ensure_session()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        
    async def ensure_session(self):
        """确保会话存在"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(timeout=self.timeout)
            
    async def close(self):
        """关闭会话"""
        if self.session and not self.session.closed:
            await self.session.close()
            
    async def health_check(self) -> bool:
        """健康检查"""
        try:
            await self.ensure_session()
            async with self.session.get(self.health_url) as response:
                return response.status == 200
        except Exception as e:
            logger.warning(f"PromptFlow健康检查失败: {e}")
            return False
            
    async def execute_flow(self, inputs: Dict[str, Any]) -> PromptFlowOutput:
        """
        执行PromptFlow流程 - 标准化版本
        
        Args:
            inputs: 标准化输入数据，支持多种格式：
                   - PromptFlowInput 对象
                   - 标准化字典格式
                   - 向后兼容的旧格式
        
        Returns:
            PromptFlowOutput: 标准化输出
        """
        start_time = time.time()
        trace_id = str(uuid.uuid4())
        
        try:
            # 🎯 标准化输入处理
            standardized_inputs = self._standardize_inputs(inputs, trace_id)
            
            logger.info(f"🔄 PromptFlow处理开始: trace_id={trace_id}, session={standardized_inputs.get('session_id')}")
            
            await self.ensure_session()
            async with self.session.post(
                self.score_url,
                json=standardized_inputs,
                headers={"Content-Type": "application/json"}
            ) as response:
                
                processing_time = time.time() - start_time
                
                if response.status == 200:
                    response_data = await response.json()
                    
                    # 🎯 创建标准化输出
                    output = PromptFlowOutput.from_api_response(response_data)
                    output.processing_time = processing_time
                    
                    logger.info(f"✅ PromptFlow处理成功: trace_id={trace_id}, 耗时: {processing_time:.2f}s")
                    return output
                    
                else:
                    error_text = await response.text()
                    error_msg = f"PromptFlow调用失败: {response.status} - {error_text}"
                    logger.error(f"❌ {error_msg}")
                    raise Exception(error_msg)
                    
        except asyncio.TimeoutError:
            processing_time = time.time() - start_time
            error_msg = f"PromptFlow服务调用超时: {self.timeout}s"
            logger.error(f"❌ {error_msg}")
            raise Exception(error_msg)
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"❌ PromptFlow服务调用异常: {e}")
            raise
            
    def _standardize_inputs(self, inputs: Any, trace_id: str) -> Dict[str, Any]:
        """标准化输入数据"""
        
        # 🎯 如果已经是PromptFlowInput对象
        if isinstance(inputs, PromptFlowInput):
            api_input = inputs.to_api_input()
            api_input["trace_id"] = trace_id
            return api_input
            
        # 🎯 如果是字典格式，进行标准化转换
        elif isinstance(inputs, dict):
            return self._convert_legacy_format(inputs, trace_id)
            
        # 🎯 其他格式不支持
        else:
            raise ValueError(f"不支持的输入格式: {type(inputs)}")
            
    def _convert_legacy_format(self, legacy_inputs: Dict[str, Any], trace_id: str) -> Dict[str, Any]:
        """转换旧格式到标准化格式"""
        
        # 🎯 提取用户消息
        user_message = legacy_inputs.get('user_message') or legacy_inputs.get('content') or legacy_inputs.get('name', '')
        
        # 🎯 构建用户档案
        user_profile_data = legacy_inputs.get('user_profile') or {}
        if not user_profile_data and 'metadata' in legacy_inputs:
            user_profile_data = legacy_inputs['metadata'].get('user_profile', {})
            
        user_profile = UserProfile(
            user_id=user_profile_data.get('user_id'),
            tenant_id=user_profile_data.get('tenant_id'),
            department=user_profile_data.get('department'),
            role=user_profile_data.get('role'),
            permissions=user_profile_data.get('permissions'),
            technical_level=user_profile_data.get('technical_level')
        )
        
        # 🎯 构建Agent档案
        agent_profile_data = legacy_inputs.get('agent_profile') or {}
        if not agent_profile_data and 'metadata' in legacy_inputs:
            agent_profile_data = legacy_inputs['metadata'].get('agent_profile', {})
            
        agent_profile = AgentProfile(
            agent_id=agent_profile_data.get('agent_id'),
            subscribed_agents=agent_profile_data.get('subscribed_agents'),
            routing_policy=agent_profile_data.get('routing_policy'),
            model_policy=agent_profile_data.get('model_policy'),
            specialization=agent_profile_data.get('specialization')
        )
        
        # 🎯 构建记忆数据
        memory_hot = [MemoryItem(**item) for item in legacy_inputs.get('memory_hot', [])]
        memory_cold = [MemoryItem(**item) for item in legacy_inputs.get('memory_cold', [])]
        
        # 🎯 构建检索文档
        retrieved_docs = [RetrievedDocument(**doc) for doc in legacy_inputs.get('retrieved_docs', [])]
        
        # 🎯 创建标准化输入
        standardized_input = PromptFlowInput(
            user_message=user_message,
            user_profile=user_profile,
            agent_profile=agent_profile,
            memory_hot=memory_hot,
            memory_cold=memory_cold,
            retrieved_docs=retrieved_docs,
            task_id=legacy_inputs.get('task_id'),
            session_id=legacy_inputs.get('session_id')
        )
        
        api_input = standardized_input.to_api_input()
        api_input["trace_id"] = trace_id
        api_input["_legacy_converted"] = True  # 标记为转换的旧格式
        
        return api_input
        
    async def batch_execute_flow(self, inputs_list: List[Dict[str, Any]]) -> List[PromptFlowOutput]:
        """批量执行PromptFlow流程"""
        tasks = [self.execute_flow(inputs) for inputs in inputs_list]
        return await asyncio.gather(*tasks, return_exceptions=True)
        
    def create_default_input(self, user_message: str, **kwargs) -> PromptFlowInput:
        """创建默认的标准化输入"""
        user_profile = UserProfile(**kwargs.get('user_profile', {}))
        agent_profile = AgentProfile(**kwargs.get('agent_profile', {}))
        
        return PromptFlowInput(
            user_message=user_message,
            user_profile=user_profile,
            agent_profile=agent_profile,
            memory_hot=[],
            memory_cold=[],
            retrieved_docs=[],
            task_id=kwargs.get('task_id'),
            session_id=kwargs.get('session_id')
        )


# 🎯 创建全局客户端实例（保持向后兼容）
pf_client = PromptFlowClient()

# 🎯 向后兼容的简化接口
async def execute_flow(inputs: dict) -> dict:
    """
    向后兼容的简化接口
    注意：返回的是原始字典格式，不是PromptFlowOutput对象
    """
    client = PromptFlowClient()
    try:
        output = await client.execute_flow(inputs)
        # 转换为旧格式以保持兼容性
        return {
            "greeting": output.enhanced_message or output.final_prompt,
            "final_prompt": output.final_prompt,
            "metadata": output.metadata,
            "processing_time": output.processing_time,
            "trace_id": output.trace_id
        }
    finally:
        await client.close()


async def test_standardized_client():
    """测试标准化客户端"""
    client = PromptFlowClient()
    
    # 🎯 测试1: 使用标准化输入对象
    user_profile = UserProfile(
        user_id="user_123",
        department="engineering",
        technical_level="expert"
    )
    
    agent_profile = AgentProfile(
        agent_id="assistant.qa",
        specialization="技术问答"
    )
    
    standardized_input = PromptFlowInput(
        user_message="如何优化Python代码性能？",
        user_profile=user_profile,
        agent_profile=agent_profile,
        memory_hot=[],
        memory_cold=[],
        retrieved_docs=[],
        task_id="test_task_001",
        session_id="test_session_001"
    )
    
    try:
        result = await client.execute_flow(standardized_input)
        print("🎯 标准化客户端测试结果:")
        print(f"  最终Prompt: {result.final_prompt[:100]}...")
        print(f"  增强消息: {result.enhanced_message[:100]}...")
        print(f"  处理时间: {result.processing_time:.2f}s")
        print(f"  追踪ID: {result.trace_id}")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
    
    finally:
        await client.close()


async def test_backward_compatibility():
    """测试向后兼容性"""
    # 🎯 测试旧格式输入
    legacy_input = {
        "name": "测试用户",
        "content": "如何学习机器学习？",
        "task_type": "qa",
        "user_context": "有一定编程基础"
    }
    
    try:
        result = await execute_flow(legacy_input)
        print("🔄 向后兼容测试结果:", result.get("greeting", ""))

        # 🎯 测试标准化字典格式
        standardized_dict_input = {
            "user_message": "Python装饰器的作用是什么？",
            "user_profile": {
                "user_id": "test_user",
                "department": "engineering"
            },
            "agent_profile": {
                "agent_id": "assistant.qa",
                "subscribed_agents": ["assistant.qa", "agent.code"]
            },
            "memory_hot": [],
            "memory_cold": [],
            "retrieved_docs": []
        }
        
        result2 = await execute_flow(standardized_dict_input)
        print("📝 标准化字典测试结果:", result2.get("greeting", ""))

    except Exception as e:
        print(f"❌ 兼容性测试失败: {e}")


if __name__ == "__main__":
    print("🚀 开始测试标准化PromptFlow客户端...")
    
    # 运行测试
    asyncio.run(test_standardized_client())
    asyncio.run(test_backward_compatibility())