# ai-os/agent_core/memory.py
# FINAL BASELINE (multi-tenant + session scoped + hot/cold + backward compatible)
# - 以 tenant_id 为一级隔离；以 session_id 为二级隔离
# - 支持 conversation_history / task_results / user_preferences / knowledge_base
# - 支持 hot/cold 记忆（结构上分区；是否落盘由上层决定）
# - 保持旧接口 Memory.add(task_id, content, result) / Memory.get(task_id) 可用
# - 新接口建议使用 MemoryManager.add_task_result(... tenant_id/session_id ...)

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import threading


def _now() -> float:
    return time.time()


@dataclass
class TaskRecord:
    task_id: str
    content: str
    result: Optional[str] = None
    timestamp: float = field(default_factory=_now)
    session_id: Optional[str] = None
    message_seq: Optional[int] = None
    request_id: Optional[str] = None
    envelope_id: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversationTurn:
    role: str
    content: str
    timestamp: float = field(default_factory=_now)
    task_id: Optional[str] = None
    message_seq: Optional[int] = None
    request_id: Optional[str] = None
    envelope_id: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TenantSessionMemory:
    # hot/cold 分区：你可以在上层决定哪些写 hot，哪些写 cold
    hot: Dict[str, Any] = field(default_factory=dict)
    cold: Dict[str, Any] = field(default_factory=dict)


