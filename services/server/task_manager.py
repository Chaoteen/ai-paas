import asyncio
import json
import logging
import time
import uuid
from typing import Callable, Any, Dict, List
import redis
from model_service import ModelService  # 确保 model_service.py 在同级目录

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


class RedisBackedEnvelopeBUS:
    """Redis Stream 消息总线（标准化版本）"""

    def __init__(self, redis_url="redis://localhost:6379",
                 stream_name="agent.processed.tasks.stream",
                 consumer_group="task_manager_workers"):
        self.redis_url = redis_url
        self.stream_name = stream_name
        self.consumer_group = consumer_group
        self.consumer_id = f"consumer_{uuid.uuid4().hex[:8]}"
        self.redis = redis.Redis.from_url(redis_url, decode_responses=True)
        self.handlers: Dict[str, List[Callable]] = {}
        self._running = False

        self._initialize_stream_group()
        logger.info(f"✅ RedisBackedEnvelopeBUS initialized - Stream: {stream_name}, Group: {consumer_group}")

    def _initialize_stream_group(self):
        try:
            self.redis.xgroup_create(name=self.stream_name, groupname=self.consumer_group, id="0", mkstream=True)
            logger.info(f"✅ 创建 Stream 消费组: {self.consumer_group}")
        except Exception as e:
            if "BUSYGROUP" not in str(e):
                logger.error(f"❌ 初始化 Stream 消费组失败: {e}")
                raise
            else:
                logger.info(f"✅ Stream 消费组已存在: {self.consumer_group}")

    async def subscribe_stream(self, topic: str, callback: Callable):
        """注册 topic 的回调"""
        if not callback:
            raise ValueError("subscribe_stream requires a callback")
        self.handlers[topic] = self.handlers.get(topic, []) + [callback]
        logger.info(f"✅ 注册处理器到主题: {topic}")

    async def start(self):
        """启动异步监听循环"""
        self._running = True
        asyncio.create_task(self._listener_loop())
        logger.info("🚀 RedisBackedEnvelopeBUS监听循环已启动")

    async def _listener_loop(self):
        while self._running:
            try:
                messages = self.redis.xreadgroup(
                    groupname=self.consumer_group,
                    consumername=self.consumer_id,
                    streams={self.stream_name: ">"},
                    count=10,
                    block=1000
                )
                for stream_name, msg_list in messages:
                    for msg_id, msg_data in msg_list:
                        raw_msg = msg_data.get("message", "")
                        if not raw_msg:
                            continue
                        try:
                            envelope = json.loads(raw_msg)
                            topic = envelope.get("topic", "unknown")
                            data = envelope.get("data", {})
                            
                            # 🎯 标准化字段提取
                            session_id = envelope.get("session_id")
                            task_id = envelope.get("task_id")
                            message_seq = envelope.get("message_seq")
                            metadata = envelope.get("metadata", {})
                            
                            logger.info(f"📨 收到标准化消息: session={session_id}, task={task_id}, seq={message_seq}")
                            
                            # 创建标准化的处理上下文
                            processing_context = {
                                "envelope": envelope,
                                "session_id": session_id,
                                "task_id": task_id,
                                "message_seq": message_seq,
                                "metadata": metadata,
                                "raw_data": data
                            }
                            
                            handlers = self.handlers.get(topic, [])
                            for handler in handlers:
                                if asyncio.iscoroutinefunction(handler):
                                    asyncio.create_task(handler(msg_id, processing_context))
                                else:
                                    # 同步函数用线程池执行
                                    asyncio.get_event_loop().run_in_executor(None, handler, msg_id, processing_context)
                            self.redis.xack(self.stream_name, self.consumer_group, msg_id)
                        except Exception as e:
                            logger.error(f"❌ 处理 Stream 消息错误: {e}")
            except Exception as e:
                logger.error(f"❌ Redis Streams处理器错误: {e}")
                await asyncio.sleep(1)

    async def publish(self, topic: str, data: Any, metadata: dict = None):
        """发布消息到 Stream - 标准化版本"""
        try:
            # 🎯 标准化消息格式
            message = {
                "topic": topic,
                "data": data,
                "timestamp": time.time(),
                "message_id": str(uuid.uuid4()),
                # 🎯 标准化字段
                "session_id": data.get("session_id"),
                "task_id": data.get("task_id"),
                "message_seq": data.get("message_seq"),
                "metadata": metadata or {}
            }
            
            msg_str = json.dumps(message)
            message_id = self.redis.xadd(self.stream_name, {"message": msg_str}, maxlen=10000)
            logger.info(f"📨 发布标准化消息到 Stream {self.stream_name}, ID: {message_id}")
            return message_id
        except Exception as e:
            logger.error(f"❌ Failed to publish to Stream {self.stream_name}: {e}")
            raise


