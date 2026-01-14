# ai-os/agent_core/memory.py
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


DEFAULT_TENANT = "default"
DEFAULT_SESSION = "default"


@dataclass
class ConversationTurn:
    role: str
    content: str
    timestamp: float = field(default_factory=lambda: time.time())


@dataclass
class TaskRecord:
    content: str
    result: Optional[str] = None
    timestamp: float = field(default_factory=lambda: time.time())
    # 预留：用于审计/追踪
    request_id: Optional[str] = None
    envelope_id: Optional[str] = None
    message_seq: Optional[int] = None


class MemoryManager:
    """
    多租户 + 会话隔离的记忆管理器（最终版）

    数据层级：
    tenant_id -> session_id -> buckets
      - conversation_history: List[ConversationTurn]
      - task_results: Dict[task_id, TaskRecord]
      - user_preferences: Dict[str, Any]
      - knowledge_base: List[Any]
      - hot: List[Any]   (预留)
      - cold: List[Any]  (预留)
    """

    def __init__(self):
        self._lock = asyncio.Lock()

        # tenant_id -> session_id -> memory dict
        self._store: Dict[str, Dict[str, Dict[str, Any]]] = {}

    # -----------------------------
    # 内部工具
    # -----------------------------
    def _normalize_scope(self, tenant_id: Optional[str], session_id: Optional[str]) -> Tuple[str, str]:
        t = tenant_id or DEFAULT_TENANT
        s = session_id or DEFAULT_SESSION
        return t, s

    def _ensure_session(self, tenant_id: str, session_id: str):
        if tenant_id not in self._store:
            self._store[tenant_id] = {}
        if session_id not in self._store[tenant_id]:
            self._store[tenant_id][session_id] = {
                "conversation_history": [],
                "task_results": {},
                "user_preferences": {},
                "knowledge_base": [],
                "hot": [],
                "cold": [],
            }

    # -----------------------------
    # 推荐新接口（多租户/会话）
    # -----------------------------
    async def add_conversation(
        self,
        tenant_id: Optional[str],
        session_id: Optional[str],
        role: str,
        content: str,
    ):
        t, s = self._normalize_scope(tenant_id, session_id)
        async with self._lock:
            self._ensure_session(t, s)
            self._store[t][s]["conversation_history"].append(
                ConversationTurn(role=role, content=content)
            )

    async def add_task_result(
        self,
        tenant_id: Optional[str],
        session_id: Optional[str],
        task_id: str,
        content: str,
        result: Optional[str],
        *,
        request_id: Optional[str] = None,
        envelope_id: Optional[str] = None,
        message_seq: Optional[int] = None,
    ):
        t, s = self._normalize_scope(tenant_id, session_id)
        async with self._lock:
            self._ensure_session(t, s)
            self._store[t][s]["task_results"][task_id] = TaskRecord(
                content=content,
                result=result,
                request_id=request_id,
                envelope_id=envelope_id,
                message_seq=message_seq,
            )

    async def get_recent_conversations(
        self,
        tenant_id: Optional[str],
        session_id: Optional[str],
        n: int = 10,
    ) -> List[Dict[str, Any]]:
        t, s = self._normalize_scope(tenant_id, session_id)
        async with self._lock:
            self._ensure_session(t, s)
            turns: List[ConversationTurn] = self._store[t][s]["conversation_history"][-n:]
            return [
                {"role": x.role, "content": x.content, "timestamp": x.timestamp}
                for x in turns
            ]

    async def get_task_result(
        self,
        tenant_id: Optional[str],
        session_id: Optional[str],
        task_id: str,
    ) -> Optional[Dict[str, Any]]:
        t, s = self._normalize_scope(tenant_id, session_id)
        async with self._lock:
            self._ensure_session(t, s)
            rec: Optional[TaskRecord] = self._store[t][s]["task_results"].get(task_id)
            if not rec:
                return None
            return {
                "content": rec.content,
                "result": rec.result,
                "timestamp": rec.timestamp,
                "request_id": rec.request_id,
                "envelope_id": rec.envelope_id,
                "message_seq": rec.message_seq,
            }

    async def set_user_preference(
        self,
        tenant_id: Optional[str],
        session_id: Optional[str],
        key: str,
        value: Any,
    ):
        t, s = self._normalize_scope(tenant_id, session_id)
        async with self._lock:
            self._ensure_session(t, s)
            self._store[t][s]["user_preferences"][key] = value

    async def get_user_preferences(
        self,
        tenant_id: Optional[str],
        session_id: Optional[str],
    ) -> Dict[str, Any]:
        t, s = self._normalize_scope(tenant_id, session_id)
        async with self._lock:
            self._ensure_session(t, s)
            return dict(self._store[t][s]["user_preferences"])

    async def add_hot_memory(
        self,
        tenant_id: Optional[str],
        session_id: Optional[str],
        item: Any,
    ):
        t, s = self._normalize_scope(tenant_id, session_id)
        async with self._lock:
            self._ensure_session(t, s)
            self._store[t][s]["hot"].append(item)

    async def add_cold_memory(
        self,
        tenant_id: Optional[str],
        session_id: Optional[str],
        item: Any,
    ):
        t, s = self._normalize_scope(tenant_id, session_id)
        async with self._lock:
            self._ensure_session(t, s)
            self._store[t][s]["cold"].append(item)

    async def get_hot_memory(
        self,
        tenant_id: Optional[str],
        session_id: Optional[str],
        n: int = 20,
    ) -> List[Any]:
        t, s = self._normalize_scope(tenant_id, session_id)
        async with self._lock:
            self._ensure_session(t, s)
            return list(self._store[t][s]["hot"][-n:])

    async def get_cold_memory(
        self,
        tenant_id: Optional[str],
        session_id: Optional[str],
        n: int = 20,
    ) -> List[Any]:
        t, s = self._normalize_scope(tenant_id, session_id)
        async with self._lock:
            self._ensure_session(t, s)
            return list(self._store[t][s]["cold"][-n:])

    # -----------------------------
    # 便捷接口：从标准 envelope 写入
    # -----------------------------
    async def add_from_envelope(
        self,
        envelope: Dict[str, Any],
        *,
        assistant_result: Optional[str] = None,
    ):
        """
        从你标准化后的 envelope 直接写入 task_results / conversation_history。
        envelope 期望字段：
        - tenant_id/session_id/task_id
        - data.content 或 input.user_message
        - request_id/envelope_id/message_seq (可选)
        """
        tenant_id = envelope.get("tenant_id")
        session_id = envelope.get("session_id")
        task_id = envelope.get("task_id") or "unknown_task"
        message_seq = envelope.get("message_seq")

        request_id = envelope.get("request_id")
        envelope_id = envelope.get("envelope_id")

        data = envelope.get("data", {}) if isinstance(envelope.get("data"), dict) else {}
        content = data.get("content") or data.get("user_message") or ""

        # 记录用户消息
        if content:
            await self.add_conversation(tenant_id, session_id, role="user", content=content)

        # 记录任务结果
        await self.add_task_result(
            tenant_id,
            session_id,
            task_id=task_id,
            content=content,
            result=assistant_result,
            request_id=request_id,
            envelope_id=envelope_id,
            message_seq=message_seq,
        )

    # -----------------------------
    # 管理工具：清理/统计
    # -----------------------------
    async def get_stats(self) -> Dict[str, Any]:
        async with self._lock:
            tenants = len(self._store)
            sessions = sum(len(self._store[t]) for t in self._store)
            tasks = 0
            turns = 0
            for t in self._store:
                for s in self._store[t]:
                    tasks += len(self._store[t][s]["task_results"])
                    turns += len(self._store[t][s]["conversation_history"])
            return {
                "tenants": tenants,
                "sessions": sessions,
                "tasks": tasks,
                "conversation_turns": turns,
            }

    async def clear_tenant(self, tenant_id: str):
        async with self._lock:
            self._store.pop(tenant_id, None)

    async def clear_session(self, tenant_id: str, session_id: str):
        async with self._lock:
            if tenant_id in self._store:
                self._store[tenant_id].pop(session_id, None)