class MemoryManager:
    """
    多租户记忆管理器（内存版）

    数据隔离：
      tenant_id -> session_id -> TenantSessionMemory

    说明：
    - 你当前系统里 memory.py 主要用于兼容测试/本地调试。
    - 若你要把 cold memory 落盘（Redis/SQLite/VectorDB），建议把“存取接口”保留，
      将具体存储实现下沉到独立模块（memory_store/）。
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._store: Dict[str, Dict[str, TenantSessionMemory]] = {}
        # user 级别偏好（tenant隔离）
        self._user_prefs: Dict[str, Dict[str, Dict[str, Any]]] = {}  # tenant -> user_id -> prefs

    # -------------------------
    # 内部：获取/创建 session mem
    # -------------------------

    def _get_session_mem(self, tenant_id: str, session_id: str) -> TenantSessionMemory:
        with self._lock:
            if tenant_id not in self._store:
                self._store[tenant_id] = {}
            if session_id not in self._store[tenant_id]:
                self._store[tenant_id][session_id] = TenantSessionMemory(
                    hot={
                        "conversation_history": [],
                        "task_results": {},
                        "knowledge_base": [],
                    },
                    cold={
                        "conversation_history": [],
                        "task_results": {},
                        "knowledge_base": [],
                    },
                )
            return self._store[tenant_id][session_id]

    def _ensure_tenant(self, tenant_id: Optional[str]) -> str:
        # 最小化侵入：未传 tenant 统一归入 default
        return tenant_id or "default"

    def _ensure_session(self, session_id: Optional[str], task_id: Optional[str] = None) -> str:
        if session_id:
            return session_id
        if task_id:
            return f"sess_{task_id}"
        return "sess_default"

    # -------------------------
    # Conversation
    # -------------------------

    def add_conversation(
        self,
        role: str,
        content: str,
        *,
        tenant_id: Optional[str] = None,
        session_id: Optional[str] = None,
        task_id: Optional[str] = None,
        message_seq: Optional[int] = None,
        request_id: Optional[str] = None,
        envelope_id: Optional[str] = None,
        mem_tier: str = "hot",  # "hot" | "cold"
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        tenant = self._ensure_tenant(tenant_id)
        session = self._ensure_session(session_id, task_id)
        sess_mem = self._get_session_mem(tenant, session)

        turn = ConversationTurn(
            role=role,
            content=content,
            task_id=task_id,
            message_seq=message_seq,
            request_id=request_id,
            envelope_id=envelope_id,
            extra=extra or {},
        )

        with self._lock:
            bucket = sess_mem.hot if mem_tier == "hot" else sess_mem.cold
            bucket["conversation_history"].append(turn.__dict__)

    def get_recent_conversations(
        self,
        n: int = 10,
        *,
        tenant_id: Optional[str] = None,
        session_id: Optional[str] = None,
        task_id: Optional[str] = None,
        mem_tier: str = "hot",
    ) -> List[Dict[str, Any]]:
        tenant = self._ensure_tenant(tenant_id)
        session = self._ensure_session(session_id, task_id)
        sess_mem = self._get_session_mem(tenant, session)

        bucket = sess_mem.hot if mem_tier == "hot" else sess_mem.cold
        history = bucket.get("conversation_history", [])
        return history[-n:]

    # -------------------------
    # Task Results
    # -------------------------

    def add_task_result(
        self,
        task_id: str,
        content: str,
        result: Optional[str],
        *,
        tenant_id: Optional[str] = None,
        session_id: Optional[str] = None,
        message_seq: Optional[int] = None,
        request_id: Optional[str] = None,
        envelope_id: Optional[str] = None,
        mem_tier: str = "hot",
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        tenant = self._ensure_tenant(tenant_id)
        session = self._ensure_session(session_id, task_id)
        sess_mem = self._get_session_mem(tenant, session)

        record = TaskRecord(
            task_id=task_id,
            content=content,
            result=result,
            session_id=session,
            message_seq=message_seq,
            request_id=request_id,
            envelope_id=envelope_id,
            extra=extra or {},
        )

        with self._lock:
            bucket = sess_mem.hot if mem_tier == "hot" else sess_mem.cold
            bucket["task_results"][task_id] = record.__dict__

    def get_task_result(
        self,
        task_id: str,
        *,
        tenant_id: Optional[str] = None,
        session_id: Optional[str] = None,
        mem_tier: str = "hot",
    ) -> Optional[Dict[str, Any]]:
        tenant = self._ensure_tenant(tenant_id)
        session = self._ensure_session(session_id, task_id)
        sess_mem = self._get_session_mem(tenant, session)

        bucket = sess_mem.hot if mem_tier == "hot" else sess_mem.cold
        return bucket.get("task_results", {}).get(task_id)

    # -------------------------
    # Knowledge Base (simple list)
    # -------------------------

    def add_knowledge(
        self,
        item: Any,
        *,
        tenant_id: Optional[str] = None,
        session_id: Optional[str] = None,
        mem_tier: str = "cold",
    ) -> None:
        tenant = self._ensure_tenant(tenant_id)
        session = self._ensure_session(session_id, None)
        sess_mem = self._get_session_mem(tenant, session)

        with self._lock:
            bucket = sess_mem.hot if mem_tier == "hot" else sess_mem.cold
            bucket["knowledge_base"].append({"value": item, "timestamp": _now()})

    def get_knowledge(
        self,
        *,
        tenant_id: Optional[str] = None,
        session_id: Optional[str] = None,
        mem_tier: str = "cold",
    ) -> List[Dict[str, Any]]:
        tenant = self._ensure_tenant(tenant_id)
        session = self._ensure_session(session_id, None)
        sess_mem = self._get_session_mem(tenant, session)

        bucket = sess_mem.hot if mem_tier == "hot" else sess_mem.cold
        return list(bucket.get("knowledge_base", []))

    # -------------------------
    # User Preferences (tenant scoped)
    # -------------------------

    def set_user_preferences(
        self,
        user_id: str,
        prefs: Dict[str, Any],
        *,
        tenant_id: Optional[str] = None,
    ) -> None:
        tenant = self._ensure_tenant(tenant_id)
        with self._lock:
            if tenant not in self._user_prefs:
                self._user_prefs[tenant] = {}
            self._user_prefs[tenant][user_id] = dict(prefs)

    def get_user_preferences(
        self,
        user_id: str,
        *,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        tenant = self._ensure_tenant(tenant_id)
        with self._lock:
            return dict(self._user_prefs.get(tenant, {}).get(user_id, {}))

    # -------------------------
    # Generic (backward compatible-ish)
    # -------------------------

    def add(self, key: str, value: Any, *, tenant_id: Optional[str] = None, session_id: Optional[str] = None) -> None:
        """
        旧版通用 add：现在默认写到 hot 的 key list
        """
        tenant = self._ensure_tenant(tenant_id)
        session = self._ensure_session(session_id, None)
        sess_mem = self._get_session_mem(tenant, session)
        with self._lock:
            if key not in sess_mem.hot:
                sess_mem.hot[key] = []
            if not isinstance(sess_mem.hot[key], list):
                # 不破坏已有结构：如果不是 list，直接覆盖为 list
                sess_mem.hot[key] = []
            sess_mem.hot[key].append(value)

    def get(self, key: str, *, tenant_id: Optional[str] = None, session_id: Optional[str] = None) -> Any:
        tenant = self._ensure_tenant(tenant_id)
        session = self._ensure_session(session_id, None)
        sess_mem = self._get_session_mem(tenant, session)
        return sess_mem.hot.get(key, [])


class Memory:
    """
    MemoryManager 的适配器类，保持与现有测试代码兼容
    - 旧接口：add(task_id, content, result=None), get(task_id)
    - 新增：可选 tenant_id/session_id/request_id/envelope_id 透传
    """

    def __init__(self, tenant_id: Optional[str] = None, session_id: Optional[str] = None):
        self.manager = MemoryManager()
        self._tenant_id = tenant_id or "default"
        self._session_id = session_id  # 可为空
        # 兼容现有测试代码：history 指向 task_results
        # 注意：现在是“按 tenant/session 分区”，所以 history 不再是全局 dict
        self.history: Dict[str, Any] = {}

    def add(
        self,
        task_id: str,
        content: str,
        result: str = None,
        *,
        tenant_id: Optional[str] = None,
        session_id: Optional[str] = None,
        message_seq: Optional[int] = None,
        request_id: Optional[str] = None,
        envelope_id: Optional[str] = None,
        mem_tier: str = "hot",
        extra: Optional[Dict[str, Any]] = None,
    ):
        tenant = tenant_id or self._tenant_id
        sess = session_id or self._session_id or f"sess_{task_id}"

        self.manager.add_task_result(
            task_id=task_id,
            content=content,
            result=result,
            tenant_id=tenant,
            session_id=sess,
            message_seq=message_seq,
            request_id=request_id,
            envelope_id=envelope_id,
            mem_tier=mem_tier,
            extra=extra,
        )

        # 兼容：history 里也放一份（仅当前 adapter 视角）
        self.history[task_id] = {"content": content, "result": result, "timestamp": _now()}

    def get(
        self,
        task_id: str,
        *,
        tenant_id: Optional[str] = None,
        session_id: Optional[str] = None,
        mem_tier: str = "hot",
    ):
        tenant = tenant_id or self._tenant_id
        sess = session_id or self._session_id or f"sess_{task_id}"
        return self.manager.get_task_result(task_id, tenant_id=tenant, session_id=sess, mem_tier=mem_tier)