class TaskManager:
    """核心任务管理器 - 标准化版本"""

    def __init__(self):
        self.bus = RedisBackedEnvelopeBUS()
        self.model = ModelService(self.bus)
        # 🎯 任务状态追踪
        self.task_status = {}
        self.session_tasks = {}

    def _extract_model_config(self, metadata: dict) -> dict:
        """从标准化metadata中提取模型配置"""
        agent_profile = metadata.get("agent_profile", {})
        model_policy = agent_profile.get("model_policy", {})
        
        return {
            "model": model_policy.get("default_model", "qwen-8b"),
            "temperature": model_policy.get("temperature", 0.2),
            "max_tokens": model_policy.get("max_tokens", 2048),
            "fallback_chain": model_policy.get("fallback_chain", [])
        }

    def _prepare_model_input(self, processing_context: dict) -> dict:
        """准备标准化的模型输入"""
        raw_data = processing_context["raw_data"]
        metadata = processing_context["metadata"]
        
        # 🎯 构建完整的模型输入上下文
        model_input = {
            "task_id": processing_context["task_id"],
            "session_id": processing_context["session_id"],
            "content": raw_data.get("content", ""),
            "task_type": raw_data.get("task_type", "general"),
            # 🎯 PromptFlow处理信息
            "promptflow_processed": raw_data.get("promptflow_processed", False),
            "original_content": raw_data.get("original_content", ""),
            # 🎯 模型配置
            "model_config": self._extract_model_config(metadata),
            # 🎯 用户和Agent上下文
            "user_profile": metadata.get("user_profile", {}),
            "agent_profile": metadata.get("agent_profile", {}),
            "session_context": metadata.get("session_context", {}),
            # 🎯 处理状态
            "processing_count": raw_data.get("_processing_count", 0),
            "ts_pub": raw_data.get("ts_pub", time.time())
        }
        
        return model_input

    def _create_result_envelope(self, processing_context: dict, model_output: dict, model_used: str) -> dict:
        """创建标准化的结果消息（包含 Control Plane 同步匹配字段）"""
        raw_data = processing_context["raw_data"]
        envelope = processing_context["envelope"]

        result_data = {
            # ✅ Control Plane 同步匹配字段（关键）
            "request_id": raw_data.get("request_id") or envelope.get("request_id"),
            "envelope_id": raw_data.get("envelope_id") or envelope.get("envelope_id"),
            "tenant_id": raw_data.get("tenant_id") or envelope.get("tenant_id"),

            # 标准化任务标识
            "session_id": processing_context["session_id"],
            "task_id": processing_context["task_id"],
            "message_seq": processing_context["message_seq"],
            "original_task_id": raw_data.get("original_task_id"),

            # 处理结果
            "result": model_output.get("content", ""),
            "status": "completed",
            "processing_time": model_output.get("processing_time", 0),

            # 模型使用信息
            "model_used": model_used,
            "token_usage": model_output.get("token_usage", {}),
            "inference_latency": model_output.get("inference_latency", 0),

            # 上下文信息
            "target_agent": envelope.get("target_agent"),
            "promptflow_processed": raw_data.get("promptflow_processed", False),
            "routed_by": envelope.get("routed_by"),

            # 时间戳
            "start_time": envelope.get("timestamp"),
            "completion_time": time.time(),
        }
        return result_data


    async def handle_task(self, msg_id, processing_context: dict):
        """处理任务 - 标准化版本"""
        session_id = processing_context["session_id"]
        task_id = processing_context["task_id"]
        message_seq = processing_context["message_seq"]
        
        logger.info(f"[TaskManager] 📨 收到标准化任务: session={session_id}, task={task_id}, seq={message_seq}")
        
        try:
            # 🎯 更新任务状态
            self._update_task_status(session_id, task_id, "processing")
            
            # 🎯 准备模型输入
            model_input = self._prepare_model_input(processing_context)
            logger.info(f"[TaskManager] 🔧 准备模型输入完成: {task_id}")
            
            # 🎯 调用模型服务
            model_output = await asyncio.get_event_loop().run_in_executor(
                None, self.model.handle_task, model_input
            )
            
            # 🎯 创建标准化结果
            model_used = model_input["model_config"]["model"]
            result_data = self._create_result_envelope(processing_context, model_output, model_used)
            
            # 🎯 发布结果到结果流
            await self.bus.publish("agent.result.stream", result_data, processing_context["metadata"])
            
            # 🎯 更新任务状态为完成
            self._update_task_status(session_id, task_id, "completed")
            
            logger.info(f"[TaskManager] ✅ 任务处理完成: {task_id}, 使用模型: {model_used}")
            
            # 🎯 可选：触发记忆存储
            await self._trigger_memory_storage(processing_context, model_output)
            
        except Exception as e:
            logger.error(f"[TaskManager] ❌ 任务处理失败: {task_id}, 错误: {e}")
            self._update_task_status(session_id, task_id, "failed")
            
            # 🎯 发布错误结果
            error_result = {
                "session_id": session_id,
                "task_id": task_id,
                "message_seq": message_seq,
                "status": "failed",
                "error": str(e),
                "completion_time": time.time()
            }
            await self.bus.publish("agent.result.stream", error_result, processing_context["metadata"])

    def _update_task_status(self, session_id: str, task_id: str, status: str):
        """更新任务状态"""
        if session_id not in self.session_tasks:
            self.session_tasks[session_id] = {}
        
        self.session_tasks[session_id][task_id] = {
            "status": status,
            "update_time": time.time()
        }
        
        logger.debug(f"[TaskManager] 🔄 更新任务状态: session={session_id}, task={task_id}, status={status}")

    async def _trigger_memory_storage(self, processing_context: dict, model_output: dict):
        """触发记忆存储（可选功能）"""
        try:
            # 🎯 检查是否需要存储到记忆系统
            session_context = processing_context["metadata"].get("session_context", {})
            memory_policy = session_context.get("memory_policy", "none")
            
            if memory_policy != "none":
                memory_data = {
                    "session_id": processing_context["session_id"],
                    "task_id": processing_context["task_id"],
                    "message_seq": processing_context["message_seq"],
                    "user_message": processing_context["raw_data"].get("content", ""),
                    "assistant_response": model_output.get("content", ""),
                    "timestamp": time.time(),
                    "type": "hot"  # 默认为热记忆
                }
                
                # 🎯 发布到记忆流（如果记忆服务已部署）
                # await self.bus.publish("stream.memory_manager.update", memory_data, processing_context["metadata"])
                logger.info(f"[TaskManager] 🧠 触发记忆存储: {processing_context['task_id']}")
                
        except Exception as e:
            logger.warning(f"[TaskManager] ⚠️ 记忆存储触发失败: {e}")

    def get_session_stats(self, session_id: str) -> dict:
        """获取会话统计信息"""
        if session_id not in self.session_tasks:
            return {"error": "Session not found"}
        
        tasks = self.session_tasks[session_id]
        completed = sum(1 for task in tasks.values() if task["status"] == "completed")
        failed = sum(1 for task in tasks.values() if task["status"] == "failed")
        processing = sum(1 for task in tasks.values() if task["status"] == "processing")
        
        return {
            "session_id": session_id,
            "total_tasks": len(tasks),
            "completed": completed,
            "failed": failed,
            "processing": processing,
            "success_rate": completed / len(tasks) if tasks else 0
        }

    async def start(self):
        """启动任务管理器 - 标准化版本"""
        logger.info("[TaskManager] 🚀 启动标准化任务管理器...")
        
        # 🎯 订阅标准化消息流
        await self.bus.subscribe_stream("agent.processed.tasks.stream", self.handle_task)
        
        # 🎯 启动总线监听
        await self.bus.start()
        
        # 🎯 等待模型初始化
        await self.model.initialize()
        
        logger.info("[TaskManager] ✅ 标准化任务管理器启动成功")
        
        # 🎯 启动状态监控（可选）
        asyncio.create_task(self._status_monitor())

    async def _status_monitor(self):
        """状态监控任务"""
        while True:
            try:
                # 每30秒输出一次统计信息
                await asyncio.sleep(30)
                active_sessions = len(self.session_tasks)
                total_tasks = sum(len(tasks) for tasks in self.session_tasks.values())
                
                logger.info(f"[TaskManager] 📊 状态监控 - 活跃会话: {active_sessions}, 总任务数: {total_tasks}")
                
                # 清理过期的会话（24小时无活动）
                self._cleanup_old_sessions()
                
            except Exception as e:
                logger.error(f"[TaskManager] ❌ 状态监控错误: {e}")
                await asyncio.sleep(60)  # 出错后等待更久

    def _cleanup_old_sessions(self):
        """清理过期会话"""
        current_time = time.time()
        expired_sessions = []
        
        for session_id, tasks in self.session_tasks.items():
            # 如果所有任务都完成且超过24小时无更新
            latest_update = max(task["update_time"] for task in tasks.values())
            if current_time - latest_update > 24 * 3600:  # 24小时
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            del self.session_tasks[session_id]
            logger.info(f"[TaskManager] 🗑️ 清理过期会话: {session_id}")

    async def stop(self):
        """停止任务管理器"""
        logger.info("[TaskManager] 🛑 停止任务管理器...")
        # 可以添加优雅关闭逻辑
        if hasattr(self.bus, 'stop'):
            await self.bus.stop()


# 🎯 使用示例
async def main():
    """主函数示例"""
    task_manager = TaskManager()
    try:
        await task_manager.start()
        
        # 保持运行
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("[TaskManager] 收到停止信号")
        await task_manager.stop()

if __name__ == "__main__":
    asyncio.run(main())