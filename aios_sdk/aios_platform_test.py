#!/usr/bin/env python3
"""
AIOS平台完整流程测试 - 最终修复版本
"""

import sys
import os
import uuid
import datetime
import json
from typing import Dict, Any, List

# 添加SDK路径
sys.path.insert(0, os.path.dirname(__file__))

# 导入AIOS SDK
import agent_pb2
import inference_pb2
import envelope_pb2
import prompt_pb2
import vector_pb2

class AiosPlatformSimulator:
    """AIOS平台模拟器"""
    
    def __init__(self):
        self.session_id = f"sess_{uuid.uuid4().hex[:8]}"
        self.user_id = "user_001"
        self.tenant_id = "tenant_abc"
        
    def simulate_user_request(self, user_message: str) -> Dict[str, Any]:
        """模拟用户请求的完整流程"""
        print("🚀 开始模拟用户请求流程")
        print("=" * 60)
        
        # 1. 用户输入
        print(f"1. 📝 用户输入: '{user_message}'")
        user_input = self._create_user_input(user_message)
        
        # 2. API Gateway处理
        print("2. 🌐 API Gateway - 会话路由和鉴权")
        session_context = self._api_gateway_process(user_input)
        
        # 3. AI Agent Orchestrator处理
        print("3. 🧠 AI Agent Orchestrator - 智能编排")
        agent_decision = self._orchestrator_process(session_context)
        
        # 4. Prompt Engineering
        print("4. 🎯 Prompt Engine - 提示词工程")
        prompt_request = self._prompt_engineering(agent_decision, user_message)
        
        # 5. Memory检索
        print("5. 🧠 Memory Engine - 记忆检索")
        memory_context = self._memory_retrieval(session_context)
        
        # 6. RAG检索
        print("6. 📚 RAG Engine - 知识检索")
        rag_context = self._rag_retrieval(user_message)
        
        # 7. 模型推理
        print("7. 🤖 Model Inference - 模型调用")
        inference_result = self._model_inference(prompt_request, memory_context, rag_context)
        
        # 8. 结果处理
        print("8. 📦 Result Processing - 结果封装")
        final_response = self._process_result(inference_result, session_context)
        
        # 9. 返回用户
        print("9. ✅ 返回用户结果")
        return final_response
    
    def _create_user_input(self, message: str) -> envelope_pb2.Envelope:
        """创建用户输入信封"""
        # 创建用户配置
        user_profile = envelope_pb2.UserProfile(
            user_id=self.user_id,
            tenant_id=self.tenant_id,
            department="engineering",
            role="developer"
        )
        user_profile.permissions.extend(["rag", "model:qwen72b", "agent:assistant"])
        
        # 创建模型策略
        model_policy = envelope_pb2.ModelPolicy(
            default_model="qwen-7b",
            fallback_model="qwen-4b"
        )
        model_policy.allowed_models.extend(["qwen-7b", "qwen-4b", "qwen-2b"])
        
        # 创建Agent配置
        agent_profile = envelope_pb2.AgentProfile(
            subscribed_agents=["assistant.qa", "assistant.workflow"],
            routing_policy="intent_based"
        )
        agent_profile.model_policy.CopyFrom(model_policy)
        
        # 创建会话上下文
        session_context = envelope_pb2.SessionContext(
            context_window=4096,
            memory_policy="hot_cold_split"
        )
        session_context.enabled_features.extend(["memory", "rag", "multi_agent"])
        
        # 创建标准元数据
        metadata = envelope_pb2.StandardMetadata(
            request_id=f"req_{uuid.uuid4().hex[:8]}",
            timestamp=datetime.datetime.now().isoformat(),
            source_service="user_frontend",
            target_service="api_gateway",
            correlation_id=f"corr_{uuid.uuid4().hex[:8]}",
            version="1.0.0"
        )
        
        # 设置headers
        metadata.headers['x-user-id'] = self.user_id
        metadata.headers['x-tenant-id'] = self.tenant_id
        metadata.headers['x-department'] = "engineering"
        
        # 设置各个profile
        metadata.user_profile.CopyFrom(user_profile)
        metadata.agent_profile.CopyFrom(agent_profile)
        metadata.session_context.CopyFrom(session_context)
        
        # 创建信封
        envelope = envelope_pb2.Envelope(
            message_id=f"msg_{uuid.uuid4().hex[:8]}",
            message_type="user_input",
            payload=message.encode('utf-8'),
            metadata=metadata
        )
        
        return envelope
    
    def _api_gateway_process(self, user_input: envelope_pb2.Envelope) -> Dict[str, Any]:
        """API Gateway处理 - 会话路由和鉴权"""
        # 创建会话
        session = agent_pb2.Session(
            session_id=self.session_id,
            user_id=self.user_id,
            tenant_id=self.tenant_id,
            created_at=datetime.datetime.now().isoformat(),
            status=agent_pb2.SessionStatus.ACTIVE
        )
        
        # 创建任务
        task = agent_pb2.Task(
            task_id=f"task_{uuid.uuid4().hex[:8]}",
            session_id=self.session_id,
            message_seq=1,
            agent_id="orchestrator",
            goal="process_user_query",
            priority=agent_pb2.TaskPriority.NORMAL
        )
        
        # 复制metadata到task
        task.metadata.CopyFrom(user_input.metadata)
        
        return {
            "session": session,
            "task": task,
            "user_input": user_input
        }
    
    def _orchestrator_process(self, session_context: Dict[str, Any]) -> Dict[str, Any]:
        """AI Agent Orchestrator处理 - 智能编排"""
        task = session_context["task"]
        user_input = session_context["user_input"]
        
        # 意图识别（简化版）
        user_message = user_input.payload.decode('utf-8')
        intent = self._classify_intent(user_message)
        
        # Agent选择
        selected_agent = self._select_agent(intent)
        
        print(f"   🎯 意图识别: {intent}")
        print(f"   🤖 选择Agent: {selected_agent}")
        
        return {
            "intent": intent,
            "selected_agent": selected_agent,
            "task": task
        }
    
    def _prompt_engineering(self, agent_decision: Dict[str, Any], user_message: str) -> inference_pb2.InferenceRequest:
        """Prompt Engineering - 提示词工程"""
        agent_type = agent_decision["selected_agent"]
        
        # 根据Agent类型选择不同的提示词模板
        if agent_type == "assistant.qa":
            prompt_template = self._create_qa_prompt(user_message)
        elif agent_type == "assistant.workflow":
            prompt_template = self._create_workflow_prompt(user_message)
        else:
            prompt_template = self._create_general_prompt(user_message)
        
        # 创建推理请求 - 使用正确的字段
        request = inference_pb2.InferenceRequest(
            session_id=self.session_id,
            task_id=agent_decision["task"].task_id,
            model_id="qwen-7b",
            input_text=prompt_template
        )
        
        # 设置参数（如果parameters字段是map类型）
        request.parameters['max_tokens'] = '1000'
        request.parameters['temperature'] = '0.7'
        request.parameters['top_p'] = '0.9'
        
        print(f"   📝 构建提示词: {prompt_template[:100]}...")
        
        return request
    
    def _memory_retrieval(self, session_context: Dict[str, Any]) -> List[envelope_pb2.MemoryItem]:
        """Memory Engine - 记忆检索"""
        # 模拟记忆检索
        memories = [
            envelope_pb2.MemoryItem(
                id="mem_001",
                session_id=self.session_id,
                content="用户之前询问过AI相关的问题",
                type="conversation",
                timestamp=datetime.datetime.now().isoformat(),
                relevance_score=0.8
            )
        ]
        
        print(f"   📝 检索到 {len(memories)} 条相关记忆")
        return memories
    
    def _rag_retrieval(self, user_message: str) -> List[envelope_pb2.RetrievedDocument]:
        """RAG Engine - 知识检索"""
        # 模拟RAG检索
        docs = [
            envelope_pb2.RetrievedDocument(
                id="doc_001",
                content="AIOS平台是一个基于gRPC的AI PaaS平台，支持多Agent编排和模型调度。",
                source="platform_docs",
                similarity_score=0.9
            ),
            envelope_pb2.RetrievedDocument(
                id="doc_002", 
                content="平台提供完整的SDK和API，方便开发者集成和使用各种AI能力。",
                source="platform_docs",
                similarity_score=0.7
            )
        ]
        
        print(f"   📚 检索到 {len(docs)} 条相关知识")
        return docs
    
    def _model_inference(self, prompt_request: inference_pb2.InferenceRequest, 
                        memories: List[envelope_pb2.MemoryItem],
                        docs: List[envelope_pb2.RetrievedDocument]) -> inference_pb2.InferenceResponse:
        """Model Inference - 模型调用"""
        # 模拟模型推理
        response_text = self._simulate_llm_response(
            prompt_request.input_text,
            memories,
            docs
        )
        
        # 创建推理响应
        response = inference_pb2.InferenceResponse(
            session_id=self.session_id,
            task_id=prompt_request.task_id,
            output_text=response_text,
            model_used="qwen-7b",
            latency_ms=1250,
            cost_token=350,
            finish_reason="stop"
        )
        
        # 设置token使用情况
        response.token_usage.CopyFrom(envelope_pb2.TokenUsage(
            prompt_tokens=150,
            completion_tokens=200,
            total_tokens=350,
            estimated_cost=0.02
        ))
        
        # 添加解释信息
        response.explain_json = json.dumps({
            "reasoning": "基于用户查询和检索到的知识生成回答",
            "confidence": 0.85,
            "sources_used": [doc.id for doc in docs]
        })
        
        print(f"   🤖 模型响应生成完成 ({len(response_text)} 字符)")
        
        return response
    
    def _process_result(self, inference_result: inference_pb2.InferenceResponse,
                       session_context: Dict[str, Any]) -> Dict[str, Any]:
        """结果处理和封装"""
        task = session_context["task"]
        
        # 创建任务状态
        task_status = agent_pb2.TaskStatus(
            task_id=task.task_id,
            session_id=self.session_id,
            state="COMPLETED",
            output=inference_result.output_text,
            agent_used="assistant.qa",
            model_used=inference_result.model_used,
            processing_time=inference_result.latency_ms / 1000.0
        )
        
        task_status.token_usage.CopyFrom(inference_result.token_usage)
        
        return {
            "session_id": self.session_id,
            "task_id": task.task_id,
            "response": inference_result.output_text,
            "task_status": task_status,
            "metadata": {
                "model_used": inference_result.model_used,
                "latency_ms": inference_result.latency_ms,
                "token_usage": {
                    "total": inference_result.token_usage.total_tokens,
                    "cost": inference_result.token_usage.estimated_cost
                },
                "explanation": json.loads(inference_result.explain_json) if inference_result.explain_json else {}
            }
        }
    
    # 辅助方法
    def _classify_intent(self, message: str) -> str:
        """简化版意图分类"""
        message_lower = message.lower()
        if "如何" in message_lower or "怎么" in message_lower or "怎样" in message_lower:
            return "qa"
        elif "步骤" in message_lower or "流程" in message_lower or "方法" in message_lower:
            return "workflow"
        else:
            return "general"
    
    def _select_agent(self, intent: str) -> str:
        """根据意图选择Agent"""
        agent_map = {
            "qa": "assistant.qa",
            "workflow": "assistant.workflow", 
            "general": "assistant.general"
        }
        return agent_map.get(intent, "assistant.general")
    
    def _create_qa_prompt(self, user_message: str) -> str:
        """创建QA提示词"""
        return f"""你是一个专业的AI助手，专门回答技术问题。

用户问题: {user_message}

请提供详细、准确的技术指导，包括必要的步骤和注意事项。"""
    
    def _create_workflow_prompt(self, user_message: str) -> str:
        """创建工作流提示词"""
        return f"""你是一个流程指导专家，擅长将复杂任务分解为清晰的步骤。

用户需求: {user_message}

请提供分步骤的详细指导，确保每个步骤都具体可行。"""
    
    def _create_general_prompt(self, user_message: str) -> str:
        """创建通用提示词"""
        return f"""你是一个有帮助的AI助手。

用户请求: {user_message}

请提供清晰、有用的回答，帮助用户解决问题。"""
    
    def _simulate_llm_response(self, prompt: str, memories: List, docs: List) -> str:
        """模拟LLM响应"""
        # 基于提示词内容生成模拟响应
        user_message = prompt.split("用户")[1].split(":")[1].strip() if "用户" in prompt else prompt
        
        if "如何" in user_message or "怎么" in user_message:
            return f"""关于"{user_message}"，我为您提供以下指导：

1. **理解基础概念**：首先熟悉AIOS平台的核心组件和架构
2. **环境准备**：配置开发环境，安装必要的SDK和工具链
3. **实践示例**：从简单的示例开始，逐步掌握平台使用方法
4. **项目应用**：将学到的知识应用到实际项目中

AIOS平台提供了完整的文档和示例代码，您可以在官方文档中找到详细的使用指南。平台支持多Agent协作、模型调度、记忆管理等功能，能够满足各种AI应用开发需求。"""
        
        elif "步骤" in user_message or "流程" in user_message:
            return f"""完成"{user_message}"的具体步骤如下：

**步骤1: 需求分析**
- 明确任务目标和预期结果
- 确定所需的数据和资源

**步骤2: 方案设计**  
- 设计处理流程和数据流
- 选择合适的Agent和模型

**步骤3: 实施执行**
- 配置任务参数和环境
- 执行处理流程

**步骤4: 结果验证**
- 检查处理结果的准确性
- 优化和调整方案

每个步骤都有相应的工具和支持，AIOS平台会协助您完成整个流程。"""
        
        else:
            return f"""AIOS平台是一个功能强大的AI PaaS平台，主要特点包括：

• **多Agent编排**：支持多种AI Agent的协同工作
• **模型调度**：智能选择最适合的AI模型
• **记忆管理**：提供短期和长期记忆能力  
• **知识检索**：集成RAG系统，增强回答准确性
• **可扩展架构**：易于集成新的AI能力和服务

平台适用于各种AI应用场景，包括智能客服、内容生成、数据分析等。通过标准化的API和SDK，开发者可以快速构建和部署AI应用。"""

