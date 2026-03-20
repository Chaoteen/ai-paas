#!/usr/bin/env python3
"""
Redis消息总线启动脚本 - 兼容标准化消息总线版本
"""

import asyncio
import logging
import signal
import os
import sys
import redis.asyncio as redis
import json
import time

# 直接从当前工程导入 redis_bus（迁移到 ai-paas 后不再注入旧路径）
try:
    from redis_bus import create_message_bus, RedisBackedEnvelopeBUS
except ModuleNotFoundError as e:
    print(f"❌ 模块导入失败，请检查路径: {e}")
    print(f"🔍 当前 sys.path: {sys.path}")
    sys.exit(1)
except Exception as e:
    print(f"❌ 导入 redis_bus.py 时发生未知错误: {e}")
    sys.exit(1)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/redis_bus.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

async def standardized_task_handler(processing_context):
    """
    标准化任务处理器 - 兼容新版 processing_context 接口
    """
    # 🎯 从标准化 processing_context 中提取信息
    envelope = processing_context["envelope"]
    session_id = processing_context["session_id"]
    task_id = processing_context["task_id"]
    message_seq = processing_context["message_seq"]
    metadata = processing_context["metadata"]
    raw_data = processing_context["raw_data"]
    
    logger.info(f"🔧 处理标准化任务 - Session: {session_id}, Task: {task_id}, Seq: {message_seq}")
    
    # 🎯 检查消息来源，避免处理结果消息
    topic = envelope.get("topic", "unknown")
    if topic == "agent.result" or topic == "agent.final.result":
        logger.info(f"🔄 跳过结果消息，避免循环: {task_id}")
        return {"status": "skipped", "reason": "result_message_loop_prevention"}
    
    # 🎯 检查是否已经包含结果数据
    if "result" in str(raw_data):
        logger.info(f"🔄 跳过已包含结果的消息: {task_id}")
        return {"status": "skipped", "reason": "already_has_result"}
    
    # 🎯 处理任务
    result = {
        "status": "processed", 
        "task_id": task_id,
        "session_id": session_id,
        "message_seq": message_seq,
        "processed_by": "run_bus_standardized",
        "timestamp": time.time()
    }
    
    # 🎯 发布到最终结果Stream
    try:
        redis_client = redis.from_url("redis://localhost:6379", decode_responses=True)
        
        target_stream = "agent.final.results.stream"
        result_message = {
            "topic": "agent.final.result",
            "data": result,
            "timestamp": time.time(),
            "session_id": session_id,
            "task_id": task_id,
            "message_seq": message_seq,
            "metadata": {
                "source_handler": "standardized_task_handler",
                "processing_time": time.time()
            }
        }
        
        await redis_client.xadd(target_stream, {
            "message": json.dumps(result_message)
        })
        logger.info(f"✅ 已发布标准化最终结果到 {target_stream}: {task_id}")
        
    except Exception as e:
        logger.error(f"❌ 发布最终结果失败: {e}")
    
    return result

async def legacy_task_handler(processing_context):
    """
    向后兼容的处理器 - 同时支持新旧消息格式
    """
    try:
        # 🎯 检测消息格式并统一处理
        if isinstance(processing_context, dict) and "raw_data" in processing_context:
            # 新版标准化格式
            return await standardized_task_handler(processing_context)
        else:
            # 🎯 旧版格式兼容处理
            data = processing_context
            logger.warning(f"⚠️ 收到旧版格式消息，使用兼容处理: {data.get('task_id', 'unknown')}")
            
            # 提取 task_id（兼容多层嵌套）
            task_id = "unknown"
            if "task_id" in data and data["task_id"] != "unknown":
                task_id = data["task_id"]
            elif "data" in data:
                inner_data = data.get("data", {})
                if "task_id" in inner_data and inner_data["task_id"] != "unknown":
                    task_id = inner_data["task_id"]
            
            # 检查循环和结果
            if data.get("topic") == "agent.result":
                logger.info(f"🔄 跳过结果消息(旧格式): {task_id}")
                return {"status": "skipped", "reason": "result_message_loop_prevention"}
            
            if "result" in str(data):
                logger.info(f"🔄 跳过已包含结果的消息(旧格式): {task_id}")
                return {"status": "skipped", "reason": "already_has_result"}
            
            # 处理并发布结果
            result = {"status": "processed", "task_id": task_id}
            
            redis_client = redis.from_url("redis://localhost:6379", decode_responses=True)
            target_stream = "agent.final.results.stream"
            
            await redis_client.xadd(target_stream, {
                "message": json.dumps({
                    "topic": "agent.final.result",
                    "data": {
                        "task_id": task_id,
                        "result": result,
                        "timestamp": time.time(),
                        "processed_by": "run_bus_legacy"
                    }
                })
            })
            logger.info(f"✅ 已发布兼容性结果到 {target_stream}: {task_id}")
            
            return result
            
    except Exception as e:
        logger.error(f"❌ 兼容处理器错误: {e}")
        return {"status": "error", "reason": str(e)}

