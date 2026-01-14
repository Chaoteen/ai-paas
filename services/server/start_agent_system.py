import asyncio
import sys
import os
import logging
from typing import Dict, List
import signal

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from task_manager import TaskManager

class AgentSystemManager:
    """标准化Agent系统管理器"""
    
    def __init__(self):
        self.task_manager = None
        self.running = False
        self.start_time = None
        
        # 🎯 系统配置
        self.config = {
            "health_check_interval": 30,
            "stats_log_interval": 60,
            "graceful_shutdown_timeout": 30
        }

    async def start(self):
        """启动Agent系统"""
        self.start_time = asyncio.get_event_loop().time()
        self.running = True
        
        logger.info("🚀 启动标准化Agent系统...")
        
        try:
            # 🎯 初始化TaskManager
            self.task_manager = TaskManager()
            
            # 🎯 启动TaskManager
            await self.task_manager.start()
            
            logger.info("✅ 标准化Agent系统启动成功")
            
            # 🎯 启动监控任务
            asyncio.create_task(self._health_monitor())
            asyncio.create_task(self._stats_logger())
            
            # 🎯 等待停止信号
            await self._wait_for_shutdown()
            
        except Exception as e:
            logger.error(f"❌ Agent系统启动失败: {e}")
            raise

    async def stop(self):
        """停止Agent系统"""
        if not self.running:
            return
            
        logger.info("🛑 停止标准化Agent系统...")
        self.running = False
        
        try:
            # 🎯 优雅关闭TaskManager
            if self.task_manager:
                await self.task_manager.stop()
                
            logger.info("✅ 标准化Agent系统已停止")
            
        except Exception as e:
            logger.error(f"❌ Agent系统停止失败: {e}")

    async def _health_monitor(self):
        """系统健康监控"""
        while self.running:
            try:
                # 🎯 检查系统健康状态
                health_status = await self._check_health()
                
                if not health_status["healthy"]:
                    logger.warning(f"⚠️ 系统健康检查失败: {health_status['issues']}")
                
                await asyncio.sleep(self.config["health_check_interval"])
                
            except Exception as e:
                logger.error(f"❌ 健康监控错误: {e}")
                await asyncio.sleep(self.config["health_check_interval"])

    async def _check_health(self) -> Dict[str, any]:
        """检查系统健康状态"""
        health_status = {
            "healthy": True,
            "issues": [],
            "timestamp": asyncio.get_event_loop().time()
        }
        
        # 🎯 检查TaskManager状态
        if not self.task_manager:
            health_status["healthy"] = False
            health_status["issues"].append("TaskManager未初始化")
            
        # 🎯 这里可以添加更多健康检查逻辑
        # 例如：检查Redis连接、模型服务可用性等
        
        return health_status

    async def _stats_logger(self):
        """系统统计日志"""
        while self.running:
            try:
                # 🎯 记录系统统计信息
                stats = await self._collect_system_stats()
                logger.info(f"📊 系统统计 - 运行时间: {stats['uptime']:.0f}s, "
                          f"活跃会话: {stats['active_sessions']}, "
                          f"总任务数: {stats['total_tasks']}")
                
                await asyncio.sleep(self.config["stats_log_interval"])
                
            except Exception as e:
                logger.error(f"❌ 统计日志错误: {e}")
                await asyncio.sleep(self.config["stats_log_interval"])

    async def _collect_system_stats(self) -> Dict[str, any]:
        """收集系统统计信息"""
        stats = {
            "uptime": asyncio.get_event_loop().time() - self.start_time,
            "active_sessions": 0,
            "total_tasks": 0
        }
        
        # 🎯 从TaskManager获取统计信息
        if self.task_manager and hasattr(self.task_manager, 'session_tasks'):
            stats["active_sessions"] = len(self.task_manager.session_tasks)
            stats["total_tasks"] = sum(
                len(tasks) for tasks in self.task_manager.session_tasks.values()
            )
            
        return stats

    async def _wait_for_shutdown(self):
        """等待关闭信号"""
        # 🎯 设置信号处理
        loop = asyncio.get_event_loop()
        for sig in [signal.SIGINT, signal.SIGTERM]:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))
        
        # 🎯 等待运行标志
        while self.running:
            await asyncio.sleep(1)

async def main():
    """主函数"""
    system_manager = AgentSystemManager()
    
    try:
        await system_manager.start()
    except Exception as e:
        logger.error(f"❌ Agent系统运行失败: {e}")
        raise
    finally:
        await system_manager.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 收到键盘中断信号")
    except Exception as e:
        logger.error(f"❌ 系统异常退出: {e}")
        sys.exit(1)