def main():
    """主测试函数"""
    print("🤖 AIOS平台完整流程测试")
    print("=" * 50)
    
    # 创建平台模拟器
    platform = AiosPlatformSimulator()
    
    # 测试用例
    test_cases = [
        "如何使用AIOS平台开发AI应用？",
        "完成一个数据处理任务的步骤是什么？",
        "介绍一下AIOS平台的主要功能",
        "怎样在AIOS平台上配置一个新的Agent？"
    ]
    
    successful_tests = 0
    total_tests = len(test_cases)
    
    for i, user_message in enumerate(test_cases, 1):
        print(f"\n📋 测试用例 {i}/{total_tests}: {user_message}")
        print("-" * 50)
        
        try:
            result = platform.simulate_user_request(user_message)
            successful_tests += 1
            
            print(f"\n🎯 最终结果:")
            print(f"   会话ID: {result['session_id']}")
            print(f"   任务ID: {result['task_id']}") 
            print(f"   使用模型: {result['metadata']['model_used']}")
            print(f"   响应延迟: {result['metadata']['latency_ms']}ms")
            print(f"   Token使用: {result['metadata']['token_usage']['total']}")
            print(f"   估计成本: ${result['metadata']['token_usage']['cost']:.4f}")
            print(f"\n💬 响应内容:")
            print(f"   {result['response']}")
            
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 50)
    print(f"📊 测试结果: {successful_tests}/{total_tests} 通过")
    if successful_tests == total_tests:
        print("🎉 所有测试用例执行成功！")
        print("💡 AIOS平台SDK和消息流程工作正常")
    else:
        print("⚠️  部分测试用例失败，请检查错误信息")

if __name__ == "__main__":
    main()