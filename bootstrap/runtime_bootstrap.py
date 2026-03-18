from __future__ import annotations

import inspect
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List
from bootstrap.generation_bootstrap import build_generation_toolset

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from bootstrap.model_bootstrap import build_model_backed_llm_adapter
from control_plane.agent_registry import AgentRegistry
from control_plane.control_bus import ControlBus, InMemoryControlEventRepository
from data_plane.data_bus import DataBus, InMemoryDataEventRepository
from data_plane.redis_stream_bus import RedisStreamBus
from runtime.agent_runtime import AgentRuntime
from runtime.idempotency import InMemoryIdempotencyStore
from runtime.policy_engine import PolicyEngine
from runtime.runtime_metrics import InMemoryRuntimeMetrics
from runtime.skill_registry import SkillRegistry
from runtime.skill_resolver import SkillResolver
from runtime.state_store import InMemoryRuntimeStateStore
from runtime.tool_executor import ToolExecutor
from runtime.trace_store import InMemoryTraceStore


def _normalize_database_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class RuntimeDB:
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]

    @asynccontextmanager
    async def session(self):
        session = self.session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    async def dispose(self) -> None:
        await self.engine.dispose()


@dataclass
class InMemoryAgentRepository:
    items: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    async def save(self, agent: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(agent)
        now = _utc_now_iso()
        data.setdefault("created_at", now)
        data.setdefault("updated_at", now)
        data.setdefault("heartbeat_at", now)
        self.items[data["id"]] = data
        return data

    async def get(self, agent_id: str) -> Dict[str, Any] | None:
        return self.items.get(agent_id)

    async def list(self, tenant_id: str | None = None) -> List[Dict[str, Any]]:
        values = list(self.items.values())
        if tenant_id is not None:
            values = [x for x in values if x.get("tenant_id") == tenant_id]
        return values

    async def delete(self, agent_id: str) -> bool:
        if agent_id in self.items:
            del self.items[agent_id]
            return True
        return False

    async def update_status(self, agent_id: str, status: str) -> bool:
        item = self.items.get(agent_id)
        if not item:
            return False
        item["status"] = status
        item["updated_at"] = _utc_now_iso()
        return True

    async def touch_heartbeat(self, agent_id: str) -> bool:
        item = self.items.get(agent_id)
        if not item:
            return False
        now = _utc_now_iso()
        item["heartbeat_at"] = now
        item["last_heartbeat_at"] = now
        item["updated_at"] = now
        return True


def _get_persistence_mode() -> str:
    return os.getenv("AI_PAAS_PERSISTENCE", "memory").strip().lower()


def _get_event_bus_mode() -> str:
    return os.getenv("AI_PAAS_EVENT_BUS", "memory").strip().lower()


def _build_event_bus_if_needed() -> RedisStreamBus | None:
    event_bus_mode = _get_event_bus_mode()
    if event_bus_mode != "redis":
        return None
    return RedisStreamBus.from_env()


def _build_runtime_db() -> RuntimeDB:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required when AI_PAAS_PERSISTENCE=postgres")

    normalized_url = _normalize_database_url(database_url)
    engine = create_async_engine(normalized_url, future=True, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return RuntimeDB(engine=engine, session_factory=session_factory)


def _instantiate_repository(repo_cls: Any, db: RuntimeDB) -> Any:
    sig = inspect.signature(repo_cls.__init__)
    params = list(sig.parameters.keys())[1:]

    if not params:
        return repo_cls()

    kwargs: Dict[str, Any] = {}
    if "db" in params:
        kwargs["db"] = db
    if "session_factory" in params:
        kwargs["session_factory"] = db.session_factory
    if "session_maker" in params:
        kwargs["session_maker"] = db.session_factory
    if "engine" in params:
        kwargs["engine"] = db.engine

    if kwargs:
        return repo_cls(**kwargs)
    if len(params) == 1:
        return repo_cls(db)
    return repo_cls()


def _build_agent_registry(agent_repository: Any, control_bus: Any) -> AgentRegistry:
    sig = inspect.signature(AgentRegistry.__init__)
    params = list(sig.parameters.keys())[1:]

    kwargs: Dict[str, Any] = {}
    if "agent_repository" in params:
        kwargs["agent_repository"] = agent_repository
    elif "repository" in params:
        kwargs["repository"] = agent_repository
    elif "repo" in params:
        kwargs["repo"] = agent_repository

    if "control_bus" in params:
        kwargs["control_bus"] = control_bus

    if kwargs:
        return AgentRegistry(**kwargs)
    if len(params) >= 2:
        return AgentRegistry(agent_repository, control_bus)
    if len(params) == 1:
        return AgentRegistry(agent_repository)
    return AgentRegistry()


def _split_extra_skill_dirs(value: str | None) -> list[str]:
    if not value:
        return []
    items = [x.strip() for x in value.split(os.pathsep)]
    return [x for x in items if x]


def _build_agent_runtime(
    data_bus: DataBus,
    trace_store: Any | None = None,
    runtime_metrics: Any | None = None,
) -> AgentRuntime:
    bundled_dir = os.getenv("AI_PAAS_BUNDLED_SKILLS_DIR", "skills/bundled")
    local_dir = os.getenv(
        "AI_PAAS_LOCAL_SKILLS_DIR",
        os.path.expanduser("~/.ai-paas/skills"),
    )
    workspace_dir = os.getenv("AI_PAAS_WORKSPACE_SKILLS_DIR")
    extra_dirs = _split_extra_skill_dirs(os.getenv("AI_PAAS_EXTRA_SKILL_DIRS"))

    registry = SkillRegistry(
        bundled_dir=bundled_dir,
        local_dir=local_dir,
        workspace_dir=workspace_dir,
        extra_dirs=extra_dirs,
    )
    resolver = SkillResolver(registry)
    policy_engine = PolicyEngine()

    llm_adapter = build_model_backed_llm_adapter(
        config=None,
        trace_store=trace_store,
        runtime_metrics=runtime_metrics,
        default_model_ref=os.getenv("AI_PAAS_DEFAULT_MODEL_REF"),
    )

    generation_tools = build_generation_toolset(
        config=None,
        trace_store=trace_store,
        runtime_metrics=runtime_metrics,
    )

    tool_executor = ToolExecutor(
        generation_tools=generation_tools,
    )

    return AgentRuntime(
        registry=registry,
        resolver=resolver,
        policy_engine=policy_engine,
        llm_adapter=llm_adapter,
        tool_executor=tool_executor,
        data_bus=data_bus,
    )


def _build_router_worker_if_possible(
    agent_registry: Any,
    data_bus: DataBus,
    event_bus: RedisStreamBus | None,
):
    if event_bus is None:
        return None

    from data_plane.router_worker import RouterWorker

    return RouterWorker(
        agent_registry=agent_registry,
        data_bus=data_bus,
        event_bus=event_bus,
        consumer_group="router-workers",
        consumer_name=os.getenv("AI_PAAS_ROUTER_CONSUMER", "router-1"),
    )


def _build_agent_worker_if_possible(
    agent_registry: Any,
    data_bus: DataBus,
    event_bus: RedisStreamBus | None,
    agent_runtime: AgentRuntime,
    state_store: InMemoryRuntimeStateStore,
    idempotency_store: InMemoryIdempotencyStore,
):
    if event_bus is None:
        return None

    from data_plane.agent_worker import AgentWorker

    return AgentWorker(
        agent_registry=agent_registry,
        data_bus=data_bus,
        event_bus=event_bus,
        agent_runtime=agent_runtime,
        state_store=state_store,
        idempotency_store=idempotency_store,
        consumer_group="agent-workers",
        consumer_name=os.getenv("AI_PAAS_AGENT_CONSUMER", "agent-1"),
    )


async def _build_memory_runtime_state() -> Dict[str, Any]:
    event_bus = _build_event_bus_if_needed()

    control_repo = InMemoryControlEventRepository()
    data_repo = InMemoryDataEventRepository()
    agent_repo = InMemoryAgentRepository()

    trace_store = InMemoryTraceStore()
    runtime_metrics = InMemoryRuntimeMetrics()

    control_bus = ControlBus(repository=control_repo, event_bus=event_bus)
    data_bus = DataBus(
        repository=data_repo,
        event_bus=event_bus,
        trace_store=trace_store,
        runtime_metrics=runtime_metrics,
    )

    if event_bus is not None:
        control_bus.ensure_consumer_group("control-plane-workers")
        data_bus.ensure_consumer_group("data-plane-workers")

    agent_registry = _build_agent_registry(agent_repo, control_bus)
    agent_runtime = _build_agent_runtime(
        data_bus,
        trace_store=trace_store,
        runtime_metrics=runtime_metrics,
    )

    state_store = InMemoryRuntimeStateStore()
    idempotency_store = InMemoryIdempotencyStore()

    router_worker = _build_router_worker_if_possible(agent_registry, data_bus, event_bus)
    agent_worker = _build_agent_worker_if_possible(
        agent_registry,
        data_bus,
        event_bus,
        agent_runtime,
        state_store,
        idempotency_store,
    )

    return {
        "mode": "memory",
        "db": None,
        "agent_registry": agent_registry,
        "control_bus": control_bus,
        "data_bus": data_bus,
        "agent_runtime": agent_runtime,
        "state_store": state_store,
        "idempotency_store": idempotency_store,
        "trace_store": trace_store,
        "runtime_metrics": runtime_metrics,
        "router_worker": router_worker,
        "agent_worker": agent_worker,
    }


async def _build_postgres_runtime_state() -> Dict[str, Any]:
    db = _build_runtime_db()
    event_bus = _build_event_bus_if_needed()

    from control_plane.repositories.postgres_agent_repository import PostgresAgentRepository
    from control_plane.repositories.postgres_control_event_repository import (
        PostgresControlEventRepository,
    )
    from data_plane.repositories.postgres_data_event_repository import (
        PostgresDataEventRepository,
    )

    agent_repo = _instantiate_repository(PostgresAgentRepository, db)
    control_repo = _instantiate_repository(PostgresControlEventRepository, db)
    data_repo = _instantiate_repository(PostgresDataEventRepository, db)

    trace_store = InMemoryTraceStore()
    runtime_metrics = InMemoryRuntimeMetrics()

    control_bus = ControlBus(repository=control_repo, event_bus=event_bus)
    data_bus = DataBus(
        repository=data_repo,
        event_bus=event_bus,
        trace_store=trace_store,
        runtime_metrics=runtime_metrics,
    )

    if event_bus is not None:
        control_bus.ensure_consumer_group("control-plane-workers")
        data_bus.ensure_consumer_group("data-plane-workers")

    agent_registry = _build_agent_registry(agent_repo, control_bus)
    agent_runtime = _build_agent_runtime(
        data_bus,
        trace_store=trace_store,
        runtime_metrics=runtime_metrics,
    )

    state_store = InMemoryRuntimeStateStore()
    idempotency_store = InMemoryIdempotencyStore()

    router_worker = _build_router_worker_if_possible(agent_registry, data_bus, event_bus)
    agent_worker = _build_agent_worker_if_possible(
        agent_registry,
        data_bus,
        event_bus,
        agent_runtime,
        state_store,
        idempotency_store,
    )

    return {
        "mode": "postgres",
        "db": db,
        "agent_registry": agent_registry,
        "control_bus": control_bus,
        "data_bus": data_bus,
        "agent_runtime": agent_runtime,
        "state_store": state_store,
        "idempotency_store": idempotency_store,
        "trace_store": trace_store,
        "runtime_metrics": runtime_metrics,
        "router_worker": router_worker,
        "agent_worker": agent_worker,
    }


async def build_runtime_state() -> Dict[str, Any]:
    mode = _get_persistence_mode()
    if mode == "postgres":
        return await _build_postgres_runtime_state()
    return await _build_memory_runtime_state()