import logging
from typing import Dict, Any, Optional
import time
import uuid

logger = logging.getLogger(__name__)

class AgentService:
    """标准化Agent服务"""
    
    def __init__(self, model_spec, bus):
        self.model_spec = model_spec
        self.bus = bus
        self.agent_id = f"agent.{model_spec.model_id}"
        
        # 🎯 订阅标准化消息通道
        self.bus.subscribe(f"agent.model.{model_spec.model_id}", self.on_task)
        
        # 🎯 Agent状态统计
        self.stats = {
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "total_processing_time": 0.0
        }
        
        logger.info(f"[AgentService:{self.agent_id}] ✅ 标准化Agent就绪")

    async def on_task(self, processing_context: Dict[str, Any]):
        """处理分配到本Agent的任务 - 标准化版本"""
        start_time = time.time()
        
        try:
            # 🎯 提取标准化字段
            envelope = processing_context["envelope"]
            session_id = processing_context["session_id"]
            task_id = processing_context["task_id"]
            message_seq = processing_context["message_seq"]
            metadata = processing_context["metadata"]
            raw_data = processing_context["raw_data"]
            
            logger.info(f"[AgentService:{self.agent_id}] 📨 处理任务: session={session_id}, task={task_id}, seq={message_seq}")
            
            # 🎯 更新统计
            self.stats["total_tasks"] += 1
            
            # 🎯 准备Agent处理上下文
            agent_context = self._prepare_agent_context(processing_context)
            
            # 🎯 执行Agent处理逻辑
            result = await self._process_with_agent(agent_context)
            
            # 🎯 创建标准化响应
            response_data = self._create_agent_response(processing_context, result, start_time)
            
            # 🎯 发布到结果流
            await self.bus.publish("agent.result.stream", response_data, metadata)
            
            # 🎯 更新成功统计
            self.stats["completed_tasks"] += 1
            processing_time = time.time() - start_time
            self.stats["total_processing_time"] += processing_time
            
            logger.info(f"[AgentService:{self.agent_id}] ✅ 任务完成: {task_id}, 耗时: {processing_time:.2f}s")
            
        except Exception as e:
            # 🎯 处理失败
            self.stats["failed_tasks"] += 1
            logger.error(f"[AgentService:{self.agent_id}] ❌ 任务处理失败: {task_id}, 错误: {e}")
            
            # 🎯 发布错误响应
            error_response = self._create_error_response(processing_context, str(e), start_time)
            await self.bus.publish("agent.result.stream", error_response, metadata)

    def _prepare_agent_context(self, processing_context: Dict[str, Any]) -> Dict[str, Any]:
        """准备Agent处理上下文"""
        raw_data = processing_context["raw_data"]
        metadata = processing_context["metadata"]
        
        return {
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
            
            # 🎯 上下文信息
            "user_profile": metadata.get("user_profile", {}),
            "agent_profile": metadata.get("agent_profile", {}),
            "session_context": metadata.get("session_context", {}),
            
            # 🎯 模型配置
            "model_config": {
                "model": self.model_spec.model_id,
                "temperature": 0.2,
                "max_tokens": 2048
            }
        }

    async def _process_with_agent(self, agent_context: Dict[str, Any]) -> Dict[str, Any]:
        """使用Agent处理任务"""
        # 🎯 这里添加实际的Agent处理逻辑
        # 例如：调用模型API、执行工具、与其他Agent协作等
        
        # 模拟处理逻辑
        content = agent_context["content"]
        user_profile = agent_context["user_profile"]
        
        # 基于用户档案和任务类型定制化处理
        if user_profile.get("technical_level") == "expert":
            response_style = "technical"
        else:
            response_style = "friendly"
            
        # 模拟处理结果
        result = {
            "content": f"[{self.agent_id}] 处理结果: {content} (风格: {response_style})",
            "processing_details": {
                "agent_used": self.agent_id,
                "style_applied": response_style,
                "processing_steps": ["意图理解", "内容生成", "质量检查"]
            },
            "confidence": 0.85
        }
        
        # 模拟处理延迟
        await asyncio.sleep(0.1)
        
        return result

    def _create_agent_response(self, processing_context: Dict[str, Any], 
                             result: Dict[str, Any], start_time: float) -> Dict[str, Any]:
        """创建标准化Agent响应"""
        processing_time = time.time() - start_time
        
        return {
            # 🎯 任务标识
            "session_id": processing_context["session_id"],
            "task_id": processing_context["task_id"],
            "message_seq": processing_context["message_seq"],
            "original_task_id": processing_context["raw_data"].get("original_task_id"),
            
            # 🎯 处理结果
            "result": result["content"],
            "status": "completed",
            "processing_time": processing_time,
            
            # 🎯 Agent信息
            "agent_used": self.agent_id,
            "agent_confidence": result.get("confidence", 0.8),
            "processing_details": result.get("processing_details", {}),
            
            # 🎯 模型信息
            "model_used": self.model_spec.model_id,
            "token_usage": {
                "prompt_tokens": len(processing_context["raw_data"].get("content", "")),
                "completion_tokens": len(result["content"]),
                "total_tokens": len(processing_context["raw_data"].get("content", "")) + len(result["content"])
            },
            
            # 🎯 时间信息
            "start_time": start_time,
            "completion_time": time.time(),
            
            # 🎯 上下文信息
            "target_agent": processing_context["envelope"].get("target_agent"),
            "promptflow_processed": processing_context["raw_data"].get("promptflow_processed", False)
        }

    def _create_error_response(self, processing_context: Dict[str, Any], 
                             error_message: str, start_time: float) -> Dict[str, Any]:
        """创建错误响应"""
        return {
            "session_id": processing_context["session_id"],
            "task_id": processing_context["task_id"],
            "message_seq": processing_context["message_seq"],
            "status": "failed",
            "error": error_message,
            "agent_used": self.agent_id,
            "processing_time": time.time() - start_time,
            "completion_time": time.time()
        }

    def get_stats(self) -> Dict[str, Any]:
        """获取Agent统计信息"""
        avg_time = (self.stats["total_processing_time"] / self.stats["completed_tasks"] 
                   if self.stats["completed_tasks"] > 0 else 0)
        
        return {
            "agent_id": self.agent_id,
            "total_tasks": self.stats["total_tasks"],
            "completed_tasks": self.stats["completed_tasks"],
            "failed_tasks": self.stats["failed_tasks"],
            "success_rate": (self.stats["completed_tasks"] / self.stats["total_tasks"] 
                           if self.stats["total_tasks"] > 0 else 0),
            "average_processing_time": avg_time,
            "total_processing_time": self.stats["total_processing_time"]
        }
