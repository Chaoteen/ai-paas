from __future__ import annotations

import os

from control_plane.agent_registry import AgentRegistry, InMemoryAgentRepository
from control_plane.control_bus import ControlBus, InMemoryControlEventRepository
from data_plane.data_bus import DataBus, InMemoryDataEventRepository

from persistence.db import Database
from persistence.settings import PostgresSettings
from persistence.models import Base as PersistenceBase

from control_plane.repositories.postgres_agent_repository import PostgresAgentRepository
from control_plane.repositories.postgres_control_event_repository import (
    PostgresControlEventRepository,
)
from data_plane.repositories.postgres_data_event_repository import (
    PostgresDataEventRepository,
)


def use_postgres_persistence() -> bool:
    return os.getenv("AI_PAAS_USE_POSTGRES", "false").lower() == "true"


async def build_runtime_state() -> dict:
    """
    构建运行时依赖：
    - agent_registry
    - control_bus
    - data_bus
    - db（可选）
    """
    if use_postgres_persistence():
        settings = PostgresSettings(
            host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            database=os.getenv("POSTGRES_DB", "ai_paas"),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", "postgres"),
            echo=os.getenv("POSTGRES_ECHO", "false").lower() == "true",
        )
        db = Database(settings)

        async with db.engine.begin() as conn:
            await conn.run_sync(PersistenceBase.metadata.create_all)

        agent_repo = PostgresAgentRepository(db)
        control_repo = PostgresControlEventRepository(db)
        data_repo = PostgresDataEventRepository(db)

        control_bus = ControlBus(repository=control_repo)
        data_bus = DataBus(repository=data_repo)
        agent_registry = AgentRegistry(repository=agent_repo, control_bus=control_bus)

        return {
            "mode": "postgres",
            "db": db,
            "agent_registry": agent_registry,
            "control_bus": control_bus,
            "data_bus": data_bus,
        }

    control_bus = ControlBus(repository=InMemoryControlEventRepository())
    data_bus = DataBus(repository=InMemoryDataEventRepository())
    agent_registry = AgentRegistry(
        repository=InMemoryAgentRepository(),
        control_bus=control_bus,
    )

    return {
        "mode": "memory",
        "db": None,
        "agent_registry": agent_registry,
        "control_bus": control_bus,
        "data_bus": data_bus,
    }