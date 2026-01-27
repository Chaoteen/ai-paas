import os
import pytest
import httpx

def _env(name: str, default: str | None = None) -> str:
    v = os.getenv(name, default)
    if v is None or v == "":
        raise RuntimeError(f"Missing env var: {name}")
    return v

@pytest.fixture(scope="session")
def base_url() -> str:
    return _env("AI_PAAS_BASE_URL")

@pytest.fixture(scope="session")
def tenant_a() -> str:
    return os.getenv("AI_PAAS_TENANT_A", "tenant_a")

@pytest.fixture(scope="session")
def tenant_b() -> str:
    return os.getenv("AI_PAAS_TENANT_B", "tenant_b")

@pytest.fixture(scope="session")
def token_tenant_a_admin() -> str:
    return _env("AI_PAAS_TOKEN_TENANT_A_ADMIN")

@pytest.fixture(scope="session")
def token_tenant_b_user() -> str:
    return _env("AI_PAAS_TOKEN_TENANT_B_USER")

@pytest.fixture
def client(base_url: str) -> httpx.Client:
    return httpx.Client(base_url=base_url, timeout=10.0)
