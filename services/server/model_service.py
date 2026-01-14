import asyncio
import json
import logging
import time
import uuid
from typing import Dict, Any, Optional
import aiohttp

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


class ModelService:
    """标准化模型服务封装 - 支持多模型和标准化消息格式"""

    def __init__(self, bus):
        self.bus = bus
        self.model_identity = "deepseek-r1-latest"
        self.initialized = False
        
        # 🎯 模型配置
        self.model_configs = {
            "deepseek-r1-latest": {
                "api_url": "https://api.deepseek.com/v1/chat/completions",
                "max_tokens": 2048,
                "temperature": 0.2,
                "timeout": 30
            },
            "qwen-8b": {
                "api_url": "https://api.qwen.ai/v1/chat/completions", 
                "max_tokens": 2048,
                "temperature": 0.3,
                "timeout": 30
            }
        }
        
        # 🎯 服务统计
        self.service_stats = {
            "total_requests": 0,
            "successful_responses": 0,
            "failed_responses": 0,
            "total_processing_time": 0.0,
            "total_tokens_used": 0
        }
        
        # 🎯 HTTP会话
        self.http_session: Optional[aiohttp.ClientSession] = None

    async def initialize(self):
        """初始化模型服务，订阅对应 topic"""
        if not self.initialized:
            # 🎯 创建HTTP会话
            self.http_session = aiohttp.ClientSession()
            
            # 🎯 订阅标准化消息通道
            await self.bus.subscribe_stream(f"agent.model.{self.model_identity}", self.on_task)
            logger.info(f"✅ 注册标准化处理器到主题: agent.model.{self.model_identity}")
            self.initialized = True

    async def on_task(self, msg_id, processing_context: Dict[str, Any]):
        """异步回调处理任务 - 标准化版本"""
        start_time = time.time()
        
        try:
            # 🎯 提取标准化字段
            session_id = processing_context["session_id"]
            task_id = processing_context["task_id"] 
            message_seq = processing_context["message_seq"]
            metadata = processing_context["metadata"]
            raw_data = processing_context["raw_data"]
            
            logger.info(f"[ModelService] 🧩 收到标准化任务: session={session_id}, task={task_id}, seq={message_seq}")
            
            # 🎯 更新统计
            self.service_stats["total_requests"] += 1
            
            # 🎯 准备模型输入
            model_input = self._prepare_model_input(processing_context)
            
            # 🎯 调用模型API
            model_output = await self._call_model_api(model_input)
            
            # 🎯 创建标准化结果
            result_data = self._create_standardized_result(processing_context, model_output, start_time)
            
            # 🎯 发布标准化结果
            await self.bus.publish("agent.result.stream", result_data, metadata)
            
            # 🎯 更新成功统计
            self.service_stats["successful_responses"] += 1
            processing_time = time.time() - start_time
            self.service_stats["total_processing_time"] += processing_time
            self.service_stats["total_tokens_used"] += model_output.get("token_usage", {}).get("total_tokens", 0)
            
            logger.info(f"[ModelService] ✅ 模型处理完成: {task_id}, 耗时: {processing_time:.2f}s")
            
        except Exception as e:
            # 🎯 处理失败
            self.service_stats["failed_responses"] += 1
            logger.error(f"[ModelService] ❌ 模型处理失败: {task_id}, 错误: {e}")
            
            # 🎯 发布错误结果
            error_result = self._create_error_result(processing_context, str(e), start_time)
            await self.bus.publish("agent.result.stream", error_result, metadata)

    def _prepare_model_input(self, processing_context: Dict[str, Any]) -> Dict[str, Any]:
        """准备标准化模型输入"""
        raw_data = processing_context["raw_data"]
        metadata = processing_context["metadata"]
        
        # 🎯 获取模型配置
        agent_profile = metadata.get("agent_profile", {})
        model_policy = agent_profile.get("model_policy", {})
        model_config = self.model_configs.get(self.model_identity, {})
        
        # 🎯 构建完整的模型输入
        model_input = {
            # 🎯 任务标识
            "session_id": processing_context["session_id"],
            "task_id": processing_context["task_id"],
            "message_seq": processing_context["message_seq"],
            
            # 🎯 输入内容
            "content": raw_data.get("content", ""),
            "original_content": raw_data.get("original_content", ""),
            "task_type": raw_data.get("task_type", "general"),
            
            # 🎯 处理状态
            "processing_count": raw_data.get("_processing_count", 0),
            "promptflow_processed": raw_data.get("promptflow_processed", False),
            
            # 🎯 模型配置
            "model_config": {
                "model": self.model_identity,
                "temperature": model_policy.get("temperature", model_config.get("temperature", 0.2)),
                "max_tokens": model_policy.get("max_tokens", model_config.get("max_tokens", 2048)),
                "api_url": model_config.get("api_url"),
                "timeout": model_config.get("timeout", 30)
            },
            
            # 🎯 上下文信息
            "user_profile": metadata.get("user_profile", {}),
            "agent_profile": metadata.get("agent_profile", {}),
            "session_context": metadata.get("session_context", {})
        }
        
        logger.debug(f"[ModelService] 🔧 准备模型输入: {model_input['task_id']}")
        return model_input

    async def _call_model_api(self, model_input: Dict[str, Any]) -> Dict[str, Any]:
        """调用模型API - 支持真实API调用和模拟模式"""
        start_time = time.time()
        
        try:
            # 🎯 构建API请求
            api_payload = self._build_api_payload(model_input)
            model_config = model_input["model_config"]
            
            # 🎯 检查是否配置了真实API
            if model_config.get("api_url") and self.http_session:
                # 🎯 真实API调用
                result = await self._call_real_api(api_payload, model_config)
            else:
                # 🎯 模拟API调用（向后兼容）
                result = await self._call_mock_api(model_input)
            
            # 🎯 添加处理时间
            result["processing_time"] = time.time() - start_time
            result["inference_latency"] = result["processing_time"]
            
            return result
            
        except Exception as e:
            logger.error(f"[ModelService] ❌ API调用失败: {e}")
            raise

    async def _call_real_api(self, api_payload: Dict[str, Any], model_config: Dict[str, Any]) -> Dict[str, Any]:
        """调用真实模型API"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {model_config.get('api_key', '')}"
        }
        
        timeout = aiohttp.ClientTimeout(total=model_config.get("timeout", 30))
        
        try:
            async with self.http_session.post(
                model_config["api_url"],
                json=api_payload,
                headers=headers,
                timeout=timeout
            ) as response:
                
                if response.status == 200:
                    response_data = await response.json()
                    
                    # 🎯 解析API响应
                    return self._parse_api_response(response_data)
                else:
                    error_text = await response.text()
                    raise Exception(f"API调用失败: {response.status} - {error_text}")
                    
        except asyncio.TimeoutError:
            raise Exception(f"API调用超时: {model_config.get('timeout', 30)}s")
        except Exception as e:
            raise Exception(f"API调用异常: {str(e)}")

    def _build_api_payload(self, model_input: Dict[str, Any]) -> Dict[str, Any]:
        """构建API请求载荷"""
        content = model_input["content"]
        model_config = model_input["model_config"]
        user_profile = model_input["user_profile"]
        
        # 🎯 基于用户档案定制系统提示
        system_prompt = self._build_system_prompt(user_profile, model_input["task_type"])
        
        return {
            "model": self.model_identity,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content}
            ],
            "temperature": model_config["temperature"],
            "max_tokens": model_config["max_tokens"],
            "stream": False
        }

    def _build_system_prompt(self, user_profile: Dict[str, Any], task_type: str) -> str:
        """构建系统提示"""
        base_prompt = "你是一个有帮助的AI助手。请根据用户的问题提供准确、有用的回答。"
        
        # 🎯 基于用户技术水平调整提示
        technical_level = user_profile.get("technical_level", "beginner")
        if technical_level == "expert":
            base_prompt += " 用户具有专业技术背景，可以使用专业术语和深入分析。"
        elif technical_level == "beginner":
            base_prompt += " 请用简单易懂的语言解释，避免使用专业术语。"
        
        # 🎯 基于任务类型调整提示
        task_prompts = {
            "code": "请提供高质量的代码示例和解释。",
            "analysis": "请进行深入分析，提供详细的推理过程。", 
            "summary": "请提供简洁明了的总结。",
            "translation": "请提供准确的翻译。"
        }
        
        task_prompt = task_prompts.get(task_type, "")
        return base_prompt + " " + task_prompt

    def _parse_api_response(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """解析API响应"""
        try:
            choices = response_data.get("choices", [])
            if not choices:
                raise Exception("API响应中没有choices字段")
                
            message = choices[0].get("message", {})
            content = message.get("content", "")
            
            usage = response_data.get("usage", {})
            
            return {
                "content": content,
                "token_usage": {
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0)
                },
                "finish_reason": choices[0].get("finish_reason", "stop")
            }
        except Exception as e:
            raise Exception(f"解析API响应失败: {str(e)}")

    async def _call_mock_api(self, model_input: Dict[str, Any]) -> Dict[str, Any]:
        """模拟API调用（向后兼容）"""
        content = model_input["content"]
        user_profile = model_input["user_profile"]
        
        # 🎯 模拟处理延迟
        await asyncio.sleep(1)
        
        # 🎯 基于用户档案定制响应
        technical_level = user_profile.get("technical_level", "beginner")
        if technical_level == "expert":
            response_style = "技术性强的专业回答"
        else:
            response_style = "简单易懂的解释"
        
        # 🎯 模拟token使用
        prompt_tokens = len(content)
        completion_tokens = len(content) * 2  # 模拟生成长度
        
        return {
            "content": f"[{self.model_identity}] 模型处理结果 ({response_style}): {content}",
            "token_usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens
            },
            "finish_reason": "stop"
        }

    def _create_standardized_result(self, processing_context: Dict[str, Any], 
                                  model_output: Dict[str, Any], start_time: float) -> Dict[str, Any]:
        """创建标准化结果"""
        processing_time = time.time() - start_time
        
        return {
            # 🎯 任务标识
            "session_id": processing_context["session_id"],
            "task_id": processing_context["task_id"],
            "message_seq": processing_context["message_seq"],
            "original_task_id": processing_context["raw_data"].get("original_task_id"),
            
            # 🎯 处理结果
            "result": model_output["content"],
            "status": "completed",
            "processing_time": processing_time,
            "inference_latency": model_output.get("inference_latency", processing_time),
            
            # 🎯 模型信息
            "model_used": self.model_identity,
            "token_usage": model_output.get("token_usage", {}),
            "finish_reason": model_output.get("finish_reason", "stop"),
            
            # 🎯 时间信息
            "start_time": start_time,
            "completion_time": time.time(),
            
            # 🎯 上下文信息
            "target_agent": processing_context["envelope"].get("target_agent"),
            "promptflow_processed": processing_context["raw_data"].get("promptflow_processed", False),
            "routed_by": processing_context["envelope"].get("routed_by")
        }

    def _create_error_result(self, processing_context: Dict[str, Any], 
                           error_message: str, start_time: float) -> Dict[str, Any]:
        """创建错误结果"""
        return {
            "session_id": processing_context["session_id"],
            "task_id": processing_context["task_id"],
            "message_seq": processing_context["message_seq"],
            "status": "failed",
            "error": error_message,
            "model_used": self.model_identity,
            "processing_time": time.time() - start_time,
            "completion_time": time.time()
        }

    def get_service_stats(self) -> Dict[str, Any]:
        """获取服务统计信息"""
        total_requests = self.service_stats["total_requests"]
        successful_responses = self.service_stats["successful_responses"]
        
        avg_processing_time = (self.service_stats["total_processing_time"] / successful_responses 
                             if successful_responses > 0 else 0)
        
        return {
            "model_identity": self.model_identity,
            "total_requests": total_requests,
            "successful_responses": successful_responses,
            "failed_responses": self.service_stats["failed_responses"],
            "success_rate": (successful_responses / total_requests if total_requests > 0 else 0),
            "average_processing_time": avg_processing_time,
            "total_processing_time": self.service_stats["total_processing_time"],
            "total_tokens_used": self.service_stats["total_tokens_used"],
            "avg_tokens_per_request": (self.service_stats["total_tokens_used"] / successful_responses 
                                     if successful_responses > 0 else 0)
        }

    async def close(self):
        """关闭服务"""
        if self.http_session and not self.http_session.closed:
            await self.http_session.close()
            logger.info("[ModelService] 🔒 HTTP会话已关闭")

    # 🎯 向后兼容的方法
    async def handle_task_legacy(self, task_id: str, content: str):
        """向后兼容的任务处理方法"""
        logger.warning(f"[ModelService] ⚠️ 使用旧版handle_task: {task_id}")
        
        # 🎯 创建模拟的processing_context
        processing_context = {
            "session_id": f"sess_{task_id}",
            "task_id": task_id,
            "message_seq": 0,
            "metadata": {},
            "raw_data": {"content": content},
            "envelope": {}
        }
        
        await self.on_task(None, processing_context)

    def handle_task(self, task_id: str, content: str):
        """同步处理任务（向后兼容）"""
        logger.info(f"[ModelService] 🔍 旧版handle_task调用: task_id={task_id}")
        asyncio.get_event_loop().create_task(self.handle_task_legacy(task_id, content))