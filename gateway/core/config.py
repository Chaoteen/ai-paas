from pydantic import BaseModel
import os


class Settings(BaseModel):
    # API
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))

    # Auth
    JWT_SECRET: str = os.getenv("JWT_SECRET", "CHANGE_ME")
    JWT_ALG: str = os.getenv("JWT_ALG", "HS256")

    # OPA
    OPA_ENABLED: bool = os.getenv("OPA_ENABLED", "true").lower() == "true"
    OPA_URL: str = os.getenv("OPA_URL", "http://127.0.0.1:8181")
    OPA_UI_POLICY_PATH: str = os.getenv("OPA_UI_POLICY_PATH", "/v1/data/ui/allow")

    # UI definition
    UI_DEF_DIR: str = os.getenv("UI_DEF_DIR", os.path.join(os.path.dirname(__file__), "..", "ui_def"))


settings = Settings()
