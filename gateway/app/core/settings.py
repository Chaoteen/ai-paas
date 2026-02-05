from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ===== Runtime =====
    ENV: str = "dev"

    # ===== Gateway =====
    GATEWAY_HOST: str = "0.0.0.0"
    GATEWAY_PORT: int = 8000

    # ===== Auth / ABAC / OPA =====
    OPA_URL: str = "http://127.0.0.1:8181"

    # ===== External Services =====
    FLOWISE_URL: str | None = None
    PROMPTFLOW_URL: str | None = None
    LANGGRAPH_URL: str | None = None

    # Pydantic v2 settings config
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