async def main():
    # 读取配置（可由环境变量覆盖）
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    stream_name = os.getenv("REDIS_STREAM", "agent.routed.tasks.stream")
    consumer_group = os.getenv("CONSUMER_GROUP", "model_workers")
    enable_deduplication = os.getenv("ENABLE_DEDUPLICATION", "true").lower() == "true"

    # 🎯 使用新的标准化工厂函数创建总线实例
    try:
        bus = create_message_bus(
            redis_url=redis_url,
            stream_name=stream_name,
            consumer_group=consumer_group,
            enable_deduplication=enable_deduplication
        )
        logger.info(f"✅ 创建标准化Redis总线实例成功 - 去重: {enable_deduplication}")
    except Exception as e:
        logger.critical(f"❌ 创建标准化Redis总线实例失败: {e}")
        # 🎯 尝试回退到直接实例化
        try:
            logger.info("🔄 尝试回退到直接实例化...")
            bus = RedisBackedEnvelopeBUS(
                redis_url=redis_url,
                stream_name=stream_name,
                consumer_group=consumer_group,
                enable_deduplication=enable_deduplication
            )
            logger.info("✅ 回退到直接实例化成功")
        except Exception as fallback_error:
            logger.critical(f"❌ 所有实例化方式均失败: {fallback_error}")
            sys.exit(1)

    # 🎯 注册处理器 - 使用标准化处理器
    try:
        await bus.subscribe("ai.tasks", standardized_task_handler)
        await bus.subscribe("model.inference", standardized_task_handler)
        await bus.subscribe("agent.model.agent.translate", standardized_task_handler)
        await bus.subscribe("agent.model.agent.default", standardized_task_handler)
        
        # 🎯 可选：注册兼容性处理器到其他主题
        # await bus.subscribe("legacy.tasks", legacy_task_handler)
        
        logger.info("✅ 成功注册标准化消息处理器")
        
        # 🎯 打印总线统计信息
        stats = bus.get_bus_stats()
        logger.info(f"📊 总线统计: {stats}")
        
    except Exception as e:
        logger.error(f"❌ 注册处理器失败: {e}")
        await bus.stop()
        sys.exit(1)

    # 信号处理：优雅关闭
    shutdown_event = asyncio.Event()

    def signal_handler():
        logger.info("🛑 收到终止信号 (SIGINT/SIGTERM)，准备关闭...")
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    # 启动总线（带重试）
    connected = False
    for i in range(5):
        try:
            try:
                await bus.start()
            except TypeError:
                await bus.start(use_streams=True)

            connected = True
            logger.info("✅ Redis标准化消息总线已启动")
            break
        except Exception as e:
            logger.error(f"❌ 启动失败 (第 {i+1} 次): {e}")
            if i < 4:
                backoff = 2 ** i
                logger.info(f"🔁 {backoff} 秒后重试...")
                await asyncio.sleep(backoff)
            else:
                logger.critical("❌ 重试5次后仍无法连接Redis，退出程序")
    
    if not connected:
        sys.exit(1)

    # 保持运行，等待关闭信号
    logger.info(f"📝 订阅主题: ai.tasks, model.inference, agent.model.agent.translate, agent.model.agent.default")
    logger.info(f"📡 Stream: {stream_name}, Group: {consumer_group}")
    logger.info(f"🎯 消息格式: 标准化processing_context")
    logger.info(f"🔄 幂等去重: {enable_deduplication}")
    logger.info("⏳ 等待消息中... 按 Ctrl+C 或发送 SIGTERM 可停止服务")

    try:
        await shutdown_event.wait()  # 等待信号触发
    except Exception as e:
        logger.warning(f"⚠️ 主循环异常: {e}")

    # 关闭总线
    try:
        await bus.stop()
        logger.info("👋 Redis标准化消息总线已安全停止")
        
        # 🎯 打印最终统计
        final_stats = bus.get_bus_stats()
        logger.info(f"📊 最终总线统计: {final_stats}")
        
    except Exception as e:
        logger.error(f"❌ 停止总线时出错: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # 已被 signal_handler 处理，这里只是兜底
        logger.info("👋 用户主动中断程序")
    except Exception as e:
        logger.critical(f"❌ 主程序异常退出: {e}", exc_info=True)
        sys.exit(1)