class Memory:
    """
    兼容旧测试代码的适配器（保持接口不变）

    旧接口问题：
    - 原来只按 task_id 存，没有 tenant/session，存在串租风险
    兼容策略：
    - 默认落到 default/default
    - 仍然提供 history 映射（指向 default/default 的 task_results）
    """

    def __init__(self):
        self.manager = MemoryManager()
        self._tenant_id = DEFAULT_TENANT
        self._session_id = DEFAULT_SESSION

        # 兼容旧测试代码：直接暴露 default/default 的 task_results dict 视图（只读语义）
        # 注意：这里为了兼容，history 是一个动态读取的属性形式更安全，但旧代码可能当作 dict 使用。
        self.history: Dict[str, Any] = {}

    async def _refresh_history_view(self):
        # 将 default/default task_results 映射到 self.history（用于兼容调试）
        recs = await self.manager.get_stats()
        _ = recs  # 占位，避免 lint
        # 这里不做真实深拷贝：只提供 get 接口即可；如果你确实有旧代码直接读取 history，
        # 可以在 add/get 时同步更新 self.history

    async def add(self, task_id: str, content: str, result: str = None):
        await self.manager.add_task_result(
            self._tenant_id,
            self._session_id,
            task_id=task_id,
            content=content,
            result=result,
        )
        # 同步维护兼容视图
        self.history[task_id] = {"content": content, "result": result, "timestamp": time.time()}

    async def get(self, task_id: str):
        rec = await self.manager.get_task_result(self._tenant_id, self._session_id, task_id)
        return rec
